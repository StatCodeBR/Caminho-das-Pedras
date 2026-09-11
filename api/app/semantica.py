"""Busca por significado no serviço de consulta, com runtime ONNX.

Espelha `pipeline/embeddings.py` e `pipeline/semantica.py` com uma diferença
deliberada: aqui não há PyTorch. O pipeline gera os vetores com
sentence-transformers, que traz quase dois gigabytes de dependências; o serviço
vetoriza a pergunta com fastembed, sobre o export ONNX do mesmo modelo. O código
executado é outro e o vetor precisa ser o mesmo — é o que o teste de paridade
garante, contra a referência que o pipeline gera.

A duplicação com o pipeline é deliberada e registrada, como a de
`recuperacao.py`: os dois projetos não podem se importar, porque este não pode
carregar torch. Se divergirem nos prefixos ou na versão do catálogo, a busca
degrada em silêncio — por isso os dois lados têm teste sobre o mesmo contrato.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .recuperacao import Recuperado, _data, carregar_recursos

MODELO = "intfloat/multilingual-e5-small"
DIMENSAO = 384

# O fastembed não traz o e5 pequeno na lista nativa — só o grande, de 1024
# dimensões e 2,2 GB. Ele entra como modelo customizado, a partir do export ONNX
# que o próprio repositório do modelo publica, com o pooling por média que o
# sentence-transformers usa. A paridade medida contra o pipeline foi de cosseno
# 1,000000, inclusive no texto mais longo do corpus.
ARQUIVO_ONNX = "onnx/model.onnx"

PREFIXO_DOCUMENTO = "passage: "
PREFIXO_CONSULTA = "query: "

TOLERANCIA_NORMA = 1e-3
BLOCO = 1024 * 1024

_registrado = False


def runtime_disponivel() -> bool:
    """O fastembed está instalado?

    Ele mora num grupo opcional e fica fora da imagem enquanto a busca semântica
    está desligada em produção. Quem instala vetores precisa instalá-lo junto.
    """
    import importlib.util

    return importlib.util.find_spec("fastembed") is not None


def _registrar() -> None:
    global _registrado
    if _registrado:
        return
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    try:
        TextEmbedding.add_custom_model(
            model=MODELO,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=MODELO),
            dim=DIMENSAO,
            model_file=ARQUIVO_ONNX,
        )
    except ValueError:
        # O registro é global ao processo; registrar de novo é o único
        # ValueError que `add_custom_model` ergue, e não é erro.
        pass
    _registrado = True


def normalizar(matriz: Any) -> np.ndarray:
    """Divide cada linha pela própria norma. Vetor nulo é erro, não zero."""
    matriz = np.asarray(matriz, dtype=np.float32)
    if matriz.ndim == 1:
        matriz = matriz[None, :]
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    if np.any(normas == 0):
        raise ValueError("o modelo devolveu um vetor nulo; não há como normalizá-lo")
    return (matriz / normas).astype(np.float32)


class Vetorizador:
    """A única porta de entrada para vetorizar texto no serviço.

    Como no pipeline, só existem `documentos` e `consulta`, e cada um aplica o
    seu prefixo. `documentos` existe aqui apenas para o teste de paridade: o
    serviço nunca vetoriza fichas, só lê os vetores que o pipeline gravou.
    """

    def __init__(self, *, _modelo: Any = None) -> None:
        self._modelo = _modelo

    def _obter(self) -> Any:
        if self._modelo is None:
            _registrar()
            from fastembed import TextEmbedding

            self._modelo = TextEmbedding(MODELO)
        return self._modelo

    def _vetorizar(self, textos: Sequence[str], prefixo: str) -> np.ndarray:
        brutos = list(self._obter().embed([prefixo + texto for texto in textos]))
        return normalizar(np.array(brutos, dtype=np.float32))

    def documentos(self, textos: Sequence[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, DIMENSAO), dtype=np.float32)
        return self._vetorizar(textos, PREFIXO_DOCUMENTO)

    def consulta(self, texto: str) -> np.ndarray:
        return self._vetorizar([texto], PREFIXO_CONSULTA)[0]


# --- contrato dos artefatos — espelho de pipeline/semantica.py -----------


class IndiceInconsistente(RuntimeError):
    """Vetores ausentes, corrompidos ou de outra versão do catálogo."""


def ler_fichas(conexao: sqlite3.Connection) -> list[tuple[str, str]]:
    return [
        (linha[0], linha[1] or "")
        for linha in conexao.execute(
            "SELECT conjunto_id, texto_indexavel FROM ficha ORDER BY conjunto_id"
        )
    ]


def versao_do_catalogo(fichas: Iterable[tuple[str, str]]) -> str:
    digestor = hashlib.sha256()
    for identificador, texto in fichas:
        digestor.update(identificador.encode("utf-8"))
        digestor.update(b"\x00")
        digestor.update(texto.encode("utf-8"))
        digestor.update(b"\x1e")
    return digestor.hexdigest()


def soma_sha256(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(BLOCO), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


@dataclass
class Indice:
    vetores: np.ndarray
    ids: list[str]
    versao: str
    modelo: str


def carregar(conexao: sqlite3.Connection, vetores_em: Path, ids_em: Path) -> Indice:
    """Carrega os vetores e recusa qualquer um que não corresponda ao banco."""
    if not vetores_em.is_file() or not ids_em.is_file():
        raise IndiceInconsistente(f"vetores não encontrados em {vetores_em.parent}")

    try:
        meta = json.loads(ids_em.read_text(encoding="utf-8"))
    except ValueError as erro:
        raise IndiceInconsistente(f"{ids_em.name} ilegível: {erro}") from None

    if soma_sha256(vetores_em) != meta.get("sha256_vetores"):
        raise IndiceInconsistente(
            f"{vetores_em.name} não é o arquivo que {ids_em.name} descreve: "
            "os dois foram gravados por execuções diferentes"
        )

    vetores = np.load(vetores_em, allow_pickle=False)
    ids = list(meta.get("ids") or [])
    dimensao = int(meta.get("dimensao") or 0)
    if vetores.shape != (len(ids), dimensao):
        raise IndiceInconsistente(
            f"a matriz tem forma {vetores.shape}, mas o manifesto declara "
            f"{len(ids)} identificadores de dimensão {dimensao}"
        )
    if meta.get("modelo") != MODELO:
        raise IndiceInconsistente(
            f"vetores gerados por {meta.get('modelo')!r}, mas o serviço consulta "
            f"com {MODELO!r}: os dois espaços não são comparáveis"
        )

    fichas = ler_fichas(conexao)
    if len(fichas) != len(ids):
        raise IndiceInconsistente(
            f"{len(ids)} vetores para {len(fichas)} fichas: o banco mudou depois "
            "da vetorização"
        )
    if [identificador for identificador, _ in fichas] != ids:
        raise IndiceInconsistente(
            "os identificadores não estão na ordem das fichas: a linha de cada "
            "vetor apontaria para o conjunto errado"
        )
    if versao_do_catalogo(fichas) != meta.get("versao"):
        raise IndiceInconsistente(
            "vetores e banco são de versões diferentes do catálogo: o texto de "
            "alguma ficha mudou depois da vetorização"
        )

    normas = np.linalg.norm(vetores, axis=1)
    if len(normas) and not np.allclose(normas, 1.0, atol=TOLERANCIA_NORMA):
        raise IndiceInconsistente(
            f"vetores fora da norma unitária (entre {normas.min():.4f} e "
            f"{normas.max():.4f}): o produto escalar deixaria de ser cosseno"
        )

    return Indice(
        vetores=vetores.astype(np.float32, copy=False),
        ids=ids,
        versao=meta["versao"],
        modelo=meta["modelo"],
    )


# --- busca ---------------------------------------------------------------


def buscar(
    conexao: sqlite3.Connection,
    indice: Indice,
    vetorizador: Vetorizador,
    consulta: str,
    limite: int = 5,
) -> list[Recuperado]:
    """Os conjuntos de significado mais próximo, no formato da busca léxica.

    A pontuação é o cosseno cru. A léxica aplica penalização por confiança e
    usa outra escala; decidir como combinar as duas é trabalho da fusão.
    """
    if not (consulta or "").strip():
        return []
    k = min(limite, len(indice.ids))
    if k <= 0:
        return []

    # Produto escalar puro: os dois lados já têm norma 1.
    pontos = indice.vetores @ vetorizador.consulta(consulta)
    melhores = np.argpartition(-pontos, k - 1)[:k]
    melhores = melhores[np.argsort(-pontos[melhores], kind="stable")]
    escolhidos = [indice.ids[i] for i in melhores]

    marcadores = ", ".join("?" * len(escolhidos))
    linhas = {
        linha["conjunto_id"]: linha
        for linha in conexao.execute(
            f"""
            SELECT f.conjunto_id, c.nome AS slug, c.titulo, c.organizacao,
                   c.dados_atualizados_em, c.metadados_atualizados_em,
                   f.confianca, f.resumo, f.perguntas_json
            FROM ficha f JOIN conjunto c ON c.id = f.conjunto_id
            WHERE f.conjunto_id IN ({marcadores})
            """,
            escolhidos,
        )
    }

    recuperados: list[Recuperado] = []
    for posicao, (identificador, linha_da_matriz) in enumerate(
        zip(escolhidos, melhores), start=1
    ):
        linha = linhas[identificador]
        try:
            perguntas = [str(p) for p in json.loads(linha["perguntas_json"] or "[]")]
        except ValueError:
            perguntas = []
        recuperados.append(
            Recuperado(
                conjunto_id=identificador,
                posicao=posicao,
                pontuacao=float(pontos[linha_da_matriz]),
                nome=linha["slug"],
                titulo=linha["titulo"] or "",
                organizacao=linha["organizacao"] or "",
                confianca=linha["confianca"],
                resumo=linha["resumo"] or "",
                perguntas=perguntas,
                dados_atualizados_em=_data(linha["dados_atualizados_em"]),
                metadados_atualizados_em=_data(linha["metadados_atualizados_em"]),
            )
        )
    carregar_recursos(conexao, recuperados)
    return recuperados
