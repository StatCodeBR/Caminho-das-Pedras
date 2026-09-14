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
import socket
import sqlite3
import ssl
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

CLASSES = (
    "disponivel",
    "indisponivel",
    "bloqueado",
    "cadeia_incompleta",
    "dominio_inexistente",
    "instavel",
    "nao_verificado",
)

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
    """Classe **provisória**, decidida só pelo que aquele endereço respondeu.

    404 e 410 são remoção declarada. 5xx e 429 são o servidor mal, não o
    arquivo ausente — tratar como removido esconderia um dado que existe.
    Demais 4xx significam que o usuário não consegue baixar, que é o que
    importa para quem vai clicar no link.

    Provisória porque `indisponivel` afirma que o host respondeu e negou este
    endereço, e uma requisição isolada não sustenta essa afirmação: se o host
    recusou **todas**, o 403 é bloqueio e não ausência. Essa distinção precisa
    do agregado por host, e vem depois, em `reconhecer_bloqueios()`.
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


# --- causa da falha de conexão -------------------------------------------

# Códigos de verificação de certificado do OpenSSL que significam "não consegui
# montar a cadeia até uma raiz confiável": o servidor não enviou o intermediário
# que assinou a folha.
#
# São números, e não trechos da mensagem, de propósito. O texto do OpenSSL é
# string de biblioteca: muda entre versões e entre distribuições, e este projeto
# roda em NixOS no desenvolvimento e em Debian na imagem. Casar
# `"unable to get local issuer"` funcionaria hoje e quebraria em silêncio na
# próxima atualização — e a quebra apareceria como reclassificação em massa de
# milhares de recursos, não como erro.
VERIFY_CADEIA_INCOMPLETA = frozenset(
    {
        2,  # unable to get issuer certificate
        20,  # unable to get local issuer certificate
        21,  # unable to verify the first certificate
    }
)

LIMITE_DA_CADEIA = 8


def _na_cadeia(
    erro: BaseException, tipos: type | tuple[type, ...]
) -> BaseException | None:
    """Procura um tipo de exceção percorrendo as causas de `erro`.

    O httpx embrulha o erro real: o `ConnectError` que chega tem o erro de TLS
    ou de resolução lá no fundo, atrás do httpcore. Sem percorrer a cadeia, as
    cinco causas distintas viram um rótulo só.
    """
    visto: set[int] = set()
    atual: BaseException | None = erro
    for _ in range(LIMITE_DA_CADEIA):
        if atual is None or id(atual) in visto:
            break
        visto.add(id(atual))
        if isinstance(atual, tipos):
            return atual
        atual = atual.__cause__ or atual.__context__
    return None


def _causa_mais_funda(erro: BaseException) -> BaseException:
    """A exceção do fundo da cadeia, que é a que diz o que realmente houve."""
    visto: set[int] = set()
    atual = erro
    for _ in range(LIMITE_DA_CADEIA):
        seguinte = atual.__cause__ or atual.__context__
        if seguinte is None or id(seguinte) in visto:
            break
        visto.add(id(seguinte))
        atual = seguinte
    return atual


def classificar_falha_de_conexao(erro: BaseException) -> tuple[str, str]:
    """Separa as causas que o httpx agrupa sob `ConnectError`.

    Cadeia incompleta não é link morto: o arquivo está lá, e o navegador o baixa
    porque busca o intermediário faltante sozinho. Chamar isso de instável
    descreveria o nosso cliente, não o link. Domínio que não resolve é o oposto:
    `instavel` sugere passageiro, e não há nada de passageiro em um domínio que
    deixou de existir.
    """
    if _na_cadeia(erro, socket.gaierror) is not None:
        return "dominio_inexistente", "domínio não resolve"

    certificado = _na_cadeia(erro, ssl.SSLCertVerificationError)
    if certificado is not None:
        codigo = getattr(certificado, "verify_code", None)
        if codigo in VERIFY_CADEIA_INCOMPLETA:
            return "cadeia_incompleta", f"cadeia de certificação incompleta ({codigo})"
        return "instavel", f"certificado inválido ({codigo})"

    if _na_cadeia(erro, ssl.SSLError) is not None:
        return "instavel", "erro de TLS"

    # Nomear a exceção de fora gravaria `ConnectError` de novo — o rótulo único
    # que esta mudança existe para desfazer. O fundo da cadeia é o que diz se
    # foi recusa de TCP, tempo de conexão ou protocolo.
    return "instavel", type(_causa_mais_funda(erro)).__name__


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
            except httpx.ConnectError as erro:
                # Precisa vir antes do HTTPError: ConnectError é subclasse dele,
                # e a ordem invertida faria o ramo genérico engolir as cinco
                # causas distintas de novo.
                decorrido = asyncio.get_running_loop().time() - inicio
                classe, motivo = classificar_falha_de_conexao(erro)
                return Resultado(None, classe, int(decorrido * 1000), motivo)
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
    classe: str | None = None,
) -> tuple[list[sqlite3.Row], int]:
    """Devolve o que checar e quantos foram pulados por ainda estarem frescos."""
    total = conexao.execute("SELECT COUNT(*) FROM recurso").fetchone()[0]

    condicoes: list[str] = []
    params: list[Any] = []

    if somente_falhas:
        # Falha por exclusão, e não por lista. Enumerar as classes deixaria toda
        # classe nova fora do reprocessamento sem que ninguém percebesse — foi
        # assim que `bloqueado`, `cadeia_incompleta` e `dominio_inexistente`
        # teriam nascido invisíveis para este caminho.
        condicoes.append("classe_saude IS NOT NULL AND classe_saude <> 'disponivel'")

    if classe is not None:
        condicoes.append("classe_saude = ?")
        params.append(classe)

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


# --- reconhecimento de host que bloqueia ---------------------------------

# Volume mínimo de recursos verificados para que um host possa ser acusado de
# bloquear. Varrido sobre o catálogo completo em 2026-09-12, com as outras duas
# condições fixas (zero sucessos, maioria de 403):
#
#   mínimo   hosts   recursos   além dos três grandes
#        1      11      5.511   doi.org, siorg.planejamento.gov.br, …
#        5       5      5.503   angovbr-my.sharepoint.com, mapa.cultura.gov.br
#       10       4      5.498   mapa.cultura.gov.br
#       20       3      5.487   (nenhum)
#       30       2      5.463   (nenhum)
#
# Não há joelho, e o motivo é instrutivo: o limiar quase não move o total —
# 0,4% entre o extremo e 20 — porque três hosts concentram tudo. O que ele move
# é quantos hosts são acusados, de 3 para 11.
#
# Vinte é pelos hosts de uma observação só. Com mínimo 1, o `doi.org` — o
# resolvedor global de DOI — entraria na lista por causa de um único 403.
# Declarar bloqueador a partir de uma amostra de um seria exatamente a
# afirmação sem sustentação que esta classe existe para evitar.
#
# O custo: `mapa.cultura.gov.br`, com 11 de 11 negativas, provavelmente bloqueia
# e segue contado como ausência confirmada. Onze recursos, contra o risco de
# acusar um host a partir de uma medição.
MINIMO_PARA_ACUSAR_BLOQUEIO = 20
FRACAO_403_PARA_BLOQUEIO = 0.5

MOTIVO_BLOQUEIO = "host recusou toda a verificação"


def _host(link: str | None) -> str:
    if not link:
        return ""
    try:
        return urlparse(link.strip()).netloc.lower()
    except ValueError:
        return ""


def hosts_que_bloqueiam(conexao: sqlite3.Connection) -> dict[str, int]:
    """Hosts que recusaram toda a verificação, com quantos recursos cada um.

    As três condições valem juntas: volume mínimo, **zero** sucessos e maioria
    de 403. Zero sucessos é o que separa recusa de host de negativa por arquivo
    — um host que respondeu a alguns e negou outros está funcionando, e o 403
    ali é sobre o arquivo.
    """
    agregado: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "ok": 0, "403": 0}
    )
    for linha in conexao.execute(
        "SELECT link, status_http FROM recurso WHERE status_http IS NOT NULL"
    ):
        dados = agregado[_host(linha["link"])]
        dados["n"] += 1
        status = linha["status_http"]
        if 200 <= status < 400:
            dados["ok"] += 1
        elif status == 403:
            dados["403"] += 1

    return {
        host: dados["n"]
        for host, dados in agregado.items()
        if host
        and dados["n"] >= MINIMO_PARA_ACUSAR_BLOQUEIO
        and dados["ok"] == 0
        and dados["403"] > dados["n"] * FRACAO_403_PARA_BLOQUEIO
    }


def reconhecer_bloqueios(conexao: sqlite3.Connection) -> dict[str, int]:
    """Reclassifica como `bloqueado` os recursos de host que nos recusa.

    Roda sobre resultado já gravado e **não emite requisição**: a evidência já
    está no banco. É o que permite corrigir o rótulo de milhares de recursos sem
    repetir horas de varredura e de carga sobre os órgãos.
    """
    bloqueadores = hosts_que_bloqueiam(conexao)
    if not bloqueadores:
        return {}

    corrigidos: dict[str, int] = {}
    for linha in conexao.execute(
        "SELECT id, link FROM recurso WHERE status_http IS NOT NULL"
    ):
        host = _host(linha["link"])
        if host not in bloqueadores:
            continue
        conexao.execute(
            "UPDATE recurso SET classe_saude = ?, motivo_saude = ? WHERE id = ?",
            ("bloqueado", MOTIVO_BLOQUEIO, linha["id"]),
        )
        corrigidos[host] = corrigidos.get(host, 0) + 1
    conexao.commit()
    return corrigidos


def reconhecer_dominios_mortos(conexao: sqlite3.Connection) -> int:
    """Separa domínio que não resolve dos demais erros de conexão.

    Resolve **uma vez por host**, não por recurso: são 149 hosts para 8.280
    recursos na varredura de 2026-09-12. Não é requisição HTTP — é a mesma
    consulta de DNS que qualquer conexão faria antes de abrir o soquete.
    """
    hosts: dict[str, list[str]] = defaultdict(list)
    for linha in conexao.execute(
        "SELECT id, link FROM recurso WHERE classe_saude = 'instavel'"
        " AND motivo_saude = 'ConnectError'"
    ):
        hosts[_host(linha["link"])].append(linha["id"])

    corrigidos = 0
    for host, ids in hosts.items():
        if not host:
            continue
        try:
            socket.getaddrinfo(host.split(":")[0], None)
            continue
        except socket.gaierror:
            pass
        except (UnicodeError, OSError):
            # Host malformado não é domínio morto: é link que nunca foi URL, e
            # inventar veredito sobre ele seria afirmar o que não medimos.
            continue
        for recurso_id in ids:
            conexao.execute(
                "UPDATE recurso SET classe_saude = ?, motivo_saude = ? WHERE id = ?",
                ("dominio_inexistente", "domínio não resolve", recurso_id),
            )
            corrigidos += 1
    conexao.commit()
    return corrigidos


# --- relatório -----------------------------------------------------------


@dataclass
class Relatorio:
    verificados: int = 0
    pulados: int = 0
    requisicoes: int = 0
    classes: dict[str, int] = field(default_factory=dict)
    latencias: list[int] = field(default_factory=list)
    bloqueadores: dict[str, int] = field(default_factory=dict)
    dominios_mortos: int = 0

    def contar(self, resultado: Resultado) -> None:
        self.verificados += 1
        self.classes[resultado.classe] = self.classes.get(resultado.classe, 0) + 1
        if resultado.latencia_ms is not None:
            self.latencias.append(resultado.latencia_ms)


GLOSSARIO = {
    "disponivel": "respondeu 2xx nesta verificação",
    "indisponivel": "o host respondeu e negou este endereço: 404, 410 ou outro 4xx",
    "bloqueado": "o host recusou toda a verificação; nada se afirma sobre o arquivo",
    "cadeia_incompleta": "o servidor não envia o certificado intermediário; o "
    "navegador baixa, nosso cliente não",
    "dominio_inexistente": "o domínio não resolve em DNS",
    "instavel": "não respondeu de forma confiável: tempo esgotado, 5xx ou 429",
    "nao_verificado": "sem URL ou com link que não é um endereço",
}


SEM_VERIFICACAO_POSSIVEL = ("bloqueado", "nao_verificado")


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
    # A ausência confirmada nunca é apresentada sozinha quando há host que nos
    # recusa: sem isto, a proporção de links mortos é lida como medida quando
    # parte dela é cegueira do verificador. Na varredura de 2026-09-12 a
    # diferença era o dobro — 9,1% contra 4,8%.
    ausentes = relatorio.classes.get("indisponivel", 0)
    cegos = sum(relatorio.classes.get(c, 0) for c in SEM_VERIFICACAO_POSSIVEL)
    log("")
    log(f"  ausência confirmada:      {ausentes}")
    log(f"  sem verificação possível: {cegos}")

    if relatorio.bloqueadores:
        log("")
        log("  hosts que recusaram toda a verificação:")
        for host, quantos in sorted(
            relatorio.bloqueadores.items(), key=lambda par: -par[1]
        ):
            log(f"    {quantos:6d}  {host}")
        log("  esses recursos não são contados como ausência: nada foi")
        log("  verificado neles, e a classe não afirma o que não medimos.")
    else:
        log("")
        log("  nenhum host recusou a verificação inteira.")

    if relatorio.dominios_mortos:
        log(f"  domínios sem DNS reclassificados: {relatorio.dominios_mortos}")

    if relatorio.latencias:
        ordenadas = sorted(relatorio.latencias)
        mediana = ordenadas[len(ordenadas) // 2]
        p95 = ordenadas[min(len(ordenadas) - 1, int(len(ordenadas) * 0.95))]
        log("")
        log(f"  latência mediana:     {mediana} ms")
        log(f"  latência p95:         {p95} ms")
    log(f"  banco:                {banco}")


# --- orquestração --------------------------------------------------------


def contar_classes(
    conexao: sqlite3.Connection, *, desde: str | None = None
) -> dict[str, int]:
    """Conta as classes no banco, opcionalmente só o que esta corrida tocou."""
    sql = "SELECT classe_saude, COUNT(*) AS quantos FROM recurso"
    params: list[Any] = []
    if desde is not None:
        sql += " WHERE checado_em >= ?"
        params.append(desde)
    sql += " GROUP BY classe_saude"
    return {
        linha["classe_saude"]: linha["quantos"]
        for linha in conexao.execute(sql, params)
        if linha["classe_saude"]
    }


def reclassificar(banco: Path) -> Relatorio:
    """Corrige os rótulos do que já foi medido, sem repetir a varredura.

    A evidência de bloqueio já está gravada, e a de domínio morto custa uma
    consulta de DNS por host. Refazer as 141.942 requisições da varredura
    completa para trocar rótulo seria três horas de carga sobre 630 órgãos para
    não descobrir nada novo.
    """
    conexao = abrir_banco(banco)
    relatorio = Relatorio()
    try:
        relatorio.bloqueadores = reconhecer_bloqueios(conexao)
        relatorio.dominios_mortos = reconhecer_dominios_mortos(conexao)
        relatorio.classes = contar_classes(conexao)
        relatorio.verificados = sum(relatorio.classes.values())
    finally:
        conexao.close()
    return relatorio


async def verificar_tudo(
    *,
    banco: Path,
    limite: int | None = None,
    idade_maxima: int | None = None,
    somente_falhas: bool = False,
    classe: str | None = None,
    cliente: httpx.AsyncClient | None = None,
) -> Relatorio:
    conexao = abrir_banco(banco)
    relatorio = Relatorio()
    inicio_utc = agora_utc()

    try:
        recursos, pulados = selecionar(
            conexao,
            limite=limite,
            idade_maxima=idade_maxima,
            somente_falhas=somente_falhas,
            classe=classe,
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

        # Segunda passada. Só agora existe o agregado por host que distingue
        # "este arquivo não está lá" de "este host não me deixa olhar".
        relatorio.bloqueadores = reconhecer_bloqueios(conexao)
        if relatorio.bloqueadores:
            relatorio.classes = contar_classes(conexao, desde=inicio_utc)
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
        False, "--somente-falhas", help="Reprocessa tudo que não está disponível."
    ),
    classe: Optional[str] = typer.Option(
        None,
        "--classe",
        help="Reverifica apenas esta classe, ex.: bloqueado.",
    ),
    reclassificar_apenas: bool = typer.Option(
        False,
        "--reclassificar",
        help="Corrige rótulos do que já foi medido, sem nova requisição HTTP.",
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

    if classe is not None and classe not in CLASSES:
        log(f"classe desconhecida: {classe}")
        log(f"classes válidas: {', '.join(CLASSES)}")
        raise typer.Exit(code=2)

    if reclassificar_apenas:
        log("reclassificando o que já foi medido; nenhuma requisição HTTP")
        relatorio = reclassificar(banco)
        imprimir_relatorio(relatorio, banco)
        return

    log(f"User-Agent: {user_agent()}")
    relatorio = asyncio.run(
        verificar_tudo(
            banco=banco,
            limite=limite,
            idade_maxima=idade_maxima,
            somente_falhas=somente_falhas,
            classe=classe,
        )
    )
    imprimir_relatorio(relatorio, banco)


if __name__ == "__main__":
    app()
