"""Coleta bruta do catálogo do Portal Brasileiro de Dados Abertos.

Primeira camada do pipeline: conversa com a API do dados.gov.br e grava JSONL
sem transformar nada. Todas as etapas seguintes leem do arquivo, nunca da rede.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import httpx
import typer
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

RAIZ = Path(__file__).resolve().parent
DIRETORIO_BRUTO = RAIZ / "bruto"
ARQUIVO_SEMENTES = RAIZ / "sementes.txt"

URL_BASE_PADRAO = "https://dados.gov.br/dados/api/publico"
CAMINHO_CONJUNTOS = "/conjuntos-dados"
CABECALHO_CHAVE = "chave-api-dados-abertos"

MAX_TENTATIVAS = 5
CONCORRENCIA = 10
# A API devolve página vazia com status 200 em cerca de um terço dos pedidos.
# Vazio é ruído até prova em contrário, e a prova é a repetição.
REPETICOES_VAZIO = 6
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

AJUDA_CREDENCIAL = (
    "Defina DADOS_GOV_API_KEY antes de rodar a coleta.\n"
    "A chave é gratuita: entre em https://dados.gov.br com uma conta gov.br,\n"
    "abra 'Minha conta' e gere a chave de API. Guarde-a no .env do projeto,\n"
    "que não é versionado."
)


# --- segredos e log ------------------------------------------------------

_SEGREDOS: list[str] = []


def registrar_segredo(valor: str | None) -> None:
    """Marca um valor para ser mascarado em qualquer mensagem de log."""
    if valor:
        _SEGREDOS.append(valor)


def log(mensagem: object) -> None:
    """Escreve no stderr com todo segredo conhecido mascarado."""
    texto = str(mensagem)
    for segredo in _SEGREDOS:
        texto = texto.replace(segredo, "***")
    print(texto, file=sys.stderr, flush=True)


# --- ambiente ------------------------------------------------------------


def carregar_env() -> None:
    """Lê `.env` do pipeline e da raiz, sem sobrepor o ambiente já definido."""
    for arquivo in (RAIZ / ".env", RAIZ.parent / ".env"):
        if not arquivo.is_file():
            continue
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            nome, _, valor = linha.partition("=")
            os.environ.setdefault(nome.strip(), valor.strip().strip("\"'"))


class CredencialAusente(RuntimeError):
    """A chave da API não foi fornecida pelo ambiente."""


def obter_chave() -> str:
    chave = os.environ.get("DADOS_GOV_API_KEY", "").strip()
    if not chave:
        raise CredencialAusente(AJUDA_CREDENCIAL)
    registrar_segredo(chave)
    return chave


# --- cliente da API ------------------------------------------------------


class ErroRepetivel(Exception):
    """Falha transitória: vale repetir com recuo."""


class ErroPermanente(Exception):
    """Falha que não melhora com repetição."""


def _recuo_base() -> float:
    """Multiplicador do recuo. Reduzido nos testes para não dormir de verdade."""
    return float(os.environ.get("COLETA_RECUO_BASE", "1"))


class ClientePortal:
    """Cliente assíncrono do portal, com recuo exponencial e concorrência presa."""

    def __init__(self, cliente: httpx.AsyncClient, concorrencia: int = CONCORRENCIA):
        self._cliente = cliente
        self._semaforo = asyncio.Semaphore(concorrencia)
        self.recuos = 0
        self.vazios_repetidos = 0

    async def _executar(self, caminho: str, params: dict[str, Any] | None) -> Any:
        async with self._semaforo:
            try:
                resposta = await self._cliente.get(caminho, params=params)
            except httpx.TransportError as erro:
                raise ErroRepetivel(f"falha de transporte: {type(erro).__name__}") from None

        if resposta.status_code == 429 or resposta.status_code >= 500:
            self.recuos += 1
            raise ErroRepetivel(f"HTTP {resposta.status_code} em {caminho}")
        if resposta.status_code >= 400:
            raise ErroPermanente(f"HTTP {resposta.status_code} em {caminho}")

        try:
            return resposta.json()
        except ValueError:
            raise ErroPermanente(f"resposta não é JSON em {caminho}") from None

    async def pedir(self, caminho: str, params: dict[str, Any] | None = None) -> Any:
        base = _recuo_base()
        resultado: Any = None
        async for tentativa in AsyncRetrying(
            retry=retry_if_exception_type(ErroRepetivel),
            wait=wait_exponential(multiplier=base, min=base, max=base * 30),
            stop=stop_after_attempt(MAX_TENTATIVAS),
            reraise=True,
        ):
            with tentativa:
                resultado = await self._executar(caminho, params)
        return resultado

    async def listar(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return extrair_lista(await self.pedir(CAMINHO_CONJUNTOS, params))

    async def listar_confirmando(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Repete a página vazia antes de acreditar nela. Ver REPETICOES_VAZIO."""
        for tentativa in range(REPETICOES_VAZIO + 1):
            itens = await self.listar(params)
            if itens:
                return itens
            if tentativa < REPETICOES_VAZIO:
                self.vazios_repetidos += 1
                await asyncio.sleep(_recuo_base() * (tentativa + 1))
        return []

    async def detalhar(self, identificador: str) -> dict[str, Any]:
        payload = await self.pedir(f"{CAMINHO_CONJUNTOS}/{identificador}")
        if isinstance(payload, list):
            return payload[0] if payload else {}
        return payload if isinstance(payload, dict) else {}


def extrair_lista(payload: Any) -> list[dict[str, Any]]:
    """Aceita tanto lista pura quanto envelope, porque o portal varia."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for chave in ("dados", "data", "result", "resultado", "conjuntos", "items"):
            valor = payload.get(chave)
            if isinstance(valor, list):
                return [item for item in valor if isinstance(item, dict)]
    return []


def extrair_id(conjunto: dict[str, Any]) -> str | None:
    for chave in ("id", "_id", "identificador", "idConjuntoDados", "name"):
        valor = conjunto.get(chave)
        if isinstance(valor, (str, int)) and str(valor).strip():
            return str(valor).strip()
    return None


# --- progresso -----------------------------------------------------------


@dataclass
class Progresso:
    """Estado de retomada, separado por modo para a amostra não sujar a base."""

    caminho: Path
    estado: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def carregar(cls, caminho: Path) -> "Progresso":
        if caminho.is_file():
            try:
                bruto = json.loads(caminho.read_text(encoding="utf-8"))
                if isinstance(bruto, dict):
                    return cls(caminho, {k: v for k, v in bruto.items() if isinstance(v, dict)})
            except ValueError:
                log(f"progresso.json ilegível, recomeçando do zero: {caminho}")
        return cls(caminho)

    def _do_modo(self, modo: str) -> dict[str, Any]:
        return self.estado.setdefault(modo, {"ultima_pagina": 0, "concluida": False})

    def ultima_pagina(self, modo: str) -> int:
        return int(self._do_modo(modo).get("ultima_pagina", 0))

    def concluida(self, modo: str) -> bool:
        return bool(self._do_modo(modo).get("concluida", False))

    def confirmar(self, modo: str, pagina: int, *, concluida: bool = False) -> None:
        atual = self._do_modo(modo)
        atual["ultima_pagina"] = pagina
        atual["concluida"] = concluida
        atual["atualizado_em"] = agora_utc()
        self.gravar()

    def gravar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(self.estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- arquivos ------------------------------------------------------------


def ids_ja_gravados(destino: Path) -> set[str]:
    if not destino.is_file():
        return set()
    vistos: set[str] = set()
    with destino.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            try:
                registro = json.loads(linha)
            except ValueError:
                continue
            identificador = extrair_id(registro) if isinstance(registro, dict) else None
            if identificador:
                vistos.add(identificador)
    return vistos


def ler_sementes(caminho: Path) -> list[str]:
    if not caminho.is_file():
        return []
    sementes: list[str] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            sementes.append(linha)
    return sementes


# --- coleta --------------------------------------------------------------


@dataclass
class Resultado:
    gravados: int = 0
    falhas: int = 0
    paginas: int = 0
    recuos: int = 0
    vazios_repetidos: int = 0
    sementes_nao_resolvidas: int = 0
    ja_concluida: bool = False


async def coletar(
    *,
    chave: str,
    destino: Path,
    caminho_progresso: Path,
    caminho_falhas: Path,
    limite: Optional[int] = None,
    sementes: Sequence[str] = (),
    url_base: str | None = None,
) -> Resultado:
    """Percorre o catálogo e grava JSONL bruto. Nunca aborta por falha de item."""
    modo = "amostra" if limite else "completa"
    progresso = Progresso.carregar(caminho_progresso)
    resultado = Resultado()

    if progresso.concluida(modo) and destino.is_file():
        resultado.ja_concluida = True
        return resultado

    destino.parent.mkdir(parents=True, exist_ok=True)
    vistos = ids_ja_gravados(destino)
    resultado.gravados = len(vistos)

    url_base = url_base or os.environ.get("DADOS_GOV_API_URL", URL_BASE_PADRAO)
    cabecalhos = {CABECALHO_CHAVE: chave, "accept": "application/json"}

    async with httpx.AsyncClient(
        base_url=url_base, headers=cabecalhos, timeout=TIMEOUT, follow_redirects=True
    ) as http:
        portal = ClientePortal(http)
        with destino.open("a", encoding="utf-8") as saida:

            def gravar(registro: dict[str, Any]) -> None:
                saida.write(json.dumps(registro, ensure_ascii=False) + "\n")
                saida.flush()

            def anotar_falha(identificador: str, motivo: str) -> None:
                caminho_falhas.parent.mkdir(parents=True, exist_ok=True)
                with caminho_falhas.open("a", encoding="utf-8") as arquivo:
                    arquivo.write(
                        json.dumps(
                            {
                                "identificador": identificador,
                                "motivo": motivo,
                                "quando": agora_utc(),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                resultado.falhas += 1

            async def montar(
                conjunto: dict[str, Any], pagina_origem: object
            ) -> dict[str, Any] | None:
                identificador = extrair_id(conjunto)
                if not identificador:
                    anotar_falha("<sem identificador>", "registro sem campo de id")
                    return None
                detalhe: dict[str, Any] | None = None
                try:
                    detalhe = await portal.detalhar(identificador)
                except (ErroRepetivel, ErroPermanente) as erro:
                    anotar_falha(identificador, str(erro))
                return {
                    **conjunto,
                    "detalhe": detalhe,
                    "coletado_em": agora_utc(),
                    "pagina_origem": pagina_origem,
                }

            async def absorver(conjuntos: list[dict[str, Any]], origem: object) -> int:
                """Detalha e grava o que ainda não foi visto, respeitando o limite."""
                pendentes = []
                for conjunto in conjuntos:
                    identificador = extrair_id(conjunto)
                    if identificador and identificador in vistos:
                        continue
                    if limite is not None and len(pendentes) + resultado.gravados >= limite:
                        break
                    if identificador:
                        vistos.add(identificador)
                    pendentes.append(conjunto)

                registros = await asyncio.gather(
                    *(montar(conjunto, origem) for conjunto in pendentes)
                )
                gravados = 0
                for registro in registros:
                    if registro is None:
                        continue
                    gravar(registro)
                    gravados += 1
                resultado.gravados += gravados
                return gravados

            # Sementes primeiro: cada linha é um identificador do portal, e o
            # endpoint de detalhe aceita tanto o UUID quanto o slug da URL.
            # A busca por título não serve aqui: o slug `arboviroses-dengue`
            # pertence a um conjunto chamado "Sinan/Dengue".
            async def semear(identificador: str) -> dict[str, Any] | None:
                try:
                    detalhe = await portal.detalhar(identificador)
                except (ErroRepetivel, ErroPermanente) as erro:
                    anotar_falha(identificador, str(erro))
                    return None
                if not detalhe:
                    anotar_falha(identificador, "semente resolveu para conteúdo vazio")
                    return None
                return {
                    **detalhe,
                    "detalhe": detalhe,
                    "coletado_em": agora_utc(),
                    "pagina_origem": f"semente:{identificador}",
                }

            identificadores = [linha.strip() for linha in sementes if linha.strip()]
            if identificadores and limite is not None:
                achados = await asyncio.gather(
                    *(semear(identificador) for identificador in identificadores)
                )
                for registro in achados:
                    if registro is None:
                        resultado.sementes_nao_resolvidas += 1
                        continue
                    if resultado.gravados >= limite:
                        break
                    identificador = extrair_id(registro)
                    if identificador:
                        if identificador in vistos:
                            continue
                        vistos.add(identificador)
                    gravar(registro)
                    resultado.gravados += 1
                log(
                    f"sementes: {resultado.gravados} de {len(identificadores)} "
                    f"identificadores ({resultado.sementes_nao_resolvidas} não resolvidos)"
                )

            pagina = progresso.ultima_pagina(modo) + 1
            tamanho_pagina = 0

            while limite is None or resultado.gravados < limite:
                try:
                    conjuntos = await portal.listar_confirmando({"pagina": pagina})
                except (ErroRepetivel, ErroPermanente) as erro:
                    anotar_falha(f"<pagina {pagina}>", str(erro))
                    log(f"página {pagina} falhou, encerrando: {erro}")
                    break

                if not conjuntos:
                    # Vazio confirmado. Só é fim se a página seguinte concordar.
                    seguinte = await portal.listar_confirmando({"pagina": pagina + 1})
                    if not seguinte:
                        progresso.confirmar(modo, pagina - 1, concluida=True)
                        log(f"fim da listagem confirmado na página {pagina}")
                        break
                    log(f"página {pagina} vazia, mas a listagem continua; seguindo")
                    progresso.confirmar(modo, pagina)
                    pagina += 1
                    conjuntos = seguinte

                tamanho_pagina = max(tamanho_pagina, len(conjuntos))
                gravados = await absorver(conjuntos, pagina)

                resultado.paginas += 1
                progresso.confirmar(modo, pagina)
                log(f"página {pagina}: {gravados} conjuntos, total {resultado.gravados}")

                if len(conjuntos) < tamanho_pagina:
                    progresso.confirmar(modo, pagina, concluida=True)
                    log(f"página {pagina} veio incompleta: fim da listagem")
                    break

                pagina += 1

            if limite is not None and resultado.gravados >= limite:
                progresso.confirmar(modo, pagina - 1, concluida=True)

        resultado.recuos = portal.recuos
        resultado.vazios_repetidos = portal.vazios_repetidos

    return resultado


# --- interface de linha de comando --------------------------------------

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    limite: Optional[int] = typer.Option(
        None, "--limite", min=1, help="Coleta no máximo N conjuntos, em arquivo separado."
    ),
    recomecar: bool = typer.Option(
        False, "--recomecar", help="Ignora o progresso e recomeça da primeira página."
    ),
) -> None:
    """Coleta o catálogo do dados.gov.br e grava JSONL bruto."""
    carregar_env()

    try:
        chave = obter_chave()
    except CredencialAusente as erro:
        log(str(erro))
        raise typer.Exit(code=2)

    destino = DIRETORIO_BRUTO / ("conjuntos-dev.jsonl" if limite else "conjuntos.jsonl")
    caminho_progresso = DIRETORIO_BRUTO / "progresso.json"
    caminho_falhas = DIRETORIO_BRUTO / "falhas.jsonl"

    if recomecar and caminho_progresso.is_file():
        progresso = Progresso.carregar(caminho_progresso)
        progresso.estado.pop("amostra" if limite else "completa", None)
        progresso.gravar()

    sementes = ler_sementes(ARQUIVO_SEMENTES) if limite else []
    if sementes:
        log(f"{len(sementes)} identificadores lidos de {ARQUIVO_SEMENTES.name}")

    resultado = asyncio.run(
        coletar(
            chave=chave,
            destino=destino,
            caminho_progresso=caminho_progresso,
            caminho_falhas=caminho_falhas,
            limite=limite,
            sementes=sementes,
        )
    )

    if resultado.ja_concluida:
        log(f"coleta já concluída; {destino} permanece inalterado")
        return

    log(
        f"total de conjuntos em {destino.name}: {resultado.gravados} "
        f"({resultado.paginas} páginas, {resultado.falhas} falhas, "
        f"{resultado.recuos} recuos, {resultado.vazios_repetidos} vazios repetidos)"
    )


if __name__ == "__main__":
    app()
