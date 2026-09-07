"""Testes do enriquecimento. Nenhum toca a API: o cliente é sempre dublado."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import enriquece
import normaliza
import provedores
import temas


# --- dublês --------------------------------------------------------------


class BlocoTexto(SimpleNamespace):
    type = "text"


class ProvedorFalso(provedores.Provedor):
    """Um provedor de teste: devolve respostas na ordem e conta as chamadas.

    Herda de Provedor para que o teste falhe se a interface mudar de forma
    incompatível — é o ponto de ter interface.
    """

    nome = "dublê"

    def __init__(self, respostas: list[str], modelo: str = "modelo-de-teste"):
        self.respostas = list(respostas)
        self.modelo = modelo
        self.chamadas = 0

    def gerar(self, sistema: str, entrada: str, esquema: dict) -> str:
        self.chamadas += 1
        return self.respostas.pop(0) if self.respostas else "{}"


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
    provedor = ProvedorFalso([FICHA_VALIDA] * 3)
    primeiro = enriquece.enriquecer(banco=banco, provedor=provedor)
    assert primeiro.do_modelo == 3
    assert provedor.chamadas == 3

    segundo_provedor = ProvedorFalso([])
    segundo = enriquece.enriquecer(banco=banco, provedor=segundo_provedor)

    assert segundo_provedor.chamadas == 0
    assert segundo.do_cache == 3
    assert segundo.aproveitamento_cache == 1.0


def test_mudar_o_prompt_invalida_o_cache(banco, monkeypatch, tmp_path):
    """Cenário: prompt alterado."""
    provedor = ProvedorFalso([FICHA_VALIDA] * 3)
    enriquece.enriquecer(banco=banco, provedor=provedor)

    outro_prompt = tmp_path / "ficha.md"
    outro_prompt.write_text("Instrução diferente.\n{temas}\n", encoding="utf-8")
    monkeypatch.setattr(enriquece, "ARQUIVO_PROMPT", outro_prompt)

    novo_provedor = ProvedorFalso([FICHA_VALIDA] * 3)
    relatorio = enriquece.enriquecer(banco=banco, provedor=novo_provedor)

    assert novo_provedor.chamadas == 3
    assert relatorio.do_cache == 0


def test_metadado_alterado_reprocessa_so_aquele_conjunto(banco):
    """Cenário: metadado de um conjunto alterado."""
    provedor = ProvedorFalso([FICHA_VALIDA] * 3)
    enriquece.enriquecer(banco=banco, provedor=provedor)

    conexao = sqlite3.connect(banco)
    conexao.execute("UPDATE conjunto SET descricao = ? WHERE nome = ?", ("Outra.", "conjunto-1"))
    conexao.commit()
    conexao.close()

    novo_provedor = ProvedorFalso([FICHA_VALIDA])
    relatorio = enriquece.enriquecer(banco=banco, provedor=novo_provedor)

    assert novo_provedor.chamadas == 1
    assert relatorio.do_cache == 2


# --- degradação ----------------------------------------------------------


def test_resposta_malformada_tenta_de_novo_e_depois_cai_no_fallback(banco):
    """Cenário: resposta malformada."""
    # Três respostas ruins para o primeiro conjunto: 1 tentativa + 2 repetições.
    provedor = ProvedorFalso(["não é json", "{", "ainda não", FICHA_VALIDA, FICHA_VALIDA])
    relatorio = enriquece.enriquecer(banco=banco, provedor=provedor)

    assert provedor.chamadas == 5
    assert relatorio.de_fallback == 1
    assert relatorio.do_modelo == 2

    fallback = [f for f in fichas(banco) if f["origem"] == "fallback"][0]
    assert fallback["confianca"] == "baixa"
    assert json.loads(fallback["perguntas_json"]) == []


def test_conjunto_nunca_e_descartado(banco):
    """Cenário: conjunto nunca descartado — metadado ruim ainda vira ficha."""
    provedor = ProvedorFalso(["lixo"] * 9)
    enriquece.enriquecer(banco=banco, provedor=provedor)

    assert len(fichas(banco)) == 3
    assert all(f["texto_indexavel"] for f in fichas(banco))


# --- validação da estrutura ---------------------------------------------


def test_tema_fora_da_lista_e_descartado(banco):
    """Cenário: tema fora da lista fechada."""
    resposta = json.loads(FICHA_VALIDA)
    resposta["temas"] = ["saude", "gastronomia-molecular", "educacao"]
    provedor = ProvedorFalso([json.dumps(resposta, ensure_ascii=False)] * 3)

    enriquece.enriquecer(banco=banco, provedor=provedor)

    guardados = json.loads(fichas(banco)[0]["temas_json"])
    assert guardados == ["saude", "educacao"]
    assert all(temas.valido(t) for t in guardados)


def test_confianca_baixa_limita_a_duas_perguntas(banco):
    """Cenário: confiança baixa."""
    resposta = json.loads(FICHA_VALIDA)
    resposta["confianca"] = "baixa"
    resposta["perguntas"] = [f"pergunta {n}?" for n in range(5)]
    provedor = ProvedorFalso([json.dumps(resposta, ensure_ascii=False)] * 3)

    enriquece.enriquecer(banco=banco, provedor=provedor)

    assert len(json.loads(fichas(banco)[0]["perguntas_json"])) == 2


def test_confianca_desconhecida_e_rejeitada(banco):
    resposta = json.loads(FICHA_VALIDA)
    resposta["confianca"] = "altíssima"
    provedor = ProvedorFalso([json.dumps(resposta, ensure_ascii=False)] * 9)

    relatorio = enriquece.enriquecer(banco=banco, provedor=provedor)

    assert relatorio.de_fallback == 3


# --- derivação -----------------------------------------------------------


def test_texto_indexavel_nao_consome_tokens(banco):
    """Cenário: reconstrução dos índices."""
    provedor = ProvedorFalso([FICHA_VALIDA] * 3)
    enriquece.enriquecer(banco=banco, provedor=provedor)

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


class ProvedorComLote(ProvedorFalso):
    """Provedor que oferece lote, para exercitar submissão e retomada."""

    nome = "dublê-lote"

    def __init__(self, respostas: list[str], modelo: str = "modelo-de-teste"):
        super().__init__(respostas, modelo)
        self.submissoes = 0
        self.itens: list[str] = []

    def suporta_lote(self) -> bool:
        return True

    def submeter_lote(self, itens, sistema, esquema):
        self.submissoes += 1
        self.itens = [identificador for identificador, _ in itens]
        return "lote-teste"

    def lote_concluido(self, lote_id: str) -> bool:
        return True

    def resultados_lote(self, lote_id: str):
        for identificador in self.itens or [f"id-{n}" for n in range(3)]:
            yield identificador, FICHA_VALIDA


def test_lote_interrompido_e_retomado_sem_resubmeter(banco):
    """Cenário: interrupção durante a espera."""
    provedor = ProvedorComLote([])
    # Simula a interrupção: o lote foi submetido e o estado ficou em disco.
    enriquece.gravar_lote_pendente(
        {"lote_id": "lote-teste", "modelo": provedor.identificador, "itens": 3}
    )

    relatorio = enriquece.enriquecer_em_lote(banco=banco, provedor=provedor, espera=0)

    assert provedor.submissoes == 0  # retomou, não resubmeteu
    assert relatorio.do_modelo == 3
    assert not enriquece.ARQUIVO_LOTE.exists()


def test_lote_novo_e_submetido_e_o_identificador_persistido(banco):
    provedor = ProvedorComLote([])
    relatorio = enriquece.enriquecer_em_lote(banco=banco, provedor=provedor, espera=0)

    assert provedor.submissoes == 1
    assert relatorio.do_modelo == 3
    # Concluído sem sobras: o arquivo de retomada é apagado.
    assert not enriquece.ARQUIVO_LOTE.exists()


def test_provedor_sem_lote_cai_para_o_caminho_sincrono(banco):
    """Não suportar lote é diferente de fingir que suporta."""
    provedor = ProvedorFalso([FICHA_VALIDA] * 3)
    assert provedor.suporta_lote() is False

    relatorio = enriquece.enriquecer_em_lote(banco=banco, provedor=provedor, espera=0)

    assert provedor.chamadas == 3
    assert relatorio.do_modelo == 3


def test_modelo_fica_gravado_na_ficha(banco):
    """Quem escreveu a ficha precisa ser auditável depois."""
    provedor = ProvedorFalso([FICHA_VALIDA] * 3, modelo="modelo-x")
    enriquece.enriquecer(banco=banco, provedor=provedor)

    assert all(f["modelo"] == "dublê/modelo-x" for f in fichas(banco))


def test_trocar_de_modelo_invalida_o_cache(banco):
    """Ficha escrita por outro modelo é outra ficha."""
    primeiro = ProvedorFalso([FICHA_VALIDA] * 3, modelo="modelo-a")
    enriquece.enriquecer(banco=banco, provedor=primeiro)

    segundo = ProvedorFalso([FICHA_VALIDA] * 3, modelo="modelo-b")
    relatorio = enriquece.enriquecer(banco=banco, provedor=segundo)

    assert segundo.chamadas == 3
    assert relatorio.do_cache == 0
    assert all(f["modelo"] == "dublê/modelo-b" for f in fichas(banco))


def test_relatorio_traz_distribuicao_de_confianca(banco):
    """Cenário: execução concluída."""
    baixa = json.loads(FICHA_VALIDA)
    baixa["confianca"] = "baixa"
    provedor = ProvedorFalso(
        [FICHA_VALIDA, json.dumps(baixa, ensure_ascii=False), FICHA_VALIDA]
    )

    relatorio = enriquece.enriquecer(banco=banco, provedor=provedor)

    assert relatorio.total == 3
    assert relatorio.confianca == {"alta": 2, "baixa": 1}
    assert relatorio.de_fallback == 0


# --- seleção de provedor -------------------------------------------------


def test_identificador_junta_provedor_e_modelo():
    p = provedores.ProvedorCohere(modelo="command-a-03-2025")
    assert p.identificador == "cohere/command-a-03-2025"


def test_criar_provedor_por_nome(monkeypatch):
    monkeypatch.delenv("PROVEDOR", raising=False)
    assert provedores.criar_provedor("cohere").nome == "cohere"
    assert provedores.criar_provedor("anthropic").nome == "anthropic"
    # Padrão do projeto quando nada é dito.
    assert provedores.criar_provedor().nome == provedores.PROVEDOR_PADRAO


def test_provedor_desconhecido_falha_com_lista(monkeypatch):
    monkeypatch.delenv("PROVEDOR", raising=False)
    with pytest.raises(ValueError, match="cohere"):
        provedores.criar_provedor("provedor-que-nao-existe")


def test_provedor_sem_chave_diz_qual_variavel_falta(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    p = provedores.ProvedorCohere()
    with pytest.raises(provedores.SemCredencial, match="COHERE_API_KEY"):
        p.gerar("sistema", "entrada", {})


# --- trava de confiança --------------------------------------------------


def test_descricao_pobre_forca_confianca_baixa(banco):
    """A ficha nunca declara mais confiança do que a fonte sustenta."""
    conexao = sqlite3.connect(banco)
    # 27 caracteres: o caso "11. Mortalidade Materna" que virou near miss.
    conexao.execute("UPDATE conjunto SET descricao = ? WHERE nome = ?", ("Dados de mortalidade.", "conjunto-0"))
    conexao.commit()
    conexao.close()

    alta = json.loads(FICHA_VALIDA)
    alta["confianca"] = "alta"
    alta["perguntas"] = [f"pergunta {n}?" for n in range(5)]
    provedor = ProvedorFalso([json.dumps(alta, ensure_ascii=False)] * 3)

    enriquece.enriquecer(banco=banco, provedor=provedor)

    por_id = {f["conjunto_id"]: f for f in fichas(banco)}
    travada = por_id["id-0"]
    assert travada["confianca"] == "baixa"
    # Baixa limita a 2 perguntas, contendo o dano no texto indexável.
    assert len(json.loads(travada["perguntas_json"])) == 2
    # Os outros, com descrição rica, mantêm o que o modelo disse.
    assert por_id["id-1"]["confianca"] == "alta"


def test_trava_nao_promove_confianca():
    """A trava só rebaixa; nunca inventa confiança que o modelo não deu."""
    ficha = enriquece.FichaGerada.model_validate_json(FICHA_VALIDA)
    rica = {"descricao": "x" * 500}
    assert enriquece.travar_confianca(rica, ficha).confianca == "alta"

    baixa = ficha.model_copy(update={"confianca": "baixa"})
    assert enriquece.travar_confianca(rica, baixa).confianca == "baixa"


def test_limiar_e_o_da_faixa_observada():
    """Sem descrição, com descrição no limite, e logo acima dele."""
    ficha = enriquece.FichaGerada.model_validate_json(FICHA_VALIDA)
    assert enriquece.travar_confianca({"descricao": None}, ficha).confianca == "baixa"
    curta = {"descricao": "x" * (enriquece.LIMIAR_DESCRICAO_POBRE - 1)}
    assert enriquece.travar_confianca(curta, ficha).confianca == "baixa"
    suficiente = {"descricao": "x" * enriquece.LIMIAR_DESCRICAO_POBRE}
    assert enriquece.travar_confianca(suficiente, ficha).confianca == "alta"


# --- contenção de taxa ---------------------------------------------------


def test_cohere_espaca_as_chamadas(monkeypatch):
    """A chave trial permite 20/min; espaçar é o que evita o 429."""
    monkeypatch.setenv("COHERE_CHAMADAS_POR_MINUTO", "60")
    p = provedores.ProvedorCohere()
    assert p._intervalo == 1.0

    monkeypatch.setenv("COHERE_CHAMADAS_POR_MINUTO", "18")
    assert round(provedores.ProvedorCohere()._intervalo, 2) == 3.33


def test_cohere_repete_apos_429_em_vez_de_abortar(monkeypatch):
    """Estourar o limite não pode jogar fora as fichas já pagas."""
    from cohere.errors import TooManyRequestsError

    monkeypatch.setenv("COHERE_CHAMADAS_POR_MINUTO", "6000")  # sem espera real
    tentativas = {"n": 0}

    class ChatFalso:
        def chat(self, **kwargs):
            tentativas["n"] += 1
            if tentativas["n"] < 3:
                raise TooManyRequestsError(headers={}, body={})
            return SimpleNamespace(message=SimpleNamespace(content=[BlocoTexto(text="{}")]))

    p = provedores.ProvedorCohere(cliente=ChatFalso())
    assert p.gerar("sistema", "entrada", {}) == "{}"
    assert tentativas["n"] == 3
    assert p.esperas_por_limite == 2
