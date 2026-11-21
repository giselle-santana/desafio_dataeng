-- 01: raw_linhas -> obs_validas + rejeitados
-- Tudo aqui e recalculado do zero a partir de raw_linhas (idempotente por construcao).
-- Invariante: cada linha de raw_linhas termina em obs_validas OU em rejeitados.

-- Numero tolerante: aceita 93, "93", "93.0". Texto nao numerico, NaN, inf ou fora de
-- +-2^53 -> NULL (a linha vira 'metrica_invalida'; nunca uma excecao que derruba o dia).
CREATE OR REPLACE MACRO metrica(t) AS (
    CASE WHEN try_cast(t AS DOUBLE) IS NOT NULL
          AND isfinite(try_cast(t AS DOUBLE))
          AND abs(try_cast(t AS DOUBLE)) <= 9007199254740992
          AND try_cast(t AS DOUBLE) = floor(try_cast(t AS DOUBLE))
         THEN CAST(try_cast(t AS DOUBLE) AS BIGINT) END
);

-- Instante plausivel: so entre 2000 e 2100. Fora disso (epoch gigante, ano 0001, 9999...) -> NULL.
CREATE OR REPLACE MACRO ts_plausivel(x) AS (
    CASE WHEN x >= TIMESTAMP '2000-01-01' AND x < TIMESTAMP '2100-01-01' THEN x END
);

-- Instante -> TIMESTAMP em UTC. Numero = epoch (segundos se < 1e11, senao ms).
-- Texto ISO com offset (ex.: -03:00) e convertido p/ UTC; sem offset assume-se UTC.
CREATE OR REPLACE MACRO ts_utc(tipo, txt) AS ts_plausivel(
    CASE
        WHEN tipo IN ('BIGINT','UBIGINT','INTEGER','UINTEGER','HUGEINT','UHUGEINT','DOUBLE') THEN
            CASE WHEN try_cast(txt AS DOUBLE) IS NULL OR NOT isfinite(try_cast(txt AS DOUBLE))
                      OR abs(try_cast(txt AS DOUBLE)) >= 1e14 THEN NULL
                 WHEN abs(try_cast(txt AS DOUBLE)) < 100000000000
                      THEN make_timestamp(CAST(try_cast(txt AS DOUBLE) * 1000000 AS BIGINT))
                 ELSE make_timestamp(CAST(try_cast(txt AS DOUBLE) * 1000 AS BIGINT))
            END
        WHEN tipo = 'VARCHAR' THEN CAST(try_cast(txt AS TIMESTAMPTZ) AS TIMESTAMP)
    END
);

CREATE OR REPLACE TEMP TABLE _campos AS
WITH b AS (
    SELECT *, CASE WHEN json_valid(conteudo) THEN CAST(conteudo AS JSON) END AS j
    FROM _raw
)
SELECT
    dia_chegada, arquivo, linha_no, conteudo,
    j IS NOT NULL                                           AS json_ok,
    json_type(j)                                            AS tipo_raiz,
    lower(trim(json_extract_string(j, '$.source')))         AS source,
    CASE lower(trim(json_extract_string(j, '$.platform')))
        WHEN 'yt' THEN 'yt' WHEN 'youtube'   THEN 'yt'
        WHEN 'ig' THEN 'ig' WHEN 'instagram' THEN 'ig'
        WHEN 'tt' THEN 'tt' WHEN 'tiktok'    THEN 'tt'
    END                                                     AS platform,
    nullif(trim(json_extract_string(j, '$.post_id')), '')   AS post_id,
    nullif(trim(json_extract_string(j, '$.creator_id')), '') AS creator_id,
    json_type(j, '$.post_id')                               AS post_id_tipo,
    json_type(j, '$.creator_id')                            AS creator_id_tipo,
    json_type(j, '$.metrics')                               AS metrics_tipo,
    ts_utc(json_type(j, '$.published_at'), json_extract_string(j, '$.published_at')) AS published_at,
    ts_utc(json_type(j, '$.collected_at'), json_extract_string(j, '$.collected_at')) AS collected_at,
    lower(trim(json_extract_string(j, '$.status')))         AS status,
    json_extract_string(j, '$.metrics.views')               AS views_txt,
    json_extract_string(j, '$.metrics.likes')               AS likes_txt,
    -- a api passou a chamar 'comments' de 'comment_count' (a partir de ~05/09)
    coalesce(json_extract_string(j, '$.metrics.comments'),
             json_extract_string(j, '$.metrics.comment_count')) AS comments_txt,
    json_extract_string(j, '$.metrics.shares')              AS shares_txt
FROM b;

CREATE OR REPLACE TEMP TABLE _tipadas AS
SELECT *,
    metrica(views_txt) AS views_n, metrica(likes_txt) AS likes_n,
    metrica(comments_txt) AS comments_n, metrica(shares_txt) AS shares_n
FROM _campos;

CREATE OR REPLACE TEMP TABLE _classificadas AS
SELECT
    dia_chegada, arquivo, linha_no, conteudo, source, platform, post_id, creator_id,
    published_at, collected_at, status,
    -- negativo (ex.: shares = -1 na pagina) = "nao sei": vira NULL, nunca 0
    CASE WHEN views_n    >= 0 THEN views_n    END AS views,
    CASE WHEN likes_n    >= 0 THEN likes_n    END AS likes,
    CASE WHEN comments_n >= 0 THEN comments_n END AS comments,
    CASE WHEN shares_n   >= 0 THEN shares_n   END AS shares,
    (coalesce(views_n < 0, false)::INT + coalesce(likes_n < 0, false)::INT
     + coalesce(comments_n < 0, false)::INT + coalesce(shares_n < 0, false)::INT) AS metricas_sentinela,
    CASE
        WHEN NOT json_ok                                   THEN 'json_invalido'
        WHEN tipo_raiz <> 'OBJECT'                         THEN 'json_nao_e_objeto'
        WHEN source IS NULL OR source NOT IN ('api','pagina') THEN 'source_invalida'
        WHEN platform IS NULL                              THEN 'plataforma_desconhecida'
        WHEN post_id IS NULL                               THEN 'post_id_ausente'
        WHEN post_id_tipo NOT IN ('VARCHAR','BIGINT','UBIGINT','HUGEINT','UHUGEINT') THEN 'post_id_invalido'
        WHEN creator_id IS NULL                            THEN 'creator_id_ausente'
        WHEN creator_id_tipo NOT IN ('VARCHAR','BIGINT','UBIGINT','HUGEINT','UHUGEINT') THEN 'creator_id_invalido'
        WHEN metrics_tipo IS NOT NULL AND metrics_tipo NOT IN ('OBJECT','NULL') THEN 'metrics_invalido'
        WHEN status IS NULL OR status NOT IN ('active','removed') THEN 'status_invalido'
        WHEN published_at IS NULL                          THEN 'published_at_invalido'
        WHEN collected_at IS NULL                          THEN 'collected_at_invalido'
        WHEN published_at > collected_at                   THEN 'publicado_depois_da_coleta'
        -- um arquivo nao pode conter coleta posterior ao fim do dia em que chegou
        WHEN collected_at >= CAST(dia_chegada AS TIMESTAMP) + INTERVAL 1 DAY THEN 'coletado_apos_chegada'
        WHEN (views_txt IS NOT NULL AND views_n IS NULL) OR (likes_txt IS NOT NULL AND likes_n IS NULL)
          OR (comments_txt IS NOT NULL AND comments_n IS NULL) OR (shares_txt IS NOT NULL AND shares_n IS NULL)
                                                           THEN 'metrica_invalida'
    END AS motivo
FROM _tipadas;

-- Duplicata = mesma observacao (post + fonte + instante). Fica a da chegada mais
-- recente; as demais vao para rejeitados com motivo (e contam nas checagens de qualidade).
CREATE OR REPLACE TEMP TABLE _dedup AS
SELECT *,
    row_number() OVER (PARTITION BY platform, post_id, source, collected_at
                       ORDER BY dia_chegada DESC, arquivo DESC, linha_no DESC) AS rn,
    count(DISTINCT (status, views, likes, comments, shares))
        OVER (PARTITION BY platform, post_id, source, collected_at) AS n_versoes
FROM _classificadas WHERE motivo IS NULL;

-- Coleta "zerada": uma metrica valendo 0 quando o valor anterior DELA (qualquer fonte, instante
-- anterior) era positivo. Metrica acumulada nao volta a zero: e falha de coleta. A linha inteira
-- vai para rejeitados (com o texto original, para alguem verificar). Post novo com 0
-- legitimo (sem passado positivo) e preservado. A regra olha o que ja foi carregado.
CREATE OR REPLACE TEMP TABLE _janela AS
SELECT *,
    max(views)    OVER w AS prev_views,    max(likes)  OVER w AS prev_likes,
    max(comments) OVER w AS prev_comments, max(shares) OVER w AS prev_shares
FROM _dedup WHERE rn = 1
WINDOW w AS (PARTITION BY platform, post_id ORDER BY collected_at, source, dia_chegada, linha_no
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);

CREATE OR REPLACE TEMP TABLE _zeradas AS
SELECT *,
    coalesce(status = 'active' AND (
           (views    = 0 AND coalesce(prev_views,    0) > 0)
        OR (likes    = 0 AND coalesce(prev_likes,    0) > 0)
        OR (comments = 0 AND coalesce(prev_comments, 0) > 0)
        OR (shares   = 0 AND coalesce(prev_shares,   0) > 0)), false) AS suspeita
FROM _janela;

CREATE OR REPLACE TABLE obs_validas AS
SELECT dia_chegada, arquivo, linha_no, source, platform, post_id, creator_id,
       published_at, collected_at, status, views, likes, comments, shares, metricas_sentinela
FROM _zeradas WHERE NOT suspeita;

CREATE OR REPLACE TABLE rejeitados AS
SELECT dia_chegada, arquivo, linha_no, motivo, platform, post_id, collected_at, conteudo
FROM _classificadas WHERE motivo IS NOT NULL
UNION ALL
SELECT dia_chegada, arquivo, linha_no, 'duplicata_observacao', platform, post_id, collected_at, conteudo
FROM _dedup WHERE rn > 1
UNION ALL
SELECT dia_chegada, arquivo, linha_no, 'metricas_zeradas_suspeitas', platform, post_id, collected_at, conteudo
FROM _zeradas WHERE suspeita;
