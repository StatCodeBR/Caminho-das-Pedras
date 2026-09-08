"""Respostas que não custam token: template e ausência.

O texto é montado da ficha, em português simples. O público inclui gente que
nunca ouviu falar em API, CSV ou dados abertos, então nada aqui usa jargão sem
explicar, e o link da página no portal aparece sempre — é por ele que a pessoa
confere o que estamos dizendo.
"""

from __future__ import annotations

from .recuperacao import Recuperado

MAX_RECURSOS_MOSTRADOS = 6

SUGESTOES = (
    "tente o nome do órgão que publica o dado, como “ANAC” ou “Ministério da Saúde”",
    "troque termos técnicos por palavras do dia a dia, como “hospital” em vez de “estabelecimento de saúde”",
    "use uma palavra a menos: buscas curtas costumam achar mais",
)


def _formatos(item: Recuperado) -> list[str]:
    vistos: dict[str, None] = {}
    for recurso in item.recursos:
        if recurso.formato:
            vistos.setdefault(recurso.formato.upper(), None)
    return list(vistos)


def _linha_recurso(recurso) -> str:
    partes = [recurso.titulo or "(sem título)"]
    if recurso.formato:
        partes.append(f"[{recurso.formato.upper()}]")
    texto = " ".join(partes)
    if not recurso.disponivel:
        # O recurso continua listado: ele existe no catálogo e a pessoa tem
        # direito de saber que existe e está fora do ar.
        return f"- {texto} — link fora do ar quando verificamos"
    if recurso.link:
        return f"- {texto} — {recurso.link}"
    return f"- {texto}"


def montar_template(item: Recuperado) -> str:
    """A resposta de correspondência direta, montada da ficha."""
    linhas: list[str] = []
    titulo = item.titulo or item.nome
    linhas.append(f"**{titulo}**")
    linhas.append("")
    if item.resumo:
        linhas.append(item.resumo)
        linhas.append("")

    if item.organizacao:
        orgao = item.organizacao.replace("-", " ")
        linhas.append(f"Quem publica: {orgao}.")

    formatos = _formatos(item)
    if formatos:
        linhas.append(f"Formatos disponíveis: {', '.join(formatos)}.")

    if item.confianca == "baixa":
        # A ficha foi escrita a partir de metadados pobres. Dizer isso é o que
        # separa a resposta honesta da que apenas soa segura.
        linhas.append(
            "O órgão publicou pouca descrição sobre este conjunto, então o "
            "resumo acima pode não cobrir tudo que ele contém."
        )

    if item.recursos:
        linhas.append("")
        linhas.append("Arquivos:")
        for recurso in item.recursos[:MAX_RECURSOS_MOSTRADOS]:
            linhas.append(_linha_recurso(recurso))
        restantes = len(item.recursos) - MAX_RECURSOS_MOSTRADOS
        if restantes > 0:
            linhas.append(f"- e mais {restantes} na página do conjunto")

    linhas.append("")
    linhas.append(f"Página no portal: {item.url_portal}")
    return "\n".join(linhas)


def montar_ausencia() -> str:
    """Quando nada foi encontrado. Nenhum conjunto é mencionado.

    Devolver algo do assunto aproximado seria pior: o usuário perderia tempo
    abrindo um conjunto que não responde à pergunta dele, e passaria a
    desconfiar de todas as respostas seguintes.
    """
    linhas = [
        "Não encontrei nenhum conjunto de dados que responda a essa pergunta.",
        "",
        "Isso pode significar que o dado não está publicado no Portal Brasileiro "
        "de Dados Abertos, ou que ele está lá com outro nome.",
        "",
        "O que costuma ajudar:",
    ]
    linhas.extend(f"- {sugestao}" for sugestao in SUGESTOES)
    return "\n".join(linhas)


def montar_reduzido(itens: list[Recuperado]) -> str:
    """Sem o modelo disponível, lista o que a busca achou, sem redigir.

    Pior que a resposta redigida e muito melhor que erro: os conjuntos e os
    links continuam corretos, porque saem direto da ficha.
    """
    linhas = [
        "Não consegui redigir uma resposta agora, mas encontrei estes conjuntos "
        "que podem servir:",
        "",
    ]
    for item in itens:
        linhas.append(f"- **{item.titulo or item.nome}** — {item.url_portal}")
    return "\n".join(linhas)
