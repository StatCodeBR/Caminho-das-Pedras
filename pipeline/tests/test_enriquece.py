"""Testes do enriquecimento. Nenhum toca a API: o cliente é sempre dublado."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import enriquece
import normaliza
import temas


# --- dublês --------------------------------------------------------------


class BlocoTexto(SimpleNamespace):
    type = "text"


class ClienteFalso:
    """Devolve as respostas na ordem dada e conta quantas vezes foi chamado."""

    def __init__(self, respostas: list[str]):
        self.respostas = list(respostas)
        self.chamadas = 0
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.chamadas += 1
        texto = self.respostas.pop(0) if self.respostas else "{}"
        return SimpleNamespace(content=[BlocoTexto(text=texto)])


FICHA_VALIDA = json.dumps(
    {
        "resumo": "Registros de casos de dengue notificados no país.",
        "perguntas": ["quantos casos de dengue tiveram no meu município?"],
        "temas": ["saude"],
        "abrangencia": "nacional",
        "granularidade": "municipio",
        "confianca": "alta",
    },
    ensure_ascii=False,
)


# --- fixtures ------------------------------------------------------------


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    """Um catálogo mínimo, montado pelo próprio normalizador."""
    entrada = tmp_path / "conjuntos.jsonl"
    registros = []
    for n in range(3):
        detalhe = {
            "id": f"id-{n}",
            "nome": f"conjunto-{n}",
            "titulo": f"Conjunto {n}",
            "descricao": "Descrição suficiente para o modelo trabalhar." * 2,
            "organizacao": "ministerio-da-saude",
            "tags": [{"id": "t1", "name": "Dengue"}],
            "temas": [],
            "descontinuado": False,
            "recursos": [
                {"id": f"id-{n}-r0", "titulo": "Casos de 2024", "formato": "CSV"},
                {"id": f"id-{n}-r1", "titulo": "Dicionário de dados", "formato": "PDF"},
            ],
        }
        registros.append({"id": f"id-{n}", "nome": detalhe["nome"], "detalhe": detalhe})
    entrada.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros), encoding="utf-8"
    )
    caminho = tmp_path / "dados.db"
    normaliza.normalizar(entrada, caminho, tmp_path / "quarentena.jsonl")
    return caminho


@pytest.fixture(autouse=True)
def cache_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(enriquece, "DIRETORIO_CACHE", tmp_path / "cache")
    monkeypatch.setattr(enriquece, "ARQUIVO_LOTE", tmp_path / "cache" / "lote.json")


def fichas(banco: Path) -> list[sqlite3.Row]:
    conexao = sqlite3.connect(banco)
    conexao.row_factory = sqlite3.Row
    try:
        return list(conexao.execute("SELECT * FROM ficha ORDER BY conjunto_id"))
    finally:
        conexao.close()


# --- entrada determinística ---------------------------------------------


def test_entrada_traz_os_campos_pedidos(banco):
    """A entrada leva nome, título, órgão, descrição, tags e títulos de recursos."""
    conexao = enriquece.abrir_banco(banco)
    try:
        conjunto = enriquece.ler_conjuntos(conexao, 1)[0]
    finally:
        conexao.close()

    entrada = enriquece.montar_entrada(conjunto)

    assert "nome: conjunto-0" in entrada
    assert "titulo: Conjunto 0" in entrada
    assert "orgao: ministerio-da-saude" in entrada
    assert "Descrição suficiente" in entrada
    assert "tags: Dengue" in entrada
    assert "- Casos de 2024" in entrada
    assert "- Dicionário de dados" in entrada


def test_entrada_e_deterministica(banco):
    conexao = enriquece.abrir_banco(banco)
    try:
        conjunto = enriquece.ler_conjuntos(conexao, 1)[0]
    finally:
        conexao.close()

    assert enriquece.montar_entrada(conjunto) == enriquece.montar_entrada(conjunto)


# --- cache ---------------------------------------------------------------


def test_item_ja_em_cache_nao_gera_chamada(banco):
    """Cenário: reexecução sem alterações."""
    cliente = ClienteFalso([FICHA_VALIDA] * 3)
    primeiro = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)
    assert primeiro.do_modelo == 3
    assert cliente.chamadas == 3

    segundo_cliente = ClienteFalso([])
    segundo = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=segundo_cliente)

    assert segundo_cliente.chamadas == 0
    assert segundo.do_cache == 3
    assert segundo.aproveitamento_cache == 1.0


def test_mudar_o_prompt_invalida_o_cache(banco, monkeypatch, tmp_path):
    """Cenário: prompt alterado."""
    cliente = ClienteFalso([FICHA_VALIDA] * 3)
    enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    outro_prompt = tmp_path / "ficha.md"
    outro_prompt.write_text("Instrução diferente.\n{temas}\n", encoding="utf-8")
    monkeypatch.setattr(enriquece, "ARQUIVO_PROMPT", outro_prompt)

    novo_cliente = ClienteFalso([FICHA_VALIDA] * 3)
    relatorio = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=novo_cliente)

    assert novo_cliente.chamadas == 3
    assert relatorio.do_cache == 0


def test_metadado_alterado_reprocessa_so_aquele_conjunto(banco):
    """Cenário: metadado de um conjunto alterado."""
    cliente = ClienteFalso([FICHA_VALIDA] * 3)
    enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    conexao = sqlite3.connect(banco)
    conexao.execute("UPDATE conjunto SET descricao = ? WHERE nome = ?", ("Outra.", "conjunto-1"))
    conexao.commit()
    conexao.close()

    novo_cliente = ClienteFalso([FICHA_VALIDA])
    relatorio = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=novo_cliente)

    assert novo_cliente.chamadas == 1
    assert relatorio.do_cache == 2


# --- degradação ----------------------------------------------------------


def test_resposta_malformada_tenta_de_novo_e_depois_cai_no_fallback(banco):
    """Cenário: resposta malformada."""
    # Três respostas ruins para o primeiro conjunto: 1 tentativa + 2 repetições.
    cliente = ClienteFalso(["não é json", "{", "ainda não", FICHA_VALIDA, FICHA_VALIDA])
    relatorio = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    assert cliente.chamadas == 5
    assert relatorio.de_fallback == 1
    assert relatorio.do_modelo == 2

    fallback = [f for f in fichas(banco) if f["origem"] == "fallback"][0]
    assert fallback["confianca"] == "baixa"
    assert json.loads(fallback["perguntas_json"]) == []


def test_conjunto_nunca_e_descartado(banco):
    """Cenário: conjunto nunca descartado — metadado ruim ainda vira ficha."""
    cliente = ClienteFalso(["lixo"] * 9)
    enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    assert len(fichas(banco)) == 3
    assert all(f["texto_indexavel"] for f in fichas(banco))


# --- validação da estrutura ---------------------------------------------


def test_tema_fora_da_lista_e_descartado(banco):
    """Cenário: tema fora da lista fechada."""
    resposta = json.loads(FICHA_VALIDA)
    resposta["temas"] = ["saude", "gastronomia-molecular", "educacao"]
    cliente = ClienteFalso([json.dumps(resposta, ensure_ascii=False)] * 3)

    enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    guardados = json.loads(fichas(banco)[0]["temas_json"])
    assert guardados == ["saude", "educacao"]
    assert all(temas.valido(t) for t in guardados)


def test_confianca_baixa_limita_a_duas_perguntas(banco):
    """Cenário: confiança baixa."""
    resposta = json.loads(FICHA_VALIDA)
    resposta["confianca"] = "baixa"
    resposta["perguntas"] = [f"pergunta {n}?" for n in range(5)]
    cliente = ClienteFalso([json.dumps(resposta, ensure_ascii=False)] * 3)

    enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    assert len(json.loads(fichas(banco)[0]["perguntas_json"])) == 2


def test_confianca_desconhecida_e_rejeitada(banco):
    resposta = json.loads(FICHA_VALIDA)
    resposta["confianca"] = "altíssima"
    cliente = ClienteFalso([json.dumps(resposta, ensure_ascii=False)] * 9)

    relatorio = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    assert relatorio.de_fallback == 3


# --- derivação -----------------------------------------------------------


def test_texto_indexavel_nao_consome_tokens(banco):
    """Cenário: reconstrução dos índices."""
    cliente = ClienteFalso([FICHA_VALIDA] * 3)
    enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    conexao = enriquece.abrir_banco(banco)
    try:
        conjunto = enriquece.ler_conjuntos(conexao, 1)[0]
    finally:
        conexao.close()

    ficha = enriquece.FichaGerada.model_validate_json(FICHA_VALIDA).normalizada()

    # Nenhum cliente envolvido: a derivação é pura concatenação.
    primeiro = enriquece.texto_indexavel(conjunto, ficha)
    segundo = enriquece.texto_indexavel(conjunto, ficha)

    assert primeiro == segundo
    assert "Registros de casos de dengue" in primeiro
    assert "quantos casos de dengue" in primeiro
    assert "ministerio-da-saude" in primeiro
    assert "Dengue" in primeiro


# --- lote ----------------------------------------------------------------


def test_lote_interrompido_e_retomado_sem_resubmeter(banco, monkeypatch):
    """Cenário: interrupção durante a espera."""
    submissoes = {"n": 0}

    class ClienteLote:
        def __init__(self):
            self.messages = SimpleNamespace(
                create=lambda **k: SimpleNamespace(content=[BlocoTexto(text=FICHA_VALIDA)]),
                batches=SimpleNamespace(
                    create=self._criar,
                    retrieve=lambda lote_id: SimpleNamespace(processing_status="ended"),
                    results=self._resultados,
                ),
            )
            self.ids: list[str] = []

        def _criar(self, requests):
            submissoes["n"] += 1
            self.ids = [pedido["custom_id"] for pedido in requests]
            return SimpleNamespace(id="msgbatch_teste")

        def _resultados(self, lote_id):
            for identificador in self.ids or [f"id-{n}" for n in range(3)]:
                yield SimpleNamespace(
                    custom_id=identificador,
                    result=SimpleNamespace(
                        type="succeeded",
                        message=SimpleNamespace(content=[BlocoTexto(text=FICHA_VALIDA)]),
                    ),
                )

    # Simula a interrupção: o lote foi submetido e o estado ficou em disco.
    enriquece.gravar_lote_pendente(
        {"lote_id": "msgbatch_teste", "modelo": "dublê", "itens": 3}
    )

    cliente = ClienteLote()
    relatorio = enriquece.enriquecer_em_lote(
        banco=banco, modelo="dublê", cliente=cliente, espera=0
    )

    assert submissoes["n"] == 0  # retomou, não resubmeteu
    assert relatorio.do_modelo == 3
    assert not enriquece.ARQUIVO_LOTE.exists()


def test_relatorio_traz_distribuicao_de_confianca(banco):
    """Cenário: execução concluída."""
    baixa = json.loads(FICHA_VALIDA)
    baixa["confianca"] = "baixa"
    cliente = ClienteFalso(
        [FICHA_VALIDA, json.dumps(baixa, ensure_ascii=False), FICHA_VALIDA]
    )

    relatorio = enriquece.enriquecer(banco=banco, modelo="dublê", cliente=cliente)

    assert relatorio.total == 3
    assert relatorio.confianca == {"alta": 2, "baixa": 1}
    assert relatorio.de_fallback == 0
