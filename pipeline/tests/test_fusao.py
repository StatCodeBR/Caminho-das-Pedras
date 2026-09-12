"""Testes da fusão por posição.

Nada aqui toca banco nem modelo: a fusão é função pura sobre rankings já
ordenados, e os rankings são listas de objetos com os campos que ela lê. O que
se verifica é o contrato — soma das contribuições, vantagem da concordância,
independência de escala, determinismo e resiliência.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import fusao


@dataclass
class Item:
    conjunto_id: str
    pontuacao: float = 0.0
    nome: str = ""
    titulo: str = ""
    organizacao: str = ""
    confianca: str = "alta"
    resumo: str = ""


def r(*ids: str, pontuacao: float = 1.0) -> list[Item]:
    return [Item(conjunto_id=i, nome=f"conjunto-{i}", pontuacao=pontuacao) for i in ids]


# --- RRF -----------------------------------------------------------------


def test_soma_as_contribuicoes_dos_dois_rankings():
    fundidos = fusao.fundir({"lexica": r("a"), "semantica": r("a")}, limite=5, k=60)
    assert len(fundidos) == 1
    assert fundidos[0].pontuacao == pytest.approx(2 / 61)


def test_concordancia_vence_primeiro_lugar_isolado():
    # `b` é terceiro nos dois; `a` é primeiro em um só. 2/63 > 1/61.
    fundidos = fusao.fundir(
        {"lexica": r("a", "x", "b"), "semantica": r("y", "z", "b")}, limite=5, k=60
    )
    assert [f.conjunto_id for f in fundidos][:2] == ["b", "a"]


def test_a_escala_das_pontuacoes_nao_influi():
    # Mesmas ordens, pontuações de magnitudes absurdamente diferentes.
    pequenas = {"lexica": r("a", "b", pontuacao=0.001), "semantica": r("b", "a", pontuacao=0.002)}
    enormes = {"lexica": r("a", "b", pontuacao=9_999.0), "semantica": r("b", "a", pontuacao=42.0)}
    assert [f.conjunto_id for f in fusao.fundir(pequenas, 5, 60)] == [
        f.conjunto_id for f in fusao.fundir(enormes, 5, 60)
    ]


def test_k_maior_achata_as_diferencas():
    poucos = fusao.fundir({"lexica": r("a", "b")}, 5, k=1)
    muitos = fusao.fundir({"lexica": r("a", "b")}, 5, k=1000)
    assert poucos[0].pontuacao - poucos[1].pontuacao > muitos[0].pontuacao - muitos[1].pontuacao


# --- determinismo --------------------------------------------------------


def test_empate_desempata_por_identificador():
    # `b` e `a` empatam: cada um é primeiro em um ranking.
    fundidos = fusao.fundir({"lexica": r("b"), "semantica": r("a")}, 5, 60)
    assert [f.conjunto_id for f in fundidos] == ["a", "b"]
    assert fundidos[0].pontuacao == pytest.approx(fundidos[1].pontuacao)


def test_ordem_de_chegada_dos_rankings_nao_altera_o_resultado():
    """As buscas rodam em paralelo no serviço; qual termina antes não pode contar."""
    um = fusao.fundir({"lexica": r("a", "b"), "semantica": r("b", "c")}, 5, 60)
    outro = fusao.fundir({"semantica": r("b", "c"), "lexica": r("a", "b")}, 5, 60)
    assert [f.conjunto_id for f in um] == [f.conjunto_id for f in outro]
    assert [f.pontuacao for f in um] == [f.pontuacao for f in outro]


def test_posicoes_sao_sequenciais_a_partir_de_um():
    fundidos = fusao.fundir({"lexica": r("a", "b", "c")}, limite=2, k=60)
    assert [f.posicao for f in fundidos] == [1, 2]


# --- proveniência --------------------------------------------------------


def test_proveniencia_traz_ranking_e_posicao():
    fundidos = fusao.fundir(
        {"lexica": r("x", "a"), "semantica": r("a", "y")}, limite=5, k=60
    )
    primeiro = next(f for f in fundidos if f.conjunto_id == "a")
    assert primeiro.origens == {"lexica": 2, "semantica": 1}
    assert primeiro.rankings == ["lexica", "semantica"]


def test_proveniencia_de_quem_veio_de_um_ranking_so():
    fundidos = fusao.fundir({"lexica": r("a"), "semantica": r("b")}, limite=5, k=60)
    assert next(f for f in fundidos if f.conjunto_id == "b").rankings == ["semantica"]


def test_pontuacao_de_cada_ranking_e_preservada():
    # O RRF não usa estas pontuações, mas o roteamento precisa delas: a escala
    # do RRF não diz nada sobre pertinência.
    rankings = {"lexica": r("a", pontuacao=23.6), "semantica": r("a", pontuacao=0.87)}
    fundido = fusao.fundir(rankings, 5, 60)[0]
    assert fundido.pontuacoes == {"lexica": pytest.approx(23.6), "semantica": pytest.approx(0.87)}


# --- orquestração e resiliência -----------------------------------------


def _lexica(_con, _consulta, limite):
    return r("a", "b")[:limite]


def _semantica(_con, _consulta, limite):
    return r("b", "c")[:limite]


def _explode(_con, _consulta, _limite):
    raise RuntimeError("índice indisponível")


def test_busca_funde_os_dois_rankings():
    fundidos = fusao.buscar(None, "pergunta", 5, lexica=_lexica, semantica=_semantica)
    assert [f.conjunto_id for f in fundidos] == ["b", "a", "c"]


def test_falha_da_semantica_degrada_para_lexica(capsys):
    registros: list[str] = []
    fundidos = fusao.buscar(
        None, "p", 5, lexica=_lexica, semantica=_explode, registrar=registros.append
    )
    assert [f.conjunto_id for f in fundidos] == ["a", "b"]
    assert any("semantica" in m for m in registros)


def test_falha_da_lexica_degrada_para_semantica():
    registros: list[str] = []
    fundidos = fusao.buscar(
        None, "p", 5, lexica=_explode, semantica=_semantica, registrar=registros.append
    )
    assert [f.conjunto_id for f in fundidos] == ["b", "c"]
    assert any("lexica" in m for m in registros)


def test_falha_dos_dois_retorna_vazio_sem_erguer():
    registros: list[str] = []
    assert fusao.buscar(
        None, "p", 5, lexica=_explode, semantica=_explode, registrar=registros.append
    ) == []
    assert any("nenhum ranking" in m for m in registros)


def test_sem_semantica_configurada_usa_so_a_lexica():
    fundidos = fusao.buscar(None, "p", 5, lexica=_lexica, semantica=None)
    assert [f.conjunto_id for f in fundidos] == ["a", "b"]


def test_profundidade_pedida_e_maior_que_o_retorno():
    pedidos: list[int] = []

    def espiao(_con, _consulta, limite):
        pedidos.append(limite)
        return r("a", "b", "c")

    fusao.buscar(None, "p", 2, lexica=espiao, profundidade_candidatos=40)
    assert pedidos == [40]


def test_profundidade_nunca_menor_que_o_limite():
    pedidos: list[int] = []

    def espiao(_con, _consulta, limite):
        pedidos.append(limite)
        return r("a")

    fusao.buscar(None, "p", 10, lexica=espiao, profundidade_candidatos=3)
    assert pedidos == [10]


def test_parametros_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("RRF_K", "10")
    monkeypatch.setenv("PROFUNDIDADE_BUSCA", "7")
    assert fusao.rrf_k() == 10.0
    assert fusao.profundidade() == 7
    assert fusao.fundir({"lexica": r("a")}, 5)[0].pontuacao == pytest.approx(1 / 11)
