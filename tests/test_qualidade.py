"""Cada checagem de qualidade precisa ser capaz de falhar (senao nao protege nada)."""
from datetime import date

import pytest
from conftest import escrever, obs, rodar

from pipeline import quality


def checar(con):
    linhas = quality.executar(con, "t", date(2026, 9, 2), 1)
    return {l[3]: (l[4], l[5]) for l in linhas}


def base(con, dados):
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [obs(coletado="2026-09-02T08:00:00Z"), obs(post="q", coletado="2026-09-02T09:00:00Z")])
    rodar(con, dados, "2026-09-02")
    # a curva so tem linhas de dias encerrados: precisa de coleta posterior para existir
    escrever(dados, "2026-09-04", "api_a.jsonl.gz", [obs(coletado="2026-09-04T08:00:00Z")])
    rodar(con, dados, "2026-09-04")


def test_estado_saudavel_nao_tem_falha_nem_alerta(con, dados):
    base(con, dados)
    r = checar(con)
    assert all(s not in ("falha", "alerta") for s, _ in r.values()), r


@pytest.mark.parametrize("estraga,checagem", [
    ("INSERT INTO posts_estado_atual SELECT * FROM posts_estado_atual LIMIT 1", "estado_atual_chave_unica"),
    ("UPDATE posts_curva_diaria SET dia = 31 WHERE dia = 0", "curva_dia_entre_0_e_30"),
    ("UPDATE posts_estado_atual SET views = -1 WHERE post_id = 'p1'", "metricas_nao_negativas"),
])
def test_invariantes_quebradas_dao_falha(con, dados, estraga, checagem):
    base(con, dados)
    con.execute(estraga)
    assert checar(con)[checagem][0] == "falha"


def test_reconciliacao_acusa_linha_sumida(con, dados):
    base(con, dados)
    con.execute("DELETE FROM obs_validas WHERE post_id = 'q'")      # simula perda silenciosa
    assert checar(con)["reconciliacao_linhas"] == ("falha", 1)


def test_alerta_queda_de_metrica(con, dados):
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [
        obs(coletado="2026-09-02T08:00:00Z", metrics={"views": 100, "likes": 10, "comments": 1}),
        obs(coletado="2026-09-02T09:00:00Z", metrics={"views": 98, "likes": 10, "comments": 1})])
    rodar(con, dados, "2026-09-02")
    assert checar(con)["quedas_de_metrica"] == ("alerta", 1)
    assert con.execute("SELECT views FROM posts_estado_atual").fetchone()[0] == 98  # mantida como observada


