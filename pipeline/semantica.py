"""Busca por significado, sobre os vetores gerados por `vetoriza.py`.

A léxica acerta quando a pessoa usa as palavras do catálogo; esta cobre quando
não usa — "remédio de graça" contra "assistência farmacêutica". As duas
convivem, e a fusão vem na mudança 08. Aqui o resultado sai no mesmo formato da
léxica para que a fusão não precise saber de onde cada lista veio.

A pontuação é o cosseno cru, sem a penalização por confiança que a léxica
aplica. Decidir como combinar as duas escalas é trabalho da fusão.

O arquivo binário não guarda identificadores: a linha *i* da matriz corresponde
ao identificador *i* de `vectors.json`. Essa ordem é contrato, e vetor órfão de
uma versão anterior do banco apontaria para o conjunto errado sem sintoma
nenhum. Por isso a carga confere três coisas antes de aceitar os artefatos: que
o `.npy` é o que o `.json` descreve, que a contagem bate com a de fichas, e que
os dois foram gerados sobre o mesmo texto que o banco tem agora.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

import embeddings
from busca import LIMITE_PADRAO, Resultado

RAIZ = Path(__file__).resolve().parent
DIRETORIO_DADOS = RAIZ / "dados"
ARQUIVO_VETORES = DIRETORIO_DADOS / "vectors.npy"
ARQUIVO_IDENTIFICADORES = DIRETORIO_DADOS / "vectors.json"

# Folga para arredondamento de float32. Uma norma fora disto não é imprecisão:
# é vetor que não passou pela normalização, e o produto escalar deixaria de ser
# cosseno.
TOLERANCIA_NORMA = 1e-3

BLOCO = 1024 * 1024


class IndiceInconsistente(RuntimeError):
    """Vetores ausentes, corrompidos ou de outra versão do catálogo."""


# --- contrato dos artefatos ---------------------------------------------


def ler_fichas(conexao: sqlite3.Connection) -> list[tuple[str, str]]:
    """O que se vetoriza, na ordem em que se vetoriza. A ordem é contrato."""
    return [
        (linha[0], linha[1] or "")
        for linha in conexao.execute(
            "SELECT conjunto_id, texto_indexavel FROM ficha ORDER BY conjunto_id"
        )
    ]


def versao_do_catalogo(fichas: Iterable[tuple[str, str]]) -> str:
    """Impressão digital do texto vetorizado.

    Cobre identificador e texto, na ordem. Recoletar, reenriquecer ou mudar o
    prompt muda o texto indexável de alguma ficha, e com ele esta soma — que é
    o que faz vetores velhos serem recusados em vez de servidos.
    """
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


def carregar(
    conexao: sqlite3.Connection,
    vetores_em: Path = ARQUIVO_VETORES,
    ids_em: Path = ARQUIVO_IDENTIFICADORES,
) -> Indice:
    """Carrega os vetores e recusa qualquer um que não corresponda ao banco."""
    if not vetores_em.is_file() or not ids_em.is_file():
        raise IndiceInconsistente(
            f"vetores não encontrados em {vetores_em.parent}; rode: just vetores"
        )

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

    fichas = ler_fichas(conexao)
    if len(fichas) != len(ids):
        raise IndiceInconsistente(
            f"{len(ids)} vetores para {len(fichas)} fichas: o banco mudou depois "
            "da vetorização; rode: just vetores"
        )
    if [identificador for identificador, _ in fichas] != ids:
        raise IndiceInconsistente(
            "os identificadores não estão na ordem das fichas: a linha de cada "
            "vetor apontaria para o conjunto errado"
        )
    if versao_do_catalogo(fichas) != meta.get("versao"):
        raise IndiceInconsistente(
            "vetores e banco são de versões diferentes do catálogo: o texto de "
            "alguma ficha mudou depois da vetorização; rode: just vetores"
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
        modelo=str(meta.get("modelo") or ""),
    )


# --- busca ---------------------------------------------------------------


def buscar(
    conexao: sqlite3.Connection,
    indice: Indice,
    vetorizador: embeddings.Vetorizador,
    consulta: str,
    limite: int = LIMITE_PADRAO,
) -> list[Resultado]:
    """Os conjuntos de significado mais próximo, no formato da busca léxica."""
    if not (consulta or "").strip():
        return []
    total = len(indice.ids)
    k = min(limite, total)
    if k <= 0:
        return []

    # Produto escalar puro: os dois lados já têm norma 1, então isto é o
    # cosseno. Nenhuma divisão acontece em tempo de consulta.
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
                   f.confianca, f.resumo
            FROM ficha f JOIN conjunto c ON c.id = f.conjunto_id
            WHERE f.conjunto_id IN ({marcadores})
            """,
            escolhidos,
        )
    }

    resultados: list[Resultado] = []
    for posicao, (identificador, linha_da_matriz) in enumerate(
        zip(escolhidos, melhores), start=1
    ):
        linha = linhas[identificador]
        pontuacao = float(pontos[linha_da_matriz])
        resultados.append(
            Resultado(
                conjunto_id=identificador,
                posicao=posicao,
                pontuacao=pontuacao,
                pontuacao_bruta=pontuacao,
                nome=linha["slug"],
                titulo=linha["titulo"] or "",
                organizacao=linha["organizacao"] or "",
                confianca=linha["confianca"],
                resumo=linha["resumo"] or "",
                casados={},
            )
        )
    return resultados
