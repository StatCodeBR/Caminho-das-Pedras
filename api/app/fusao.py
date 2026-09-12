"""Funde os rankings léxico e semântico por posição, no serviço.

Espelho de `pipeline/fusao.py`, com duas diferenças que a produção impõe: as
duas buscas rodam em paralelo, porque aqui a latência é percebida por quem
espera a resposta, e o resultado sai como `Recuperado`, que é o que o resto do
serviço já consome.

Reciprocal Rank Fusion: cada ranking contribui `1 / (k + posição)`. Só a ordem
importa — BM25 não tem teto e depende do corpus, o cosseno vive entre menos um e
um, e somá-los com pesos exigiria recalibrar a cada recatalogação.

A pontuação do RRF serve para ordenar, e não diz nada sobre pertinência: ela
vale cerca de 0,016 para um primeiro lugar. Quem precisa decidir se a
recuperação sustenta resposta usa `pontuacoes`, que preserva a pontuação de cada
ranking na escala dele.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Iterable, Mapping

from .recuperacao import Recuperado

LEXICA = "lexica"
SEMANTICA = "semantica"


def fundir(
    rankings: Mapping[str, Iterable[Recuperado]], limite: int, k: float
) -> list[Recuperado]:
    """Combina rankings já ordenados. Função pura: não busca nada.

    O desempate é pelo identificador do conjunto, em ordem crescente. Precisa
    ser assim, e não pela ordem de chegada: as buscas rodam em paralelo, e usar
    a ordem de conclusão faria a mesma pergunta devolver ordens diferentes
    conforme qual terminasse primeiro.
    """
    pontos: dict[str, float] = {}
    origens: dict[str, dict[str, int]] = {}
    pontuacoes: dict[str, dict[str, float]] = {}
    fonte: dict[str, Recuperado] = {}

    for nome in sorted(rankings):
        for posicao, item in enumerate(rankings[nome], start=1):
            identificador = item.conjunto_id
            pontos[identificador] = pontos.get(identificador, 0.0) + 1.0 / (k + posicao)
            origens.setdefault(identificador, {})[nome] = posicao
            pontuacoes.setdefault(identificador, {})[nome] = float(item.pontuacao)
            fonte.setdefault(identificador, item)

    ordenados = sorted(pontos, key=lambda i: (-pontos[i], i))
    finalistas: list[Recuperado] = []
    for posicao, identificador in enumerate(ordenados[:limite], start=1):
        item = fonte[identificador]
        item.posicao = posicao
        item.pontuacao = pontos[identificador]
        item.origens = origens[identificador]
        item.pontuacoes = pontuacoes[identificador]
        finalistas.append(item)
    return finalistas


async def buscar(
    consulta: str,
    limite: int,
    *,
    lexica: Callable[[int], list[Recuperado]],
    semantica: Callable[[int], list[Recuperado]] | None,
    profundidade: int,
    k: float,
    registrar: Callable[[str, Exception], None] | None = None,
) -> list[Recuperado]:
    """Roda os dois rankings em paralelo e funde o que sobreviver.

    Cada busca é síncrona e bloqueia — SQLite de um lado, produto de matriz do
    outro —, então vai para uma thread. Falha de um ranking não derruba a
    consulta: o resultado sai do outro, e a ocorrência é registrada. Meia
    resposta é melhor que nenhuma, mas silêncio sobre a metade que faltou não é.
    """
    fundo = max(profundidade, limite)
    tarefas: dict[str, Any] = {}
    if lexica is not None:
        tarefas[LEXICA] = asyncio.to_thread(lexica, fundo)
    if semantica is not None:
        tarefas[SEMANTICA] = asyncio.to_thread(semantica, fundo)

    concluidas = await asyncio.gather(*tarefas.values(), return_exceptions=True)

    rankings: dict[str, list[Recuperado]] = {}
    for nome, resultado in zip(tarefas, concluidas):
        if isinstance(resultado, Exception):
            if registrar is not None:
                registrar(nome, resultado)
            continue
        rankings[nome] = list(resultado)

    if not rankings:
        # Os dois falharam. Vazio é ausência de resultado, não erro: quem
        # consome já sabe tratar "não encontrei".
        return []

    return fundir(rankings, limite, k)
