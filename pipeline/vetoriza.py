"""Gera os vetores das fichas para a busca semântica.

Sexta camada do pipeline, ao lado do índice léxico. Nada aqui chama modelo de
linguagem nem gasta dinheiro: o texto vetorizado é o `texto_indexavel` que o
enriquecimento já gravou, e o modelo de embedding roda localmente.

Grava dois arquivos, sempre juntos: `vectors.npy`, a matriz, e `vectors.json`,
com os identificadores na mesma ordem, a versão do catálogo que os originou e a
soma do `.npy`. Os dois são escritos em temporários e só então renomeados, e a
soma amarra um ao outro — um `.npy` de outra execução é recusado na carga.

Também produz a referência do teste de paridade, `--referencia`: vetores de
textos fixos, gerados por este runtime, que o serviço de consulta precisa
reproduzir com o dele.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import typer

import embeddings
import semantica

RAIZ = Path(__file__).resolve().parent
ARQUIVO_REFERENCIA = RAIZ / "tests" / "fixtures" / "paridade_e5.npz"

# Textos fixos, e não tirados do banco: a referência precisa ser estável entre
# recoletas, senão toda atualização do catálogo quebraria o teste de paridade
# sem que nada tivesse divergido. Cobrem os dois prefixos, acento, sigla e um
# texto longo, que é onde runtimes diferentes costumam discordar no truncamento.
TEXTOS_REFERENCIA: tuple[tuple[str, str], ...] = (
    ("consulta", "onde acho dados de dengue na minha cidade"),
    ("consulta", "quanto o governo gasta com publicidade e propaganda"),
    ("consulta", "remédio de graça pelo SUS"),
    ("consulta", "IDEB das escolas públicas"),
    ("documento", "Casos confirmados de dengue notificados ao Sinan, por município "
     "e semana epidemiológica. Permite acompanhar a evolução da doença ao longo "
     "do tempo."),
    ("documento", " ".join(
        ["Relação de estabelecimentos de saúde cadastrados no CNES, com endereço, "
         "tipo de unidade, número de leitos, esfera administrativa e serviços "
         "oferecidos em cada município brasileiro."] * 6
    )),
)


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gravar(
    vetores: np.ndarray,
    ids: list[str],
    versao: str,
    vetores_em: Path = semantica.ARQUIVO_VETORES,
    ids_em: Path = semantica.ARQUIVO_IDENTIFICADORES,
) -> dict:
    """Grava os dois artefatos, ou nenhum.

    `np.save` com caminho acrescenta `.npy` a qualquer nome que não termine
    assim — `vectors.npy.tmp` viraria `vectors.npy.tmp.npy`. Por isso a escrita
    é por descritor de arquivo.
    """
    vetores = np.ascontiguousarray(vetores, dtype=np.float32)
    if vetores.shape[0] != len(ids):
        raise ValueError(f"{vetores.shape[0]} vetores para {len(ids)} identificadores")

    temporario_npy = vetores_em.with_name(vetores_em.name + ".tmp")
    temporario_json = ids_em.with_name(ids_em.name + ".tmp")
    vetores_em.parent.mkdir(parents=True, exist_ok=True)

    with temporario_npy.open("wb") as arquivo:
        np.save(arquivo, vetores, allow_pickle=False)

    meta = {
        "versao": versao,
        "modelo": embeddings.MODELO,
        "dimensao": int(vetores.shape[1]),
        "total": len(ids),
        "gerado_em": agora_utc(),
        "sha256_vetores": semantica.soma_sha256(temporario_npy),
        "ids": ids,
    }
    temporario_json.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")

    os.replace(temporario_npy, vetores_em)
    os.replace(temporario_json, ids_em)
    return meta


def gerar_referencia(vetorizador: embeddings.Vetorizador, destino: Path) -> None:
    """Vetores dos textos fixos, pela interface pública — com os prefixos dela."""
    vetores = [
        vetorizador.consulta(texto)
        if tipo == "consulta"
        else vetorizador.documentos([texto])[0]
        for tipo, texto in TEXTOS_REFERENCIA
    ]
    destino.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        destino,
        tipos=np.array([tipo for tipo, _ in TEXTOS_REFERENCIA]),
        textos=np.array([texto for _, texto in TEXTOS_REFERENCIA]),
        vetores=np.array(vetores, dtype=np.float32),
        modelo=np.array(embeddings.MODELO),
    )


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    banco: Path = typer.Option(
        semantica.DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
    lote: int = typer.Option(64, "--lote", min=1, help="Textos por lote."),
    dispositivo: Optional[str] = typer.Option(
        None, "--dispositivo", help="cuda ou cpu. Padrão: cuda se houver."
    ),
    referencia: bool = typer.Option(
        False, "--referencia", help="Só regrava a referência do teste de paridade."
    ),
) -> None:
    """Vetoriza o texto indexável de todas as fichas."""
    vetorizador = embeddings.Vetorizador(dispositivo)

    if referencia:
        gerar_referencia(vetorizador, ARQUIVO_REFERENCIA)
        log(f"referência de paridade gravada em {ARQUIVO_REFERENCIA}")
        return

    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        raise typer.Exit(code=2)

    conexao = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        fichas = semantica.ler_fichas(conexao)
    finally:
        conexao.close()
    if not fichas:
        log("nenhuma ficha no banco — o enriquecimento já rodou?")
        raise typer.Exit(code=2)

    versao = semantica.versao_do_catalogo(fichas)

    carga = time.perf_counter()
    log(f"carregando {embeddings.MODELO} em {vetorizador.dispositivo}...")
    carga = time.perf_counter() - carga

    inicio = time.perf_counter()
    vetores = vetorizador.documentos(
        [texto for _, texto in fichas], lote=lote, progresso=True
    )
    duracao = time.perf_counter() - inicio

    meta = gravar(vetores, [identificador for identificador, _ in fichas], versao)
    normas = np.linalg.norm(vetores, axis=1)
    tamanho = semantica.ARQUIVO_VETORES.stat().st_size

    log("")
    log("relatório de vetorização")
    log(f"  modelo:        {meta['modelo']} ({meta['dimensao']} dimensões)")
    log(f"  dispositivo:   {vetorizador.dispositivo}")
    log(f"  fichas:        {meta['total']}")
    log(f"  carga:         {carga:.1f}s")
    log(f"  vetorização:   {duracao:.1f}s ({meta['total'] / duracao:.0f} fichas/s)")
    log(f"  normas:        {normas.min():.6f} a {normas.max():.6f}")
    log(f"  vectors.npy:   {tamanho} bytes ({tamanho / 1e6:.2f} MB)")
    log(f"  versão:        {meta['versao'][:16]}…")


if __name__ == "__main__":
    app()
