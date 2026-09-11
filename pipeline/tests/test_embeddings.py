"""Testes do módulo de embedding, sem baixar o modelo.

Um substituto no lugar do sentence-transformers registra tudo que chega até ele
e devolve vetores deliberadamente fora da norma. Assim dá para verificar as duas
garantias do módulo — prefixo sempre aplicado, norma sempre 1 — sem os trinta
segundos de carga do modelo real.
"""

from __future__ import annotations

import numpy as np
import pytest

import embeddings
from embeddings import PREFIXO_CONSULTA, PREFIXO_DOCUMENTO, Vetorizador


class ModeloFalso:
    device = "cpu"

    def __init__(self) -> None:
        self.recebidos: list[str] = []

    def encode(self, textos, **_opcoes):
        self.recebidos.extend(textos)
        # Fora da norma de propósito, e diferente por texto.
        return np.array(
            [[float(len(t)), 3.0, 4.0] + [0.0] * (embeddings.DIMENSAO - 3) for t in textos],
            dtype=np.float32,
        )


@pytest.fixture
def modelo():
    return ModeloFalso()


def test_documentos_recebem_prefixo_de_documento(modelo):
    Vetorizador(_modelo=modelo).documentos(["casos de dengue", "leitos"])
    assert modelo.recebidos == ["passage: casos de dengue", "passage: leitos"]


def test_consulta_recebe_prefixo_de_consulta(modelo):
    Vetorizador(_modelo=modelo).consulta("onde acho dados de dengue")
    assert modelo.recebidos == ["query: onde acho dados de dengue"]


def test_nao_existe_caminho_publico_sem_prefixo(modelo):
    """A interface pública tem só as duas portas, e as duas aplicam prefixo.

    Se alguém acrescentar um método que vetorize texto cru, este teste quebra —
    que é o ponto: a omissão do prefixo degrada a busca em silêncio.
    """
    publicos = {nome for nome in dir(Vetorizador) if not nome.startswith("_")}
    assert publicos == {"documentos", "consulta", "dispositivo"}

    vetorizador = Vetorizador(_modelo=modelo)
    vetorizador.documentos(["a", "b"])
    vetorizador.consulta("c")
    assert all(
        texto.startswith((PREFIXO_DOCUMENTO, PREFIXO_CONSULTA)) for texto in modelo.recebidos
    )


def test_documentos_saem_com_norma_unitaria(modelo):
    vetores = Vetorizador(_modelo=modelo).documentos(["a", "bb", "um texto mais longo"])
    assert vetores.dtype == np.float32
    assert vetores.shape == (3, embeddings.DIMENSAO)
    np.testing.assert_allclose(np.linalg.norm(vetores, axis=1), 1.0, atol=1e-6)


def test_consulta_devolve_um_vetor_com_norma_unitaria(modelo):
    vetor = Vetorizador(_modelo=modelo).consulta("pergunta")
    assert vetor.shape == (embeddings.DIMENSAO,)
    assert np.linalg.norm(vetor) == pytest.approx(1.0, abs=1e-6)


def test_vetor_nulo_e_recusado_em_vez_de_virar_nan():
    with pytest.raises(ValueError, match="nulo"):
        embeddings.normalizar(np.zeros((1, 4)))


def test_lista_vazia_nao_chama_o_modelo(modelo):
    vetores = Vetorizador(_modelo=modelo).documentos([])
    assert vetores.shape == (0, embeddings.DIMENSAO)
    assert modelo.recebidos == []
