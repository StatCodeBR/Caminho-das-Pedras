"""Paridade, lado da geração: o runtime do pipeline ainda reproduz a referência.

A paridade entre os dois runtimes é verificada em duas metades, uma em cada
projeto, porque os dois não podem se importar — `api/` não pode carregar torch.
A referência em `tests/fixtures/paridade_e5.npz` foi gerada por este runtime;
este teste confirma que ele ainda a reproduz, e `api/tests/test_paridade.py`
confirma que o runtime ONNX também. Juntos, garantem que os vetores do índice e
os da pergunta moram no mesmo espaço.

Divergência aqui não quebra a busca de forma visível: ela só degrada, e o erro
seria atribuído ao prompt ou aos dados. Por isso nenhum catálogo é publicado sem
este teste passar.
"""

from __future__ import annotations

import numpy as np
import pytest

import embeddings
import vetoriza

pytestmark = pytest.mark.paridade

LIMIAR = 0.999


def test_pipeline_reproduz_a_referencia():
    referencia = np.load(vetoriza.ARQUIVO_REFERENCIA, allow_pickle=False)
    assert str(referencia["modelo"]) == embeddings.MODELO

    vetorizador = embeddings.Vetorizador("cpu")
    for tipo, texto, esperado in zip(
        referencia["tipos"], referencia["textos"], referencia["vetores"]
    ):
        texto = str(texto)
        obtido = (
            vetorizador.consulta(texto)
            if str(tipo) == "consulta"
            else vetorizador.documentos([texto])[0]
        )
        similaridade = float(obtido @ esperado)
        assert similaridade > LIMIAR, f"{tipo} {texto[:40]!r}: {similaridade:.6f}"
