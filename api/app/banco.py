"""Acesso somente leitura ao catálogo.

O serviço nunca escreve no `dados.db`: quem o produz é o pipeline, offline. Abrir
em modo leitura é a garantia mecânica disso — uma escrita acidental ergue erro em
vez de corromper o artefato que levou horas para ser gerado.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class CatalogoIndisponivel(RuntimeError):
    """O banco não existe ou não tem índice."""


def abrir(caminho: Path) -> sqlite3.Connection:
    if not caminho.is_file():
        raise CatalogoIndisponivel(f"catálogo não encontrado: {caminho}")
    # `mode=ro` no URI: o SQLite recusa qualquer escrita nesta conexão.
    conexao = sqlite3.connect(
        f"file:{caminho}?mode=ro", uri=True, check_same_thread=False
    )
    conexao.row_factory = sqlite3.Row
    return conexao


def tem_indice(conexao: sqlite3.Connection) -> bool:
    return (
        conexao.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ficha_fts'"
        ).fetchone()
        is not None
    )
