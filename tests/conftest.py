import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from pipeline import db, pipeline


def obs(post="p1", platform="yt", source="api", coletado="2026-09-02T10:00:00Z",
        publicado="2026-09-01T12:00:00Z", status="active", metrics=None, creator="c1"):
    """Monta uma observacao no formato bruto. metrics=None -> {views,likes,comments}."""
    if metrics is None:
        metrics = {"views": 100, "likes": 10, "comments": 1}
    return {"source": source, "platform": platform, "post_id": post, "creator_id": creator,
            "published_at": publicado, "collected_at": coletado, "status": status, "metrics": metrics}


def escrever(dados: Path, dia: str, nome: str, linhas) -> Path:
    """Grava um .jsonl.gz em dados/<dia>/. Item str vai como esta (linha crua); dict vira JSON."""
    pasta = dados / dia
    pasta.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(l if isinstance(l, str) else json.dumps(l) for l in linhas) + "\n"
    caminho = pasta / nome
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        f.write(texto)
    return caminho


@pytest.fixture
def dados(tmp_path):
    return tmp_path / "dados"


@pytest.fixture
def con(tmp_path):
    c = db.conectar(tmp_path / "t.duckdb")
    yield c
    c.close()


def rodar(con, dados, *dias, run_id="t"):
    for d in dias:
        pipeline.processar_dia(con, dados, date.fromisoformat(d), run_id)


def tabela(con, nome):
    return con.execute(f"SELECT * FROM {nome} ORDER BY ALL").fetchall()


def quebrar_invariante(monkeypatch):
    """Depois da reconstrucao de cada dia, duplica uma linha de posts_estado_atual: a checagem
    real `estado_atual_chave_unica` (sql/06_qualidade.sql) precisa acusar 'falha'."""
    original = pipeline.reconstruir

    def reconstruir_e_estragar(con, *args, **kwargs):
        original(con, *args, **kwargs)
        con.execute("INSERT INTO posts_estado_atual SELECT * FROM posts_estado_atual LIMIT 1")

    monkeypatch.setattr(pipeline, "reconstruir", reconstruir_e_estragar)
