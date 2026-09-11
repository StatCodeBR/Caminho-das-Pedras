"""Testes do núcleo de recuperação da api.

Este módulo é porta do `pipeline/busca.py`, e a duplicação está registrada como
dívida. Enquanto ela existir, o que importa testar aqui é que os dois lados
concordam: se divergirem, a produção recupera diferente do que a avaliação mede,
e essa falha não dá alarme nenhum.
"""

from __future__ import annotations

import sqlite3

import pytest

from app import recuperacao


def montar_indice(caminho, fichas):
    """Só o índice: é tudo que o filtro de termo comum consulta."""
    con = sqlite3.connect(caminho)
    con.executescript(
        """
        CREATE VIRTUAL TABLE ficha_fts USING fts5(
            conjunto_id UNINDEXED, nome, perguntas, resumo, orgao, tags,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )
    con.executemany(
        "INSERT INTO ficha_fts (conjunto_id,nome,perguntas,resumo,orgao,tags)"
        " VALUES (?,?,?,?,?,?)",
        [
            (
                f["id"],
                f.get("nome", ""),
                " ".join(f.get("perguntas", [])),
                f.get("resumo", ""),
                f.get("orgao", ""),
                " ".join(f.get("tags", [])),
            )
            for f in fichas
        ],
    )
    con.commit()
    return con


@pytest.fixture
def indice_com_tema_carimbado(tmp_path):
    """60 fichas com o mesmo rótulo de tema; o assunto real em duas delas.

    Reproduz o defeito medido no catálogo completo: `financas` aparecia em 40,2%
    das fichas com 100% dessas ocorrências vindas da coluna de tags.
    """
    fichas = [
        {
            "id": str(i),
            "nome": f"conjunto-{i}",
            "resumo": f"Registro do assunto {i}.",
            "perguntas": [f"onde acho o assunto {i}?"],
            "tags": ["economia"],
        }
        for i in range(60)
    ]
    fichas[0]["resumo"] = "Series de economia do banco central."
    fichas[1]["perguntas"] = ["como anda a economia?"]
    con = montar_indice(tmp_path / "dados.db", fichas)
    con.row_factory = sqlite3.Row
    yield con
    con.close()


def test_rotulo_de_tema_nao_torna_o_termo_comum(indice_com_tema_carimbado):
    # Em 60 de 60 fichas pela tag, em 2 pelo texto natural. Vale o texto.
    assert recuperacao.frequencia(indice_com_tema_carimbado, "economia") == 2
    assert recuperacao.descartar_comuns(
        indice_com_tema_carimbado, ["onde", "economia"]
    ) == ["economia"]


def test_termo_comum_no_texto_natural_continua_descartado(indice_com_tema_carimbado):
    # "assunto" está no resumo das 60: comum de verdade, e some da consulta.
    assert "assunto" not in recuperacao.descartar_comuns(
        indice_com_tema_carimbado, ["assunto", "economia"]
    )


def test_tag_continua_casando_no_indice(indice_com_tema_carimbado):
    # Excluir a coluna da *medição* não pode excluí-la da *recuperação*.
    total = indice_com_tema_carimbado.execute(
        "SELECT count(*) FROM ficha_fts WHERE ficha_fts MATCH ?", ('"economia"',)
    ).fetchone()[0]
    assert total == 60


def test_filtro_desligado_em_indice_pequeno(tmp_path):
    # Com 3 fichas, "aparece em 33%" não é evidência de termo comum.
    con = montar_indice(
        tmp_path / "d.db",
        [{"id": str(i), "resumo": "dados dados"} for i in range(3)],
    )
    try:
        assert recuperacao.descartar_comuns(con, ["dados", "creche"]) == [
            "dados",
            "creche",
        ]
    finally:
        con.close()
