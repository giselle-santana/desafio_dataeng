"""Integracao com a pasta dados/ de verdade (so invariantes, nao valores de regra)."""
from pathlib import Path

import pytest

from pipeline import db, pipeline

DADOS = Path(__file__).parent.parent / "dados"
pytestmark = pytest.mark.skipif(not DADOS.is_dir(), reason="pasta dados/ ausente")


def test_pipeline_nos_10_dias_reais(tmp_path):
    con = db.conectar(tmp_path / "r.duckdb")
    for d in pipeline.intervalo(*(__import__("datetime").date(2026, 9, i) for i in (1, 10))):
        res = pipeline.processar_dia(con, DADOS, d, "r")
        assert not pipeline.quality.tem_falha(res), [r for r in res if r[4] == "falha"]
    c = lambda s: con.execute(s).fetchone()[0]
    assert c("SELECT count(*) FROM raw_linhas") == c("SELECT count(*) FROM obs_validas") + c("SELECT count(*) FROM rejeitados")
    assert c("SELECT count(*) FROM raw_linhas") == 47285                       # nada se perdeu na leitura
    assert c("SELECT count(*) FROM rejeitados WHERE motivo = 'json_invalido'") == 6   # as 6 linhas truncadas
    assert c("SELECT count(*) FROM posts_estado_atual") == c("SELECT count(DISTINCT (platform, post_id)) FROM posts_estado_atual") == 1799
    assert c("SELECT count(*) FROM posts_curva_diaria WHERE dia NOT BETWEEN 0 AND 30") == 0
    assert c("SELECT count(*) FROM posts_estado_atual WHERE least(views, likes, comments, shares) < 0") == 0
