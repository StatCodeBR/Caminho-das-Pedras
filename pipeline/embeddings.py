"""Vetores de significado para as fichas e para as perguntas.

O modelo — multilingual-e5-small — foi treinado com prefixos que distinguem
documento de consulta. Indexar sem `passage: ` ou consultar sem `query: ` produz
resultados piores de um jeito sutil demais para ser notado: a busca não quebra,
só erra mais, e o erro seria atribuído ao prompt ou aos dados. Por isso o
prefixo é responsabilidade deste módulo e de ninguém mais — não existe método
público que vetorize texto cru.

Os vetores saem normalizados para norma 1, de modo que a similaridade de
cosseno vira produto escalar puro. A normalização é feita aqui, e não delegada a
um parâmetro da biblioteca, para que seja verificável e não dependa de versão.

Este é o runtime de *geração*, com PyTorch. O serviço de consulta usa outro
runtime, ONNX, sobre o mesmo modelo — ver `api/app/semantica.py` e o teste de
paridade, que garante que os dois produzem o mesmo vetor.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

MODELO = "intfloat/multilingual-e5-small"
DIMENSAO = 384

PREFIXO_DOCUMENTO = "passage: "
PREFIXO_CONSULTA = "query: "


def normalizar(matriz: Any) -> np.ndarray:
    """Divide cada linha pela própria norma. Vetor nulo é erro, não zero."""
    matriz = np.asarray(matriz, dtype=np.float32)
    if matriz.ndim == 1:
        matriz = matriz[None, :]
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    if np.any(normas == 0):
        # Vetor nulo não tem direção: normalizá-lo daria NaN, e um NaN na matriz
        # contamina o ranking inteiro sem erro nenhum.
        raise ValueError("o modelo devolveu um vetor nulo; não há como normalizá-lo")
    return (matriz / normas).astype(np.float32)


class Vetorizador:
    """A única porta de entrada para vetorizar texto.

    Os dois métodos públicos, `documentos` e `consulta`, aplicam cada um o seu
    prefixo. Não há um terceiro: texto sem prefixo não tem por onde entrar.

    O modelo é carregado na primeira chamada, não na construção — são quase
    trinta segundos, e quem só quer montar o objeto não deveria pagá-los.
    """

    def __init__(self, dispositivo: str | None = None, *, _modelo: Any = None) -> None:
        self._dispositivo = dispositivo
        # Injeção para teste: um substituto com `encode`, que dispensa baixar o
        # modelo e permite verificar o que de fato chega até ele.
        self._modelo = _modelo

    def _obter(self) -> Any:
        if self._modelo is None:
            import torch
            from sentence_transformers import SentenceTransformer

            dispositivo = self._dispositivo or (
                "cuda" if torch.cuda.is_available() else "cpu"
            )
            self._modelo = SentenceTransformer(MODELO, device=dispositivo)
        return self._modelo

    @property
    def dispositivo(self) -> str:
        return str(getattr(self._obter(), "device", self._dispositivo or "?"))

    def _vetorizar(
        self, textos: Sequence[str], prefixo: str, lote: int, progresso: bool
    ) -> np.ndarray:
        brutos = self._obter().encode(
            [prefixo + texto for texto in textos],
            batch_size=lote,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=progresso,
        )
        return normalizar(brutos)

    def documentos(
        self, textos: Sequence[str], lote: int = 64, progresso: bool = False
    ) -> np.ndarray:
        """Uma linha por texto, na mesma ordem, com o prefixo de documento."""
        if not textos:
            return np.zeros((0, DIMENSAO), dtype=np.float32)
        return self._vetorizar(textos, PREFIXO_DOCUMENTO, lote, progresso)

    def consulta(self, texto: str) -> np.ndarray:
        """Um vetor só, com o prefixo de consulta."""
        return self._vetorizar([texto], PREFIXO_CONSULTA, 1, False)[0]
