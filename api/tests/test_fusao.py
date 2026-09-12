"""Testes da fusão no serviço.

Nada aqui toca banco nem modelo: os rankings são listas de `Recuperado`
montadas à mão. O que se verifica é o contrato — soma das contribuições,
vantagem da concordância, determinismo, proveniência e resiliência —, e que as
duas buscas de fato rodam em paralelo.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app import fusao
from app.recuperacao import Recuperado

K = 60.0


def r(*ids: str, pontuacao: float = 1.0) -> list[Recuperado]:
    return [
        Recuperado(
            conjunto_id=i,
            posicao=posicao,
            pontuacao=pontuacao,
            nome=f"conjunto-{i}",
            titulo=f"Conjunto {i}",
            organizacao="orgao",
            confianca="alta",
            resumo="",
        )
        for posicao, i in enumerate(ids, start=1)
    ]


# --- RRF -----------------------------------------------------------------


def test_soma_as_contribuicoes_dos_dois_rankings():
    fundidos = fusao.fundir({"lexica": r("a"), "semantica": r("a")}, 5, K)
    assert len(fundidos) == 1
    assert fundidos[0].pontuacao == pytest.approx(2 / 61)


def test_concordancia_vence_primeiro_lugar_isolado():
    fundidos = fusao.fundir(
        {"lexica": r("a", "x", "b"), "semantica": r("y", "z", "b")}, 5, K
    )
    assert [f.conjunto_id for f in fundidos][:2] == ["b", "a"]


def test_posicoes_sao_reescritas_pela_fusao():
    fundidos = fusao.fundir({"lexica": r("a", "b", "c")}, limite=2, k=K)
    assert [f.posicao for f in fundidos] == [1, 2]


def test_empate_desempata_por_identificador():
    fundidos = fusao.fundir({"lexica": r("b"), "semantica": r("a")}, 5, K)
    assert [f.conjunto_id for f in fundidos] == ["a", "b"]


def test_ordem_de_chegada_nao_altera_o_resultado():
    um = fusao.fundir({"lexica": r("a", "b"), "semantica": r("b", "c")}, 5, K)
    outro = fusao.fundir({"semantica": r("b", "c"), "lexica": r("a", "b")}, 5, K)
    assert [f.conjunto_id for f in um] == [f.conjunto_id for f in outro]


# --- proveniência --------------------------------------------------------


def test_proveniencia_traz_ranking_posicao_e_pontuacao():
    rankings = {
        "lexica": r("x") + r("a", pontuacao=23.6),
        "semantica": r("a", pontuacao=0.87),
    }
    # A segunda lista de `r` recomeça a numeração, então ajusto a posição.
    rankings["lexica"][1].posicao = 2
    fundidos = fusao.fundir(rankings, 5, K)
    primeiro = next(f for f in fundidos if f.conjunto_id == "a")
    assert primeiro.origens == {"lexica": 2, "semantica": 1}
    assert primeiro.pontuacoes["lexica"] == pytest.approx(23.6)
    assert primeiro.pontuacoes["semantica"] == pytest.approx(0.87)


def test_resultado_de_um_ranking_so_registra_so_ele():
    fundidos = fusao.fundir({"lexica": r("a"), "semantica": r("b")}, 5, K)
    assert next(f for f in fundidos if f.conjunto_id == "b").origens == {"semantica": 1}


def test_a_pontuacao_final_e_a_do_rrf_nao_a_do_ranking():
    """A escala do RRF não diz nada sobre pertinência, e quem roteia precisa saber."""
    fundidos = fusao.fundir({"lexica": r("a", pontuacao=23.6)}, 5, K)
    assert fundidos[0].pontuacao == pytest.approx(1 / 61)
    assert fundidos[0].pontuacoes["lexica"] == pytest.approx(23.6)


# --- orquestração --------------------------------------------------------


def _lexica(limite):
    return r("a", "b")[:limite]


def _semantica(limite):
    return r("b", "c")[:limite]


def _explode(_limite):
    raise RuntimeError("índice indisponível")


async def test_funde_os_dois_rankings():
    fundidos = await fusao.buscar(
        "p", 5, lexica=_lexica, semantica=_semantica, profundidade=50, k=K
    )
    assert [f.conjunto_id for f in fundidos] == ["b", "a", "c"]


async def test_falha_da_semantica_degrada_para_lexica():
    registros: list[str] = []
    fundidos = await fusao.buscar(
        "p", 5, lexica=_lexica, semantica=_explode, profundidade=50, k=K,
        registrar=lambda nome, erro: registros.append(nome),
    )
    assert [f.conjunto_id for f in fundidos] == ["a", "b"]
    assert registros == ["semantica"]


async def test_falha_da_lexica_degrada_para_semantica():
    registros: list[str] = []
    fundidos = await fusao.buscar(
        "p", 5, lexica=_explode, semantica=_semantica, profundidade=50, k=K,
        registrar=lambda nome, erro: registros.append(nome),
    )
    assert [f.conjunto_id for f in fundidos] == ["b", "c"]
    assert registros == ["lexica"]


async def test_falha_dos_dois_retorna_vazio_sem_erguer():
    registros: list[str] = []
    fundidos = await fusao.buscar(
        "p", 5, lexica=_explode, semantica=_explode, profundidade=50, k=K,
        registrar=lambda nome, erro: registros.append(nome),
    )
    assert fundidos == []
    assert sorted(registros) == ["lexica", "semantica"]


async def test_profundidade_pedida_e_maior_que_o_retorno():
    pedidos: list[int] = []

    def espiao(limite):
        pedidos.append(limite)
        return r("a")

    await fusao.buscar("p", 2, lexica=espiao, semantica=None, profundidade=40, k=K)
    assert pedidos == [40]


async def test_profundidade_nunca_menor_que_o_limite():
    pedidos: list[int] = []

    def espiao(limite):
        pedidos.append(limite)
        return r("a")

    await fusao.buscar("p", 10, lexica=espiao, semantica=None, profundidade=3, k=K)
    assert pedidos == [10]


async def test_as_duas_buscas_rodam_em_paralelo():
    """Sequencial custaria a soma; em paralelo, pouco mais que a mais lenta."""
    def devagar(ids):
        def buscar(limite):
            time.sleep(0.30)
            return r(*ids)
        return buscar

    inicio = time.perf_counter()
    await fusao.buscar(
        "p", 5, lexica=devagar(("a",)), semantica=devagar(("b",)),
        profundidade=50, k=K,
    )
    assert time.perf_counter() - inicio < 0.55
