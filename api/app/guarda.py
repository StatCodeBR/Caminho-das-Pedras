"""Verificação mecânica da ancoragem.

Instruir o modelo a não inventar é necessário e insuficiente. A garantia vem de
conferir a saída: toda URL do texto gerado precisa estar entre as URLs enviadas
no contexto, e todo conjunto mencionado precisa ter sido recuperado.

URL fora da lista significa fabricação, e a resposta inteira é descartada — não
corrigida. Corrigir exigiria adivinhar a intenção, e uma resposta remendada
esconde que o modelo alucinou. É preferível falhar visivelmente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .recuperacao import Recuperado

# Casa http/https até o primeiro espaço ou delimitador de markdown. A pontuação
# final é aparada depois: "veja em https://x/y." não deve virar uma URL com ponto.
URL = re.compile(r"https?://[^\s<>\)\]\"']+", re.IGNORECASE)

PONTUACAO_FINAL = ".,;:!?"


def extrair_urls(texto: str) -> list[str]:
    achadas: dict[str, None] = {}
    for bruta in URL.findall(texto or ""):
        achadas.setdefault(bruta.rstrip(PONTUACAO_FINAL), None)
    return list(achadas)


def _normalizar(url: str) -> str:
    """Compara sem diferenças que não mudam o destino."""
    return url.strip().rstrip("/").lower()


def urls_permitidas(fichas: list[Recuperado]) -> set[str]:
    """Tudo que o modelo viu: a página de cada conjunto e o link de cada recurso."""
    permitidas: set[str] = set()
    for ficha in fichas:
        permitidas.add(_normalizar(ficha.url_portal))
        for recurso in ficha.recursos:
            if recurso.link:
                permitidas.add(_normalizar(recurso.link))
    return permitidas


@dataclass
class Veredito:
    aprovada: bool
    urls_fabricadas: list[str] = field(default_factory=list)
    conjuntos_inventados: list[str] = field(default_factory=list)

    @property
    def motivo(self) -> str:
        partes = []
        if self.urls_fabricadas:
            partes.append(f"URLs fora do contexto: {', '.join(self.urls_fabricadas)}")
        if self.conjuntos_inventados:
            partes.append(
                f"conjuntos não recuperados: {', '.join(self.conjuntos_inventados)}"
            )
        return "; ".join(partes)


# Um slug do portal citado no texto. Serve para pegar menção a conjunto que não
# foi recuperado mesmo quando o modelo não escreve a URL inteira.
SLUG_CITADO = re.compile(
    r"dados\.gov\.br/dados/conjuntos-dados/([A-Za-z0-9_\-]+)", re.IGNORECASE
)


def verificar(texto: str, fichas: list[Recuperado]) -> Veredito:
    permitidas = urls_permitidas(fichas)
    fabricadas = [
        url for url in extrair_urls(texto) if _normalizar(url) not in permitidas
    ]

    recuperados = {ficha.nome.lower() for ficha in fichas}
    inventados = [
        slug
        for slug in dict.fromkeys(SLUG_CITADO.findall(texto or ""))
        if slug.lower() not in recuperados
    ]

    return Veredito(
        aprovada=not fabricadas and not inventados,
        urls_fabricadas=fabricadas,
        conjuntos_inventados=inventados,
    )
