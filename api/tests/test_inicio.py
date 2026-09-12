"""A busca semântica na inicialização do serviço.

Até a fusão (mudança 08), os vetores são opcionais: ausentes, o serviço sobe com
a semântica desligada; presentes e inconsistentes, ele não sobe. Os dois lados
importam — o primeiro mantém a produção de pé enquanto nada consome a busca
semântica, o segundo impede que um vetor de outra versão do catálogo aponte para
o conjunto errado sem sintoma nenhum.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import semantica
from app.configuracao import configuracao
from tests.test_resposta import FICHAS, montar_banco


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    catalogo = montar_banco(tmp_path / "dados.db", FICHAS)
    vetores = tmp_path / "vectors.npy"
    monkeypatch.setenv("BANCO", str(catalogo))
    monkeypatch.setenv("VETORES", str(vetores))
    monkeypatch.setenv("MODO_STUB", "1")
    configuracao.cache_clear()
    yield catalogo, vetores
    configuracao.cache_clear()


def _gravar(catalogo, vetores_em, *, ids=None, versao=None, so_npy=False):
    conexao = sqlite3.connect(catalogo)
    fichas = semantica.ler_fichas(conexao)
    conexao.close()
    ids = ids if ids is not None else [i for i, _ in fichas]
    with vetores_em.open("wb") as arquivo:
        # Linhas da identidade: norma 1 por construção.
        np.save(arquivo, np.eye(len(ids), 4, dtype=np.float32))
    if so_npy:
        return
    vetores_em.with_suffix(".json").write_text(
        json.dumps(
            {
                "versao": versao or semantica.versao_do_catalogo(fichas),
                "modelo": semantica.MODELO,
                "dimensao": 4,
                "sha256_vetores": semantica.soma_sha256(vetores_em),
                "ids": ids,
            }
        ),
        encoding="utf-8",
    )


def _cliente() -> TestClient:
    from app.principal import app

    return TestClient(app)


def test_sem_vetores_o_servico_nao_sobe(ambiente):
    """Desde a fusão a semântica entra em toda resposta.

    Subir sem ela responderia só com a léxica, no mesmo formato e sem sinal
    nenhum de que metade da recuperação sumiu.
    """
    with pytest.raises(RuntimeError, match="obrigatória"):
        with _cliente():
            pass


def test_vetores_coerentes_ligam_a_semantica(ambiente):
    catalogo, vetores = ambiente
    _gravar(catalogo, vetores)
    with _cliente() as cliente:
        estado = cliente.get("/saude").json()["busca_semantica"]
    assert estado == {"ativa": True, "vetores": 2, "modelo": semantica.MODELO}


def test_vetores_de_outra_versao_impedem_a_subida(ambiente):
    catalogo, vetores = ambiente
    _gravar(catalogo, vetores, versao="0" * 64)
    with pytest.raises(semantica.IndiceInconsistente, match="versões diferentes"):
        with _cliente():
            pass


def test_contagem_divergente_impede_a_subida(ambiente):
    catalogo, vetores = ambiente
    _gravar(catalogo, vetores, ids=["1", "2", "3"])
    with pytest.raises(semantica.IndiceInconsistente, match="3 vetores para 2 fichas"):
        with _cliente():
            pass


def test_metade_dos_artefatos_impede_a_subida(ambiente):
    # Um `.npy` sem o seu `.json` não é ausência: é resto de outra execução.
    catalogo, vetores = ambiente
    _gravar(catalogo, vetores, so_npy=True)
    with pytest.raises(semantica.IndiceInconsistente, match="não encontrados"):
        with _cliente():
            pass


# --- runtime opcional ----------------------------------------------------


def test_vetores_sem_runtime_impedem_a_subida(ambiente, monkeypatch):
    """Vetores presentes e fastembed ausente: a semântica se diria ativa e
    quebraria na primeira consulta. Melhor não subir."""
    catalogo, vetores = ambiente
    _gravar(catalogo, vetores)
    monkeypatch.setattr(semantica, "runtime_disponivel", lambda: False)
    with pytest.raises(RuntimeError, match="runtime da busca semântica"):
        with _cliente():
            pass


def test_modelo_indisponivel_impede_a_subida(ambiente, monkeypatch):
    """O modelo entra no build. Se faltar, o serviço quebraria na primeira
    pergunta — que é o pior momento para descobrir."""
    from app import principal

    catalogo, vetores = ambiente
    _gravar(catalogo, vetores)

    class SemModelo:
        def consulta(self, _texto):
            raise RuntimeError("modelo não encontrado no cache")

    monkeypatch.setattr(principal, "construir_vetorizador", SemModelo)
    with pytest.raises(RuntimeError, match="modelo de consulta"):
        with _cliente():
            pass
