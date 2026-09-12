"""Mede se a recuperação encontra o conjunto certo.

Sexta camada, e a única que diz se as cinco anteriores serviram para alguma
coisa. As perguntas são escritas à mão, no vocabulário de quem não conhece o
catálogo — gerar as perguntas a partir dos títulos mediria a capacidade do
sistema de casar texto consigo mesmo, que é justamente o problema fácil.

Recall@5 é a métrica que dirige decisões: se o conjunto certo não chega ao
contexto, nenhuma redação salva a resposta. MRR entra como secundária, porque
distingue colocar o acerto em primeiro de colocá-lo em quinto.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import typer

import busca

RAIZ = Path(__file__).resolve().parent
DIRETORIO_DADOS = RAIZ / "dados"
ARQUIVO_PERGUNTAS = RAIZ.parent / "avaliacao" / "perguntas.csv"
ARQUIVO_HISTORICO = RAIZ.parent / "avaliacao" / "historico.jsonl"

PROFUNDIDADES = (5, 10)
LIMITE_BUSCA = max(PROFUNDIDADES)

# Marca de pergunta que o catálogo não responde. Não é identificador e nunca é
# procurado no banco: saber calar é parte do produto, e uma pergunta sem
# resposta contaria como falha justamente quando o sistema acerta ao não
# inventar.
AUSENCIA = "nenhum"

# Queda de recall@5 tolerada antes de a execução falhar. Acima disto, uma
# mudança aparentemente inofensiva nos pesos ou no prompt degradou a busca.
LIMIAR_REGRESSAO = 0.05

# As recuperações que a avaliação sabe medir. Cada uma se compara só consigo
# mesma no histórico: a diferença entre elas é de método, não regressão.
RECUPERACOES = ("lexica", "semantica", "hibrida")


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- conjunto de avaliação -----------------------------------------------


@dataclass
class Pergunta:
    texto: str
    aceitaveis: list[str]
    tema: str
    dificuldade: str

    @property
    def espera_ausencia(self) -> bool:
        """A resposta certa é não encontrar nada."""
        return not self.aceitaveis


def _identificadores(bruto: str | None) -> list[str]:
    """Os slugs aceitáveis, sem o marcador de ausência.

    `nenhum` sai da lista em vez de virar slug: procurá-lo no catálogo
    reportaria anotação quebrada onde há anotação deliberada.
    """
    achados: list[str] = []
    for pedaco in (bruto or "").replace(",", ";").split(";"):
        limpo = pedaco.strip().strip('"')
        if limpo and limpo.lower() != AUSENCIA:
            achados.append(limpo)
    return achados


def ler_perguntas(caminho: Path) -> list[Pergunta]:
    perguntas: list[Pergunta] = []
    with caminho.open(encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            texto = (linha.get("pergunta") or "").strip()
            if not texto:
                continue
            perguntas.append(
                Pergunta(
                    texto=texto,
                    aceitaveis=_identificadores(linha.get("conjuntos_aceitaveis")),
                    tema=(linha.get("tema") or "sem tema").strip(),
                    dificuldade=(linha.get("dificuldade") or "sem nível").strip(),
                )
            )
    return perguntas


# --- medição -------------------------------------------------------------


@dataclass
class Avaliada:
    pergunta: Pergunta
    recuperados: list[str]
    titulos: list[str] = field(default_factory=list)

    @property
    def posicao_do_acerto(self) -> Optional[int]:
        """Posição, começando em 1, do primeiro conjunto aceitável recuperado.

        Para pergunta de ausência, acertar é não recuperar nada — e o acerto
        vale posição 1, senão o MRR puniria a resposta correta.
        """
        if self.pergunta.espera_ausencia:
            return 1 if not self.recuperados else None
        for posicao, identificador in enumerate(self.recuperados, start=1):
            if identificador in self.pergunta.aceitaveis:
                return posicao
        return None

    def acertou_ate(self, profundidade: int) -> bool:
        posicao = self.posicao_do_acerto
        return posicao is not None and posicao <= profundidade

    @property
    def reciproco(self) -> float:
        posicao = self.posicao_do_acerto
        return 1.0 / posicao if posicao else 0.0


@dataclass
class Metricas:
    total: int
    recall: dict[int, float]
    mrr: float

    def como_dicionario(self) -> dict[str, Any]:
        return {
            "total": self.total,
            **{f"recall@{p}": round(v, 4) for p, v in self.recall.items()},
            "mrr": round(self.mrr, 4),
        }


def medir(avaliadas: Iterable[Avaliada]) -> Metricas:
    itens = list(avaliadas)
    if not itens:
        return Metricas(0, {p: 0.0 for p in PROFUNDIDADES}, 0.0)
    return Metricas(
        total=len(itens),
        recall={
            profundidade: sum(a.acertou_ate(profundidade) for a in itens) / len(itens)
            for profundidade in PROFUNDIDADES
        },
        mrr=statistics.fmean(a.reciproco for a in itens),
    )


def avaliar(
    conexao: sqlite3.Connection,
    perguntas: list[Pergunta],
    buscar: Callable[[sqlite3.Connection, str, int], list[Any]] | None = None,
) -> list[Avaliada]:
    """Roda a recuperação para cada pergunta. Determinística por construção.

    `buscar` escolhe qual recuperação é avaliada; o padrão é a léxica. As duas
    devolvem o mesmo formato, então o resto da avaliação não sabe qual rodou —
    e é isso que torna os números comparáveis.
    """
    buscar = buscar or busca.buscar
    avaliadas: list[Avaliada] = []
    for pergunta in perguntas:
        resultados = buscar(conexao, pergunta.texto, LIMITE_BUSCA)
        avaliadas.append(
            Avaliada(
                pergunta=pergunta,
                recuperados=[r.nome for r in resultados],
                titulos=[r.titulo or r.nome for r in resultados],
            )
        )
    return avaliadas


def por_segmento(avaliadas: list[Avaliada], campo: str) -> dict[str, Metricas]:
    grupos: dict[str, list[Avaliada]] = {}
    for a in avaliadas:
        grupos.setdefault(getattr(a.pergunta, campo), []).append(a)
    return {chave: medir(itens) for chave, itens in sorted(grupos.items())}


# --- anotações quebradas -------------------------------------------------


def anotacoes_ausentes(conexao: sqlite3.Connection, perguntas: list[Pergunta]) -> list[str]:
    """Slugs anotados que não existem no banco.

    Anotação quebrada mede recall baixo por erro de digitação, não por falha da
    busca — o diagnóstico precisa distinguir as duas coisas.
    """
    citados = {s for p in perguntas for s in p.aceitaveis}
    if not citados:
        return []
    existentes = {
        linha[0]
        for linha in conexao.execute(
            "SELECT c.nome FROM conjunto c JOIN ficha f ON f.conjunto_id = c.id"
        )
    }
    return sorted(citados - existentes)


# --- histórico -----------------------------------------------------------


def ler_ultima(caminho: Path, recuperacao: str | None = None) -> dict[str, Any] | None:
    """A execução mais recente — da mesma recuperação, quando indicada.

    Comparar a semântica com a última léxica acusaria regressão, ou melhora,
    que é só diferença de método. Cada recuperação se compara consigo mesma.
    Registros de antes de haver mais de uma são léxicos.
    """
    if not caminho.is_file():
        return None
    ultima = None
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            registro = json.loads(linha)
        except ValueError:
            continue
        if recuperacao and registro.get("recuperacao", "lexica") != recuperacao:
            continue
        ultima = registro
    return ultima


def gravar_execucao(caminho: Path, registro: dict[str, Any]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def versao_da_recuperacao(
    conexao: sqlite3.Connection, recuperacao: str = "lexica", indice: Any = None
) -> dict[str, Any]:
    """O que identifica a recuperação avaliada, para o histórico ser comparável."""
    fichas = conexao.execute("SELECT count(*) FROM ficha").fetchone()[0]
    modelos = sorted(
        linha[0] for linha in conexao.execute("SELECT DISTINCT modelo FROM ficha")
    )
    versao: dict[str, Any] = {
        "recuperacao": recuperacao,
        "fichas": fichas,
        "modelos": modelos,
    }
    if recuperacao in ("semantica", "hibrida") and indice is not None:
        versao["modelo_embedding"] = indice.modelo
        versao["versao_vetores"] = indice.versao[:16]
    if recuperacao in ("lexica", "hibrida"):
        versao["pesos"] = busca.pesos()
        versao["fatores"] = busca.fatores()
    if recuperacao == "hibrida":
        import fusao

        versao["rrf_k"] = fusao.rrf_k()
        versao["profundidade"] = fusao.profundidade()
    return versao


# --- relatório -----------------------------------------------------------


def _linha_metricas(rotulo: str, m: Metricas) -> str:
    return (
        f"  {rotulo:<16} n={m.total:<4} "
        f"recall@5 {m.recall[5]:6.1%}   recall@10 {m.recall[10]:6.1%}   "
        f"MRR {m.mrr:.3f}"
    )


def imprimir_relatorio(
    avaliadas: list[Avaliada],
    geral: Metricas,
    anterior: dict[str, Any] | None,
    recuperacao: str = "lexica",
) -> None:
    log("")
    log("relatório de avaliação da recuperação")
    log(f"  recuperação:      {recuperacao}")
    log(f"  perguntas:        {geral.total}")
    ausencia = [a for a in avaliadas if a.pergunta.espera_ausencia]
    if ausencia:
        acertos = sum(a.acertou_ate(5) for a in ausencia)
        log(f"  de ausência:      {len(ausencia)} ({acertos} acertadas)")
    log("")
    log(_linha_metricas("GERAL", geral))

    log("")
    log("  por dificuldade")
    for chave, m in por_segmento(avaliadas, "dificuldade").items():
        log(_linha_metricas(chave, m))

    log("")
    log("  por tema")
    for chave, m in por_segmento(avaliadas, "tema").items():
        log(_linha_metricas(chave, m))

    falhas = [a for a in avaliadas if not a.acertou_ate(max(PROFUNDIDADES))]
    if falhas:
        log("")
        log(f"  perguntas que falharam ({len(falhas)})")
        for a in falhas:
            esperado = "nenhum resultado" if a.pergunta.espera_ausencia else ", ".join(
                a.pergunta.aceitaveis
            )
            log(f"    · {a.pergunta.texto}")
            log(f"      esperado: {esperado}")
            if a.recuperados:
                for posicao, (slug, titulo) in enumerate(
                    zip(a.recuperados[:5], a.titulos[:5]), start=1
                ):
                    log(f"      {posicao}. {slug}  —  {titulo[:52]}")
            else:
                log("      (a busca não retornou nada)")

    if anterior:
        delta = geral.recall[5] - anterior.get("recall@5", 0.0)
        sinal = "+" if delta >= 0 else ""
        log("")
        log(f"  execução anterior: recall@5 {anterior.get('recall@5', 0.0):.1%} "
            f"em {anterior.get('quando', '?')}")
        log(f"  variação:          {sinal}{delta:.1%}")
        if delta > 0:
            log("  melhorou.")
    else:
        log("")
        log("  primeira execução: esta é a linha de base.")


# --- interface de linha de comando --------------------------------------

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    perguntas: Path = typer.Option(
        ARQUIVO_PERGUNTAS, "--perguntas", help="CSV do conjunto de avaliação."
    ),
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
    historico: Path = typer.Option(
        ARQUIVO_HISTORICO, "--historico", help="JSONL com o histórico de execuções."
    ),
    limiar: float = typer.Option(
        LIMIAR_REGRESSAO, "--limiar", help="Queda de recall@5 tolerada."
    ),
    registrar: bool = typer.Option(
        True, "--registrar/--sem-registrar", help="Acrescenta ao histórico."
    ),
    recuperacao: str = typer.Option(
        "lexica", "--recuperacao", help="Qual recuperação avaliar: lexica ou semantica."
    ),
) -> None:
    """Mede recall@5, recall@10 e MRR da recuperação."""
    if recuperacao not in RECUPERACOES:
        log(f"recuperação desconhecida: {recuperacao!r}. Conhecidas: {', '.join(RECUPERACOES)}")
        raise typer.Exit(code=2)
    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        raise typer.Exit(code=2)
    if not perguntas.is_file():
        log(f"conjunto de avaliação não encontrado: {perguntas}")
        raise typer.Exit(code=2)

    conexao = busca.abrir_banco(banco)
    try:
        if not busca.indice_existe(conexao):
            log("índice não encontrado; rode antes: uv run python indexa.py")
            raise typer.Exit(code=2)
        lista = ler_perguntas(perguntas)
        if not lista:
            log("nenhuma pergunta no conjunto de avaliação")
            raise typer.Exit(code=2)

        # Anotação que não resolve mede recall baixo por erro de digitação, não
        # por falha da busca, e o número sai com cara de regressão real. Antes
        # isto só aparecia no fim do relatório, depois de o número contaminado
        # já estar no histórico — e a planilha corrompeu os mesmos slugs quatro
        # vezes. Conferir antes de medir é o que impede isso.
        quebradas = anotacoes_ausentes(conexao, lista)
        if quebradas:
            log(f"{len(quebradas)} anotação(ões) em {perguntas.name} não existem no banco:")
            for slug in quebradas:
                log(f"  · {slug}")
            log("")
            log("a avaliação não roda com anotação quebrada: o número mediria erro de")
            log("digitação, não a busca, e nada é gravado no histórico. Confira")
            log("maiúsculas, hífens duplos e prefixos colados — ver avaliacao/README.md.")
            raise typer.Exit(code=2)
        buscar: Callable[[sqlite3.Connection, str, int], list[Any]] | None = None
        indice: Any = None
        if recuperacao in ("semantica", "hibrida"):
            # Import tardio: a avaliação léxica não deve pagar a carga do numpy,
            # e muito menos a do modelo.
            import embeddings
            import fusao
            import semantica

            try:
                indice = semantica.carregar(conexao)
            except semantica.IndiceInconsistente as erro:
                log(str(erro))
                raise typer.Exit(code=2)
            vetorizador = embeddings.Vetorizador()

            def _semantica(con: sqlite3.Connection, texto: str, limite: int) -> list[Any]:
                return semantica.buscar(con, indice, vetorizador, texto, limite)

            def _hibrida(con: sqlite3.Connection, texto: str, limite: int) -> list[Any]:
                return fusao.buscar(
                    con, texto, limite, lexica=busca.buscar, semantica=_semantica
                )

            buscar = _semantica if recuperacao == "semantica" else _hibrida

        avaliadas = avaliar(conexao, lista, buscar)
        geral = medir(avaliadas)
        versao = versao_da_recuperacao(conexao, recuperacao, indice)
    finally:
        conexao.close()

    anterior = ler_ultima(historico, recuperacao)
    imprimir_relatorio(avaliadas, geral, anterior, recuperacao)

    if registrar:
        gravar_execucao(
            historico,
            {"quando": agora_utc(), **versao, **geral.como_dicionario()},
        )

    if anterior is not None:
        queda = anterior.get("recall@5", 0.0) - geral.recall[5]
        if queda > limiar:
            log("")
            log(f"REGRESSÃO: recall@5 caiu {queda:.1%}, acima do limiar de {limiar:.1%}")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
