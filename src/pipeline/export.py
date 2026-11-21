"""Exporta as tabelas para saida/ (CSV) e escreve o resultado das checagens.

O que vai em cada arquivo (colunas, formatos, ordem) e definido em SQL (sql/07_saida.sql).
Aqui so se escreve o arquivo, de forma atomica.
"""
from __future__ import annotations

import os
from pathlib import Path

import duckdb

from .db import ler_sql

# nome do arquivo -> visao criada por sql/07_saida.sql
VISOES = {
    "posts_estado_atual": "saida_posts_estado_atual",
    "posts_curva_diaria": "saida_posts_curva_diaria",
    "rejeitados": "saida_rejeitados",
}


def _lit(texto) -> str:
    """Literal SQL de texto (aspas simples escapadas): caminhos como C:\\Users\\O'Neil quebrariam o COPY."""
    return "'" + str(texto).replace("'", "''") + "'"


def _copiar(con, consulta: str, destino: Path) -> None:
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    con.execute(f"COPY ({consulta}) TO {_lit(tmp)} (HEADER, DELIMITER ',')")
    os.replace(tmp, destino)  # troca atomica: nunca fica CSV pela metade


def exportar(con: duckdb.DuckDBPyConnection, saida: Path, run_id: str) -> list[Path]:
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    con.execute(ler_sql("07_saida.sql"))
    gerados = []
    for nome, visao in VISOES.items():
        destino = saida / f"{nome}.csv"
        _copiar(con, f"SELECT * FROM {visao}", destino)
        gerados.append(destino)
    destino = saida / "qualidade_resultados.csv"
    _copiar(con, f"SELECT * FROM saida_qualidade({_lit(run_id)})", destino)
    gerados.append(destino)
    return gerados
