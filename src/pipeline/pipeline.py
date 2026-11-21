"""Orquestracao: processa um dia de chegada de forma atomica."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import duckdb

from . import ingest, quality

SQL_DIR = Path(__file__).parent / "sql"
ETAPAS = ["01_observacoes.sql", "02_metricas.sql", "03_estado_atual.sql", "04_curva_diaria.sql"]


def reconstruir(con: duckdb.DuckDBPyConnection, ate: date | None = None) -> None:
    """Recalcula TODAS as tabelas derivadas a partir de raw_linhas.

    Reconstruir tudo (em vez de acumular) e o que torna correto: reprocessar, receber
    arquivo atrasado e rodar dias fora de ordem dao sempre o mesmo resultado.

    `ate`: considera so os dias de chegada <= `ate` (estado "como estava ao fim desse dia").
    Sem `ate`, usa tudo o que esta carregado. As etapas leem `_raw` e `_arquivos`, copias
    filtradas de raw_linhas e arquivos, e nunca as tabelas completas.
    """
    filtro, params = ("", []) if ate is None else (" WHERE dia_chegada <= ?", [ate])
    con.execute(f"CREATE OR REPLACE TEMP TABLE _raw AS SELECT * FROM raw_linhas{filtro}", params)
    con.execute(f"CREATE OR REPLACE TEMP TABLE _arquivos AS SELECT * FROM arquivos{filtro}", params)
    for nome in ETAPAS:
        con.execute((SQL_DIR / nome).read_text(encoding="utf-8"))


def processar_dia(con: duckdb.DuckDBPyConnection, dados_dir: Path, dia: date, run_id: str) -> list[tuple]:
    """Carga + reconstrucao + checagens numa unica transacao: ou tudo, ou nada.

    - as checagens do dia D olham o estado ate o dia D (reconstrucao com `ate=dia`), entao o
      resultado nao depende de haver dias posteriores ja carregados (reexecucao = 1a execucao);
    - se ha dias posteriores, o estado completo e reconstruido antes do COMMIT, para as tabelas
      derivadas continuarem refletindo tudo o que esta carregado;

    - erro (ex.: arquivo corrompido): rollback e a excecao sobe; o banco fica como estava;
    - checagem com status 'falha': rollback do dia (as tabelas nunca guardam estado que
      viola uma invariante), mas o RESULTADO das checagens e gravado, para investigar.
    """
    con.execute("BEGIN")
    try:
        n_arquivos = ingest.carregar_dia(con, Path(dados_dir), dia)
        reconstruir(con, ate=dia)
        resultados = quality.executar(con, run_id, dia, n_arquivos)
        if quality.tem_falha(resultados):
            con.execute("ROLLBACK")
            con.execute("BEGIN")
            quality.gravar(con, resultados)
            con.execute("COMMIT")
            return resultados
        if con.execute("SELECT count(*) > 0 FROM raw_linhas WHERE dia_chegada > ?", [dia]).fetchone()[0]:
            reconstruir(con)  # volta ao estado completo (ha dias posteriores ja carregados)
        quality.gravar(con, resultados)
        con.execute("COMMIT")
        return resultados
    except BaseException:
        con.execute("ROLLBACK")
        raise


def intervalo(de: date, ate: date):
    d = de
    while d <= ate:
        yield d
        d += timedelta(days=1)
