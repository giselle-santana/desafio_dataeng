import pytest
from conftest import escrever, obs, quebrar_invariante

from pipeline import cli


def args(tmp, *resto):
    return ["--db", str(tmp / "w.duckdb"), "run", "--dados", str(tmp / "dados"), "--saida", str(tmp / "saida"), *resto]


def test_run_um_dia_e_intervalo(tmp_path, dados):
    escrever(dados, "2026-09-01", "api_a.jsonl.gz", [obs(coletado="2026-09-01T10:00:00Z")])
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [obs(post="q", coletado="2026-09-02T10:00:00Z")])
    assert cli.main(args(tmp_path, "--de", "2026-09-01")) == 0
    assert cli.main(args(tmp_path, "--de", "2026-09-01", "--ate", "2026-09-02")) == 0
    assert (tmp_path / "saida" / "posts_estado_atual.csv").exists()
    assert (tmp_path / "saida" / "posts_curva_diaria.csv").exists()
    assert cli.main(["--db", str(tmp_path / "w.duckdb"), "exportar", "--saida", str(tmp_path / "s2")]) == 0
    assert (tmp_path / "s2" / "posts_estado_atual.csv").exists()


def test_intervalo_invertido_e_erro(tmp_path, dados):
    assert cli.main(args(tmp_path, "--de", "2026-09-05", "--ate", "2026-09-01")) == 1


def test_falha_de_qualidade_reverte_o_dia_interrompe_e_nao_exporta(tmp_path, dados, monkeypatch):
    escrever(dados, "2026-09-01", "api_a.jsonl.gz", [obs(coletado="2026-09-01T10:00:00Z")])
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [obs(coletado="2026-09-02T10:00:00Z")])
    assert cli.main(args(tmp_path, "--de", "2026-09-01", "--sem-exportar")) == 0
    quebrar_invariante(monkeypatch)
    assert cli.main(args(tmp_path, "--de", "2026-09-02", "--ate", "2026-09-03")) == 2
    assert not (tmp_path / "saida").exists()                         # nao exportou
    import duckdb
    c = duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True)
    assert c.execute("SELECT count(DISTINCT dia_chegada) FROM raw_linhas").fetchone()[0] == 1   # dia 02 revertido
    assert c.execute("SELECT status FROM qualidade_resultados WHERE checagem='estado_atual_chave_unica' AND dia_chegada = DATE '2026-09-02'").fetchone()[0] == "falha"  # mas o resultado ficou
    assert c.execute("SELECT count(*) FROM qualidade_resultados WHERE dia_chegada = DATE '2026-09-03'").fetchone()[0] == 0  # parou no 1o dia ruim
