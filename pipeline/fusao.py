"""Funde os rankings léxico e semântico por posição.

Reciprocal Rank Fusion: cada ranking contribui `1 / (k + posição)` para cada
conjunto que traz. Só a ordem importa, e é isso que resolve o problema de
origem — BM25 não tem teto e depende do corpus, o cosseno vive entre menos um e
um, e somar os dois com pesos exigiria recalibrar a cada recatalogação.

A consequência prática do somatório é que concordância vale mais que destaque
isolado: um conjunto em terceiro nos dois rankings supera um primeiro colocado
em apenas um. É justamente o caso que motiva fundir.

Espelhado em `api/app/fusao.py`, como o resto do núcleo de recuperação: os dois
projetos não podem se importar, porque a api não carrega torch.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

# O valor consagrado do RRF. Fica configurável por completude, mas mexer nele
# sem número da avaliação na mão é chute: `k` grande achata as contribuições e
# aproxima a fusão de uma votação simples; `k` pequeno faz o primeiro lugar de
# cada ranking dominar.
RRF_K_PADRAO = 60.0

# Quantos candidatos pedir a cada ranking antes de fundir. Maior que o retorno
# de propósito: truncar cedo elimina o conjunto que aparece em décimo nos dois,
# que é o que a fusão existe para encontrar.
#
# Medido sobre as catorze perguntas de avaliação, e o resultado contraria a
# intuição de pedir muitos candidatos:
#
#   profundidade   5     10     20     50
#   recall@5     71,4%  78,6%  71,4%  64,3%
#   MRR          0,419  0,530  0,524  0,478
#
# A causa é aritmética: com profundidade 50, dois lugares medianos somam mais
# que um primeiro lugar isolado — 1/88 + 1/71 supera 1/61 —, e a fusão passa a
# premiar o que os dois rankings acharam morno sobre o que um deles acertou em
# cheio. Na pergunta "a água que chega na minha casa é boa", os conjuntos do
# SISAGUA, primeiros na léxica, perderam para uma projeção de uso de água que
# estava em 28º e 11º.
#
# Continua maior que o retorno, que é o ponto de pedir mais de cinco. Calibrado
# sobre n=14: revisar quando o conjunto de avaliação crescer.
PROFUNDIDADE_PADRAO = 10

LEXICA = "lexica"
SEMANTICA = "semantica"


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def _do_ambiente(chave: str, padrao: float) -> float:
    try:
        return float(os.environ.get(chave, padrao))
    except ValueError:
        return padrao


def rrf_k() -> float:
    return _do_ambiente("RRF_K", RRF_K_PADRAO)


def profundidade() -> int:
    return int(_do_ambiente("PROFUNDIDADE_BUSCA", PROFUNDIDADE_PADRAO))


@dataclass
class Fundido:
    """Um finalista, com a proveniência que o levou até ali."""

    conjunto_id: str
    posicao: int
    pontuacao: float
    nome: str
    titulo: str
    organizacao: str
    confianca: str
    resumo: str
    # Ranking de origem -> posição ocupada nele. Serve a três coisas:
    # diagnosticar falha na avaliação, explicar ao usuário por que o conjunto
    # apareceu, e dar ao roteamento mais informação que a pontuação final.
    origens: dict[str, int] = field(default_factory=dict)
    # Ranking de origem -> pontuação naquele ranking, na escala dele. O RRF não
    # a usa; quem roteia precisa dela, porque a escala do RRF não diz nada
    # sobre pertinência.
    pontuacoes: dict[str, float] = field(default_factory=dict)

    @property
    def rankings(self) -> list[str]:
        return sorted(self.origens)


def fundir(
    rankings: Mapping[str, Iterable[Any]],
    limite: int,
    k: float | None = None,
) -> list[Fundido]:
    """Combina rankings já ordenados. Função pura: não busca nada.

    O desempate é pelo identificador do conjunto, em ordem crescente. Precisa
    ser assim, e não pela ordem de chegada: as buscas rodam em paralelo no
    serviço, e usar a ordem de conclusão faria a mesma pergunta devolver
    ordens diferentes conforme qual terminasse primeiro.
    """
    constante = rrf_k() if k is None else k
    pontos: dict[str, float] = {}
    origens: dict[str, dict[str, int]] = {}
    pontuacoes: dict[str, dict[str, float]] = {}
    fonte: dict[str, Any] = {}

    for nome in sorted(rankings):
        for posicao, item in enumerate(rankings[nome], start=1):
            identificador = item.conjunto_id
            pontos[identificador] = pontos.get(identificador, 0.0) + 1.0 / (
                constante + posicao
            )
            origens.setdefault(identificador, {})[nome] = posicao
            pontuacoes.setdefault(identificador, {})[nome] = float(item.pontuacao)
            fonte.setdefault(identificador, item)

    ordenados = sorted(pontos, key=lambda i: (-pontos[i], i))
    return [
        Fundido(
            conjunto_id=identificador,
            posicao=posicao,
            pontuacao=pontos[identificador],
            nome=fonte[identificador].nome,
            titulo=fonte[identificador].titulo,
            organizacao=fonte[identificador].organizacao,
            confianca=fonte[identificador].confianca,
            resumo=fonte[identificador].resumo,
            origens=origens[identificador],
            pontuacoes=pontuacoes[identificador],
        )
        for posicao, identificador in enumerate(ordenados[:limite], start=1)
    ]


def buscar(
    conexao: Any,
    consulta: str,
    limite: int,
    *,
    lexica: Callable[[Any, str, int], list[Any]],
    semantica: Callable[[Any, str, int], list[Any]] | None = None,
    profundidade_candidatos: int | None = None,
    k: float | None = None,
    registrar: Callable[[object], None] = log,
) -> list[Fundido]:
    """Roda os dois rankings e funde o que sobreviver.

    Falha de um ranking não derruba a consulta: o resultado sai do outro, e a
    ocorrência é registrada. Meia resposta é melhor que nenhuma, mas silêncio
    sobre a metade que faltou não é — sem o registro, a busca pareceria só ter
    piorado.

    No pipeline as duas buscas rodam em sequência; no serviço elas rodam em
    paralelo, onde a latência importa. A fusão é a mesma, e não depende disso:
    o desempate por identificador torna o resultado independente da ordem em
    que os rankings terminam.
    """
    fundo = profundidade() if profundidade_candidatos is None else profundidade_candidatos
    fundo = max(fundo, limite)
    rankings: dict[str, list[Any]] = {}

    for nome, buscar_um in ((LEXICA, lexica), (SEMANTICA, semantica)):
        if buscar_um is None:
            continue
        try:
            rankings[nome] = list(buscar_um(conexao, consulta, fundo))
        except Exception as erro:  # noqa: BLE001 — qualquer falha degrada, não derruba
            registrar(f"ranking {nome} falhou e foi ignorado nesta consulta: {erro}")

    if not rankings:
        # Os dois falharam. Vazio é ausência de resultado, não erro: quem
        # consome já sabe tratar "não encontrei".
        registrar("nenhum ranking respondeu; a consulta não retorna resultados")
        return []

    return fundir(rankings, limite, k)
