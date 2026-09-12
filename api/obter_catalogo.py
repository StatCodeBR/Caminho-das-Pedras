"""Traz o catálogo para dentro da imagem, e recusa qualquer coisa que não seja ele.

Roda **em tempo de build**, não em tempo de resposta. Não é código da aplicação
e nunca é importado por ela — está em `api/` só porque é isso que o Dockerfile
da api precisa copiar.

São dois artefatos, com soma própria cada um: o banco comprimido e o pacote dos
vetores da busca semântica. Somas separadas para que a mensagem diga qual
divergiu, e para que conferir os 31 MB de vetores não obrigue a baixar os 186 MB
do banco.

Usa apenas a biblioteca padrão de propósito: `python:3.12-slim` não traz `curl`
nem `wget`, e instalar um deles só para baixar dois arquivos aumentaria a imagem
e a superfície de ataque para sempre. `urllib`, `gzip` e `tarfile` já estão lá.

O comportamento diante de erro é falhar, sem exceção. Catálogo errado não parece
errado: os links continuam bem formados, as fichas continuam legíveis, e só
faltam conjuntos. O defeito apareceria semanas depois, indistinguível de uma
falha de busca. Falhar no build é barulhento e imediato; degradar é silencioso.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

BLOCO = 1024 * 1024
TEMPO_LIMITE = 300

# Os únicos membros que o pacote de vetores pode conter. Extrair nome vindo do
# arquivo sem conferir permitiria que um pacote trocado escrevesse onde quisesse.
MEMBROS_VETORES = ("vectors.npy", "vectors.json")


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


def baixar(url: str, destino: Path, versao: str, rotulo: str) -> None:
    log(f"baixando {rotulo} do catálogo {versao}")
    log(f"  de {url}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=TEMPO_LIMITE) as resposta:
            with destino.open("wb") as saida:
                shutil.copyfileobj(resposta, saida, BLOCO)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as falha:
        erro(
            f"FALHA AO BAIXAR {rotulo.upper()} DO CATÁLOGO {versao}",
            f"  {falha}",
            f"  url: {url}",
            "",
            "A imagem não é construída sem catálogo completo. Se a release ainda",
            "não foi publicada, gere-a com `just catalogo` e `just catalogo-publica`,",
            "ou construa com artefatos locais: --build-arg CATALOGO_LOCAL=<banco.gz>",
            "e --build-arg VETORES_LOCAIS=<vetores.tar.gz>.",
        )


def conferir(artefato: Path, esperada: str, versao: str, rotulo: str) -> None:
    recebida = soma_sha256(artefato)
    if recebida == esperada:
        log(f"  soma de {rotulo} confere: {recebida}")
        return
    erro(
        f"SOMA DE VERIFICAÇÃO DIVERGENTE EM {rotulo.upper()}, CATÁLOGO {versao}",
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
        erro("ARTEFATO CORROMPIDO: não foi possível descomprimir o banco", f"  {falha}")
    log(f"  catálogo em {destino} ({destino.stat().st_size / 1e6:.1f} MB)")


def desempacotar(pacote: Path, diretorio: Path) -> None:
    """Extrai só os dois membros esperados, e nenhum outro."""
    diretorio.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(pacote, mode="r:gz") as arquivo:
            nomes = arquivo.getnames()
            if sorted(nomes) != sorted(MEMBROS_VETORES):
                erro(
                    "PACOTE DE VETORES COM CONTEÚDO INESPERADO",
                    f"  esperado: {', '.join(sorted(MEMBROS_VETORES))}",
                    f"  recebido: {', '.join(sorted(nomes))}",
                )
            arquivo.extractall(diretorio, filter="data")
    except (OSError, EOFError, tarfile.TarError) as falha:
        erro("PACOTE DE VETORES CORROMPIDO", f"  {falha}")
    for membro in MEMBROS_VETORES:
        caminho = diretorio / membro
        log(f"  {membro} em {caminho} ({caminho.stat().st_size / 1e6:.1f} MB)")


def _asset(manifesto: dict, nome: str, manifesto_em: Path) -> dict:
    asset = (manifesto.get("assets") or {}).get(nome)
    if not asset or not asset.get("origem") or not asset.get("sha256"):
        erro(
            f"manifesto sem o asset `{nome}` completo: {manifesto_em}",
            "  cada asset precisa de `origem` e `sha256`",
        )
    return asset


def main(argumentos: list[str]) -> None:
    if len(argumentos) < 2:
        erro(
            "uso: obter_catalogo.py <catalogo.json> <destino.db> "
            "[banco-local] [vetores-locais]"
        )

    manifesto_em, destino = Path(argumentos[0]), Path(argumentos[1])
    banco_local = argumentos[2] if len(argumentos) > 2 and argumentos[2] else None
    vetores_locais = argumentos[3] if len(argumentos) > 3 and argumentos[3] else None

    try:
        manifesto = json.loads(manifesto_em.read_text(encoding="utf-8"))
    except (OSError, ValueError) as falha:
        erro(f"manifesto ilegível em {manifesto_em}: {falha}")

    versao = manifesto.get("versao", "(sem versão)")

    if banco_local or vetores_locais:
        # Escape para desenvolvimento: testar uma mudança no Dockerfile não pode
        # exigir publicar uma release. A soma não se aplica porque os arquivos
        # são locais e quem os indicou sabe o que colocou ali. O padrão continua
        # sendo o publicado, para que o descuido leve ao caminho seguro.
        if not (banco_local and vetores_locais):
            erro(
                "ARTEFATOS LOCAIS PELA METADE",
                f"  banco:   {banco_local or '(não indicado)'}",
                f"  vetores: {vetores_locais or '(não indicado)'}",
                "",
                "Indicar só um misturaria um banco local com vetores de outra versão",
                "do catálogo, e o serviço recusaria subir depois. Indique os dois.",
            )
        for rotulo, caminho in (("banco", banco_local), ("vetores", vetores_locais)):
            if not Path(caminho).is_file():
                erro(f"artefato local de {rotulo} não encontrado: {caminho}")
        log("usando artefatos locais — somas não verificadas")
        descomprimir(Path(banco_local), destino)
        desempacotar(Path(vetores_locais), destino.parent)
        return

    banco = _asset(manifesto, "banco", manifesto_em)
    vetores = _asset(manifesto, "vetores", manifesto_em)

    comprimido = destino.with_name(destino.name + ".gz")
    baixar(banco["origem"], comprimido, versao, "banco")
    conferir(comprimido, banco["sha256"], versao, "banco")
    descomprimir(comprimido, destino)
    comprimido.unlink()

    pacote = destino.parent / "vetores.tar.gz"
    baixar(vetores["origem"], pacote, versao, "vetores")
    conferir(pacote, vetores["sha256"], versao, "vetores")
    desempacotar(pacote, destino.parent)
    pacote.unlink()


if __name__ == "__main__":
    main(sys.argv[1:])
