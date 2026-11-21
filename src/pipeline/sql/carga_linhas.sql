-- Carga de UM arquivo .jsonl.gz em raw_linhas. Parametros: dia de chegada, nome do arquivo, caminho.
-- Cada linha entra como TEXTO cru (sem interpretar JSON): linha truncada vira linha invalida
-- rastreavel (rejeitados), e nao um erro que derruba o arquivo. Um .gz corrompido, ao
-- contrario, e erro do proprio read_csv e faz rollback do dia.
-- delim=chr(1): separador que nao ocorre em JSON, entao cada linha vira UMA coluna de texto.
-- Numeracao: row_number() sobre a leitura de UM arquivo (.gz nao e divisivel, entao a ordem
-- de leitura e a do arquivo; validado com 600 mil linhas e 1, 4 e 16 threads).
INSERT INTO raw_linhas
SELECT CAST(? AS DATE), ?, linha_no, conteudo
FROM (
    SELECT row_number() OVER () AS linha_no, conteudo
    FROM read_csv(?, columns={'conteudo': 'VARCHAR'}, delim=chr(1), quote='',
                  escape='', header=false, compression='gzip')
)
WHERE trim(conteudo) <> '';
