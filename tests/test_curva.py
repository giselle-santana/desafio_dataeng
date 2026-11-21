from datetime import date

from conftest import escrever, obs, rodar

PUB = "2026-09-01T12:00:00Z"


def curva(con, post="p1"):
    return {d: (v, c) for d, v, c in con.execute(
        "SELECT dia, views, sem_coleta_no_dia FROM posts_curva_diaria WHERE post_id = ? ORDER BY dia", [post]).fetchall()}


def test_dia_zero_e_dia_utc_da_publicacao_e_forward_fill(con, dados):
    escrever(dados, "2026-09-01", "api_a.jsonl.gz", [obs(coletado="2026-09-01T20:00:00Z", metrics={"views": 100, "likes": 1, "comments": 1})])
    escrever(dados, "2026-09-03", "api_a.jsonl.gz", [obs(coletado="2026-09-03T10:00:00Z", metrics={"views": 300, "likes": 1, "comments": 1})])
    # outro post, coletado em 05/09, define o horizonte dos dados carregados
    escrever(dados, "2026-09-05", "api_a.jsonl.gz", [obs(post="outro", coletado="2026-09-05T10:00:00Z", publicado="2026-09-05T01:00:00Z")])
    rodar(con, dados, "2026-09-01", "2026-09-03", "2026-09-05")
    c = curva(con)
    assert sorted(c) == [0, 1, 2, 3]                 # so dias encerrados (< 05/09); dia 0 = 01/09
    assert c[0] == (100, False)                      # coleta no proprio dia
    assert c[1] == (100, True)                       # sem coleta: repete o ultimo valor, sinalizado
    assert c[2] == (300, False)
    assert c[3] == (300, True)


def test_antes_da_primeira_observacao_e_vazio(con, dados):
    escrever(dados, "2026-09-03", "api_a.jsonl.gz", [obs(coletado="2026-09-03T10:00:00Z", publicado="2026-08-30T10:00:00Z")])
    escrever(dados, "2026-09-05", "api_a.jsonl.gz", [obs(post="outro", coletado="2026-09-05T10:00:00Z", publicado="2026-09-05T01:00:00Z")])
    rodar(con, dados, "2026-09-03", "2026-09-05")
    c = curva(con)
    assert c[0][0] is None and c[3][0] is None       # 30/08..02/09: nunca observado -> vazio, nao 0
    assert c[4][0] == 100                            # 03/09


def test_dia_zero_e_o_dia_em_sao_paulo_nao_em_utc(con, dados):
    # 23:30 em -03:00 = 02:30 UTC do dia seguinte. Em Sao Paulo ainda e dia 01/09 -> dia 0 = 01/09
    escrever(dados, "2026-09-04", "pagina_a.jsonl.gz",
             [obs(source="pagina", platform="tiktok", coletado="2026-09-04T10:00:00Z",
                  publicado="2026-09-01T23:30:00-03:00", metrics={"likes": "1", "comments": "1", "shares": "1"}),
              obs(post="outro", coletado="2026-09-06T10:00:00Z", publicado="2026-09-06T01:00:00Z")])
    rodar(con, dados, "2026-09-04")
    assert con.execute("SELECT min(data_dia) FROM posts_curva_diaria WHERE post_id='p1'").fetchone()[0] == date(2026, 9, 1)
    # os instantes continuam em UTC (contrato): published_at do estado atual segue 02:30Z
    assert str(con.execute("SELECT published_at FROM posts_estado_atual WHERE post_id='p1'").fetchone()[0]) == "2026-09-02 02:30:00"


def test_curva_nunca_passa_do_dia_30(con, dados):
    escrever(dados, "2026-09-10", "api_a.jsonl.gz", [obs(coletado="2026-09-10T10:00:00Z", publicado="2026-07-01T10:00:00Z")])
    rodar(con, dados, "2026-09-10")
    assert con.execute("SELECT min(dia), max(dia), count(*) FROM posts_curva_diaria").fetchone() == (0, 30, 31)


def test_chegada_atrasada_corrige_a_curva(con, dados):
    escrever(dados, "2026-09-03", "api_a.jsonl.gz", [obs(coletado="2026-09-03T10:00:00Z", metrics={"views": 500, "likes": 1, "comments": 1})])
    escrever(dados, "2026-09-05", "api_a.jsonl.gz", [obs(post="outro", coletado="2026-09-05T10:00:00Z", publicado="2026-09-05T01:00:00Z")])
    rodar(con, dados, "2026-09-03", "2026-09-05")
    assert curva(con)[1] == (None, True)             # 02/09 ainda sem nada conhecido
    escrever(dados, "2026-09-05", "api_atrasado.jsonl.gz", [obs(coletado="2026-09-02T10:00:00Z", metrics={"views": 300, "likes": 1, "comments": 1})])
    rodar(con, dados, "2026-09-05")                  # chegou 3 dias depois
    assert curva(con)[1] == (300, False)
    assert curva(con)[2] == (500, False)


