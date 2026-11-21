from conftest import escrever, obs, rodar


def test_metrica_mais_recente_de_cada_fonte(con, dados):
    # api traz views; pagina (mais nova) traz shares e likes. Cada metrica usa seu proprio ultimo valor.
    escrever(dados, "2026-09-02", "api_a.jsonl.gz",
             [obs(coletado="2026-09-02T08:00:00Z", metrics={"views": 1000, "likes": 50, "comments": 5})])
    escrever(dados, "2026-09-02", "pagina_a.jsonl.gz",
             [obs(source="pagina", platform="youtube", coletado="2026-09-02T09:00:00Z",
                  metrics={"likes": "55", "comments": "6", "shares": "3"})])
    rodar(con, dados, "2026-09-02")
    assert con.execute("SELECT views, likes, comments, shares FROM posts_estado_atual").fetchone() == (1000, 55, 6, 3)


def test_chegada_atrasada_nao_sobrescreve_dado_mais_novo(con, dados):
    escrever(dados, "2026-09-03", "api_a.jsonl.gz",
             [obs(coletado="2026-09-03T10:00:00Z", metrics={"views": 500, "likes": 1, "comments": 1})])
    rodar(con, dados, "2026-09-03")
    # dia seguinte chega um arquivo com coleta ANTIGA (02/09): nao pode virar o estado atual
    # (e a observacao antiga diz "removed": tambem nao pode mudar o status atual)
    escrever(dados, "2026-09-04", "api_a.jsonl.gz",
             [obs(coletado="2026-09-02T10:00:00Z", status="removed", metrics={"views": 300, "likes": 1, "comments": 1})])
    rodar(con, dados, "2026-09-04")
    views, status, ultima = con.execute("SELECT views, status, ultima_coleta_em FROM posts_estado_atual").fetchone()
    assert (views, status) == (500, "active")
    assert str(ultima) == "2026-09-03 10:00:00"


def test_post_removido_que_volta_fica_active(con, dados):
    escrever(dados, "2026-09-02", "api_a.jsonl.gz", [
        obs(coletado="2026-09-02T08:00:00Z"),
        obs(coletado="2026-09-02T09:00:00Z", status="removed") | {"metrics": None},
        obs(coletado="2026-09-02T10:00:00Z", metrics={"views": 120, "likes": 12, "comments": 2}),
    ])
    rodar(con, dados, "2026-09-02")
    assert con.execute("SELECT status, views FROM posts_estado_atual").fetchone() == ("active", 120)


