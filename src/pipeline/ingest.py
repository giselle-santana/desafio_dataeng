"""Carga da camada bruta: um dia de chegada por vez, substituindo o dia inteiro.

O Python lista a pasta e le cada .gz uma vez (integridade + sha256); o resto e SQL
(sql/carga_*.sql): leitura das linhas, numeracao e contagem.
"""
from __future__ import annotations

import gzip
import hashlib
from datetime import date
from pathlib import Path

import duckdb

from .db import ler_sql


def listar_arquivos(dados_dir: Path, dia: date) -> list[Path]:
    pasta = Path(dados_dir) / dia.isoformat()
    return sorted(pasta.glob("*.jsonl.gz")) if pasta.is_dir() else []


def _ler_gzip(caminho: Path) -> str:
    """Le o .gz inteiro, em blocos, e devolve o sha256 do conteudo DESCOMPACTADO.

    Serve a duas coisas numa passada so (memoria constante):
      * integridade: levanta se o arquivo estiver truncado ou corrompido (o modulo gzip confere
        CRC e tamanho no fim do fluxo);
      * hash do conteudo, para detectar arquivo reentregue.
    Nao da para delegar a integridade ao DuckDB: nas versoes 1.1 e 1.5 um .gz cortado (no meio ou
    sem o rodape) e lido SEM ERRO e entra incompleto; e nenhuma versao, nem a 2.0, confere o CRC.
    Ver tests/test_integridade_gzip.py.
    """
    h = hashlib.sha256()
    with gzip.open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def carregar_dia(con: duckdb.DuckDBPyConnection, dados_dir: Path, dia: date) -> int | None:
    """Substitui as linhas brutas do dia pelas dos arquivos hoje presentes na pasta.

    Retorna o numero de arquivos carregados, ou None se a pasta nao tem arquivos
    (nesse caso NAO apaga nada: ausencia de arquivo nao pode virar perda de dados).
    Deve ser chamada dentro de uma transacao.
    """
    arquivos = listar_arquivos(dados_dir, dia)
    if not arquivos:
        return None

    hashes = [_ler_gzip(f) for f in arquivos]  # falha cedo (arquivo corrompido), antes de alterar qualquer coisa

    con.execute("DELETE FROM raw_linhas WHERE dia_chegada = ?", [dia])
    con.execute("DELETE FROM arquivos WHERE dia_chegada = ?", [dia])
    for f in arquivos:  # um arquivo por vez: garante a numeracao de linhas (ver carga_linhas.sql)
        con.execute(ler_sql("carga_linhas.sql"), [dia, f.name, str(f)])
    con.execute(ler_sql("carga_arquivos.sql"), [dia, [f.name for f in arquivos], hashes, dia])
    return len(arquivos)
