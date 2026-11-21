"""Checagens de qualidade. Rodam a cada dia processado e gravam em qualidade_resultados.

As regras estao em sql/06_qualidade.sql (uma consulta; cada regra e uma linha dela). Aqui so se
passa o contexto da execucao, se le o resultado e se grava.

status:  ok      -> regra respeitada (0 violacoes)
         alerta  -> violacao tolerada, merece olhar (o pipeline segue)
         falha   -> invariante quebrada: o dia e REVERTIDO (rollback), o resultado da checagem
                    fica gravado, o CLI termina com codigo 2 e nao exporta
         info    -> so um numero para acompanhar (nao tem regra)
"""
from __future__ import annotations

from datetime import date

import duckdb

from .db import ler_sql


def executar(con: duckdb.DuckDBPyConnection, run_id: str, dia: date, n_arquivos: int | None) -> list[tuple]:
    """Roda as checagens (apos a reconstrucao das tabelas). Nao grava: ver gravar().

    Cada tupla: (run_id, executado_em, dia_chegada, checagem, status, valor, detalhe).
    """
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _exec AS "
        "SELECT CAST(? AS VARCHAR) AS run_id, CAST(? AS DATE) AS dia, CAST(? AS INTEGER) AS n_arquivos",
        [run_id, dia, n_arquivos],
    )
    return con.execute(ler_sql("06_qualidade.sql")).fetchall()


def gravar(con: duckdb.DuckDBPyConnection, linhas: list[tuple]) -> None:
    # `linhas` vem da memoria porque, numa falha, o dia e revertido (ROLLBACK) e o resultado
    # precisa sobreviver a ele.
    con.executemany("INSERT INTO qualidade_resultados VALUES (?, ?, ?, ?, ?, ?, ?)", linhas)


def tem_falha(linhas: list[tuple]) -> bool:
    return any(l[4] == "falha" for l in linhas)
