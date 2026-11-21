-- Registro dos arquivos do dia em `arquivos`.
-- Parametros: dia de chegada, nomes dos arquivos, sha256 de cada um (mesma ordem; calculado em
-- ingest._ler_gzip sobre os bytes descompactados), dia de chegada (para o join).
-- n_linhas sai das proprias linhas carregadas (raw_linhas). O LEFT JOIN garante uma linha por
-- arquivo mesmo que ele nao tenha nenhuma linha util.
INSERT INTO arquivos
SELECT CAST(? AS DATE), f.arquivo, f.sha256, count(r.linha_no),
       CAST(current_timestamp AS TIMESTAMP)   -- sessao em UTC (db.conectar)
FROM (SELECT unnest(?) AS arquivo, unnest(?) AS sha256) f
LEFT JOIN raw_linhas r ON r.dia_chegada = CAST(? AS DATE) AND r.arquivo = f.arquivo
GROUP BY f.arquivo, f.sha256;
