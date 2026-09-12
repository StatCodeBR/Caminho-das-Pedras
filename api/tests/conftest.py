"""Isolamento da suíte da api."""

from __future__ import annotations

from pathlib import Path

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


class VetorizadorFalso:
    """Substituto do modelo real: devolve sempre o mesmo vetor, de quatro dimensões.

    A dimensão casa com a dos vetores que `gravar_vetores` produz. Nenhum teste
    da suíte mede qualidade de embedding — o que se mede aqui é o contrato em
    volta dele.
    """

    def consulta(self, _texto: str):
        import numpy as np

        return np.array([1, 0, 0, 0], dtype=np.float32)

    def documentos(self, textos):
        import numpy as np

        return np.zeros((len(textos), 4), dtype=np.float32)


@pytest.fixture(autouse=True)
def _sem_modelo_de_verdade(monkeypatch):
    """Nenhum teste carrega o modelo real.

    A busca semântica é obrigatória desde a fusão, então a app só sobe com
    vetores e com um vetorizador que responda. Carregar o ONNX em cada teste
    custaria segundos e não mediria nada.
    """
    from app import principal

    monkeypatch.setattr(principal, "construir_vetorizador", VetorizadorFalso)


def gravar_vetores(banco, diretorio):
    """Vetores coerentes com o banco, para os testes que sobem a app.

    Artificiais de propósito — matriz identidade, quatro dimensões —, porque o
    que precisa ser verdade nos testes é a coerência entre vetores e banco, não
    a qualidade da vizinhança.
    """
    import json
    import sqlite3

    import numpy as np

    from app import semantica

    conexao = sqlite3.connect(banco)
    fichas = semantica.ler_fichas(conexao)
    conexao.close()

    npy = Path(diretorio) / "vectors.npy"
    with npy.open("wb") as arquivo:
        np.save(arquivo, np.eye(len(fichas), 4, dtype=np.float32))
    npy.with_suffix(".json").write_text(
        json.dumps(
            {
                "versao": semantica.versao_do_catalogo(fichas),
                "modelo": semantica.MODELO,
                "dimensao": 4,
                "sha256_vetores": semantica.soma_sha256(npy),
                "ids": [i for i, _ in fichas],
            }
        ),
        encoding="utf-8",
    )
    return npy
