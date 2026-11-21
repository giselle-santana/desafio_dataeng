"""As checagens do dia D descrevem o estado ate o dia D: reexecutar nao muda a serie por dia."""
from conftest import escrever, obs, rodar, tabela

DIAS = ["2026-09-01", "2026-09-02", "2026-09-03"]
DERIVADAS = ["posts_estado_atual", "posts_curva_diaria", "obs_validas", "rejeitados"]
PUBLICADO = "2026-08-31T00:00:00Z"   # antes de qualquer coleta: nenhuma linha e rejeitada por isso


def montar(dados):
    dia1 = [obs(coletado="2026-09-01T10:00:00Z", publicado=PUBLICADO)]
    escrever(dados, "2026-09-01", "api_a.jsonl.gz", dia1)
    escrever(dados, "2026-09-02", "api_b.jsonl.gz", [obs(post="q", platform="ig", coletado="2026-09-02T10:00:00Z", publicado=PUBLICADO)])
    # o dia 03 reentrega o arquivo do dia 01 (mesmo conteudo): so a partir dai ele e duplicata
    escrever(dados, "2026-09-03", "api_a.jsonl.gz", dia1)


def resultados(con, run_id, dia=None):
    sql = "SELECT dia_chegada, checagem, status, valor FROM qualidade_resultados WHERE run_id = ?"
    params = [run_id]
    if dia:
        sql += " AND dia_chegada = ?"
        params.append(dia)
    return con.execute(sql + " ORDER BY ALL", params).fetchall()


def valor(con, run_id, dia, checagem):
    return con.execute("SELECT valor FROM qualidade_resultados WHERE run_id = ? AND dia_chegada = ? AND checagem = ?",
                       [run_id, dia, checagem]).fetchone()[0]


def test_reexecucao_repete_as_checagens_do_primeiro_processamento(con, dados):
    montar(dados)
    rodar(con, dados, *DIAS, run_id="a")          # banco vazio: o banco cresce dia a dia
    rodar(con, dados, *DIAS, run_id="b")          # banco ja com os 3 dias
    assert resultados(con, "a") == resultados(con, "b")
    # o arquivo reentregue so conta a partir do dia em que chegou
    assert [valor(con, "b", d, "arquivos_com_conteudo_identico") for d in DIAS] == [0, 0, 1]
    # e a linha do dia 01 nao vira duplicata no resultado do dia 01
    assert con.execute("SELECT count(*) FROM qualidade_resultados WHERE run_id = 'b' AND dia_chegada = DATE '2026-09-01' "
                       "AND checagem = 'rejeitados:duplicata_observacao'").fetchone()[0] == 0


def test_reprocessar_um_dia_repete_o_resultado_dele_e_mantem_o_estado_completo(con, dados):
    montar(dados)
    rodar(con, dados, *DIAS, run_id="a")
    antes = {t: tabela(con, t) for t in DERIVADAS}
    rodar(con, dados, "2026-09-01", run_id="c")   # dia 01 com os dias 02 e 03 ja carregados
    assert resultados(con, "c", "2026-09-01") == resultados(con, "a", "2026-09-01")
    assert {t: tabela(con, t) for t in DERIVADAS} == antes      # tabelas continuam com tudo o que esta carregado
    # no estado completo a linha do dia 01 e duplicata da reentrega do dia 03
    assert con.execute("SELECT count(*) FROM rejeitados WHERE motivo = 'duplicata_observacao' "
                       "AND dia_chegada = DATE '2026-09-01'").fetchone()[0] == 1
