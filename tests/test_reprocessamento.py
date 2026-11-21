import gzip

import pytest
from conftest import escrever, obs, quebrar_invariante, rodar, tabela

from pipeline import db

DERIVADAS = ["posts_estado_atual", "posts_curva_diaria", "obs_validas", "rejeitados"]


def montar(dados):
    escrever(dados, "2026-09-01", "api_a.jsonl.gz", [obs(coletado="2026-09-01T10:00:00Z"), "{truncada"])
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [
        obs(coletado="2026-09-02T10:00:00Z", metrics={"views": 200, "likes": 20, "comments": 2}),
        obs(post="q", platform="ig", coletado="2026-09-02T11:00:00Z")])
    escrever(dados, "2026-09-03", "pagina_a.jsonl.gz", [
        obs(source="pagina", platform="youtube", coletado="2026-09-01T23:00:00Z", metrics={"likes": "9", "comments": "1", "shares": "4"}),
        obs(post="q", platform="ig", coletado="2026-09-03T11:00:00Z")])


def snapshot(con):
    snap = {t: tabela(con, t) for t in DERIVADAS + ["raw_linhas"]}
    snap["arquivos"] = con.execute("SELECT dia_chegada, arquivo, sha256, n_linhas FROM arquivos ORDER BY ALL").fetchall()  # sem carregado_em
    return snap


def test_reprocessar_dia_e_intervalo_nao_duplica_nem_perde(con, dados):
    montar(dados)
    rodar(con, dados, "2026-09-01", "2026-09-02", "2026-09-03")
    antes = snapshot(con)
    rodar(con, dados, "2026-09-02")                                   # um dia
    rodar(con, dados, "2026-09-01", "2026-09-02", "2026-09-03")       # intervalo
    rodar(con, dados, "2026-09-03", "2026-09-03")
    assert snapshot(con) == antes


def test_ordem_de_processamento_nao_importa(tmp_path, dados):
    montar(dados)
    a = db.conectar(tmp_path / "a.duckdb")
    b = db.conectar(tmp_path / "b.duckdb")
    rodar(a, dados, "2026-09-01", "2026-09-02", "2026-09-03")
    rodar(b, dados, "2026-09-03", "2026-09-01", "2026-09-02")         # o atrasado primeiro
    for t in ["posts_estado_atual", "posts_curva_diaria", "obs_validas"]:
        assert tabela(a, t) == tabela(b, t), t


def test_falha_no_meio_nao_deixa_estado_pela_metade(con, dados):
    montar(dados)
    rodar(con, dados, "2026-09-01", "2026-09-02")
    antes = snapshot(con)
    ruim = escrever(dados, "2026-09-02", "api_z.jsonl.gz", [obs(post="novo")])
    ruim.write_bytes(gzip.compress(b"x" * 1000)[:-8])                 # gzip cortado: arquivo corrompido
    with pytest.raises(Exception):
        rodar(con, dados, "2026-09-02")
    assert snapshot(con) == antes                                     # rollback: nada mudou


def test_pasta_vazia_nao_apaga_dados_ja_carregados(con, dados):
    montar(dados)
    rodar(con, dados, "2026-09-01")
    antes = snapshot(con)
    for f in (dados / "2026-09-01").glob("*"):
        f.unlink()
    rodar(con, dados, "2026-09-01")
    assert snapshot(con) == antes
    assert con.execute("SELECT status FROM qualidade_resultados WHERE checagem='dia_sem_arquivos' ORDER BY executado_em DESC").fetchone()[0] == "alerta"


def test_falha_de_qualidade_nao_deixa_o_dia_aplicado(con, dados, monkeypatch):
    montar(dados)
    rodar(con, dados, "2026-09-01")
    antes = snapshot(con)
    quebrar_invariante(monkeypatch)
    rodar(con, dados, "2026-09-02")
    assert snapshot(con) == antes                                      # o dia 02 nao foi aplicado
    assert con.execute("SELECT count(*) FROM qualidade_resultados WHERE checagem='estado_atual_chave_unica' AND status='falha'").fetchone()[0] == 1


