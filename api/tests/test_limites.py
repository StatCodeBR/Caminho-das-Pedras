"""Testes da contenção de consumo."""

from __future__ import annotations

import time

import pytest

from app.limites import Contencao, dia_utc


@pytest.fixture
def contencao(tmp_path):
    c = Contencao(
        tmp_path / "consumo.db", teto_diario=3, maximo_por_origem=2, janela_s=3600
    )
    yield c
    c.fechar()


# --- teto diário ---------------------------------------------------------


def test_teto_nao_recusa_ninguem(contencao):
    """A regra central: estourar o teto nunca produz erro."""
    for _ in range(3):
        contencao.registrar_chamada()
    assert contencao.em_modo_reduzido()
    v = contencao.avaliar("1.2.3.4")
    assert v.permitida is True
    assert v.reduzido is True


def test_abaixo_do_teto_nao_reduz(contencao):
    contencao.registrar_chamada()
    v = contencao.avaliar("1.2.3.4")
    assert v.permitida and not v.reduzido


def test_contagem_acumula(contencao):
    assert contencao.registrar_chamada() == 1
    assert contencao.registrar_chamada() == 2
    assert contencao.consumo_do_dia() == 2


def test_consumo_sobrevive_a_reinicio(tmp_path):
    caminho = tmp_path / "consumo.db"
    a = Contencao(caminho, teto_diario=10, maximo_por_origem=99, janela_s=60)
    a.registrar_chamada()
    a.registrar_chamada()
    a.fechar()
    # Um contador em memória zeraria aqui, e um teto que se apaga a cada deploy
    # não é teto.
    b = Contencao(caminho, teto_diario=10, maximo_por_origem=99, janela_s=60)
    try:
        assert b.consumo_do_dia() == 2
    finally:
        b.fechar()


def test_dia_em_utc():
    assert len(dia_utc()) == 10 and dia_utc().count("-") == 2


def test_contador_e_por_dia(contencao):
    contencao.registrar_chamada()
    outro = contencao._conexao
    outro.execute(
        "INSERT INTO consumo_diario (dia, chamadas) VALUES ('2000-01-01', 99)"
    )
    outro.commit()
    # O dia antigo não contamina o corrente.
    assert contencao.consumo_do_dia() == 1


# --- limite por origem ---------------------------------------------------


def test_origem_dentro_do_limite_passa(contencao):
    assert contencao.avaliar("1.2.3.4").permitida
    assert contencao.avaliar("1.2.3.4").permitida


def test_origem_acima_do_limite_e_recusada(contencao):
    contencao.avaliar("1.2.3.4")
    contencao.avaliar("1.2.3.4")
    v = contencao.avaliar("1.2.3.4")
    assert v.permitida is False
    assert v.espera_s > 0


def test_origens_diferentes_nao_se_afetam(contencao):
    contencao.avaliar("1.1.1.1")
    contencao.avaliar("1.1.1.1")
    assert not contencao.avaliar("1.1.1.1").permitida
    assert contencao.avaliar("2.2.2.2").permitida


def test_janela_desliza(tmp_path):
    c = Contencao(tmp_path / "c.db", teto_diario=99, maximo_por_origem=2, janela_s=1)
    try:
        c.avaliar("1.2.3.4")
        c.avaliar("1.2.3.4")
        assert not c.avaliar("1.2.3.4").permitida
        time.sleep(1.1)
        # Passada a janela, a origem volta a ser atendida sem intervenção.
        assert c.avaliar("1.2.3.4").permitida
    finally:
        c.fechar()


def test_poda_remove_requisicoes_velhas(tmp_path):
    c = Contencao(tmp_path / "c.db", teto_diario=99, maximo_por_origem=99, janela_s=1)
    try:
        c.avaliar("1.2.3.4")
        time.sleep(1.1)
        c.avaliar("1.2.3.4")
        n = c._conexao.execute("SELECT count(*) FROM requisicao").fetchone()[0]
        # Sem poda a tabela cresceria para sempre guardando janelas passadas.
        assert n == 1
    finally:
        c.fechar()


def test_recusa_por_origem_nao_e_afetada_pelo_teto(contencao):
    """Os dois limites são independentes: um reduz, o outro recusa."""
    for _ in range(3):
        contencao.registrar_chamada()
    contencao.avaliar("9.9.9.9")
    contencao.avaliar("9.9.9.9")
    v = contencao.avaliar("9.9.9.9")
    assert v.permitida is False  # recusa vem da origem
    assert contencao.em_modo_reduzido()  # e o teto está estourado ao mesmo tempo


# --- operação ------------------------------------------------------------


def test_estado_para_operacao(contencao):
    contencao.registrar_chamada()
    e = contencao.estado()
    assert e["consumo"] == 1
    assert e["teto"] == 3
    assert e["restante"] == 2
    assert e["modo_reduzido"] is False
    assert e["limite_por_origem"] == 2


def test_estado_marca_modo_reduzido(contencao):
    for _ in range(3):
        contencao.registrar_chamada()
    e = contencao.estado()
    assert e["modo_reduzido"] is True
    assert e["restante"] == 0
