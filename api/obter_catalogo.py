"""Traz o catálogo para dentro da imagem, e recusa qualquer coisa que não seja ele.

Roda **em tempo de build**, não em tempo de resposta. Não é código da aplicação
e nunca é importado por ela — está em `api/` só porque é isso que o Dockerfile
da api precisa copiar.

Usa apenas a biblioteca padrão de propósito: `python:3.12-slim` não traz `curl`
nem `wget`, e instalar um deles só para baixar um arquivo aumentaria a imagem e
a superfície de ataque para sempre. `urllib` e `gzip` já estão lá.

O comportamento diante de erro é falhar, sem exceção. Catálogo errado não parece
errado: os links continuam bem formados, as fichas continuam legíveis, e só
faltam conjuntos. O defeito apareceria semanas depois para alguém que procurasse
um dado que deveria existir, indistinguível de uma falha de busca. Falhar no
build é barulhento e imediato; degradar é silencioso e caro.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

BLOCO = 1024 * 1024
TEMPO_LIMITE = 120


def erro(*linhas: str) -> None:
    for linha in linhas:
        print(linha, file=sys.stderr, flush=True)
    raise SystemExit(1)


def log(mensagem: str) -> None:
    print(mensagem, file=sys.stderr, flush=True)


def soma_sha256(caminho: Path) -> str:
    digestor = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(BLOCO), b""):
            digestor.update(bloco)
    return digestor.hexdigest()


def baixar(url: str, destino: Path, versao: str) -> None:
    log(f"baixando catálogo {versao}")
    log(f"  de {url}")
    try:
        with urllib.request.urlopen(url, timeout=TEMPO_LIMITE) as resposta:
            with destino.open("wb") as saida:
                shutil.copyfileobj(resposta, saida, BLOCO)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as falha:
        erro(
            f"FALHA AO BAIXAR O CATÁLOGO {versao}",
            f"  {falha}",
            f"  url: {url}",
            "",
            "A imagem não é construída sem catálogo. Se a release ainda não foi",
            "publicada, gere-a com `just catalogo` e `just catalogo-publica`, ou",
            "construa com artefato local: --build-arg CATALOGO_LOCAL=<arquivo>.",
        )


def conferir(artefato: Path, esperada: str, versao: str) -> None:
    recebida = soma_sha256(artefato)
    if recebida == esperada:
        log(f"  soma confere: {recebida}")
        return
    erro(
        f"SOMA DE VERIFICAÇÃO DIVERGENTE NO CATÁLOGO {versao}",
        f"  esperada: {esperada}",
        f"  recebida: {recebida}",
        f"  bytes:    {artefato.stat().st_size}",
        "",
        "O artefato baixado não é o que este commit declara servir. A imagem",
        "não é construída: catálogo trocado responde com aparência de normal.",
    )


def descomprimir(artefato: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with gzip.open(artefato, "rb") as entrada, destino.open("wb") as saida:
            shutil.copyfileobj(entrada, saida, BLOCO)
    except (OSError, EOFError, gzip.BadGzipFile) as falha:
        erro(f"ARTEFATO CORROMPIDO: não foi possível descomprimir", f"  {falha}")
    log(f"  catálogo em {destino} ({destino.stat().st_size / 1e6:.1f} MB)")


def main(argumentos: list[str]) -> None:
    if len(argumentos) < 2:
        erro("uso: obter_catalogo.py <catalogo.json> <destino.db> [artefato-local]")

    manifesto_em, destino = Path(argumentos[0]), Path(argumentos[1])
    local = argumentos[2] if len(argumentos) > 2 and argumentos[2] else None

    try:
        manifesto = json.loads(manifesto_em.read_text(encoding="utf-8"))
    except (OSError, ValueError) as falha:
        erro(f"manifesto ilegível em {manifesto_em}: {falha}")

    versao = manifesto.get("versao", "(sem versão)")

    if local:
        # Escape para desenvolvimento: testar uma mudança no Dockerfile não pode
        # exigir publicar uma release. A soma não se aplica porque o arquivo é
        # local e quem o indicou sabe o que colocou ali. O padrão continua sendo
        # o publicado, para que o descuido leve ao caminho seguro.
        artefato = Path(local)
        if not artefato.is_file():
            erro(f"artefato local não encontrado: {artefato}")
        log(f"usando artefato local {artefato} — soma não verificada")
        descomprimir(artefato, destino)
        return

    for obrigatorio in ("origem", "sha256"):
        if not manifesto.get(obrigatorio):
            erro(f"manifesto sem `{obrigatorio}`: {manifesto_em}")

    # `with_suffix` trocaria a extensão: `dados.db` viraria `dados.gz`. Aqui a
    # intenção é somar, não substituir.
    artefato = destino.with_name(destino.name + ".gz")
    # O diretório precisa existir antes do download, não só antes da
    # descompressão. O caminho local não expunha isto porque vai direto para
    # `descomprimir`, que já criava o diretório — e a divergência entre os dois
    # caminhos só apareceu quando o build baixou de verdade.
    destino.parent.mkdir(parents=True, exist_ok=True)
    baixar(manifesto["origem"], artefato, versao)
    conferir(artefato, manifesto["sha256"], versao)
    descomprimir(artefato, destino)
    artefato.unlink()


if __name__ == "__main__":
    main(sys.argv[1:])
