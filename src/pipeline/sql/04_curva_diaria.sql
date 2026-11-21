-- 04: posts_curva_diaria -- uma linha por (post, dia) com dia em 0..30.
-- DIA = dia calendario em America/Sao_Paulo. Dia 0 = dia (em Sao Paulo) de published_at.
--   Todos os instantes ficam em UTC nas tabelas (contrato); so a FRONTEIRA do dia e em Sao Paulo:
--   inicio_dia_utc / fim_dia_utc mostram, em UTC, onde o dia comeca e termina.
-- Valor = ultimo valor conhecido de cada metrica ate o FIM do dia (collected_at < fim_dia_utc).
--   * dia sem coleta: repete o ultimo valor conhecido. Dois niveis de aviso:
--       sem_coleta_no_dia      = o POST nao teve nenhuma observacao no dia (tambem e true antes da 1a observacao);
--       <metrica>_coletado_em  = quando aquele valor foi de fato coletado; < inicio_dia_utc => valor herdado.
--   * antes da 1a observacao do post: NULL (nao se extrapola para tras);
--   * so ha linha para dias ja ENCERRADOS (dia < dia, em Sao Paulo, da ultima coleta carregada).
CREATE OR REPLACE MACRO dia_local(x) AS CAST((x AT TIME ZONE 'UTC') AT TIME ZONE 'America/Sao_Paulo' AS DATE);
CREATE OR REPLACE MACRO inicio_utc(x) AS CAST(CAST(x AS TIMESTAMP) AT TIME ZONE 'America/Sao_Paulo' AS TIMESTAMP);

CREATE OR REPLACE TABLE posts_curva_diaria AS
WITH h AS (SELECT dia_local(max(collected_at)) AS dia_max FROM obs_validas),
dias AS (
    SELECT p.platform, p.post_id, CAST(d.dia AS INTEGER) AS dia,
           dia_local(p.published_at) + CAST(d.dia AS INTEGER) AS data_dia
    FROM posts_estado_atual p CROSS JOIN range(0, 31) AS d(dia) CROSS JOIN h
    WHERE dia_local(p.published_at) + CAST(d.dia AS INTEGER) < h.dia_max
),
d2 AS (SELECT *, inicio_utc(data_dia) AS inicio_dia_utc, inicio_utc(data_dia + 1) AS fim_dia_utc FROM dias),
obs AS (
    SELECT platform, post_id, collected_at, status FROM obs_validas
    QUALIFY row_number() OVER (PARTITION BY platform, post_id, collected_at
                               ORDER BY CASE source WHEN 'api' THEN 0 ELSE 1 END, dia_chegada DESC) = 1
)
SELECT d.platform, d.post_id, d.dia, d.data_dia, d.inicio_dia_utc, d.fim_dia_utc,
       v.valor AS views, l.valor AS likes, c.valor AS comments, s.valor AS shares,
       v.collected_at AS views_coletado_em, l.collected_at AS likes_coletado_em,
       c.collected_at AS comments_coletado_em, s.collected_at AS shares_coletado_em,
       o.status AS status,
       o.collected_at AS ultima_coleta_em,
       (o.collected_at IS NULL OR o.collected_at < d.inicio_dia_utc) AS sem_coleta_no_dia
FROM d2 d
ASOF LEFT JOIN (SELECT platform, post_id, collected_at, valor FROM metricas_long WHERE metrica = 'views') v
     ON d.platform = v.platform AND d.post_id = v.post_id AND d.fim_dia_utc > v.collected_at
ASOF LEFT JOIN (SELECT platform, post_id, collected_at, valor FROM metricas_long WHERE metrica = 'likes') l
     ON d.platform = l.platform AND d.post_id = l.post_id AND d.fim_dia_utc > l.collected_at
ASOF LEFT JOIN (SELECT platform, post_id, collected_at, valor FROM metricas_long WHERE metrica = 'comments') c
     ON d.platform = c.platform AND d.post_id = c.post_id AND d.fim_dia_utc > c.collected_at
ASOF LEFT JOIN (SELECT platform, post_id, collected_at, valor FROM metricas_long WHERE metrica = 'shares') s
     ON d.platform = s.platform AND d.post_id = s.post_id AND d.fim_dia_utc > s.collected_at
ASOF LEFT JOIN obs o
     ON d.platform = o.platform AND d.post_id = o.post_id AND d.fim_dia_utc > o.collected_at;
