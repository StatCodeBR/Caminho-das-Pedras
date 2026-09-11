"""Isolamento da suíte da api."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _sem_vetores_do_desenvolvedor(tmp_path, monkeypatch):
    """Nenhum teste enxerga os vetores reais da máquina de quem roda a suíte.

    O padrão de VETORES aponta para `pipeline/dados/vectors.npy`, que existe
    onde o pipeline já rodou. Sem isto, todo teste que sobe a app carregaria os
    19.958 vetores reais contra o banco de teste, de duas fichas — e o serviço,
    corretamente, se recusaria a subir. Quem precisa de vetores grava os seus.
    """
    monkeypatch.setenv("VETORES", str(tmp_path / "vetores-ausentes.npy"))


@pytest.fixture(autouse=True)
def _contencao_isolada(tmp_path, monkeypatch):
    """Cada teste com o próprio estado de contenção, nunca o de desenvolvimento.

    O limite por origem mora num SQLite em `estado_dir`, e o serviço guarda a
    contenção num singleton. Sem isto, os testes que sobem a app gravavam no
    `api/estado/consumo.db` real, todos sob a origem `testclient`: rodar a suíte
    algumas vezes na mesma hora enchia a janela de 20, e testes que nada têm a
    ver com contenção passavam a falhar com 429.
    """
    from app import principal
    from app.configuracao import configuracao

    monkeypatch.setenv("ESTADO_DIR", str(tmp_path / "estado"))
    monkeypatch.setattr(principal, "_contencao", None)
    configuracao.cache_clear()
    yield
    configuracao.cache_clear()
