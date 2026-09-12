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

from .fusao import LEXICA
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


def pontuacao_lexica(recuperado: Recuperado) -> float:
    """A pontuação na escala em que os limiares foram calibrados.

    Depois da fusão, `pontuacao` é o valor do RRF — algo em torno de 0,03, que
    ordena bem e não diz nada sobre pertinência. Aplicar os limiares a ela faria
    o serviço responder "não encontrei" para tudo: medido, zero das catorze
    perguntas de avaliação sobreviveriam. Os limiares foram medidos na escala do
    BM25 e é nela que continuam valendo.

    Sem fusão, `pontuacao` já é a léxica, e o resultado é o mesmo de antes.
    """
    if recuperado.pontuacoes:
        return float(recuperado.pontuacoes.get(LEXICA, 0.0))
    return float(recuperado.pontuacao)


def concordam_os_rankings(recuperado: Recuperado) -> bool:
    """O conjunto apareceu em mais de um ranking?

    Concordância entre dois métodos independentes é evidência por si, e não
    precisa de escala calibrada — o que é uma sorte, porque o cosseno não serve
    de limiar: nas catorze perguntas ele ficou entre 0,84 e 0,90 tanto nos
    acertos quanto nos erros.
    """
    return len(recuperado.origens) > 1


def _pertinente(recuperado: Recuperado, limiar_relevancia: float) -> bool:
    """Há evidência que sustente citar este conjunto?

    Concordância entre os dois rankings basta. Sem ela, exige-se casamento
    léxico acima do limiar — e ausência da léxica não é o mesmo que pontuação
    baixa nela: quem não apareceu no ranking léxico não tem casamento nenhum,
    por mais alto que seja o cosseno.
    """
    if concordam_os_rankings(recuperado):
        return True
    if recuperado.origens and LEXICA not in recuperado.origens:
        return False
    return pontuacao_lexica(recuperado) >= limiar_relevancia


def decidir(
    recuperados: list[Recuperado],
    *,
    limiar_template: float,
    margem_template: float,
    limiar_relevancia: float,
) -> Rota:
    """Escolhe o caminho a partir das pontuações da recuperação."""
    relevantes = [r for r in recuperados if _pertinente(r, limiar_relevancia)]
    if not relevantes:
        return Rota(
            Origem.AUSENCIA,
            "nenhuma ficha alcançou o limiar de relevância",
            [],
        )

    # Se o primeiro colocado da fusão não sobreviveu ao filtro de relevância, o
    # segundo não herda o direito ao template: a fusão pôs outra coisa na frente,
    # e afirmar correspondência direta esconderia isso de quem pergunta.
    if relevantes[0] is not recuperados[0]:
        return Rota(
            Origem.MODELO,
            "o primeiro colocado da fusão não sustenta resposta por template",
            relevantes,
        )

    # O template afirma correspondência direta, e isso exige casamento literal:
    # um conjunto que só a busca semântica encontrou nunca o dispara, porque a
    # sua pontuação léxica é zero.
    primeiro = pontuacao_lexica(relevantes[0])
    if primeiro < limiar_template:
        return Rota(Origem.MODELO, "primeiro colocado abaixo do limiar", relevantes)

    segundo = pontuacao_lexica(relevantes[1]) if len(relevantes) > 1 else 0.0
    margem = primeiro - segundo
    if margem < margem_template:
        return Rota(
            Origem.MODELO,
            f"margem de {margem:.2f} sobre o segundo é menor que {margem_template:.2f}",
            relevantes,
        )

    return Rota(Origem.TEMPLATE, "correspondência destacada", relevantes)
