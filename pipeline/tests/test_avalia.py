"""Testes da avaliação da recuperação."""

from __future__ import annotations

import json

import pytest

import avalia
from avalia import Avaliada, Pergunta


def p(texto="q", aceitaveis=(), tema="t", dificuldade="media"):
    return Pergunta(texto, list(aceitaveis), tema, dificuldade)


# --- leitura do conjunto -------------------------------------------------


def test_nenhum_nao_vira_identificador():
    assert avalia._identificadores("nenhum") == []
    assert avalia._identificadores("NENHUM") == []
    assert avalia._identificadores(" Nenhum ") == []


def test_identificadores_separados_por_ponto_e_virgula_ou_virgula():
    assert avalia._identificadores("a; b, c;") == ["a", "b", "c"]


def test_pergunta_de_ausencia_reconhecida():
    assert p(aceitaveis=[]).espera_ausencia is True
    assert p(aceitaveis=["x"]).espera_ausencia is False


def test_ler_perguntas_do_csv(tmp_path):
    arquivo = tmp_path / "perguntas.csv"
    arquivo.write_text(
        "pergunta,conjuntos_aceitaveis,tema,dificuldade\n"
        "quantos hospitais,nenhum,saude,facil\n"
        "onde tem creche,a; b,educacao,media\n",
        encoding="utf-8",
    )
    perguntas = avalia.ler_perguntas(arquivo)
    assert [q.texto for q in perguntas] == ["quantos hospitais", "onde tem creche"]
    assert perguntas[0].espera_ausencia
    assert perguntas[1].aceitaveis == ["a", "b"]


def test_nenhum_nao_conta_como_anotacao_quebrada(tmp_path):
    import busca

    caminho = tmp_path / "vazio.db"
    import sqlite3

    con = sqlite3.connect(caminho)
    con.executescript(
        "CREATE TABLE conjunto (id TEXT PRIMARY KEY, nome TEXT);"
        "CREATE TABLE ficha (conjunto_id TEXT PRIMARY KEY);"
    )
    con.commit()
    con.close()
    con = busca.abrir_banco(caminho)
    try:
        assert avalia.anotacoes_ausentes(con, [p(aceitaveis=[])]) == []
        assert avalia.anotacoes_ausentes(con, [p(aceitaveis=["sumido"])]) == ["sumido"]
    finally:
        con.close()


# --- caminho de ausência -------------------------------------------------


def test_ausencia_sem_resultado_e_acerto():
    a = Avaliada(p(aceitaveis=[]), recuperados=[])
    assert a.posicao_do_acerto == 1
    assert a.acertou_ate(5)
    assert a.reciproco == 1.0


def test_ausencia_com_resultado_e_erro():
    a = Avaliada(p(aceitaveis=[]), recuperados=["qualquer"])
    assert a.posicao_do_acerto is None
    assert not a.acertou_ate(10)
    assert a.reciproco == 0.0


# --- acerto e posição ----------------------------------------------------


def test_qualquer_conjunto_aceitavel_conta_acerto():
    a = Avaliada(p(aceitaveis=["x", "y"]), recuperados=["z", "y"])
    assert a.posicao_do_acerto == 2
    assert a.acertou_ate(5)


def test_acerto_fora_da_profundidade_nao_conta():
    recuperados = [f"r{i}" for i in range(9)] + ["alvo"]
    a = Avaliada(p(aceitaveis=["alvo"]), recuperados=recuperados)
    assert a.posicao_do_acerto == 10
    assert not a.acertou_ate(5)
    assert a.acertou_ate(10)


def test_reciproco_reflete_a_posicao():
    assert Avaliada(p(aceitaveis=["a"]), ["a"]).reciproco == 1.0
    assert Avaliada(p(aceitaveis=["a"]), ["x", "a"]).reciproco == 0.5


# --- métricas ------------------------------------------------------------


def test_metricas_agregadas():
    itens = [
        Avaliada(p(aceitaveis=["a"]), ["a"]),
        Avaliada(p(aceitaveis=["b"]), ["x", "y", "z", "w", "v", "b"]),
        Avaliada(p(aceitaveis=["c"]), ["x"]),
    ]
    m = avalia.medir(itens)
    assert m.total == 3
    assert m.recall[5] == pytest.approx(1 / 3)
    assert m.recall[10] == pytest.approx(2 / 3)
    assert m.mrr == pytest.approx((1.0 + 1 / 6 + 0.0) / 3)


def test_metricas_de_lista_vazia_nao_dividem_por_zero():
    m = avalia.medir([])
    assert m.total == 0 and m.mrr == 0.0 and m.recall[5] == 0.0


def test_ordem_das_perguntas_nao_altera_agregado():
    itens = [
        Avaliada(p(aceitaveis=["a"]), ["a"]),
        Avaliada(p(aceitaveis=["b"]), ["x"]),
        Avaliada(p(aceitaveis=[]), []),
    ]
    assert avalia.medir(itens).como_dicionario() == avalia.medir(
        list(reversed(itens))
    ).como_dicionario()


def test_quebra_por_segmento():
    itens = [
        Avaliada(p(aceitaveis=["a"], dificuldade="facil"), ["a"]),
        Avaliada(p(aceitaveis=["b"], dificuldade="dificil"), ["x"]),
    ]
    por = avalia.por_segmento(itens, "dificuldade")
    assert por["facil"].recall[5] == 1.0
    assert por["dificil"].recall[5] == 0.0


# --- histórico -----------------------------------------------------------


def test_historico_le_a_ultima_execucao(tmp_path):
    caminho = tmp_path / "historico.jsonl"
    caminho.write_text(
        json.dumps({"quando": "a", "recall@5": 0.1}) + "\n"
        + json.dumps({"quando": "b", "recall@5": 0.7}) + "\n",
        encoding="utf-8",
    )
    assert avalia.ler_ultima(caminho)["recall@5"] == 0.7


def test_historico_inexistente_e_linha_de_base(tmp_path):
    assert avalia.ler_ultima(tmp_path / "nao-existe.jsonl") is None


def test_historico_ignora_linha_corrompida(tmp_path):
    caminho = tmp_path / "historico.jsonl"
    caminho.write_text(
        json.dumps({"recall@5": 0.5}) + "\nlixo{\n", encoding="utf-8"
    )
    assert avalia.ler_ultima(caminho)["recall@5"] == 0.5


def test_gravar_execucao_acrescenta(tmp_path):
    caminho = tmp_path / "h.jsonl"
    avalia.gravar_execucao(caminho, {"recall@5": 0.1})
    avalia.gravar_execucao(caminho, {"recall@5": 0.2})
    assert len(caminho.read_text(encoding="utf-8").strip().splitlines()) == 2
    assert avalia.ler_ultima(caminho)["recall@5"] == 0.2
