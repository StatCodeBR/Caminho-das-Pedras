"""Testes da busca semântica e da integridade dos seus artefatos.

Nenhum carrega o modelo: os vetores são montados à mão, com quatro dimensões, e
a consulta vem de um vetorizador falso. O que se testa aqui é o contrato — ordem,
versão, norma, formato —, não a qualidade do modelo, que é assunto da avaliação.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

import busca
import semantica
import vetoriza

FICHAS = [
    ("a1", "dengue-municipal", "Casos de dengue", "saude", "alta", "casos de dengue"),
    ("b2", "leitos", "Leitos hospitalares", "saude", "media", "leitos por hospital"),
    ("c3", "publicidade", "Gastos com publicidade", "secom", "baixa", "propaganda"),
]
# Norma 1 nos três: [0.6, 0.8] também.
VETORES = {"a1": [1, 0, 0, 0], "b2": [0, 1, 0, 0], "c3": [0.6, 0.8, 0, 0]}


def _banco(tmp_path) -> sqlite3.Connection:
    conexao = sqlite3.connect(tmp_path / "dados.db")
    conexao.executescript(
        """
        CREATE TABLE conjunto (id TEXT PRIMARY KEY, nome TEXT, titulo TEXT,
                               organizacao TEXT);
        CREATE TABLE ficha (conjunto_id TEXT PRIMARY KEY, resumo TEXT,
                            confianca TEXT, texto_indexavel TEXT);
        """
    )
    for identificador, nome, titulo, orgao, confianca, texto in FICHAS:
        conexao.execute("INSERT INTO conjunto VALUES (?,?,?,?)", (identificador, nome, titulo, orgao))
        conexao.execute(
            "INSERT INTO ficha VALUES (?,?,?,?)",
            (identificador, f"resumo de {titulo}", confianca, texto),
        )
    conexao.commit()
    conexao.row_factory = sqlite3.Row
    return conexao


def _gravar(tmp_path, conexao, vetores_por_id=VETORES):
    fichas = semantica.ler_fichas(conexao)
    vetores = np.array([vetores_por_id[i] for i, _ in fichas], dtype=np.float32)
    npy, js = tmp_path / "vectors.npy", tmp_path / "vectors.json"
    vetoriza.gravar(vetores, [i for i, _ in fichas], semantica.versao_do_catalogo(fichas), npy, js)
    return npy, js


@pytest.fixture
def artefatos(tmp_path):
    conexao = _banco(tmp_path)
    npy, js = _gravar(tmp_path, conexao)
    yield conexao, npy, js
    conexao.close()


class ConsultaFixa:
    """Vetorizador falso: devolve sempre o mesmo vetor de consulta."""

    def __init__(self, vetor) -> None:
        self.vetor = np.asarray(vetor, dtype=np.float32)

    def consulta(self, _texto: str) -> np.ndarray:
        return self.vetor


# --- artefatos -----------------------------------------------------------


def test_carrega_artefatos_coerentes(artefatos):
    conexao, npy, js = artefatos
    indice = semantica.carregar(conexao, npy, js)
    assert indice.ids == ["a1", "b2", "c3"]
    assert indice.vetores.shape == (3, 4)


def test_gravacao_deixa_so_os_dois_arquivos(artefatos, tmp_path):
    # `np.save` com caminho acrescentaria `.npy` ao temporário; a gravação por
    # descritor evita isso, e nenhum `.tmp` pode sobrar.
    nomes = sorted(p.name for p in tmp_path.iterdir() if not p.name.startswith("dados.db"))
    assert nomes == ["vectors.json", "vectors.npy"]


def test_contagem_divergente_impede_a_carga(artefatos):
    conexao, npy, js = artefatos
    conexao.execute("INSERT INTO conjunto VALUES ('d4', 'novo', 'Novo', 'x')")
    conexao.execute("INSERT INTO ficha VALUES ('d4', 'r', 'alta', 'texto novo')")
    conexao.commit()
    with pytest.raises(semantica.IndiceInconsistente, match="3 vetores para 4 fichas"):
        semantica.carregar(conexao, npy, js)


def test_texto_alterado_e_versao_diferente(artefatos):
    # Mesma contagem, mesmos identificadores, texto diferente: a contagem não
    # pegaria. É a versão que pega, e é por isso que ela cobre o texto.
    conexao, npy, js = artefatos
    conexao.execute("UPDATE ficha SET texto_indexavel = 'outro' WHERE conjunto_id = 'b2'")
    conexao.commit()
    with pytest.raises(semantica.IndiceInconsistente, match="versões diferentes"):
        semantica.carregar(conexao, npy, js)


def test_npy_de_outra_execucao_e_recusado(artefatos):
    conexao, npy, js = artefatos
    with npy.open("wb") as arquivo:
        np.save(arquivo, np.eye(3, 4, dtype=np.float32))
    with pytest.raises(semantica.IndiceInconsistente, match="execuções diferentes"):
        semantica.carregar(conexao, npy, js)


def test_vetores_fora_da_norma_sao_recusados(tmp_path):
    conexao = _banco(tmp_path)
    npy, js = _gravar(tmp_path, conexao, {i: [2, 0, 0, 0] for i in VETORES})
    with pytest.raises(semantica.IndiceInconsistente, match="norma unitária"):
        semantica.carregar(conexao, npy, js)


def test_artefatos_ausentes_sao_recusados(tmp_path):
    conexao = _banco(tmp_path)
    with pytest.raises(semantica.IndiceInconsistente, match="não encontrados"):
        semantica.carregar(conexao, tmp_path / "vectors.npy", tmp_path / "vectors.json")


# --- busca ---------------------------------------------------------------


def test_resultado_no_formato_da_busca_lexica(artefatos):
    conexao, npy, js = artefatos
    indice = semantica.carregar(conexao, npy, js)
    resultados = semantica.buscar(conexao, indice, ConsultaFixa([1, 0, 0, 0]), "dengue", 2)

    assert all(isinstance(r, busca.Resultado) for r in resultados)
    assert [r.conjunto_id for r in resultados] == ["a1", "c3"]
    assert [r.posicao for r in resultados] == [1, 2]
    assert resultados[0].nome == "dengue-municipal"
    assert resultados[0].titulo == "Casos de dengue"
    assert resultados[0].pontuacao == pytest.approx(1.0)
    assert resultados[1].pontuacao == pytest.approx(0.6)


def test_pontuacao_e_o_produto_escalar(artefatos):
    conexao, npy, js = artefatos
    indice = semantica.carregar(conexao, npy, js)
    consulta = np.array([0.0, 0.6, 0.8, 0.0], dtype=np.float32)
    resultados = semantica.buscar(conexao, indice, ConsultaFixa(consulta), "x", 3)

    esperado = {i: float(np.dot(v, consulta)) for i, v in VETORES.items()}
    for r in resultados:
        assert r.pontuacao == pytest.approx(esperado[r.conjunto_id])
    assert [r.conjunto_id for r in resultados] == sorted(esperado, key=lambda i: -esperado[i])


def test_consulta_vazia_nao_retorna_nada(artefatos):
    conexao, npy, js = artefatos
    indice = semantica.carregar(conexao, npy, js)
    assert semantica.buscar(conexao, indice, ConsultaFixa([1, 0, 0, 0]), "   ") == []


def test_limite_maior_que_o_catalogo(artefatos):
    conexao, npy, js = artefatos
    indice = semantica.carregar(conexao, npy, js)
    assert len(semantica.buscar(conexao, indice, ConsultaFixa([1, 0, 0, 0]), "x", 50)) == 3


def test_versao_segue_a_formula_documentada():
    """A mesma fórmula está escrita por extenso em api/tests/test_semantica.py.

    Os dois projetos não podem se importar; é este par de testes que impede as
    duas implementações de divergirem sem que ninguém perceba.
    """
    import hashlib

    esperado = hashlib.sha256(b"a\x00x\x1eb\x00y\x1e").hexdigest()
    assert semantica.versao_do_catalogo([("a", "x"), ("b", "y")]) == esperado
