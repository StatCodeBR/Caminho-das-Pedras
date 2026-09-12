"""Publica o catálogo como release verificável.

Última camada do pipeline, e a única que fala com a rede depois da coleta. O
banco que as camadas anteriores produziram não é código-fonte: é resultado de
uma execução, com procedência própria e peso próprio. Versioná-lo faria o
repositório crescer para sempre sem comprimir entre versões.

A divisão é: o repositório guarda a soma de verificação e o manifesto, a release
guarda os bytes. Assim a autoridade continua no repositório — trocar o catálogo
de uma imagem exige um commit, com autor e data, e `git log` responde quando o
catálogo mudou e para qual.
"""

from __future__ import annotations

import gzip
import tarfile
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer

RAIZ = Path(__file__).resolve().parent
REPOSITORIO = RAIZ.parent
DIRETORIO_DADOS = RAIZ / "dados"

# O manifesto mora na raiz do repositório, não em `pipeline/`: ele é a
# declaração de qual catálogo *este commit* serve, lida pelo build da imagem,
# cujo contexto é a raiz. Não é artefato interno do pipeline.
ARQUIVO_MANIFESTO = REPOSITORIO / "catalogo.json"

ASSET_BANCO = "dados.db.gz"
# Os vetores viajam num pacote só: o `.json` guarda a soma do `.npy` e a ordem
# dos identificadores, e separá-los em dois assets permitiria publicar metade de
# uma vetorização com metade de outra.
ASSET_VETORES = "vetores.tar.gz"

# gzip e não zstd: ganha 10 MB a menos na compressão, mas está na biblioteca
# padrão do Python, então a imagem descomprime sem instalar pacote nenhum.
# Dez megabytes por build não valem uma dependência permanente.
NIVEL_GZIP = 9

BLOCO = 1024 * 1024


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- medição do banco ----------------------------------------------------


def medir(banco: Path) -> dict[str, Any]:
    """O que o manifesto precisa dizer sobre o conteúdo do catálogo.

    Sem isto, saber o que há dentro de uma release exige baixá-la e abri-la. E a
    procedência — qual modelo escreveu as fichas — é o que permite auditar
    depois por que uma resposta saiu como saiu.
    """
    conexao = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        def conta(tabela: str) -> int:
            try:
                return conexao.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
            except sqlite3.OperationalError:
                return 0

        modelos = [
            linha[0]
            for linha in conexao.execute(
                "SELECT DISTINCT modelo FROM ficha WHERE modelo <> '' ORDER BY modelo"
            )
        ]
        gerado_em = conexao.execute("SELECT max(gerada_em) FROM ficha").fetchone()[0]
        return {
            "gerado_em": gerado_em
            or datetime.fromtimestamp(banco.stat().st_mtime, timezone.utc).isoformat(
                timespec="seconds"
            ),
            "conjuntos": conta("conjunto"),
            "recursos": conta("recurso"),
            "fichas": conta("ficha"),
            "modelos": modelos,
        }
    finally:
        conexao.close()


# --- soma e compressão ---------------------------------------------------


def soma_sha256(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(BLOCO), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def comprimir(banco: Path, destino: Path) -> Path:
    """Comprime em gzip, em blocos, para não carregar 186 MB na memória."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with banco.open("rb") as entrada:
        with gzip.GzipFile(
            filename="", mode="wb", compresslevel=NIVEL_GZIP, fileobj=destino.open("wb"),
            mtime=0,
        ) as saida:
            shutil.copyfileobj(entrada, saida, BLOCO)
    return destino


# --- manifesto -----------------------------------------------------------


def url_do_asset(repo: str, versao: str, nome: str) -> str:
    return f"https://github.com/{repo}/releases/download/{versao}/{nome}"


def empacotar_vetores(vetores: Path, identificadores: Path, destino: Path) -> Path:
    """Empacota os dois arquivos dos vetores num tar.gz determinístico.

    Determinístico de propósito: regerar o pacote sobre os mesmos vetores precisa
    dar a mesma soma, senão cada execução exigiria um commit novo do manifesto
    sem nada ter mudado. Daí zerar data, dono e grupo de cada membro.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as bruto:
        with gzip.GzipFile(
            filename="", mode="wb", compresslevel=NIVEL_GZIP, fileobj=bruto, mtime=0
        ) as comprimido:
            with tarfile.open(fileobj=comprimido, mode="w") as pacote:
                for arquivo in (vetores, identificadores):
                    info = pacote.gettarinfo(str(arquivo), arcname=arquivo.name)
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with arquivo.open("rb") as conteudo:
                        pacote.addfile(info, conteudo)
    return destino


def conferir_vetores(banco: Path, identificadores: Path) -> dict[str, Any]:
    """Os vetores descrevem o banco que vai junto? Se não, não se publica.

    Publicar um par desencontrado põe em produção um vetor que aponta para o
    conjunto errado — e isso não dá sintoma nenhum: a resposta sai bem formada,
    sobre o conjunto errado.
    """
    import semantica

    meta = json.loads(identificadores.read_text(encoding="utf-8"))
    conexao = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        versao = semantica.versao_do_catalogo(semantica.ler_fichas(conexao))
    finally:
        conexao.close()
    if meta.get("versao") != versao:
        raise ErroDePublicacao(
            "os vetores foram gerados sobre outra versão do catálogo; publicá-los "
            "juntos poria em produção vetor que aponta para o conjunto errado.\n"
            "rode: just vetores"
        )
    return meta


def montar_manifesto(
    banco: Path,
    artefato_banco: Path,
    artefato_vetores: Path,
    vetores_meta: dict[str, Any],
    versao: str,
    repo: str | None = None,
) -> dict[str, Any]:
    """O que o repositório guarda: procedência e a soma de cada asset.

    Cada asset tem soma própria para que a mensagem de erro no build diga qual
    divergiu, e para que conferir os 31 MB de vetores não obrigue a baixar e
    descomprimir os 186 MB do banco.
    """
    dono = repo or repositorio_remoto()
    return {
        # A versão é a tag da release, fixa. Nunca "a mais recente": duas
        # construções do mesmo commit precisam produzir a mesma imagem.
        "versao": versao,
        "publicado_em": agora_utc(),
        **medir(banco),
        # Qual modelo gerou os vetores. O serviço recusa subir se não for o
        # mesmo com que ele vetoriza a pergunta.
        "modelo_embedding": vetores_meta.get("modelo", ""),
        "vetores": vetores_meta.get("total", 0),
        # A URL completa mora aqui para que o build não precise saber o nome do
        # repositório: o manifesto diz onde os bytes estão e qual soma têm.
        "assets": {
            "banco": {
                "arquivo": ASSET_BANCO,
                "origem": url_do_asset(dono, versao, ASSET_BANCO),
                "sha256": soma_sha256(artefato_banco),
                "bytes": artefato_banco.stat().st_size,
                "bytes_descomprimido": banco.stat().st_size,
            },
            "vetores": {
                "arquivo": ASSET_VETORES,
                "origem": url_do_asset(dono, versao, ASSET_VETORES),
                "sha256": soma_sha256(artefato_vetores),
                "bytes": artefato_vetores.stat().st_size,
            },
        },
    }


def gravar_manifesto(manifesto: dict[str, Any], caminho: Path) -> None:
    caminho.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def ler_manifesto(caminho: Path = ARQUIVO_MANIFESTO) -> dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))


# --- publicação ----------------------------------------------------------


class ErroDePublicacao(RuntimeError):
    """Falha antes ou durante o envio à release."""


# Os dois lados da paridade: o runtime que gera os vetores e o que vetoriza a
# pergunta. Cada um só pode ser testado dentro do próprio projeto — a api não
# pode carregar torch —, então a verificação roda um pytest em cada.
PROJETOS_PARIDADE = (RAIZ, REPOSITORIO / "api")


def verificar_paridade() -> None:
    """Os dois runtimes ainda produzem o mesmo vetor? Sem isso, não se publica.

    Divergência entre eles não quebra a busca de forma visível: ela degrada, em
    silêncio, e o erro seria atribuído ao prompt ou aos dados. Publicar um
    catálogo nesse estado espalharia o defeito para a produção.
    """
    for projeto in PROJETOS_PARIDADE:
        resultado = subprocess.run(
            ["uv", "run", "pytest", "-m", "paridade", "-q"],
            cwd=projeto,
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            raise ErroDePublicacao(
                f"a paridade entre os runtimes falhou em {projeto.name}/; "
                "nenhum catálogo é publicado nesse estado.\n"
                + (resultado.stdout or resultado.stderr)[-2000:]
            )


def arvore_suja() -> list[str]:
    """Arquivos modificados ou não rastreados, que impedem a publicação.

    Publicar de árvore suja grava um manifesto que descreve um catálogo gerado
    por código que não está em lugar nenhum. A procedência, que é o propósito do
    manifesto, deixaria de ser verificável.
    """
    resultado = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPOSITORIO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [l for l in resultado.stdout.splitlines() if l.strip()]


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise ErroDePublicacao(
            "Defina GITHUB_TOKEN para publicar.\n"
            "Precisa de permissão de escrita em releases do repositório.\n"
            "Guarde no .env, que não é versionado."
        )
    return token


def _curl(argumentos: list[str], token: str, entrada: bytes | None = None) -> str:
    """Chama o curl com o token por stdin, nunca por argumento.

    Cabeçalho em `argv` fica visível para qualquer processo da máquina via `ps`.
    O `--config -` faz o curl ler a credencial da entrada padrão, que não
    aparece em lugar nenhum — é a diferença entre um segredo e um segredo que
    vaza para quem estiver olhando a lista de processos.
    """
    configuracao = f'header = "Authorization: Bearer {token}"\n'
    processo = subprocess.run(
        ["curl", "--fail-with-body", "--silent", "--show-error", "--config", "-",
         "-H", "Accept: application/vnd.github+json",
         "-H", "X-GitHub-Api-Version: 2022-11-28", *argumentos],
        cwd=REPOSITORIO,
        input=configuracao.encode() + (entrada or b""),
        capture_output=True,
        check=False,
    )
    if processo.returncode != 0:
        # A saída do curl pode ecoar o corpo da requisição; o token nunca está
        # ali, mas a mensagem é higienizada por precaução.
        erro = processo.stderr.decode(errors="replace").replace(token, "<token>")
        corpo = processo.stdout.decode(errors="replace").replace(token, "<token>")
        raise ErroDePublicacao(f"curl falhou ({processo.returncode}): {erro or corpo}")
    return processo.stdout.decode(errors="replace")


def repositorio_remoto() -> str:
    """`dono/nome` a partir do remote `origin`."""
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPOSITORIO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    corpo = url.split(":")[-1] if ":" in url and "://" not in url else url.split("/", 3)[-1]
    return corpo.removesuffix(".git").strip("/")


def criar_release(repo: str, versao: str, manifesto: dict[str, Any], token: str) -> int:
    corpo = json.dumps(
        {
            "tag_name": versao,
            "name": f"Catálogo {versao}",
            "body": (
                f"{manifesto['conjuntos']} conjuntos, {manifesto['recursos']} recursos, "
                f"{manifesto['fichas']} fichas.\n\n"
                f"Fichas escritas por: {', '.join(manifesto['modelos']) or '—'}\n"
                f"Vetores: {manifesto['vetores']} por {manifesto['modelo_embedding']}\n"
                f"Gerado em: {manifesto['gerado_em']}\n\n"
                + "\n".join(
                    f"`{a['arquivo']}  sha256:{a['sha256']}`"
                    for a in manifesto["assets"].values()
                )
            ),
        }
    )
    saida = _curl(
        [f"https://api.github.com/repos/{repo}/releases",
         "-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "@-"],
        token,
        entrada=corpo.encode(),
    )
    return json.loads(saida)["id"]


def enviar_asset(
    repo: str, release_id: int, artefato: Path, nome: str, token: str
) -> str:
    saida = _curl(
        [f"https://uploads.github.com/repos/{repo}/releases/{release_id}/assets"
         f"?name={nome}",
         "-X", "POST", "-H", "Content-Type: application/gzip",
         "--data-binary", f"@{artefato}"],
        token,
    )
    return json.loads(saida)["browser_download_url"]


# --- interface de linha de comando --------------------------------------

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
    versao: Optional[str] = typer.Option(
        None, "--versao", help="Tag da release. Padrão: catalogo-AAAA-MM-DD."
    ),
    vetores: Path = typer.Option(
        DIRETORIO_DADOS / "vectors.npy", "--vetores", help="Matriz de vetores."
    ),
    saida: Path = typer.Option(
        DIRETORIO_DADOS / ASSET_BANCO, "--saida", help="Onde gravar o banco comprimido."
    ),
    saida_vetores: Path = typer.Option(
        DIRETORIO_DADOS / ASSET_VETORES, "--saida-vetores",
        help="Onde gravar o pacote dos vetores.",
    ),
    manifesto_em: Path = typer.Option(
        ARQUIVO_MANIFESTO, "--manifesto", help="Onde gravar o manifesto."
    ),
    publicar: bool = typer.Option(
        False, "--publicar", help="Envia à release. Sem isto, só gera e mede."
    ),
    permitir_sujo: bool = typer.Option(
        False, "--permitir-sujo", help="Publica com a árvore do Git suja."
    ),
) -> None:
    """Comprime o catálogo, gera manifesto e soma, e opcionalmente publica."""
    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        log("rode o pipeline antes: just dados-full")
        raise typer.Exit(code=2)

    versao = versao or f"catalogo-{date.today().isoformat()}"

    if publicar and not permitir_sujo:
        sujos = arvore_suja()
        if sujos:
            log("a árvore do Git está suja; publicar agora gravaria um manifesto")
            log("que descreve um catálogo gerado por código não versionado:")
            for linha in sujos[:10]:
                log(f"  {linha}")
            if len(sujos) > 10:
                log(f"  … e mais {len(sujos) - 10}")
            log("commite antes, ou use --permitir-sujo se souber o que está fazendo.")
            raise typer.Exit(code=1)

    if publicar:
        log("verificando a paridade entre os runtimes de geração e de consulta...")
        try:
            verificar_paridade()
        except ErroDePublicacao as erro:
            log(str(erro))
            raise typer.Exit(code=1)

    identificadores = vetores.with_suffix(".json")
    if not vetores.is_file() or not identificadores.is_file():
        log(f"vetores não encontrados em {vetores.parent}")
        log("o catálogo não se publica sem eles: rode `just vetores`")
        raise typer.Exit(code=2)
    try:
        vetores_meta = conferir_vetores(banco, identificadores)
    except ErroDePublicacao as erro:
        log(str(erro))
        raise typer.Exit(code=1)

    log(f"comprimindo {banco} ({banco.stat().st_size / 1e6:.1f} MB)...")
    artefato = comprimir(banco, saida)
    log(f"empacotando os vetores ({vetores.stat().st_size / 1e6:.1f} MB)...")
    pacote = empacotar_vetores(vetores, identificadores, saida_vetores)
    manifesto = montar_manifesto(banco, artefato, pacote, vetores_meta, versao)
    gravar_manifesto(manifesto, manifesto_em)

    log("")
    log("manifesto do catálogo")
    log(f"  versão:      {manifesto['versao']}")
    log(f"  conjuntos:   {manifesto['conjuntos']}")
    log(f"  recursos:    {manifesto['recursos']}")
    log(f"  fichas:      {manifesto['fichas']}")
    log(f"  modelos:     {', '.join(manifesto['modelos']) or '—'}")
    log(f"  vetores:     {manifesto['vetores']} por {manifesto['modelo_embedding']}")
    log(f"  gerado em:   {manifesto['gerado_em']}")
    for nome, asset in manifesto["assets"].items():
        log(f"  {nome + ':':13}{asset['arquivo']} "
            f"({asset['bytes'] / 1e6:.1f} MB)  sha256 {asset['sha256'][:16]}…")
    log(f"  manifesto:   {manifesto_em}")

    if not publicar:
        log("")
        log("nada publicado. Confira o manifesto e rode de novo com --publicar.")
        return

    try:
        token = _token()
        repo = repositorio_remoto()
        log("")
        log(f"publicando em {repo} como {versao}...")
        release_id = criar_release(repo, versao, manifesto, token)
        url = enviar_asset(repo, release_id, artefato, ASSET_BANCO, token)
        enviar_asset(repo, release_id, pacote, ASSET_VETORES, token)
    except ErroDePublicacao as erro:
        log(str(erro))
        raise typer.Exit(code=1)

    log(f"  release:     {url}")
    log("")
    log("commite o catalogo.json: é ele que diz qual catálogo a imagem serve.")


if __name__ == "__main__":
    app()
