"""Testes da indexação léxica e da busca."""

from __future__ import annotations

import json
import sqlite3

import pytest

import busca
import indexa


def _banco(tmp_path, fichas):
    """Um catálogo mínimo com as tabelas que o índice consome."""
    caminho = tmp_path / "dados.db"
    conexao = sqlite3.connect(caminho)
    conexao.executescript(
        """
        CREATE TABLE conjunto (
            id TEXT PRIMARY KEY, nome TEXT, titulo TEXT,
            descricao TEXT, organizacao TEXT, tags TEXT
        );
        CREATE TABLE ficha (
            conjunto_id TEXT PRIMARY KEY, resumo TEXT, perguntas_json TEXT,
            temas_json TEXT, confianca TEXT, texto_indexavel TEXT
        );
        """
    )
    for f in fichas:
        conexao.execute(
            "INSERT INTO conjunto VALUES (?,?,?,?,?,?)",
            (
                f["id"],
                f.get("nome", f["id"]),
                f.get("titulo", ""),
                f.get("descricao", ""),
                f.get("organizacao", ""),
                json.dumps(f.get("tags", []), ensure_ascii=False),
            ),
        )
        conexao.execute(
            "INSERT INTO ficha VALUES (?,?,?,?,?,?)",
            (
                f["id"],
                f.get("resumo", ""),
                json.dumps(f.get("perguntas", []), ensure_ascii=False),
                json.dumps(f.get("temas", []), ensure_ascii=False),
                f.get("confianca", "media"),
                "",
            ),
        )
    conexao.commit()
    conexao.close()
    indexa.indexar(caminho)
    return caminho


@pytest.fixture
def conexao(tmp_path):
    caminho = _banco(
        tmp_path,
        [
            {
                "id": "1",
                "nome": "estabelecimentos-de-saude",
                "titulo": "Estabelecimentos de Saúde",
                "organizacao": "ministerio-da-saude",
                "resumo": "Cadastro de hospitais e postos de saúde do país.",
                "perguntas": ["onde fica o hospital mais próximo?"],
                "confianca": "alta",
                "tags": [{"name": "saúde"}],
            },
            {
                "id": "2",
                "nome": "aerodromos-publicos",
                "titulo": "Aeródromos Públicos",
                "organizacao": "agencia-nacional-de-aviacao-civil-anac",
                "resumo": "Relação de aeródromos públicos mantida pela ANAC.",
                "perguntas": ["quais são os aeroportos do Brasil?"],
                "confianca": "alta",
            },
            {
                "id": "3",
                "nome": "creches-municipais",
                "titulo": "Creches Municipais",
                "organizacao": "prefeitura",
                "resumo": "Unidades de educação infantil do município.",
                "perguntas": ["quantas creches tem na cidade?"],
                "confianca": "baixa",
            },
        ],
    )
    conexao = busca.abrir_banco(caminho)
    yield conexao
    conexao.close()


# --- tokenização e escape ------------------------------------------------


def test_consulta_sem_acento_encontra_registro_com_acento(conexao):
    resultados = busca.buscar(conexao, "saude")
    assert [r.conjunto_id for r in resultados] == ["1"]


def test_consulta_com_acento_e_caixa_encontra_registro_sem_acento(conexao):
    resultados = busca.buscar(conexao, "AERÓDROMOS")
    assert [r.conjunto_id for r in resultados] == ["2"]


def test_aspas_desbalanceadas_nao_quebram_a_consulta(conexao):
    resultados = busca.buscar(conexao, 'creches" na cidade')
    assert [r.conjunto_id for r in resultados] == ["3"]


def test_operadores_digitados_sao_texto_comum(conexao):
    # Sem escape, `NEAR` e o asterisco seriam sintaxe e ergueriam OperationalError.
    resultados = busca.buscar(conexao, "creches AND OR NEAR * (hospital")
    assert {r.conjunto_id for r in resultados} == {"1", "3"}


def test_consulta_vazia_nao_retorna_nada_nem_erra(conexao):
    assert busca.buscar(conexao, "") == []
    assert busca.buscar(conexao, "   ") == []
    assert busca.buscar(conexao, "!!! ???") == []


def test_escapar_neutraliza_aspas_internas():
    assert busca.escapar('a"b') == '"a" OR "b"'
    assert busca.escapar("AND") == '"AND"'


# --- ranking -------------------------------------------------------------


def test_termo_em_pergunta_pesa_mais_que_em_resumo(tmp_path):
    caminho = _banco(
        tmp_path,
        [
            {"id": "p", "nome": "a", "perguntas": ["onde tem creche?"], "confianca": "alta"},
            {"id": "r", "nome": "b", "resumo": "Unidades de creche.", "confianca": "alta"},
        ],
    )
    conexao = busca.abrir_banco(caminho)
    try:
        assert [r.conjunto_id for r in busca.buscar(conexao, "creche")] == ["p", "r"]
    finally:
        conexao.close()


def test_pesos_configuraveis_sem_alterar_codigo(tmp_path, monkeypatch):
    caminho = _banco(
        tmp_path,
        [
            {"id": "p", "nome": "a", "perguntas": ["onde tem creche?"], "confianca": "alta"},
            {"id": "r", "nome": "b", "resumo": "Unidades de creche.", "confianca": "alta"},
        ],
    )
    monkeypatch.setenv("BUSCA_PESO_PERGUNTAS", "0.1")
    monkeypatch.setenv("BUSCA_PESO_RESUMO", "9.0")
    conexao = busca.abrir_banco(caminho)
    try:
        assert [r.conjunto_id for r in busca.buscar(conexao, "creche")] == ["r", "p"]
    finally:
        conexao.close()


def test_confianca_alta_vence_empate_com_baixa(tmp_path):
    caminho = _banco(
        tmp_path,
        [
            {"id": "baixa", "nome": "a", "resumo": "creche", "confianca": "baixa"},
            {"id": "alta", "nome": "b", "resumo": "creche", "confianca": "alta"},
        ],
    )
    conexao = busca.abrir_banco(caminho)
    try:
        resultados = busca.buscar(conexao, "creche")
        assert [r.conjunto_id for r in resultados] == ["alta", "baixa"]
        # Penalizada, não excluída: a bruta permanece comparável.
        assert resultados[1].pontuacao < resultados[1].pontuacao_bruta
    finally:
        conexao.close()


def test_ficha_de_baixa_confianca_continua_recuperavel(conexao):
    resultados = busca.buscar(conexao, "creches")
    assert [r.conjunto_id for r in resultados] == ["3"]
    assert resultados[0].confianca == "baixa"


def test_sigla_do_orgao_recupera_o_conjunto(conexao):
    resultados = busca.buscar(conexao, "anac")
    assert [r.conjunto_id for r in resultados] == ["2"]
    assert "orgao" in resultados[0].casados


def test_resultado_traz_posicao_e_pontuacao(conexao):
    resultados = busca.buscar(conexao, "saude hospital creches")
    assert [r.posicao for r in resultados] == list(range(1, len(resultados) + 1))
    assert all(r.pontuacao > 0 for r in resultados)
    assert all(r.conjunto_id for r in resultados)


def test_limite_corta_o_ranking(conexao):
    assert len(busca.buscar(conexao, "saude hospital creches aerodromos", limite=2)) == 2


# --- termos comuns demais ------------------------------------------------


@pytest.fixture
def corpus_grande(tmp_path):
    """60 fichas onde "dados" está em todas e "creche" em nenhuma."""
    fichas = [
        {
            "id": str(i),
            "nome": f"conjunto-{i}",
            "titulo": f"Conjunto {i}",
            "resumo": f"Dados sobre o assunto {i}.",
            "perguntas": [f"onde acho dados sobre o assunto {i}?"],
            "confianca": "alta",
        }
        for i in range(60)
    ]
    fichas[0]["resumo"] = "Dados sobre aerodromos."
    caminho = _banco(tmp_path, fichas)
    conexao = busca.abrir_banco(caminho)
    yield conexao
    conexao.close()


def test_termo_ausente_com_stopwords_nao_inventa_resultados(corpus_grande):
    # "creche" não existe no corpus; "onde", "dados" e "sobre" existem em todas.
    # Sem o filtro, os comuns sustentariam um ranking inteiro de irrelevantes.
    assert busca.buscar(corpus_grande, "onde acho dados sobre creche") == []


def test_termo_raro_sobrevive_ao_filtro(corpus_grande):
    resultados = busca.buscar(corpus_grande, "onde acho dados sobre aerodromos")
    assert [r.conjunto_id for r in resultados] == ["0"]


def test_consulta_so_de_termos_comuns_ainda_responde(corpus_grande):
    # Todos comuns: ficam os menos comuns em vez de devolver vazio.
    assert busca.buscar(corpus_grande, "dados sobre") != []


def test_termo_unico_nunca_e_descartado(corpus_grande):
    # Uma palavra só é a pergunta inteira; filtrar deixaria a busca muda.
    assert busca.buscar(corpus_grande, "dados") != []


def test_filtro_desligado_em_corpus_pequeno(conexao):
    # Com 3 fichas, "aparece em 33%" não é evidência de termo comum.
    assert busca.descartar_comuns(conexao, ["hospital", "creches"]) == ["hospital", "creches"]


# --- a coluna de tags não vota em quem é palavra banal --------------------


@pytest.fixture
def corpus_com_tema_carimbado(tmp_path):
    """60 fichas com o mesmo rótulo de tema, e o assunto real em duas delas.

    Reproduz o defeito medido no catálogo completo: `financas` aparecia em 40,2%
    das fichas com 100% dessas ocorrências vindas da coluna de tags, porque é ali
    que a indexação escreve o vocabulário controlado de temas. O termo é de
    assunto — o que o cidadão digita — e o filtro o descartava por artefato
    nosso.
    """
    fichas = [
        {
            "id": str(i),
            "nome": f"conjunto-{i}",
            "titulo": f"Conjunto {i}",
            "resumo": f"Registro do assunto {i}.",
            "perguntas": [f"onde acho o assunto {i}?"],
            "confianca": "alta",
            "tags": [{"name": "economia"}],
        }
        for i in range(60)
    ]
    # Só nestas duas a palavra foi escrita por gente, e não carimbada por tema.
    fichas[0]["resumo"] = "Séries de economia do banco central."
    fichas[1]["perguntas"] = ["como anda a economia?"]
    caminho = _banco(tmp_path, fichas)
    conexao = busca.abrir_banco(caminho)
    yield conexao
    conexao.close()


def test_rotulo_de_tema_nao_torna_o_termo_comum(corpus_com_tema_carimbado):
    # Em 60 de 60 fichas pela tag, em 2 pelo texto natural. Vale o texto.
    assert busca.frequencia(corpus_com_tema_carimbado, "economia") == 2
    assert busca.descartar_comuns(corpus_com_tema_carimbado, ["onde", "economia"]) == [
        "economia"
    ]


def test_termo_comum_no_texto_natural_continua_descartado(corpus_com_tema_carimbado):
    # "assunto" está no resumo das 60: comum de verdade, e some da consulta.
    assert "assunto" not in busca.descartar_comuns(
        corpus_com_tema_carimbado, ["assunto", "economia"]
    )


def test_busca_por_termo_de_tema_recupera(corpus_com_tema_carimbado):
    # O ponto da mudança: a pergunta que antes voltava vazia agora responde.
    resultados = busca.buscar(corpus_com_tema_carimbado, "onde acho economia")
    # "1" na frente de "0" porque ali a palavra está numa pergunta de exemplo,
    # que pesa 4.0, contra o resumo, que pesa 1.0.
    assert [r.conjunto_id for r in resultados[:2]] == ["1", "0"]


def test_tag_continua_indexada_e_buscavel(tmp_path):
    # Excluir a coluna da *medição* não pode excluí-la da *recuperação*.
    caminho = _banco(
        tmp_path,
        [{"id": "1", "nome": "conjunto-um", "resumo": "Sem menção ao tema.",
          "confianca": "alta", "tags": [{"name": "saneamento"}]}],
    )
    conexao = busca.abrir_banco(caminho)
    try:
        resultados = busca.buscar(conexao, "saneamento")
        assert [r.conjunto_id for r in resultados] == ["1"]
        assert "tags" in resultados[0].casados
    finally:
        conexao.close()


# --- explicação ----------------------------------------------------------


def test_casamento_e_por_palavra_inteira_nao_por_trecho(tmp_path):
    # "rede" está contido em "prefeitura"? não; mas "rio" está em "prioridade",
    # e é esse tipo de trecho que a comparação ingênua acusaria como casamento.
    caminho = _banco(
        tmp_path,
        [{"id": "1", "nome": "prioridades", "resumo": "Lista de prioridades.", "confianca": "alta"}],
    )
    conexao = busca.abrir_banco(caminho)
    try:
        # O índice não casa "rio" com "prioridades", então a busca não retorna nada;
        # a explicação precisa concordar com o índice.
        assert busca.buscar(conexao, "rio") == []
        resultado = busca.buscar(conexao, "prioridades")[0]
        assert "prioridades" in resultado.termos_casados
        assert _casamento_direto(conexao, "rio") == {}
    finally:
        conexao.close()


def _casamento_direto(conexao, termo):
    """Aplica a explicação a uma linha do índice, sem passar pelo ranking."""
    linha = conexao.execute(
        f"SELECT {', '.join(indexa.COLUNAS)} FROM ficha_fts LIMIT 1"
    ).fetchone()
    return busca._casamentos(linha, [termo])


def test_termos_casados_sem_repeticao(conexao):
    resultado = busca.buscar(conexao, "saude saude")[0]
    assert resultado.termos_casados.count("saude") == 1


# --- índice --------------------------------------------------------------


def test_reconstrucao_nao_altera_resultados(tmp_path, conexao):
    antes = [(r.conjunto_id, round(r.pontuacao, 9)) for r in busca.buscar(conexao, "saude")]
    caminho = tmp_path / "dados.db"
    indexa.indexar(caminho)
    indexa.indexar(caminho)
    nova = busca.abrir_banco(caminho)
    try:
        depois = [(r.conjunto_id, round(r.pontuacao, 9)) for r in busca.buscar(nova, "saude")]
    finally:
        nova.close()
    assert antes == depois


def test_indice_tem_uma_entrada_por_ficha(tmp_path, conexao):
    total = conexao.execute("SELECT count(*) FROM ficha_fts").fetchone()[0]
    fichas = conexao.execute("SELECT count(*) FROM ficha").fetchone()[0]
    assert total == fichas == 3


def test_indexar_e_idempotente_no_total(tmp_path):
    caminho = _banco(tmp_path, [{"id": "1", "nome": "a", "resumo": "x"}])
    assert indexa.indexar(caminho) == 1
    assert indexa.indexar(caminho) == 1
