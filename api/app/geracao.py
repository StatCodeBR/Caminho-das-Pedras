"""Redação pelo modelo, em streaming, e o stub que a dispensa.

O contexto contém apenas as fichas recuperadas: o modelo não tem de onde tirar
um conjunto que a busca não trouxe. É a metade estrutural da ancoragem; a outra
metade é a guarda de saída.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator, Iterable

from .recuperacao import Recuperado

RAIZ = Path(__file__).resolve().parent
ARQUIVO_PROMPT = RAIZ / "prompts" / "resposta.md"

MAX_TOKENS = 1200
MAX_RECURSOS_NO_CONTEXTO = 8

# Intervalo entre fragmentos do stub. Existe para que a interface seja
# desenvolvida contra um fluxo parecido com o real, não com um despejo único.
INTERVALO_STUB = 0.03


class ModeloIndisponivel(RuntimeError):
    """Falta credencial ou o provedor recusou."""


def carregar_prompt() -> str:
    return ARQUIVO_PROMPT.read_text(encoding="utf-8")


def _descrever_recursos(item: Recuperado) -> list[str]:
    linhas: list[str] = []
    for recurso in item.recursos[:MAX_RECURSOS_NO_CONTEXTO]:
        marca = "" if recurso.disponivel else "  [INDISPONÍVEL na última verificação]"
        formato = f" ({recurso.formato.upper()})" if recurso.formato else ""
        link = f" — {recurso.link}" if recurso.link else ""
        linhas.append(f"    - {recurso.titulo or '(sem título)'}{formato}{link}{marca}")
    return linhas


def montar_contexto(fichas: Iterable[Recuperado]) -> str:
    """As fichas, e nada além delas."""
    blocos: list[str] = []
    for item in fichas:
        linhas = [
            f"### {item.titulo or item.nome}",
            f"identificador: {item.nome}",
            f"órgão: {(item.organizacao or '').replace('-', ' ')}",
            f"confiança da ficha: {item.confianca}",
            f"página no portal: {item.url_portal}",
            f"resumo: {item.resumo}",
        ]
        if item.confianca == "baixa":
            linhas.append(
                "ATENÇÃO: metadados pobres. Não afirme conteúdo além do resumo."
            )
        if item.perguntas:
            linhas.append("perguntas que este conjunto ajuda a responder:")
            linhas.extend(f"    - {p}" for p in item.perguntas)
        if item.recursos:
            linhas.append(f"arquivos ({len(item.recursos)}):")
            linhas.extend(_descrever_recursos(item))
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def montar_entrada(pergunta: str, fichas: list[Recuperado]) -> str:
    return (
        f"Pergunta da pessoa:\n{pergunta}\n\n"
        f"Fichas recuperadas ({len(fichas)}):\n\n{montar_contexto(fichas)}"
    )


# --- stub ----------------------------------------------------------------

RESPOSTA_STUB = (
    "**Resposta de demonstração.** O serviço está em modo stub, então este texto "
    "é pré-gravado e nenhuma chamada ao modelo foi feita.\n\n"
    "Em modo normal, aqui apareceria a explicação de qual conjunto responde à "
    "sua pergunta, quem o publica e em que formatos ele está disponível."
)


async def gerar_stub(
    pergunta: str, fichas: list[Recuperado], intervalo: float = INTERVALO_STUB
) -> AsyncIterator[str]:
    """Emite a resposta pré-gravada aos poucos, sem importar o cliente da API.

    O `import anthropic` não acontece neste caminho — é o que garante que o modo
    stub roda sem credencial e sem o pacote instalado.
    """
    texto = RESPOSTA_STUB
    if fichas:
        texto += f"\n\nA busca encontrou {len(fichas)} conjunto(s). O primeiro é "
        texto += f"**{fichas[0].titulo or fichas[0].nome}**, em {fichas[0].url_portal}"
    for pedaco in texto.split(" "):
        yield pedaco + " "
        if intervalo:
            await asyncio.sleep(intervalo)


# --- modelo --------------------------------------------------------------


async def gerar_com_modelo(
    pergunta: str, fichas: list[Recuperado], *, chave: str, modelo: str
) -> AsyncIterator[str]:
    """Repassa o streaming do SDK fragmento a fragmento, sem bufferizar."""
    if not chave:
        raise ModeloIndisponivel(
            "ANTHROPIC_API_KEY não definida; use MODO_STUB=1 para desenvolver "
            "a interface sem credencial."
        )
    import anthropic

    cliente = anthropic.AsyncAnthropic(api_key=chave)
    try:
        async with cliente.messages.stream(
            model=modelo,
            max_tokens=MAX_TOKENS,
            system=carregar_prompt(),
            messages=[{"role": "user", "content": montar_entrada(pergunta, fichas)}],
        ) as fluxo:
            async for pedaco in fluxo.text_stream:
                yield pedaco
    except ModeloIndisponivel:
        raise
    except Exception as erro:  # noqa: BLE001 - qualquer falha vira modo reduzido
        raise ModeloIndisponivel(str(erro)) from erro
