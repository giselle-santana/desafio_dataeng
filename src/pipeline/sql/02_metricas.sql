-- 02: uma linha por (post, metrica, instante) com valor conhecido.
-- Cada metrica e tratada separada: a api traz views/likes/comments, a pagina traz
-- likes/comments/shares. NULL nunca entra aqui (desconhecido != 0).
-- Empate de instante entre fontes: api vence (prioridade 0).
CREATE OR REPLACE TABLE metricas_long AS
WITH u AS (
    SELECT platform, post_id, collected_at, source, dia_chegada, 'views'    AS metrica, views    AS valor FROM obs_validas WHERE views    IS NOT NULL
    UNION ALL
    SELECT platform, post_id, collected_at, source, dia_chegada, 'likes'    AS metrica, likes    AS valor FROM obs_validas WHERE likes    IS NOT NULL
    UNION ALL
    SELECT platform, post_id, collected_at, source, dia_chegada, 'comments' AS metrica, comments AS valor FROM obs_validas WHERE comments IS NOT NULL
    UNION ALL
    SELECT platform, post_id, collected_at, source, dia_chegada, 'shares'   AS metrica, shares   AS valor FROM obs_validas WHERE shares   IS NOT NULL
)
SELECT platform, post_id, metrica, collected_at, valor, source
FROM u
QUALIFY row_number() OVER (PARTITION BY platform, post_id, metrica, collected_at
                           ORDER BY CASE source WHEN 'api' THEN 0 ELSE 1 END, dia_chegada DESC) = 1;
