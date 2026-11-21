import csv

from conftest import escrever, obs, rodar

from pipeline import export


def test_contrato_de_saida(con, dados, tmp_path):
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [obs(coletado="2026-09-02T10:00:00Z", publicado="2026-08-30T08:00:00Z"),
                                                       obs(post="n", coletado="2026-09-04T10:00:00Z", publicado="2026-09-04T01:00:00Z")])
    rodar(con, dados, "2026-09-02")
    saida = tmp_path / "saida"
    export.exportar(con, saida, "t")
    est = list(csv.DictReader(open(saida / "posts_estado_atual.csv")))
    cur = list(csv.DictReader(open(saida / "posts_curva_diaria.csv")))
    assert {"platform", "post_id", "creator_id", "published_at", "status", "views", "likes", "comments", "shares"} <= set(est[0])
    assert {"platform", "post_id", "dia", "views", "likes", "comments", "shares"} <= set(cur[0])
    p1 = next(r for r in est if r["post_id"] == "p1")
    assert p1["published_at"] == "2026-08-30T08:00:00Z"   # ISO 8601 em UTC
    assert p1["shares"] == ""                              # desconhecido = vazio, nao 0
    assert (saida / "rejeitados.csv").exists() and (saida / "qualidade_resultados.csv").exists()
