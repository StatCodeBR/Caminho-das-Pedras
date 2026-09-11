"""Paridade, lado da consulta: o runtime ONNX reproduz os vetores do pipeline.

A referência foi gerada pelo sentence-transformers do pipeline e mora em
`pipeline/tests/fixtures/`. Este teste lê o arquivo — não importa código do
pipeline, que carregaria torch — e vetoriza os mesmos textos pela interface
pública do serviço, com os prefixos que ela aplica. Se a similaridade cair
abaixo de 0,999, os vetores do índice e os da pergunta deixaram de morar no
mesmo espaço, e nenhum catálogo deve ser publicado.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app import semantica

pytestmark = pytest.mark.paridade

REFERENCIA = (
    Path(__file__).resolve().parents[2] / "pipeline" / "tests" / "fixtures" / "paridade_e5.npz"
)
LIMIAR = 0.999


def test_onnx_reproduz_a_referencia_do_pipeline():
    referencia = np.load(REFERENCIA, allow_pickle=False)
    assert str(referencia["modelo"]) == semantica.MODELO

    vetorizador = semantica.Vetorizador()
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
