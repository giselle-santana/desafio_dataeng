-- 03: posts_estado_atual -- uma linha por (platform, post_id).
-- Campos do post (creator_id, published_at, status): da observacao mais recente por collected_at
--   (empate: api, depois chegada mais recente). Chegada tardia NAO sobrescreve dado mais novo.
-- Metricas: ultimo valor conhecido de CADA metrica, de qualquer fonte. Post removido
--   mantem o ultimo valor conhecido (a observacao de remocao nao traz metricas).
--   <metrica>_coletado_em = instante do valor: as metricas NAO sao do mesmo instante
--   (a pagina nao traz views; a api nao traz shares), entao cada uma diz a sua idade.
CREATE OR REPLACE TABLE posts_estado_atual AS
WITH ult AS (
    SELECT *, row_number() OVER (
        PARTITION BY platform, post_id
        ORDER BY collected_at DESC, CASE source WHEN 'api' THEN 0 ELSE 1 END,
                 dia_chegada DESC, arquivo DESC, linha_no DESC) AS rn
    FROM obs_validas
),
mp AS (
    SELECT platform, post_id,
        max(valor) FILTER (WHERE metrica = 'views')    AS views,
        max(valor) FILTER (WHERE metrica = 'likes')    AS likes,
        max(valor) FILTER (WHERE metrica = 'comments') AS comments,
        max(valor) FILTER (WHERE metrica = 'shares')   AS shares,
        max(collected_at) FILTER (WHERE metrica = 'views')    AS views_coletado_em,
        max(collected_at) FILTER (WHERE metrica = 'likes')    AS likes_coletado_em,
        max(collected_at) FILTER (WHERE metrica = 'comments') AS comments_coletado_em,
        max(collected_at) FILTER (WHERE metrica = 'shares')   AS shares_coletado_em
    FROM (SELECT * FROM metricas_long
          QUALIFY row_number() OVER (PARTITION BY platform, post_id, metrica
                                     ORDER BY collected_at DESC) = 1)
    GROUP BY platform, post_id
)
SELECT u.platform, u.post_id, u.creator_id, u.published_at, u.status,
       mp.views, mp.likes, mp.comments, mp.shares,
       u.collected_at AS ultima_coleta_em,
       mp.views_coletado_em, mp.likes_coletado_em, mp.comments_coletado_em, mp.shares_coletado_em
FROM ult u LEFT JOIN mp USING (platform, post_id)
WHERE u.rn = 1;
