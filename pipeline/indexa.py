"""Constrói o índice léxico sobre as fichas.

Quinta camada do pipeline, e a primeira que responde a alguma coisa. O índice é
derivado inteiramente do que a mudança 04 já gravou: nenhuma chamada a modelo
acontece aqui, nem poderia — indexar é rearranjar texto que já existe.

Para metadado curto em português, BM25 é difícil de superar. Quando a pessoa
digita a sigla de um órgão ou o nome exato de um programa, a busca léxica acerta
onde a semântica hesita. Ela é o primeiro degrau, não um degrau provisório.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

import typer

import temas as temas_modulo

RAIZ = Path(__file__).resolve().parent
DIRETORIO_DADOS = RAIZ / "dados"

# `remove_diacritics 2` é a forma que trata corretamente os acentos fora do
# Latin-1 — a opção 1 deixa passar caracteres que o português usa. Sem isso,
# "saude" não encontraria "saúde", que é exatamente como o público digita.
TOKENIZADOR = "unicode61 remove_diacritics 2"

# Colunas indexadas, na ordem em que entram na tabela virtual. A ordem importa:
# os pesos do bm25() são posicionais.
COLUNAS = ("nome", "perguntas", "resumo", "orgao", "tags")

# As colunas em que o texto foi escrito por gente — quem publicou o dado, ou o
# modelo redigindo a ficha. São as únicas que servem para medir se uma palavra é
# comum demais para discriminar.
#
# `tags` fica de fora porque é aqui que a indexação escreve os rótulos do nosso
# próprio vocabulário controlado de temas, e contá-los faz a frequência medir
# como *nós classificamos* em vez de como as pessoas falam: no catálogo completo
# `financas` aparece em 40,2% das fichas com 100% dessas ocorrências vindas de
# tags, e `economia` em 40,5% com 99%. Ambas são palavras de assunto — o que o
# cidadão digita — e o filtro as descartava por artefato nosso.
#
# A coluna continua indexada, buscável e pesada no bm25. Ela apenas não vota em
# quem é palavra banal.
COLUNAS_MEDIDAS = tuple(c for c in COLUNAS if c != "tags")

DDL_INDICE = f"""
DROP TABLE IF EXISTS ficha_fts;

CREATE VIRTUAL TABLE ficha_fts USING fts5(
    conjunto_id UNINDEXED,
    {', '.join(COLUNAS)},
    tokenize = '{TOKENIZADOR}'
);
"""


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def _lista_json(bruto: str | None) -> list[str]:
    if not bruto:
        return []
    try:
        dados = json.loads(bruto)
    except ValueError:
        return []
    return [str(item).strip() for item in dados if str(item).strip()]


def nomes_das_tags(bruto: str | None) -> list[str]:
    """As tags vêm do portal como objetos; aqui só interessa o nome."""
    if not bruto:
        return []
    try:
        dados = json.loads(bruto)
    except ValueError:
        return []
    nomes: list[str] = []
    for item in dados if isinstance(dados, list) else []:
        nome = item.get("name") or item.get("nome") if isinstance(item, dict) else item
        if isinstance(nome, str) and nome.strip():
            nomes.append(nome.strip())
    return nomes


def _texto_do_nome(nome: str | None, titulo: str | None) -> str:
    """Slug e título juntos: o slug carrega siglas que o título escreve por extenso."""
    partes = [p for p in ((titulo or "").strip(), (nome or "").replace("-", " ").strip()) if p]
    return " ".join(partes)


def _texto_do_orgao(organizacao: str | None) -> str:
    """O órgão vem como slug. Sem os hífens, `anac` vira termo buscável."""
    return (organizacao or "").replace("-", " ").strip()


def linhas_para_indexar(conexao: sqlite3.Connection) -> Iterable[tuple[Any, ...]]:
    """Uma linha por ficha, com cada campo na sua coluna.

    Colunas separadas existem para que o bm25 possa pesá-las de forma diferente:
    um termo que aparece numa pergunta de exemplo diz mais sobre a intenção do
    usuário do que o mesmo termo perdido no meio do resumo.
    """
    consulta = """
        SELECT f.conjunto_id, c.nome, c.titulo, c.organizacao, c.tags,
               f.resumo, f.perguntas_json, f.temas_json
        FROM ficha f JOIN conjunto c ON c.id = f.conjunto_id
        ORDER BY c.nome
    """
    for linha in conexao.execute(consulta):
        temas = [
            temas_modulo.TEMAS[chave]
            for chave in _lista_json(linha["temas_json"])
            if chave in temas_modulo.TEMAS
        ]
        yield (
            linha["conjunto_id"],
            _texto_do_nome(linha["nome"], linha["titulo"]),
            " ".join(_lista_json(linha["perguntas_json"])),
            linha["resumo"] or "",
            _texto_do_orgao(linha["organizacao"]),
            " ".join(nomes_das_tags(linha["tags"]) + temas),
        )


def indexar(banco: Path) -> int:
    """Reconstrói o índice do zero. Idempotente por descarte, não por remendo.

    Atualizar índice existente exigiria rastrear o que mudou desde a última
    execução — estado a mais para errar, sobre uma tabela que se reconstrói em
    segundos. O `DROP` é a garantia de que duas execuções seguidas produzem
    exatamente o mesmo índice.
    """
    conexao = sqlite3.connect(banco)
    conexao.row_factory = sqlite3.Row
    try:
        conexao.executescript(DDL_INDICE)
        colunas = ", ".join(("conjunto_id",) + COLUNAS)
        marcadores = ", ".join("?" * (len(COLUNAS) + 1))
        linhas = list(linhas_para_indexar(conexao))
        conexao.executemany(
            f"INSERT INTO ficha_fts ({colunas}) VALUES ({marcadores})", linhas
        )
        conexao.commit()
        return len(linhas)
    finally:
        conexao.close()


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
) -> None:
    """Reconstrói o índice léxico a partir das fichas."""
    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        log("rode o enriquecimento antes: uv run python enriquece.py")
        raise typer.Exit(code=2)

    total = indexar(banco)
    log("")
    log("relatório de indexação")
    log(f"  fichas indexadas:  {total}")
    log(f"  tokenizador:       {TOKENIZADOR}")
    log(f"  banco:             {banco}")
    if total == 0:
        log("  nenhuma ficha encontrada — o enriquecimento já rodou?")


if __name__ == "__main__":
    app()
