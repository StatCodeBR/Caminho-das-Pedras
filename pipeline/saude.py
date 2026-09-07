"""Verifica se os links dos recursos do catálogo ainda respondem.

Terceira camada do pipeline. Parte relevante do que o portal cataloga aponta
para arquivo que não existe mais; mandar o usuário para um link morto queima a
confiança na primeira interação, que é justamente o que o produto promete.

Isto bate em centenas de domínios de órgãos públicos, muitos deles lentos. A
contenção por host não é otimização: é a diferença entre verificar e parecer
uma varredura hostil.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import typer

RAIZ = Path(__file__).resolve().parent
DIRETORIO_DADOS = RAIZ / "dados"

TIMEOUT_SEGUNDOS = 10.0
MAX_REDIRECIONAMENTOS = 5
CONCORRENCIA_TOTAL = 20
CONCORRENCIA_POR_HOST = 2
BYTES_DO_RANGE = 64

PROJETO = "Caminho-das-Pedras"
VERSAO = "0.1"
CONTATO_NAO_INFORMADO = "contato-nao-configurado"

CLASSES = ("disponivel", "indisponivel", "instavel", "nao_verificado")

# Status que significam "não faço HEAD", não "arquivo não existe". O 403 está
# aqui por evidência: www.gov.br, o maior host do catálogo, devolve 403 a HEAD
# e 206 ao mesmo endereço via GET, com qualquer User-Agent.
RECUSA_DE_METODO = (403, 405, 501)


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def carregar_env() -> None:
    """Lê os `.env`, com o ambiente real tendo precedência sobre o arquivo.

    Dentro de um arquivo, a última ocorrência de uma chave vence — que é o que
    todo mundo espera de um `.env` e o que `setdefault` linha a linha fazia ao
    contrário, deixando um valor vazio esquecido no topo mascarar o preenchido.
    """
    for arquivo in (RAIZ / ".env", RAIZ.parent / ".env"):
        if not arquivo.is_file():
            continue
        do_arquivo: dict[str, str] = {}
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            nome, _, valor = linha.partition("=")
            do_arquivo[nome.strip()] = valor.strip().strip("\"'")
        for nome, valor in do_arquivo.items():
            os.environ.setdefault(nome, valor)


def user_agent() -> str:
    """Quem está batendo na porta e para quem reclamar.

    O contato sai de `SAUDE_CONTATO` em vez de ficar fixo no código: ele vai
    para centenas de servidores de órgãos públicos, e endereço pessoal não
    entra em arquivo versionado sem o dono decidir.
    """
    contato = os.environ.get("SAUDE_CONTATO", "").strip() or CONTATO_NAO_INFORMADO
    return f"{PROJETO}/{VERSAO} (verificador de links de dados abertos; {contato})"


# --- esquema -------------------------------------------------------------

COLUNAS_SAUDE = {
    "status_http": "INTEGER",
    "classe_saude": "TEXT",
    "checado_em": "TEXT",
    "latencia_ms": "INTEGER",
    # Por que a classe não veio de um status: link ausente, link malformado,
    # tempo esgotado. É o que separa "o portal publicou lixo" de "o servidor
    # caiu" no diagnóstico de qualidade do catálogo.
    "motivo_saude": "TEXT",
}


def migrar(conexao: sqlite3.Connection) -> None:
    """Acrescenta as colunas de saúde se ainda não existirem."""
    existentes = {linha[1] for linha in conexao.execute("PRAGMA table_info(recurso)")}
    for coluna, tipo in COLUNAS_SAUDE.items():
        if coluna not in existentes:
            conexao.execute(f"ALTER TABLE recurso ADD COLUMN {coluna} {tipo}")
    conexao.execute(
        "CREATE INDEX IF NOT EXISTS idx_recurso_classe_saude ON recurso(classe_saude)"
    )
    conexao.commit()


def abrir_banco(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    migrar(conexao)
    return conexao


# --- classificação -------------------------------------------------------


@dataclass
class Resultado:
    status_http: Optional[int]
    classe: str
    latencia_ms: Optional[int]
    motivo: str = ""


def classificar(status: int) -> str:
    """Distingue o que sumiu do que está de mau humor.

    404 e 410 são remoção declarada. 5xx e 429 são o servidor mal, não o
    arquivo ausente — tratar como removido esconderia um dado que existe.
    Demais 4xx significam que o usuário não consegue baixar, que é o que
    importa para quem vai clicar no link.
    """
    if 200 <= status < 300:
        return "disponivel"
    if status in (404, 410):
        return "indisponivel"
    if status == 429 or status >= 500:
        return "instavel"
    if 400 <= status < 500:
        return "indisponivel"
    return "instavel"


# --- verificação ---------------------------------------------------------


def url_utilizavel(url: str) -> bool:
    """O campo `link` do portal nem sempre contém uma URL."""
    try:
        partes = urlparse(url)
    except ValueError:
        return False
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return False
    # Host com espaço ou barra invertida é frase ou caminho de Windows.
    return not any(ch in partes.netloc for ch in " \\\t")


class Verificador:
    """Um cliente HTTP com contenção total e por host."""

    def __init__(self, cliente: httpx.AsyncClient, por_host: int = CONCORRENCIA_POR_HOST):
        self._cliente = cliente
        self._por_host = por_host
        self._semaforos: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(por_host)
        )
        self.requisicoes = 0

    def _semaforo_do_host(self, url: str) -> asyncio.Semaphore:
        return self._semaforos[urlparse(url).netloc.lower()]

    async def verificar(self, url: str | None) -> Resultado:
        if not url or not url.strip():
            # Sem URL não há o que checar, e não se gasta requisição para saber.
            return Resultado(None, "nao_verificado", None, "recurso sem URL")

        url = url.strip()
        if not url_utilizavel(url):
            # O portal guarda frases no campo de link: "http://Dissertação, tese,
            # TCC...", caminhos com barra invertida, o prefixo "URL: " esquecido.
            # Não dá para checar, e consertar por palpite seria inventar dado.
            return Resultado(None, "nao_verificado", None, "link não é uma URL")
        async with self._semaforo_do_host(url):
            inicio = asyncio.get_running_loop().time()
            try:
                resposta = await self._pedir("HEAD", url)
                # O servidor recusou o método. 405 e 501 são a forma padrão de
                # dizer isso; o www.gov.br diz 403, e responde 206 ao mesmo
                # endereço via GET. Um Range de poucos bytes responde a mesma
                # pergunta sem baixar o arquivo.
                if resposta.status_code in RECUSA_DE_METODO:
                    resposta = await self._pedir(
                        "GET", url, headers={"Range": f"bytes=0-{BYTES_DO_RANGE - 1}"}
                    )
            except httpx.TimeoutException:
                decorrido = asyncio.get_running_loop().time() - inicio
                return Resultado(None, "instavel", int(decorrido * 1000), "tempo esgotado")
            except httpx.InvalidURL as erro:
                # Não herda de HTTPError; sem este ramo, uma URL torta derruba
                # a execução inteira em vez de marcar um recurso.
                return Resultado(None, "nao_verificado", None, str(erro))
            except httpx.HTTPError as erro:
                decorrido = asyncio.get_running_loop().time() - inicio
                return Resultado(
                    None, "instavel", int(decorrido * 1000), type(erro).__name__
                )

            decorrido = asyncio.get_running_loop().time() - inicio

        return Resultado(
            resposta.status_code,
            classificar(resposta.status_code),
            int(decorrido * 1000),
        )

    async def _pedir(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        """Lê só os cabeçalhos.

        `request()` baixaria o corpo inteiro quando o servidor ignora o Range —
        e muitos ignoram. A spec proíbe baixar o arquivo, e baixar também é o
        que transforma uma verificação educada em carga sobre o órgão.
        """
        self.requisicoes += 1
        requisicao = self._cliente.build_request(metodo, url, **kwargs)
        resposta = await self._cliente.send(requisicao, stream=True)
        await resposta.aclose()
        return resposta


# --- seleção -------------------------------------------------------------


def selecionar(
    conexao: sqlite3.Connection,
    *,
    limite: int | None,
    idade_maxima: int | None,
    somente_falhas: bool,
) -> tuple[list[sqlite3.Row], int]:
    """Devolve o que checar e quantos foram pulados por ainda estarem frescos."""
    total = conexao.execute("SELECT COUNT(*) FROM recurso").fetchone()[0]

    condicoes: list[str] = []
    params: list[Any] = []

    if somente_falhas:
        condicoes.append("classe_saude IN ('indisponivel', 'instavel')")

    if idade_maxima is not None:
        corte = (datetime.now(timezone.utc) - timedelta(days=idade_maxima)).isoformat()
        condicoes.append("(checado_em IS NULL OR checado_em < ?)")
        params.append(corte)

    sql = "SELECT id, link, classe_saude FROM recurso"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    sql += " ORDER BY id"
    if limite:
        sql += f" LIMIT {int(limite)}"

    escolhidos = list(conexao.execute(sql, params))
    considerados = total if limite is None else min(total, int(limite))
    return escolhidos, max(0, considerados - len(escolhidos))


def gravar(conexao: sqlite3.Connection, recurso_id: str, resultado: Resultado) -> None:
    conexao.execute(
        "UPDATE recurso SET status_http = ?, classe_saude = ?, checado_em = ?,"
        " latencia_ms = ?, motivo_saude = ? WHERE id = ?",
        (
            resultado.status_http,
            resultado.classe,
            agora_utc(),
            resultado.latencia_ms,
            resultado.motivo or None,
            recurso_id,
        ),
    )


# --- relatório -----------------------------------------------------------


@dataclass
class Relatorio:
    verificados: int = 0
    pulados: int = 0
    requisicoes: int = 0
    classes: dict[str, int] = field(default_factory=dict)
    latencias: list[int] = field(default_factory=list)

    def contar(self, resultado: Resultado) -> None:
        self.verificados += 1
        self.classes[resultado.classe] = self.classes.get(resultado.classe, 0) + 1
        if resultado.latencia_ms is not None:
            self.latencias.append(resultado.latencia_ms)


GLOSSARIO = {
    "disponivel": "respondeu 2xx nesta verificação",
    "indisponivel": "respondeu 404, 410 ou outro 4xx nesta verificação",
    "instavel": "não respondeu de forma confiável: tempo esgotado, 5xx ou 429",
    "nao_verificado": "sem URL ou com link que não é um endereço",
}


def imprimir_relatorio(relatorio: Relatorio, banco: Path) -> None:
    log("")
    log("diagnóstico de saúde do catálogo")
    # A data e a definição andam junto do número: `instavel` é o estado de um
    # instante, não um veredito sobre o publicador. Servidor com 503 hoje pode
    # estar bem amanhã, e apresentar o número sem isso seria desonesto.
    log(f"  verificado em:        {agora_utc()}")
    log(f"  recursos verificados: {relatorio.verificados}")
    if relatorio.pulados:
        log(f"  pulados (ainda frescos): {relatorio.pulados}")
    log(f"  requisições HTTP:     {relatorio.requisicoes}")
    for classe in CLASSES:
        quantidade = relatorio.classes.get(classe, 0)
        percentual = quantidade / relatorio.verificados if relatorio.verificados else 0.0
        log(f"    {classe:15s} {quantidade:5d}  ({percentual:.0%})  {GLOSSARIO[classe]}")
    if relatorio.latencias:
        ordenadas = sorted(relatorio.latencias)
        mediana = ordenadas[len(ordenadas) // 2]
        p95 = ordenadas[min(len(ordenadas) - 1, int(len(ordenadas) * 0.95))]
        log(f"  latência mediana:     {mediana} ms")
        log(f"  latência p95:         {p95} ms")
    log(f"  banco:                {banco}")


# --- orquestração --------------------------------------------------------


async def verificar_tudo(
    *,
    banco: Path,
    limite: int | None = None,
    idade_maxima: int | None = None,
    somente_falhas: bool = False,
    cliente: httpx.AsyncClient | None = None,
) -> Relatorio:
    conexao = abrir_banco(banco)
    relatorio = Relatorio()

    try:
        recursos, pulados = selecionar(
            conexao,
            limite=limite,
            idade_maxima=idade_maxima,
            somente_falhas=somente_falhas,
        )
        relatorio.pulados = pulados
        if pulados:
            log(f"{pulados} recursos pulados por checagem recente")
        if not recursos:
            log("nada a verificar")
            return relatorio

        proprio = cliente is None
        if cliente is None:
            cliente = httpx.AsyncClient(
                timeout=TIMEOUT_SEGUNDOS,
                follow_redirects=True,
                max_redirects=MAX_REDIRECIONAMENTOS,
                headers={"User-Agent": user_agent()},
                limits=httpx.Limits(max_connections=CONCORRENCIA_TOTAL),
            )

        verificador = Verificador(cliente)
        vaga = asyncio.Semaphore(CONCORRENCIA_TOTAL)

        async def tarefa(recurso: sqlite3.Row) -> tuple[str, Resultado]:
            async with vaga:
                return recurso["id"], await verificador.verificar(recurso["link"])

        try:
            concluidas = 0
            for inicio in range(0, len(recursos), 200):
                lote = recursos[inicio : inicio + 200]
                for recurso_id, resultado in await asyncio.gather(
                    *(tarefa(r) for r in lote)
                ):
                    gravar(conexao, recurso_id, resultado)
                    relatorio.contar(resultado)
                conexao.commit()
                concluidas += len(lote)
                log(f"  {concluidas}/{len(recursos)} verificados")
        finally:
            if proprio:
                await cliente.aclose()

        relatorio.requisicoes = verificador.requisicoes
        conexao.commit()
    finally:
        conexao.close()

    return relatorio


# --- interface de linha de comando --------------------------------------

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    limite: Optional[int] = typer.Option(
        None, "--limite", min=1, help="Verifica apenas os N primeiros recursos."
    ),
    idade_maxima: Optional[int] = typer.Option(
        None,
        "--idade-maxima",
        min=0,
        help="Verifica apenas o que foi checado há mais de N dias.",
    ),
    somente_falhas: bool = typer.Option(
        False, "--somente-falhas", help="Reprocessa apenas indisponíveis e instáveis."
    ),
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
) -> None:
    """Verifica os links dos recursos e grava o diagnóstico no banco."""
    carregar_env()

    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        log("rode a normalização antes: uv run python normaliza.py")
        raise typer.Exit(code=2)

    if CONTATO_NAO_INFORMADO in user_agent():
        log(
            "aviso: SAUDE_CONTATO não definido. O User-Agent vai sem endereço de "
            "contato, e órgãos públicos têm razão em bloquear quem não se identifica."
        )

    log(f"User-Agent: {user_agent()}")
    relatorio = asyncio.run(
        verificar_tudo(
            banco=banco,
            limite=limite,
            idade_maxima=idade_maxima,
            somente_falhas=somente_falhas,
        )
    )
    imprimir_relatorio(relatorio, banco)


if __name__ == "__main__":
    app()
