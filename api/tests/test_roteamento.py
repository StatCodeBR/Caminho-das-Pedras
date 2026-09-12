"""Testes do roteamento sobre resultados fundidos.

Depois da fusão, `pontuacao` é o valor do RRF — em torno de 0,03 — e os limiares
foram calibrados na escala do BM25. O que se verifica aqui é que o roteamento lê
a escala certa, que concordância entre rankings sustenta resposta, e que um
conjunto achado só pela semântica nunca vira resposta por template.
"""

from __future__ import annotations

from app.recuperacao import Recuperado
from app.roteamento import Origem, decidir

LIMIARES = {"limiar_template": 20.0, "margem_template": 2.0, "limiar_relevancia": 3.0}


def rec(identificador, rrf, *, lexica=None, semantica=None):
    pontuacoes = {}
    origens = {}
    if lexica is not None:
        pontuacoes["lexica"] = lexica
        origens["lexica"] = 1
    if semantica is not None:
        pontuacoes["semantica"] = semantica
        origens["semantica"] = 1
    return Recuperado(
        conjunto_id=identificador, posicao=1, pontuacao=rrf, nome=identificador,
        titulo=identificador, organizacao="orgao", confianca="alta", resumo="",
        origens=origens, pontuacoes=pontuacoes,
    )


def test_pontuacao_do_rrf_nao_e_confundida_com_a_lexica():
    """Sem isto, o RRF de 0,03 cairia abaixo do limiar e tudo viraria ausência."""
    rota = decidir([rec("a", 0.032, lexica=29.7, semantica=0.87)], **LIMIARES)
    assert rota.origem is Origem.TEMPLATE


def test_tudo_abaixo_do_limiar_lexico_e_sem_concordancia_e_ausencia():
    rota = decidir([rec("a", 0.032, lexica=1.2)], **LIMIARES)
    assert rota.origem is Origem.AUSENCIA
    assert rota.fichas == []


def test_concordancia_sustenta_resposta_com_lexica_fraca():
    # 1,2 está abaixo do limiar de relevância, mas os dois rankings concordam.
    rota = decidir([rec("a", 0.032, lexica=1.2, semantica=0.88)], **LIMIARES)
    assert rota.origem is Origem.MODELO
    assert [f.conjunto_id for f in rota.fichas] == ["a"]


def test_resultado_so_semantico_nao_sustenta_sozinho():
    """Sem pontuação léxica e sem concordância, não há evidência que sustente.

    O cosseno alto não vale como limiar: medido, ele fica entre 0,84 e 0,90 tanto
    nos acertos quanto nos erros.
    """
    rota = decidir([rec("a", 0.033, semantica=0.99)], **LIMIARES)
    assert rota.origem is Origem.AUSENCIA


def test_resultado_so_semantico_nunca_dispara_template():
    """Template afirma correspondência direta, e isso exige casamento literal."""
    fichas = [rec("a", 0.033, semantica=0.99), rec("b", 0.030, lexica=25.0)]
    assert decidir(fichas, **LIMIARES).origem is Origem.MODELO


def test_o_so_semantico_fica_fora_do_contexto():
    """Efeito colateral conhecido da regra escolhida.

    O conjunto que só a semântica encontrou não entra no contexto do modelo,
    mesmo quando a recuperação sustenta resposta por outro. É o preço de não ter
    um limiar semântico confiável; se a avaliação mostrar que isso custa acerto,
    a regra se revisita com número na mão.
    """
    fichas = [rec("a", 0.033, lexica=25.0), rec("b", 0.030, semantica=0.99)]
    rota = decidir(fichas, **LIMIARES)
    assert [f.conjunto_id for f in rota.fichas] == ["a"]


def test_margem_e_medida_na_escala_lexica():
    fichas = [rec("a", 0.033, lexica=29.0), rec("b", 0.032, lexica=28.5)]
    rota = decidir(fichas, **LIMIARES)
    # Margem de 0,5 na escala léxica: ambíguo, vai ao modelo.
    assert rota.origem is Origem.MODELO
    assert "margem" in rota.motivo


def test_sem_fusao_a_pontuacao_ja_e_a_lexica():
    """Compatibilidade: um ranking só, sem proveniência, roteia como antes."""
    sozinho = Recuperado(
        conjunto_id="a", posicao=1, pontuacao=25.0, nome="a", titulo="a",
        organizacao="o", confianca="alta", resumo="",
    )
    assert decidir([sozinho], **LIMIARES).origem is Origem.TEMPLATE


def test_fichas_relevantes_preservam_a_ordem_da_fusao():
    fichas = [rec("a", 0.033, lexica=10.0), rec("b", 0.030, lexica=25.0)]
    rota = decidir(fichas, **LIMIARES)
    assert [f.conjunto_id for f in rota.fichas] == ["a", "b"]
