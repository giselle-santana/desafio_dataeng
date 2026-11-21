"""Nada pode sumir em silencio: o que nao entra, fica em rejeitados com motivo."""
from conftest import escrever, obs, rodar


def test_linha_truncada_e_rejeitada_com_motivo(con, dados):
    boa = obs()
    truncada = '{"source": "api", "platform": "ig", "post_id": "x", "creator_'
    escrever(dados, "2026-09-02", "api_x.jsonl.gz", [boa, truncada])
    rodar(con, dados, "2026-09-02")
    motivo, conteudo, n = con.execute("SELECT motivo, conteudo, linha_no FROM rejeitados").fetchone()
    assert motivo == "json_invalido" and conteudo == truncada and n == 2  # texto original e linha preservados
    assert con.execute("SELECT count(*) FROM obs_validas").fetchone()[0] == 1


def test_motivos_de_rejeicao(con, dados):
    escrever(dados, "2026-09-02", "api_x.jsonl.gz", [
        obs(post="a", platform="facebook"),
        obs(post="b", status="deleted"),
        obs(post="c", coletado="2026-09-02T10:00:00Z", publicado="2026-09-02T11:00:00Z"),  # publicado depois
        obs(post="d", coletado="2026-09-03T01:00:00Z"),                                    # chegou antes de coletar
        obs(post="e", coletado="lixo"),
        obs(post="f", metrics={"views": "1.2K", "likes": 1, "comments": 1}),
    ])
    rodar(con, dados, "2026-09-02")
    got = dict(con.execute("SELECT post_id, motivo FROM rejeitados").fetchall())
    assert got == {"a": "plataforma_desconhecida", "b": "status_invalido", "c": "publicado_depois_da_coleta",
                   "d": "coletado_apos_chegada", "e": "collected_at_invalido", "f": "metrica_invalida"}


def test_coleta_zerada_apos_valores_positivos_e_falha_de_coleta(con, dados):
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [
        obs(coletado="2026-09-02T06:00:00Z", metrics={"views": 900, "likes": 90, "comments": 9}),
        obs(coletado="2026-09-02T12:00:00Z", metrics={"views": 0, "likes": 0, "comments": 0}),
    ])
    rodar(con, dados, "2026-09-02")
    assert con.execute("SELECT motivo FROM rejeitados").fetchall() == [("metricas_zeradas_suspeitas",)]
    assert con.execute("SELECT views FROM posts_estado_atual").fetchone()[0] == 900


def test_post_novo_com_zeros_legitimos_nao_e_rejeitado(con, dados):
    escrever(dados, "2026-09-02", "api_a.jsonl.gz",
             [obs(metrics={"views": 0, "likes": 0, "comments": 0})])
    rodar(con, dados, "2026-09-02")
    assert con.execute("SELECT count(*) FROM rejeitados").fetchone()[0] == 0


