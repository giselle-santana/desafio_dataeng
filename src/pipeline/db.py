"""Conexao com o DuckDB e tabelas persistentes (as que NAO sao recalculadas)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb

SQL_DIR = Path(__file__).parent / "sql"


@lru_cache(maxsize=None)
def ler_sql(nome: str) -> str:
    """Texto de um arquivo de sql/. Toda a logica de dados mora la; o Python so a executa."""
    return (SQL_DIR / nome).read_text(encoding="utf-8")

# Camada bruta: toda linha lida, valida ou nao, exatamente como chegou.
# Unica fonte de verdade; todo o resto e derivado dela.
DDL = """
CREATE TABLE IF NOT EXISTS raw_linhas (
    dia_chegada DATE    NOT NULL,   -- pasta dados/AAAA-MM-DD (UTC)
    arquivo     VARCHAR NOT NULL,
    linha_no    BIGINT  NOT NULL,   -- 1-based, dentro do arquivo
    conteudo    VARCHAR NOT NULL    -- texto original da linha
);
CREATE TABLE IF NOT EXISTS arquivos (
    dia_chegada DATE    NOT NULL,
    arquivo     VARCHAR NOT NULL,
    sha256      VARCHAR NOT NULL,   -- hash do conteudo descompactado
    n_linhas    BIGINT  NOT NULL,
    carregado_em TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS qualidade_resultados (
    run_id      VARCHAR   NOT NULL,
    executado_em TIMESTAMP NOT NULL,
    dia_chegada DATE      NOT NULL,
    checagem    VARCHAR   NOT NULL,
    status      VARCHAR   NOT NULL, -- ok | info | alerta | falha
    valor       BIGINT,
    detalhe     VARCHAR
);
"""


def conectar(caminho: str | Path = "warehouse.duckdb") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(caminho))
    # Toda conversao de timestamp assume/entrega UTC, independente da maquina.
    con.execute("SET TimeZone='UTC'")
    con.execute(DDL)
    return con
