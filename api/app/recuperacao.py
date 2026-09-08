"""Recuperação léxica sobre o índice construído pelo pipeline.

Porte fiel do núcleo de consulta do `pipeline/busca.py`. A duplicação é
deliberada: `pipeline/` e `api/` são projetos Python separados e não podem
compartilhar dependências, e este módulo usa só a biblioteca padrão para que a
imagem do serviço continue magra.

O risco dessa escolha é deriva — mudar o ranking de um lado e não do outro faria
a avaliação medir uma coisa e o usuário receber outra. Qualquer alteração aqui
precisa acontecer nos dois lugares.
"""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from typing import Any

COLUNAS = ("nome", "perguntas", "resumo", "orgao", "tags")

PESOS_PADRAO: dict[str, float] = {
    "nome": 3.0,
    "perguntas": 4.0,
    "resumo": 1.0,
    "orgao": 2.0,
    "tags": 1.5,
}
FATORES_PADRAO: dict[str, float] = {"alta": 1.0, "media": 0.85, "baixa": 0.55}

LIMIAR_TERMO_COMUM = 0.15
MINIMO_PARA_FILTRAR = 50

TERMO = re.compile(r"\w+", re.UNICODE)


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
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(ch for ch in decomposto if not unicodedata.combining(ch))


def termos(consulta: str) -> list[str]:
    vistos: dict[str, None] = {}
    for bruto in TERMO.findall(consulta or ""):
        vistos.setdefault(bruto, None)
    return list(vistos)


def _literal(palavra: str) -> str:
    return f'"{palavra.replace(chr(34), chr(34) * 2)}"'


def frequencia(conexao: sqlite3.Connection, palavra: str) -> int:
    return conexao.execute(
        "SELECT count(*) FROM ficha_fts WHERE ficha_fts MATCH ?", (_literal(palavra),)
    ).fetchone()[0]


def descartar_comuns(conexao: sqlite3.Connection, palavras: list[str]) -> list[str]:
    """Remove termos presentes em quase tudo, para que a busca possa não achar."""
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


def _data(bruto: Any) -> str | None:
    """String vazia e nulo são a mesma coisa: data não declarada.

    Distinguir os dois faria a interface exibir campo vazio em vez de dizer que
    a data não foi informada, que é justamente o traço mudo a evitar.
    """
    texto = (bruto or "").strip() if isinstance(bruto, str) else bruto
    return texto or None


@dataclass
class Recurso:
    titulo: str
    link: str
    formato: str
    disponivel: bool


@dataclass
class Recuperado:
    conjunto_id: str
    posicao: int
    pontuacao: float
    nome: str
    titulo: str
    organizacao: str
    confianca: str
    resumo: str
    perguntas: list[str] = field(default_factory=list)
    recursos: list[Recurso] = field(default_factory=list)
    # Duas datas, nunca fundidas: a primeira diz quando o dado mudou, a segunda
    # quando o registro foi editado. Um conjunto com registro editado ontem e
    # dados de 2019 não é um conjunto atualizado ontem. `None` é valor legítimo
    # — a data dos dados falta em cerca de um quinto do catálogo.
    dados_atualizados_em: str | None = None
    metadados_atualizados_em: str | None = None

    @property
    def url_portal(self) -> str:
        return f"https://dados.gov.br/dados/conjuntos-dados/{self.nome}"


def buscar(
    conexao: sqlite3.Connection, consulta: str, limite: int = 5
) -> list[Recuperado]:
    procurados = descartar_comuns(conexao, termos(consulta))
    expressao = " OR ".join(_literal(palavra) for palavra in procurados)
    if not expressao:
        return []

    peso = pesos()
    fator = fatores()
    argumentos = ", ".join(["0.0"] + [repr(peso[c]) for c in COLUNAS])

    sql = f"""
        SELECT i.conjunto_id,
               -bm25(ficha_fts, {argumentos}) AS bruta,
               c.nome AS slug, c.titulo, c.organizacao,
               c.dados_atualizados_em, c.metadados_atualizados_em,
               f.confianca, f.resumo, f.perguntas_json
        FROM ficha_fts i
        JOIN ficha f    ON f.conjunto_id = i.conjunto_id
        JOIN conjunto c ON c.id = i.conjunto_id
        WHERE ficha_fts MATCH ?
    """

    import json

    pontuados: list[tuple[float, sqlite3.Row]] = []
    for linha in conexao.execute(sql, (expressao,)):
        final = float(linha["bruta"]) * fator.get(linha["confianca"], 1.0)
        pontuados.append((final, linha))
    pontuados.sort(key=lambda item: item[0], reverse=True)

    recuperados: list[Recuperado] = []
    for posicao, (final, linha) in enumerate(pontuados[:limite], start=1):
        try:
            perguntas = [str(p) for p in json.loads(linha["perguntas_json"] or "[]")]
        except ValueError:
            perguntas = []
        recuperados.append(
            Recuperado(
                conjunto_id=linha["conjunto_id"],
                posicao=posicao,
                pontuacao=final,
                nome=linha["slug"],
                titulo=linha["titulo"] or "",
                organizacao=linha["organizacao"] or "",
                confianca=linha["confianca"],
                resumo=linha["resumo"] or "",
                perguntas=perguntas,
                dados_atualizados_em=_data(linha["dados_atualizados_em"]),
                metadados_atualizados_em=_data(linha["metadados_atualizados_em"]),
            )
        )
    carregar_recursos(conexao, recuperados)
    return recuperados


# Classes que o verificador de saúde grava. `None` significa não checado, que
# não é o mesmo que quebrado — link sem checagem é apresentado normalmente.
INDISPONIVEIS = ("indisponivel",)


def carregar_recursos(
    conexao: sqlite3.Connection, recuperados: list[Recuperado]
) -> None:
    """Anexa os recursos de cada conjunto, disponíveis primeiro.

    Recurso com link morto não some: ele aparece marcado. Esconder seria
    enganoso, porque o dado foi catalogado e o cidadão tem direito de saber que
    existe e está inacessível — e sempre há o link da página no portal.
    """
    colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(recurso)")}
    campo_saude = "classe_saude" if "classe_saude" in colunas else "NULL"
    for item in recuperados:
        linhas = conexao.execute(
            f"""SELECT titulo, link, formato, {campo_saude} AS classe
                FROM recurso WHERE conjunto_id = ? ORDER BY id""",
            (item.conjunto_id,),
        ).fetchall()
        recursos = [
            Recurso(
                titulo=(linha["titulo"] or "").strip(),
                link=(linha["link"] or "").strip(),
                formato=(linha["formato"] or "").strip(),
                disponivel=linha["classe"] not in INDISPONIVEIS,
            )
            for linha in linhas
        ]
        recursos.sort(key=lambda r: not r.disponivel)
        item.recursos = recursos
