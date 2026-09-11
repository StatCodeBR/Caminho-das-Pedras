"""Testes da busca semântica do serviço, sem baixar o modelo.

O substituto no lugar do fastembed registra o que chega até ele. A paridade com
o modelo real fica em `test_paridade.py`, fora da suíte rápida.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

import numpy as np
import pytest

from app import semantica
from app.recuperacao import Recuperado


class ModeloFalso:
    def __init__(self) -> None:
        self.recebidos: list[str] = []

    def embed(self, textos, **_opcoes):
        textos = list(textos)
        self.recebidos.extend(textos)
        for texto in textos:
            yield np.array(
                [float(len(texto)), 3.0, 4.0] + [0.0] * (semantica.DIMENSAO - 3),
                dtype=np.float32,
            )


# --- vetorizador ---------------------------------------------------------


def test_consulta_recebe_prefixo_de_consulta():
    modelo = ModeloFalso()
    semantica.Vetorizador(_modelo=modelo).consulta("onde acho dados de dengue")
    assert modelo.recebidos == ["query: onde acho dados de dengue"]


def test_documentos_recebem_prefixo_de_documento():
    modelo = ModeloFalso()
    semantica.Vetorizador(_modelo=modelo).documentos(["casos de dengue"])
    assert modelo.recebidos == ["passage: casos de dengue"]


def test_nao_existe_caminho_publico_sem_prefixo():
    publicos = {n for n in dir(semantica.Vetorizador) if not n.startswith("_")}
    assert publicos == {"documentos", "consulta"}


def test_vetores_saem_com_norma_unitaria():
    vetor = semantica.Vetorizador(_modelo=ModeloFalso()).consulta("pergunta")
    assert vetor.shape == (semantica.DIMENSAO,)
    assert np.linalg.norm(vetor) == pytest.approx(1.0, abs=1e-6)


def test_versao_segue_a_mesma_formula_do_pipeline():
    """A fórmula está escrita por extenso aqui e em pipeline/tests/test_semantica.py.

    Os dois projetos não podem se importar; é este par de testes que impede as
    duas implementações de divergirem sem que ninguém perceba.
    """
    esperado = hashlib.sha256(b"a\x00x\x1eb\x00y\x1e").hexdigest()
    assert semantica.versao_do_catalogo([("a", "x"), ("b", "y")]) == esperado


# --- artefatos e busca ---------------------------------------------------

FICHAS = [
    ("a1", "dengue-municipal", "Casos de dengue", "casos de dengue"),
    ("b2", "leitos", "Leitos hospitalares", "leitos por hospital"),
    ("c3", "publicidade", "Gastos com publicidade", "propaganda"),
]
VETORES = {"a1": [1, 0, 0, 0], "b2": [0, 1, 0, 0], "c3": [0.6, 0.8, 0, 0]}


@pytest.fixture
def artefatos(tmp_path):
    conexao = sqlite3.connect(tmp_path / "dados.db")
    conexao.executescript(
        """
        CREATE TABLE conjunto (id TEXT PRIMARY KEY, nome TEXT, titulo TEXT,
            organizacao TEXT, dados_atualizados_em TEXT, metadados_atualizados_em TEXT);
        CREATE TABLE ficha (conjunto_id TEXT PRIMARY KEY, resumo TEXT, confianca TEXT,
            perguntas_json TEXT, texto_indexavel TEXT);
        CREATE TABLE recurso (id INTEGER PRIMARY KEY, conjunto_id TEXT, titulo TEXT,
            link TEXT, formato TEXT);
        """
    )
    for identificador, nome, titulo, texto in FICHAS:
        conexao.execute(
            "INSERT INTO conjunto VALUES (?,?,?,?,?,?)",
            (identificador, nome, titulo, "orgao", "2024-01-01", "2024-02-01"),
        )
        conexao.execute(
            "INSERT INTO ficha VALUES (?,?,?,?,?)",
            (identificador, f"resumo de {titulo}", "alta", '["uma pergunta?"]', texto),
        )
        conexao.execute(
            "INSERT INTO recurso (conjunto_id, titulo, link, formato) VALUES (?,?,?,?)",
            (identificador, "arquivo", f"https://exemplo.gov.br/{nome}.csv", "CSV"),
        )
    conexao.commit()
    conexao.row_factory = sqlite3.Row

    fichas = semantica.ler_fichas(conexao)
    npy, js = tmp_path / "vectors.npy", tmp_path / "vectors.json"
    with npy.open("wb") as arquivo:
        np.save(arquivo, np.array([VETORES[i] for i, _ in fichas], dtype=np.float32))
    js.write_text(
        json.dumps(
            {
                "versao": semantica.versao_do_catalogo(fichas),
                "modelo": semantica.MODELO,
                "dimensao": 4,
                "sha256_vetores": semantica.soma_sha256(npy),
                "ids": [i for i, _ in fichas],
            }
        ),
        encoding="utf-8",
    )
    yield conexao, npy, js
    conexao.close()


class ConsultaFixa:
    def __init__(self, vetor) -> None:
        self.vetor = np.asarray(vetor, dtype=np.float32)

    def consulta(self, _texto: str) -> np.ndarray:
        return self.vetor


def test_carrega_artefatos_coerentes(artefatos):
    conexao, npy, js = artefatos
    assert semantica.carregar(conexao, npy, js).ids == ["a1", "b2", "c3"]


def test_contagem_divergente_impede_a_carga(artefatos):
    conexao, npy, js = artefatos
    conexao.execute("INSERT INTO conjunto (id, nome) VALUES ('d4', 'novo')")
    conexao.execute("INSERT INTO ficha (conjunto_id, texto_indexavel) VALUES ('d4', 't')")
    conexao.commit()
    with pytest.raises(semantica.IndiceInconsistente, match="3 vetores para 4 fichas"):
        semantica.carregar(conexao, npy, js)


def test_versao_diferente_impede_a_carga(artefatos):
    conexao, npy, js = artefatos
    conexao.execute("UPDATE ficha SET texto_indexavel = 'outro' WHERE conjunto_id = 'b2'")
    conexao.commit()
    with pytest.raises(semantica.IndiceInconsistente, match="versões diferentes"):
        semantica.carregar(conexao, npy, js)


def test_modelo_diferente_impede_a_carga(artefatos):
    conexao, npy, js = artefatos
    meta = json.loads(js.read_text(encoding="utf-8"))
    meta["modelo"] = "outro/modelo"
    js.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(semantica.IndiceInconsistente, match="não são comparáveis"):
        semantica.carregar(conexao, npy, js)


def test_busca_devolve_recuperados_com_recursos(artefatos):
    conexao, npy, js = artefatos
    indice = semantica.carregar(conexao, npy, js)
    resultados = semantica.buscar(conexao, indice, ConsultaFixa([1, 0, 0, 0]), "dengue", 2)

    assert all(isinstance(r, Recuperado) for r in resultados)
    assert [(r.conjunto_id, r.posicao) for r in resultados] == [("a1", 1), ("c3", 2)]
    assert resultados[0].pontuacao == pytest.approx(1.0)
    assert resultados[1].pontuacao == pytest.approx(0.6)
    assert resultados[0].perguntas == ["uma pergunta?"]
    assert resultados[0].recursos[0].link == "https://exemplo.gov.br/dengue-municipal.csv"
    assert resultados[0].url_portal.endswith("/dengue-municipal")
