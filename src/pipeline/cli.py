"""Linha de comando.

    python -m pipeline run --de 2026-09-01 --ate 2026-09-10    # intervalo
    python -m pipeline run --de 2026-09-03                     # um dia so
    python -m pipeline exportar                                # so regera saida/
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import db, export, pipeline, quality


def _args(argv):
    p = argparse.ArgumentParser(prog="pipeline", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--db", default="warehouse.duckdb", help="arquivo DuckDB (padrao: warehouse.duckdb)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="processa um dia (ou intervalo) de chegada e exporta")
    r.add_argument("--de", type=date.fromisoformat, required=True, help="primeiro dia de chegada (AAAA-MM-DD)")
    r.add_argument("--ate", type=date.fromisoformat, help="ultimo dia (padrao: igual a --de)")
    r.add_argument("--dados", default="dados", help="pasta com dados/AAAA-MM-DD/")
    r.add_argument("--saida", default="saida")
    r.add_argument("--sem-exportar", action="store_true")
    e = sub.add_parser("exportar", help="regera saida/ a partir do estado atual do banco")
    e.add_argument("--saida", default="saida")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = _args(argv)
    con = db.conectar(a.db)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if a.cmd == "exportar":
        con.execute("SELECT 1 FROM posts_estado_atual LIMIT 1")  # falha clara se nunca rodou
        run_id = con.execute("SELECT run_id FROM qualidade_resultados ORDER BY executado_em DESC LIMIT 1").fetchone()[0]
        print(*export.exportar(con, Path(a.saida), run_id), sep="\n")
        return 0

    ate = a.ate or a.de
    if ate < a.de:
        print("erro: --ate anterior a --de", file=sys.stderr)
        return 1
    for dia in pipeline.intervalo(a.de, ate):
        resultados = pipeline.processar_dia(con, Path(a.dados), dia, run_id)
        ruins = [(r[3], r[4], r[5]) for r in resultados if r[4] in ("alerta", "falha")]
        rej = sum(r[5] for r in resultados if r[3].startswith("rejeitados:"))
        resumo = ", ".join(f"{n}={s}({v})" for n, s, v in ruins) or "sem alertas"
        if quality.tem_falha(resultados):
            print(f"{dia}: FALHA | {resumo}", file=sys.stderr)
            print(f"Dia {dia} revertido e processamento interrompido; saida/ nao foi atualizada. "
                  "Veja a tabela qualidade_resultados.", file=sys.stderr)
            return 2
        print(f"{dia}: ok | rejeitadas no dia={rej} | {resumo}")
    if not a.sem_exportar:
        export.exportar(con, Path(a.saida), run_id)
        print(f"exportado em {a.saida}/")
    return 0
