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
