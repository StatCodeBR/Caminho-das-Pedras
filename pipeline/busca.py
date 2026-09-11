"""Busca léxica sobre o índice das fichas.

Recebe a pergunta como a pessoa a escreveu e devolve conjuntos ordenados. Nada
aqui chama modelo de linguagem: a recuperação é BM25 sobre texto já gravado.

O que o usuário digita é tratado como texto, nunca como sintaxe. Uma aspa solta
numa pergunta é um acidente de digitação, não um operador — e um erro de sintaxe
devolvido a quem só queria achar dados sobre creche seria um defeito nosso.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from indexa import COLUNAS, COLUNAS_MEDIDAS

RAIZ = Path(__file__).resolve().parent
DIRETORIO_DADOS = RAIZ / "dados"

LIMITE_PADRAO = 10

# Peso de cada coluna no bm25. A pergunta de exemplo pesa mais que tudo porque
# ela foi escrita justamente na linguagem em que a busca chega; o resumo pesa
# menos porque é prosa, e prosa dilui o termo. Ajustável por ambiente para que
# calibrar o ranking não exija tocar em código.
PESOS_PADRAO: dict[str, float] = {
    "nome": 3.0,
    "perguntas": 4.0,
    "resumo": 1.0,
    "orgao": 2.0,
    "tags": 1.5,
}

# Penalização por confiança. Multiplica a pontuação bruta, então nunca zera:
# uma ficha de confiança baixa desce no ranking, mas continua recuperável — se
# ela é a única que trata do assunto, escondê-la seria pior do que mostrá-la.
FATORES_PADRAO: dict[str, float] = {"alta": 1.0, "media": 0.85, "baixa": 0.55}

# Fração do índice acima da qual um termo é considerado comum demais para
# discriminar. Medido no próprio corpus, não contra uma lista de palavras: o
# que é vazio aqui ("dados", "registro", "qual") não é o que uma lista de
# stopwords do português traria, e muda conforme o catálogo cresce.
#
# O valor vem da distribuição observada nas 500 fichas, que separa limpo:
#   de 99%  da 58%  dados 51%  qual 46%  sobre 43%  quantos 26%  onde 19%
#   ————————————————— vão ——————————————————
#   minha 8.8%  cidade 5%  gastos 3%  dengue 1.2%  aeroportos 0.8%
# Acima do vão só há palavra de pergunta; abaixo, só assunto.
#
# No catálogo completo o vão fechou, e a correção foi tirar `tags` da conta
# (ver COLUNAS_MEDIDAS), não mexer aqui. Recalibrar não substituía: a varredura
# de 0,10 a 0,50 sobre o conjunto de avaliação não tem joelho — de 0,15 a 0,50
# ganham-se 7 termos úteis ao custo de 28 de ruído, em reta. Distribuição sem
# vão não se conserta movendo a linha de corte.
LIMIAR_TERMO_COMUM = 0.15

# Abaixo disto a frequência não é evidência de nada: num índice de três fichas,
# "aparece em 33%" descreve o acaso, não a língua. O filtro só liga quando o
# corpus é grande o bastante para que "comum" queira dizer alguma coisa.
MINIMO_PARA_FILTRAR = 50

TERMO = re.compile(r"\w+", re.UNICODE)


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def _float_do_ambiente(chave: str, padrao: float) -> float:
    try:
        return float(os.environ.get(chave, padrao))
    except ValueError:
        return padrao


def pesos() -> dict[str, float]:
    return {
        coluna: _float_do_ambiente(f"BUSCA_PESO_{coluna.upper()}", padrao)
        for coluna, padrao in PESOS_PADRAO.items()
    }


def fatores() -> dict[str, float]:
    return {
        nivel: _float_do_ambiente(f"BUSCA_FATOR_{nivel.upper()}", padrao)
        for nivel, padrao in FATORES_PADRAO.items()
    }


def sem_acento(texto: str) -> str:
    """Mesma normalização que o tokenizador do FTS5 aplica, para comparar."""
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def termos(consulta: str) -> list[str]:
    """As palavras da pergunta, sem pontuação e sem repetição."""
    vistos: dict[str, None] = {}
    for bruto in TERMO.findall(consulta or ""):
        vistos.setdefault(bruto, None)
    return list(vistos)


def _literal(palavra: str) -> str:
    return f'"{palavra.replace(chr(34), chr(34) * 2)}"'


def _so_texto_natural(palavra: str) -> str:
    """Restringe o casamento às colunas escritas por gente, não por rótulo."""
    return f"{{{' '.join(COLUNAS_MEDIDAS)}}} : {_literal(palavra)}"


def frequencia(conexao: sqlite3.Connection, palavra: str) -> int:
    """Em quantas fichas a palavra aparece no texto natural.

    A coluna `tags` não entra na conta: ver `COLUNAS_MEDIDAS`. Contá-la fazia
    `financas` valer 40,2% do corpus com 100% disso vindo de rótulo de tema.
    """
    return conexao.execute(
        "SELECT count(*) FROM ficha_fts WHERE ficha_fts MATCH ?",
        (_so_texto_natural(palavra),),
    ).fetchone()[0]


def descartar_comuns(conexao: sqlite3.Connection, palavras: list[str]) -> list[str]:
    """Remove os termos que aparecem em quase tudo, porque não discriminam nada.

    Sem isto a busca não consegue dizer "não achei". Como as palavras são unidas
    por OR, "onde acho dados sobre creche" casava em `onde`, `sobre` e `dados`
    mesmo com zero fichas sobre creche, e devolvia um ranking inteiro de
    conjuntos irrelevantes com aparência de resposta. Devolver o assunto errado
    com confiança é pior do que devolver nada, e envenenaria a avaliação de
    recuperação, que mediria ruído em vez de acerto.

    O corte é medido no corpus, não numa lista fixa: um termo é comum se está no
    texto natural de mais fichas do que `LIMIAR_TERMO_COMUM` permite. Se todos
    forem comuns, ficam os menos comuns — a pergunta ainda merece uma resposta.
    """
    total = conexao.execute("SELECT count(*) FROM ficha_fts").fetchone()[0]
    minimo = _float_do_ambiente("BUSCA_MINIMO_PARA_FILTRAR", MINIMO_PARA_FILTRAR)
    if total < minimo or len(palavras) < 2:
        return palavras

    limiar = total * _float_do_ambiente("BUSCA_LIMIAR_COMUM", LIMIAR_TERMO_COMUM)
    frequencias = {palavra: frequencia(conexao, palavra) for palavra in palavras}
    uteis = [p for p in palavras if frequencias[p] <= limiar]
    if uteis:
        return uteis
    menor = min(frequencias.values())
    return [p for p in palavras if frequencias[p] == menor]


def escapar(consulta: str) -> str:
    """Transforma a pergunta em expressão FTS5 sem significado sintático.

    Cada palavra vira uma string literal entre aspas, o que neutraliza tudo que
    o FTS5 trataria como operador: `AND`, `OR`, `NEAR`, asterisco, parêntese,
    circunflexo. A aspa interna é duplicada, que é como o SQLite escapa aspa
    dentro de literal.

    As palavras são unidas por OR, não por AND. Pergunta de gente tem artigo,
    preposição e verbo — exigir que o conjunto contenha todas as palavras de
    "quantos leitos de UTI tem na minha cidade" não devolveria nada. Com OR, o
    BM25 ordena: quem casa mais termos, e termos mais raros, sobe.
    """
    return " OR ".join(_literal(palavra) for palavra in termos(consulta))


@dataclass
class Resultado:
    """Uma linha do ranking. Traz o que a fusão da mudança 08 vai precisar."""

    conjunto_id: str
    posicao: int
    pontuacao: float
    pontuacao_bruta: float
    nome: str
    titulo: str
    organizacao: str
    confianca: str
    resumo: str
    casados: dict[str, list[str]]

    @property
    def termos_casados(self) -> list[str]:
        ordenados: dict[str, None] = {}
        for lista in self.casados.values():
            for termo in lista:
                ordenados.setdefault(termo, None)
        return list(ordenados)


def _tokens(texto: str) -> set[str]:
    """As palavras do texto, normalizadas como o tokenizador do índice faz."""
    return {sem_acento(palavra) for palavra in TERMO.findall(texto or "")}


def _casamentos(linha: sqlite3.Row, procurados: list[str]) -> dict[str, list[str]]:
    """Quais termos da pergunta aparecem em qual coluna.

    Serve à inspeção: um resultado inesperado quase sempre se explica por um
    termo genérico casando numa coluna de peso alto.

    A comparação é por palavra inteira, não por trecho. Procurar "de" dentro do
    texto casaria em "dados" e "cidade" e faria a explicação acusar casamento
    onde o índice não viu nenhum — pior que não explicar, porque parece
    explicação.
    """
    normalizados = [(t, sem_acento(t)) for t in procurados]
    achados: dict[str, list[str]] = {}
    for coluna in COLUNAS:
        presentes_na_coluna = _tokens(linha[coluna] or "")
        presentes = [bruto for bruto, alvo in normalizados if alvo in presentes_na_coluna]
        if presentes:
            achados[coluna] = presentes
    return achados


def buscar(
    conexao: sqlite3.Connection, consulta: str, limite: int = LIMITE_PADRAO
) -> list[Resultado]:
    """Os conjuntos mais relevantes para a pergunta, já ordenados e penalizados."""
    procurados = descartar_comuns(conexao, termos(consulta))
    expressao = " OR ".join(_literal(palavra) for palavra in procurados)
    if not expressao:
        # Consulta vazia não é erro: é ausência de pergunta.
        return []

    peso = pesos()
    fator = fatores()
    # A primeira coluna da tabela é `conjunto_id`, que não é indexada; o bm25
    # exige um peso por coluna declarada, então ela entra com zero.
    argumentos = ", ".join(["0.0"] + [repr(peso[c]) for c in COLUNAS])

    consulta_sql = f"""
        SELECT i.conjunto_id, {', '.join('i.' + c for c in COLUNAS)},
               -bm25(ficha_fts, {argumentos}) AS bruta,
               c.nome AS slug, c.titulo, c.organizacao, f.confianca, f.resumo
        FROM ficha_fts i
        JOIN ficha f    ON f.conjunto_id = i.conjunto_id
        JOIN conjunto c ON c.id = i.conjunto_id
        WHERE ficha_fts MATCH ?
    """

    pontuados: list[tuple[float, sqlite3.Row, float]] = []
    for linha in conexao.execute(consulta_sql, (expressao,)):
        bruta = float(linha["bruta"])
        pontuados.append((bruta * fator.get(linha["confianca"], 1.0), linha, bruta))

    # A penalização por confiança reordena, então ela precisa ser aplicada antes
    # do corte — ordenar pelo bm25 e só depois penalizar deixaria de fora fichas
    # boas empurradas para além do limite por vizinhas de confiança baixa.
    pontuados.sort(key=lambda item: item[0], reverse=True)

    return [
        Resultado(
            conjunto_id=linha["conjunto_id"],
            posicao=posicao,
            pontuacao=final,
            pontuacao_bruta=bruta,
            nome=linha["slug"],
            titulo=linha["titulo"] or "",
            organizacao=linha["organizacao"] or "",
            confianca=linha["confianca"],
            resumo=linha["resumo"] or "",
            casados=_casamentos(linha, procurados),
        )
        for posicao, (final, linha, bruta) in enumerate(pontuados[:limite], start=1)
    ]


def abrir_banco(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    return conexao


def indice_existe(conexao: sqlite3.Connection) -> bool:
    achado = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ficha_fts'"
    ).fetchone()
    return achado is not None


app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    pergunta: str = typer.Argument(..., help="A pergunta, em linguagem comum."),
    limite: int = typer.Option(LIMITE_PADRAO, "--limite", min=1, help="Quantos exibir."),
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
) -> None:
    """Busca conjuntos de dados por uma pergunta em linguagem comum."""
    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        raise typer.Exit(code=2)

    conexao = abrir_banco(banco)
    try:
        if not indice_existe(conexao):
            log("índice não encontrado; rode antes: uv run python indexa.py")
            raise typer.Exit(code=2)
        resultados = buscar(conexao, pergunta, limite)
    finally:
        conexao.close()

    if not resultados:
        print("nenhum conjunto encontrado.")
        return

    for r in resultados:
        print(f"{r.posicao:2d}. {r.titulo or r.nome}")
        print(f"    {r.nome}  ·  {r.organizacao}  ·  confiança {r.confianca}")
        print(f"    pontuação {r.pontuacao:.3f}  (bruta {r.pontuacao_bruta:.3f})")
        if r.casados:
            partes = [f"{col}: {', '.join(t)}" for col, t in r.casados.items()]
            print(f"    casou em  {' | '.join(partes)}")
        print(f"    https://dados.gov.br/dados/conjuntos-dados/{r.nome}")
        print()


if __name__ == "__main__":
    app()
