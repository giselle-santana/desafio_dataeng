# Pipeline para realização do desafio de engenharia de dados

Processa, um dia de chegada por vez, os arquivos de `dados/` (fontes `api` e `pagina`) e gera duas tabelas:

- `posts_estado_atual`: uma linha por post, com o estado mais recente conhecido;
- `posts_curva_diaria`: uma linha por post e por dia (0 a 30), com as métricas ao final do dia.

Usa Python 3.10+ e DuckDB; a lógica de dados está em SQL (`src/pipeline/sql/`).

## Como instalar e rodar

```bash
python -m venv .venv

source .venv/bin/activate

pip install -e ".[dev]"

python -m pipeline run --de 2026-09-01 --ate 2026-09-10      # processa o intervalo e exporta para saida/

python -m pipeline run --de 2026-09-03 --sem-exportar       # processa a data ou intervalo mas sem exportar o resultado para /saida

for f in posts_estado_atual posts_curva_diaria rejeitados qualidade_resultados; do   cmp saida/$f.csv saida_referencia/$f.csv && echo "$f: IGUAL"; done     # apenas o qualidade_resultados deveria apresentar um resultado diferente após o reprocessmento 

python -m pytest -q                                           # testes
```

Outras opções: `run --de 2026-09-03` (um dia só), `run ... --sem-exportar`, `exportar` (regenera `saida/`).
O banco fica em `warehouse.duckdb`. O programa termina com código 2 se uma checagem de qualidade der `falha`
(nesse caso o dia é revertido e nada é exportado).

## Saídas (`saida/`)

| Arquivo | Conteúdo |
|---|---|
| `posts_estado_atual.csv` | estado atual de cada post |
| `posts_curva_diaria.csv` | curva do dia 0 ao dia 30 |
| `rejeitados.csv` | linhas rejeitadas, com o texto original e o motivo |
| `qualidade_resultados.csv` | resultado das checagens de cada execução |

## Como funciona

```
dados/AAAA-MM-DD/*.jsonl.gz
   │  ingest.py: confere o .gz e carrega cada linha como TEXTO em raw_linhas (substitui o dia)
   ▼
raw_linhas ─► sql/01 normaliza e valida ─► obs_validas + rejeitados
              sql/02 uma linha por (post, métrica, instante)
              sql/03 posts_estado_atual
              sql/04 posts_curva_diaria
   ▼  sql/06 checagens ► qualidade_resultados      sql/07 formato dos CSVs ► export.py grava saida/
```

As decisões tomadas estão em `DECISOES.md`.
