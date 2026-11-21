"""Regras de limpeza: tudo o que a fonte 'pagina' escreve diferente da 'api'."""
from datetime import datetime, timezone

from conftest import escrever, obs, rodar

EPOCH_MS = int(datetime(2026, 9, 2, 10, tzinfo=timezone.utc).timestamp() * 1000)  # 2026-09-02T10:00:00Z


def test_pagina_normalizada(con, dados):
    # plataforma por extenso, epoch em ms, offset -03:00, metricas como texto, shares=-1
    pagina = obs(source="pagina", platform="youtube", coletado=EPOCH_MS,
                 publicado="2026-09-01T09:00:00-03:00",
                 metrics={"likes": "93", "comments": "9", "shares": "-1"})
    escrever(dados, "2026-09-02", "pagina_x.jsonl.gz", [pagina])
    rodar(con, dados, "2026-09-02")
    r = con.execute("SELECT platform, published_at, collected_at, likes, comments, shares FROM obs_validas").fetchone()
    assert r[0] == "yt"
    assert str(r[1]) == "2026-09-01 12:00:00"          # -03:00 convertido para UTC
    assert str(r[2]) == "2026-09-02 10:00:00"          # epoch ms -> UTC
    assert (r[3], r[4]) == (93, 9)                      # texto -> inteiro
    assert r[5] is None                                 # -1 e "nao sei", nunca 0 nem -1


def test_api_comment_count_vira_comments(con, dados):
    escrever(dados, "2026-09-02", "api_x.jsonl.gz",
             [obs(metrics={"views": 5, "likes": 2, "comment_count": 7})])
    rodar(con, dados, "2026-09-02")
    assert con.execute("SELECT comments FROM obs_validas").fetchone()[0] == 7


def test_post_removido_sem_metricas_nao_vira_zero(con, dados):
    escrever(dados, "2026-09-02", "api_x.jsonl.gz", [
        obs(coletado="2026-09-02T08:00:00Z", metrics={"views": 50, "likes": 5, "comments": 1}),
        obs(coletado="2026-09-02T09:00:00Z", status="removed", metrics=None) | {"metrics": None},
    ])
    rodar(con, dados, "2026-09-02")
    e = con.execute("SELECT status, views, likes, comments FROM posts_estado_atual").fetchone()
    assert e == ("removed", 50, 5, 1)  # status mais recente; metricas = ultimo valor conhecido


import pytest

SEM_OFFSET = [
    ("2026-09-02T10:00:00",         "2026-09-02 10:00:00"),   # sem offset -> assume UTC
    ("2026-09-02 10:00:00",         "2026-09-02 10:00:00"),   # separador espaco
    ("2026-09-02T10:00:00.250000Z", "2026-09-02 10:00:00.250000"),
    ("2026-09-02T07:00:00-03:00",   "2026-09-02 10:00:00"),   # offset converte para UTC
    ("2026-09-02T10:00:00+00:00",   "2026-09-02 10:00:00"),
]


def test_data_em_formato_ambiguo_e_rejeitada(con, dados):
    # dd/mm vs mm/dd e ambiguo: nao se adivinha, rejeita com motivo
    escrever(dados, "2026-09-02", "api_x.jsonl.gz", [obs(coletado="02/09/2026 10:00")])
    rodar(con, dados, "2026-09-02")
    assert con.execute("SELECT motivo FROM rejeitados").fetchall() == [("collected_at_invalido",)]


def test_epoch_em_segundos_e_em_milissegundos(con, dados):
    seg = int(datetime(2026, 9, 2, 10, tzinfo=timezone.utc).timestamp())
    escrever(dados, "2026-09-02", "api_x.jsonl.gz", [obs(post="s", coletado=seg), obs(post="ms", coletado=seg * 1000)])
    rodar(con, dados, "2026-09-02")
    assert {str(r[0]) for r in con.execute("SELECT collected_at FROM obs_validas").fetchall()} == {"2026-09-02 10:00:00"}
