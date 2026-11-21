-- 06: checagens de qualidade. UMA consulta devolve uma linha por checagem, no formato de
-- qualidade_resultados: (run_id, executado_em, dia_chegada, checagem, status, valor, detalhe).
-- Parametros: tabela temporaria _exec (run_id, dia, n_arquivos), preenchida por quality.executar.
--
-- status:  ok      -> regra respeitada (0 violacoes)
--          alerta  -> violacao tolerada, merece olhar (o pipeline segue)
--          falha   -> invariante quebrada: o dia e REVERTIDO (rollback), o resultado da checagem
--                     fica gravado, o CLI termina com codigo 2 e nao exporta
-- Uma regra nova e uma linha nova no bloco `regras` (nome, severidade se valor > 0, violacoes, descricao).
-- Usa _dedup, tabela temporaria criada por 01_observacoes.sql na mesma conexao.
WITH x AS (SELECT run_id, dia, n_arquivos, CAST(current_timestamp AS TIMESTAMP) AS agora FROM _exec),

regras(ord, nome, severidade, valor, descricao) AS (
    SELECT 100, 'reconciliacao_linhas', 'falha',
        abs((SELECT count(*) FROM _raw) - (SELECT count(*) FROM obs_validas) - (SELECT count(*) FROM rejeitados)),
        'toda linha bruta esta em obs_validas ou em rejeitados (nada some em silencio)'
    UNION ALL SELECT 101, 'estado_atual_chave_unica', 'falha',
        (SELECT count(*) - count(DISTINCT (platform, post_id)) FROM posts_estado_atual),
        'uma linha por (platform, post_id) em posts_estado_atual'
    UNION ALL SELECT 102, 'curva_chave_unica', 'falha',
        (SELECT count(*) - count(DISTINCT (platform, post_id, dia)) FROM posts_curva_diaria),
        'uma linha por (platform, post_id, dia) em posts_curva_diaria'
    UNION ALL SELECT 103, 'curva_dia_entre_0_e_30', 'falha',
        (SELECT count(*) FROM posts_curva_diaria WHERE dia NOT BETWEEN 0 AND 30),
        'dia fora do intervalo 0..30'
    UNION ALL SELECT 104, 'dominios_validos', 'falha',
        (SELECT count(*) FROM posts_estado_atual WHERE platform NOT IN ('yt','ig','tt') OR status NOT IN ('active','removed'))
        + (SELECT count(*) FROM posts_curva_diaria WHERE platform NOT IN ('yt','ig','tt')),
        'platform em yt/ig/tt e status em active/removed'
    UNION ALL SELECT 105, 'metricas_nao_negativas', 'falha',
        (SELECT count(*) FROM posts_estado_atual WHERE least(views, likes, comments, shares) < 0)
        + (SELECT count(*) FROM posts_curva_diaria WHERE least(views, likes, comments, shares) < 0),
        'nenhuma metrica negativa nas saidas (sentinela -1 virou vazio)'
    UNION ALL SELECT 108, 'duplicatas_com_valores_diferentes', 'alerta',
        (SELECT count(*) FROM _dedup WHERE rn = 1 AND n_versoes > 1),
        'mesma observacao (post+fonte+instante) chegou com valores diferentes (vale a chegada mais recente)'
    UNION ALL SELECT 109, 'quedas_de_metrica', 'alerta',
        (SELECT count(*) FROM (
            SELECT valor < lag(valor) OVER (PARTITION BY platform, post_id, metrica ORDER BY collected_at) AS caiu
            FROM metricas_long) WHERE caiu),
        'metrica acumulada que diminui entre observacoes consecutivas (mantida como observada; contagem acumulada ate o dia processado)'
    UNION ALL SELECT 110, 'arquivos_com_conteudo_identico', 'alerta',
        (SELECT coalesce(sum(n - 1), 0) FROM (SELECT count(*) AS n FROM _arquivos GROUP BY sha256 HAVING count(*) > 1)),
        'arquivos reentregues com conteudo identico (as linhas viram duplicata_observacao; contagem acumulada ate o dia processado)'
)

SELECT x.run_id, x.agora, x.dia, c.nome, c.status, CAST(coalesce(c.valor, 0) AS BIGINT), c.detalhe
FROM x, LATERAL (
    -- a pasta do dia estava vazia ou ausente? (n_arquivos NULL: nada foi alterado para o dia)
    SELECT 0 AS ord, 'dia_sem_arquivos' AS nome,
           CASE WHEN x.n_arquivos IS NULL THEN 'alerta' ELSE 'ok' END AS status,
           CASE WHEN x.n_arquivos IS NULL THEN 1 ELSE 0 END AS valor,
           CASE WHEN x.n_arquivos IS NULL
                THEN 'nenhum arquivo em dados/' || x.dia || '; nada foi alterado para esse dia'
                ELSE x.n_arquivos || ' arquivo(s) carregado(s)' END AS detalhe
    UNION ALL
    SELECT ord, nome, CASE WHEN coalesce(valor, 0) = 0 THEN 'ok' ELSE severidade END, valor, descricao FROM regras
    UNION ALL
    SELECT 500, 'rejeitados:' || motivo, 'info', count(*),
           'linhas deste dia de chegada em rejeitados (ver tabela rejeitados)'
    FROM rejeitados WHERE dia_chegada = x.dia GROUP BY motivo
) AS c
ORDER BY c.ord, c.nome;
