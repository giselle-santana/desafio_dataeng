# Decisões

## Granularidade e chaves

- **Post = `(platform, post_id)`**. Só `post_id` não basta: ids de ig e tt colidem em alguns casos. `platform` é normalizado para `yt`/`ig`/`tt` (a `pagina` escreve `youtube`, `instagram`, `tiktok`).
- **Observação = `(platform, post_id, source, collected_at)`**: a foto de um post, por uma fonte, num instante. Reentrega da mesma observação vira `duplicata_observacao`; vale a de chegada mais recente.
- `post_id` e `creator_id` ficam como **texto** (em ig/tt passam de 2^53; como número perderiam precisão).
- Granularidade das tabelas: `posts_estado_atual` = 1 linha por post; `posts_curva_diaria` = 1 linha por post e dia (0 a 30).

## Estado atual

- **Métricas: cada uma escolhida separadamente**, com o último valor conhecido (por `collected_at`) de qualquer fonte. Necessário porque a `api` não traz `shares` e a `pagina` não traz `views`. 
- **Vazio ≠ zero.** `shares = -1` (sentinela da `pagina`, 4.419 observações) vira vazio, nunca 0.
- **Campos do post** (`creator_id`, `published_at`, `status`): da observação mais recente por `collected_at`. Empate: `api` vence, depois a chegada mais recente.
- **"Mais recente" é `collected_at`, nunca a data de chegada**: arquivo atrasado não sobrescreve dado novo.
- **Post removido**: fica na tabela com `status = removed` e mantém o último valor conhecido de cada métrica (a observação de remoção não traz métricas).
- **Se voltar**: a observação `active` mais nova vence e o post volta a `active`. 

## Curva diária

- **Dia N = dia calendário em America/Sao_Paulo; dia 0 = dia (em SP) de `published_at`.** Os instantes continuam em UTC nas tabelas; só a fronteira do dia é em SP (`inicio_dia_utc`/`fim_dia_utc` mostram o corte).
- **Dia sem coleta**: repete o último valor conhecido. Dois avisos: `sem_coleta_no_dia` (o post não teve observação no dia) e `<metrica>_coletado_em` (quando o valor foi coletado de fato).
- **Post publicado antes do primeiro dia de dados**: os dias anteriores à primeira observação ficam **vazios**; não se extrapola para trás. A curva continua sendo do dia 0 da publicação, não do início dos dados.
- **Quedas de métrica** são mantidas como observadas (geram alerta).

## Reprocessamento e dados atrasados

- **Por que reprocessar não duplica**: `raw_linhas` é a única fonte de verdade e as tabelas derivadas são **recalculadas inteiras** a partir dela (`CREATE OR REPLACE`). A carga de um dia faz `DELETE` + `INSERT` do dia inteiro. Mesma entrada, mesma saída.
- **Arquivo atrasado**: entra na pasta do dia em que chegou e a reconstrução o incorpora. Como a escolha usa `collected_at`, ele corrige o histórico sem sobrescrever dado mais novo. 
- **Se a execução cair no meio**: cada dia é **uma transação** (carga + reconstrução + checagens). Erro → `ROLLBACK` e o banco fica como estava. `.gz` corrompido ou truncado é detectado (CRC via `gzip`) **antes** de qualquer alteração deve abortar o dia. A exportação grava `.tmp` e troca com `os.replace`, então nunca fica CSV pela metade.

## Qualidade

- **O que checa** (`sql/06_qualidade.sql`, a cada dia; resultado em `qualidade_resultados` e `saida/qualidade_resultados.csv`):
  - `falha` (reverte o dia, grava o resultado e o CLI sai com código 2 sem exportar): linhas brutas = válidas + rejeitadas; chave única nas duas tabelas; dia entre 0 e 30; plataforma e status válidos; nenhuma métrica negativa.
  - `alerta` (segue): quedas de métrica, duplicata com valores diferentes, arquivo reentregue com conteúdo idêntico (sha256), dia sem arquivos.
  - `info`: contagem de rejeitados por motivo.
- **O que é rejeitado** (`saida/rejeitados.csv`, com o texto original, arquivo, linha e motivo; nada some em silêncio):
  - `duplicata_observacao`: mesma observação reentregue; fica a mais recente.
  - `metricas_zeradas_suspeitas`: métrica acumulada que volta a 0 depois de ter sido positiva. Todas da `api`, com views, likes e comments zerados juntos. 
  - `publicado_depois_da_coleta`: `collected_at` anterior a `published_at`.
  - `json_invalido`: linha malformada; vira rejeitada e não derruba o arquivo.
  - Também há regras para tipos errados, `NaN`/`inf`/valores gigantes, datas implausíveis (fora de 2000–2100) e `coletado_apos_chegada`.
- **O que encontrei que não estava documentado**:
  - A `api` renomeou `comments` para `comment_count` a partir de ~05/09 (tratado com `coalesce`).
  - A `pagina` usa nomes por extenso de plataforma e `shares = -1` como "não sei".
  - Datas em formatos diferentes.
  - 3 arquivos com conteúdo idêntico a outros.
  - Coletas zeradas na `api` e coletas "antes da publicação" na `pagina`.
  - As regras de falha passam a olhar o estado até o dia D, não o completo. O número por dia significa “o que se sabia naquele dia”. Reentregas posteriores não aparecem nele. qualidade_resultados.csv continua crescendo a cada execução, mas isso é histórico, não duplicação.
- Também foi criada a pasta saida_referencia, para onde os resultados de uma execução foram copiados antes de um reprocessamento para serem utilizados de comparação entre a execução anterior e o reprocessamento  (ajudou na validação da idempotência). Apenas os arquivos qualidade_resultados.csv deve apresentar diferenças (o run_id e executado_em serão diferentes)

## Produção e escala

- **Rodar todo dia**: poderia-se agendar (cron/Airflow) logo após a chegada, com `run --de ontem` e reprocesso da janela D-5 a D, já que os arquivos chegam atrasados.
- **Monitorar**: arquivos e linhas por dia (queda = alerta `dia_sem_arquivos`), taxa de rejeição por motivo, chegada tardia, quedas de métrica, arquivos reentregues e qualquer `falha` (código de saída 2 deve gerar notificação).
- **Com 1000× mais dados**: 
  - Seria necessário parar de reconstruir tudo;
  - Camada bruta em Parquet particionado por dia;
  - Reconstrução só dos posts tocados pelos arquivos do dia, com `MERGE` nas tabelas finais;
  - Curva incremental (só janela dos últimos 30 dias por post);
  - Checagens viram agregações incrementais; `rejeitados` seria um arquivo particionado.

## O que ficou de fora

1. **Reavaliar regras como**: coleta zerada (limiar e se é rejeição ou só alerta) e curva só com dias encerrados (dia parcial com `dia_parcial`).
2. **Checagens extras**: inconsistência de `published_at`/`creator_id` entre observações e observação `active` sem métricas.
3. **Testes de ambiente e robustez**: fusos, caminhos, versões do DuckDB, entradas ruins.
4. **Uma solução mais elegante**: Uma solução mais completa seria um fluxo incremental que gravasse o estado de cada dia uma única vez, (só posts tocados) antes de a base crescer. 
5. **Desafio extra (`extra/`)**: não foi feito.