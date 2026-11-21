-- 07: visoes de exportacao (saida/*.csv). Formato do contrato: instantes em ISO 8601 UTC,
-- datas AAAA-MM-DD, ordem total (saida deterministica). Temporarias: valem so nesta conexao.
CREATE OR REPLACE TEMP MACRO iso(x) AS strftime(x, '%Y-%m-%dT%H:%M:%SZ');

CREATE OR REPLACE TEMP VIEW saida_posts_estado_atual AS
SELECT platform, post_id, creator_id, iso(published_at) AS published_at, status,
       views, likes, comments, shares,
       iso(ultima_coleta_em) AS ultima_coleta_em,
       iso(views_coletado_em) AS views_coletado_em,
       iso(likes_coletado_em) AS likes_coletado_em,
       iso(comments_coletado_em) AS comments_coletado_em,
       iso(shares_coletado_em) AS shares_coletado_em
FROM posts_estado_atual ORDER BY platform, post_id;

CREATE OR REPLACE TEMP VIEW saida_posts_curva_diaria AS
SELECT platform, post_id, dia, strftime(data_dia, '%Y-%m-%d') AS data_dia,
       iso(inicio_dia_utc) AS inicio_dia_utc, iso(fim_dia_utc) AS fim_dia_utc,
       views, likes, comments, shares, status,
       iso(ultima_coleta_em) AS ultima_coleta_em, sem_coleta_no_dia,
       iso(views_coletado_em) AS views_coletado_em,
       iso(likes_coletado_em) AS likes_coletado_em,
       iso(comments_coletado_em) AS comments_coletado_em,
       iso(shares_coletado_em) AS shares_coletado_em
FROM posts_curva_diaria ORDER BY platform, post_id, dia;

CREATE OR REPLACE TEMP VIEW saida_rejeitados AS
SELECT strftime(dia_chegada, '%Y-%m-%d') AS dia_chegada, arquivo, linha_no, motivo, platform, post_id,
       iso(collected_at) AS collected_at, conteudo
FROM rejeitados ORDER BY dia_chegada, arquivo, linha_no;

-- checagens de UMA execucao
CREATE OR REPLACE TEMP MACRO saida_qualidade(r) AS TABLE
SELECT * FROM qualidade_resultados WHERE run_id = r ORDER BY dia_chegada, checagem;
