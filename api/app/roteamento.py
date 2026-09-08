"""Decide como a pergunta será respondida.

Três caminhos, nesta ordem de verificação:

- **ausência**: a recuperação não sustenta resposta. O serviço diz que não
  encontrou, e não menciona conjunto nenhum.
- **template**: o primeiro resultado é destacadamente melhor que o segundo. A
  resposta sai montada da ficha, sem consumir token.
- **modelo**: qualquer outro caso.

A ordem importa: checar ausência primeiro impede que um resultado fraco e
isolado — pontuação baixa, mas sem concorrente — seja servido por template como
se fosse correspondência direta.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .recuperacao import Recuperado


class Origem(str, Enum):
    """Como a resposta foi produzida. Vai ao usuário e à telemetria."""

    TEMPLATE = "correspondencia_direta"
    MODELO = "redigida_pelo_modelo"
    AUSENCIA = "nao_encontrado"
    REDUZIDO = "modo_reduzido"


@dataclass
class Rota:
    origem: Origem
    motivo: str
    fichas: list[Recuperado]


def decidir(
    recuperados: list[Recuperado],
    *,
    limiar_template: float,
    margem_template: float,
    limiar_relevancia: float,
) -> Rota:
    """Escolhe o caminho a partir das pontuações da recuperação."""
    relevantes = [r for r in recuperados if r.pontuacao >= limiar_relevancia]
    if not relevantes:
        return Rota(
            Origem.AUSENCIA,
            "nenhuma ficha alcançou o limiar de relevância",
            [],
        )

    primeiro = relevantes[0]
    if primeiro.pontuacao < limiar_template:
        return Rota(Origem.MODELO, "primeiro colocado abaixo do limiar", relevantes)

    segundo = relevantes[1].pontuacao if len(relevantes) > 1 else 0.0
    margem = primeiro.pontuacao - segundo
    if margem < margem_template:
        return Rota(
            Origem.MODELO,
            f"margem de {margem:.2f} sobre o segundo é menor que {margem_template:.2f}",
            relevantes,
        )

    return Rota(Origem.TEMPLATE, "correspondência destacada", relevantes)
