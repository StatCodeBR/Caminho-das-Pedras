"""Testes do serviço de resposta ancorada."""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import banco, geracao, guarda, redacao
from app.configuracao import Configuracao, configuracao
from app.recuperacao import Recuperado, Recurso, buscar
from app.roteamento import Origem, decidir


# --- apoio ---------------------------------------------------------------


def montar_banco(caminho, fichas):
    con = sqlite3.connect(caminho)
    con.executescript(
        """
        CREATE TABLE conjunto (
            id TEXT PRIMARY KEY, nome TEXT, titulo TEXT,
            descricao TEXT, organizacao TEXT, tags TEXT,
            dados_atualizados_em TEXT, metadados_atualizados_em TEXT
        );
        CREATE TABLE recurso (
            id INTEGER PRIMARY KEY, conjunto_id TEXT, titulo TEXT,
            link TEXT, formato TEXT, classe_saude TEXT
        );
        CREATE TABLE ficha (
            conjunto_id TEXT PRIMARY KEY, resumo TEXT, perguntas_json TEXT,
            temas_json TEXT, confianca TEXT, texto_indexavel TEXT
        );
        CREATE VIRTUAL TABLE ficha_fts USING fts5(
            conjunto_id UNINDEXED, nome, perguntas, resumo, orgao, tags,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )
    for f in fichas:
        con.execute(
            "INSERT INTO conjunto VALUES (?,?,?,?,?,?,?,?)",
            (
                f["id"], f["nome"], f.get("titulo", ""), "", f.get("orgao", ""), "[]",
                f.get("dados_em"), f.get("metadados_em"),
            ),
        )
        con.execute(
            "INSERT INTO ficha VALUES (?,?,?,?,?,?)",
            (
                f["id"],
                f.get("resumo", ""),
                json.dumps(f.get("perguntas", [])),
                "[]",
                f.get("confianca", "alta"),
                "",
            ),
        )
        con.execute(
            "INSERT INTO ficha_fts (conjunto_id,nome,perguntas,resumo,orgao,tags)"
            " VALUES (?,?,?,?,?,?)",
            (
                f["id"],
                f"{f.get('titulo','')} {f['nome']}",
                " ".join(f.get("perguntas", [])),
                f.get("resumo", ""),
                f.get("orgao", ""),
                "",
            ),
        )
        for r in f.get("recursos", []):
            con.execute(
                "INSERT INTO recurso (conjunto_id,titulo,link,formato,classe_saude)"
                " VALUES (?,?,?,?,?)",
                (f["id"], r[0], r[1], r[2], r[3]),
            )
    con.commit()
    con.close()
    return caminho


FICHAS = [
    {
        "id": "1",
        "nome": "arboviroses-dengue",
        "titulo": "Sinan/Dengue",
        "orgao": "ministerio-da-saude",
        "resumo": "Casos de dengue notificados à vigilância.",
        "perguntas": ["quantos casos de dengue na minha cidade?"],
        "confianca": "alta",
        "dados_em": "2023-05-01T00:00:00+00:00",
        "metadados_em": "2024-09-09T14:46:52+00:00",
        "recursos": [
            ("Dengue 2023", "https://exemplo.gov.br/deng23.csv", "csv", "disponivel"),
            ("Dengue 2010", "https://exemplo.gov.br/deng10.csv", "csv", "indisponivel"),
        ],
    },
    {
        # Sem data dos dados e com a dos metadados em branco: os dois casos que
        # a interface precisa distinguir de "atualizado".
        "id": "2",
        "nome": "aerodromos-publicos",
        "titulo": "Aeródromos Públicos",
        "orgao": "anac",
        "resumo": "Relação de aeródromos públicos.",
        "confianca": "baixa",
        "dados_em": None,
        "metadados_em": "   ",
    },
]


@pytest.fixture
def catalogo(tmp_path):
    return montar_banco(tmp_path / "dados.db", FICHAS)


@pytest.fixture
def conexao(catalogo):
    con = banco.abrir(catalogo)
    yield con
    con.close()


@pytest.fixture
def cliente(catalogo, monkeypatch):
    configuracao.cache_clear()
    monkeypatch.setenv("BANCO", str(catalogo))
    monkeypatch.setenv("MODO_STUB", "1")
    # Com duas fichas e o termo numa delas, o IDF do BM25 é log(1,5/1,5) = 0 e a
    # pontuação sai exatamente 0,0 — o BM25 dizendo, corretamente, que num corpus
    # desse tamanho nenhum termo discrimina. O limiar de produção mandaria tudo
    # para ausência. Aqui se testa o caminho percorrido, não a calibração.
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "0.0")
    from app.principal import app

    with TestClient(app) as c:
        yield c
    configuracao.cache_clear()


def eventos(resposta):
    """Separa o SSE em (nome, dados)."""
    saida = []
    for bloco in resposta.text.split("\n\n"):
        nome = dados = None
        for linha in bloco.splitlines():
            if linha.startswith("event: "):
                nome = linha[7:]
            elif linha.startswith("data: "):
                dados = json.loads(linha[6:])
        if nome:
            saida.append((nome, dados))
    return saida


def texto_de(evs):
    return "".join(d["texto"] for n, d in evs if n == "fragmento")


def fim_de(evs):
    return next(d for n, d in evs if n == "fim")


# --- banco somente leitura -----------------------------------------------


def test_banco_abre_somente_leitura(conexao):
    with pytest.raises(sqlite3.OperationalError):
        conexao.execute("DELETE FROM ficha")


def test_banco_ausente_ergue_erro_claro(tmp_path):
    with pytest.raises(banco.CatalogoIndisponivel):
        banco.abrir(tmp_path / "nao-existe.db")


# --- recuperação ---------------------------------------------------------


def test_recupera_por_termo(conexao):
    achados = buscar(conexao, "dengue")
    assert [a.nome for a in achados] == ["arboviroses-dengue"]


def test_recurso_indisponivel_aparece_sinalizado_nao_omitido(conexao):
    item = buscar(conexao, "dengue")[0]
    assert len(item.recursos) == 2
    assert [r.disponivel for r in item.recursos] == [True, False]
    assert any(not r.disponivel for r in item.recursos)


def test_consulta_vazia_nao_recupera_nada(conexao):
    assert buscar(conexao, "   ") == []


# --- as duas datas -------------------------------------------------------


def test_as_duas_datas_vem_separadas(conexao):
    item = buscar(conexao, "dengue")[0]
    assert item.dados_atualizados_em == "2023-05-01T00:00:00+00:00"
    assert item.metadados_atualizados_em == "2024-09-09T14:46:52+00:00"
    assert item.dados_atualizados_em != item.metadados_atualizados_em


def test_data_ausente_vira_nulo_nao_string_vazia(conexao):
    item = buscar(conexao, "aerodromos")[0]
    assert item.dados_atualizados_em is None
    # Espaço em branco é data não declarada, não data em branco: sem isso a
    # interface exibiria um traço mudo em vez de dizer que não foi informada.
    assert item.metadados_atualizados_em is None


def test_data_dos_dados_nunca_e_substituida_pela_dos_metadados(conexao):
    item = buscar(conexao, "aerodromos")[0]
    assert item.dados_atualizados_em is None


def test_resumo_do_evento_final_traz_as_duas_chaves(cliente):
    fim = fim_de(eventos(cliente.post("/perguntar", json={"pergunta": "dengue"})))
    ficha = fim["fichas"][0]
    assert "dados_atualizados_em" in ficha
    assert "metadados_atualizados_em" in ficha
    assert ficha["dados_atualizados_em"] == "2023-05-01T00:00:00+00:00"


def test_chave_da_data_existe_mesmo_quando_nula(cliente):
    fim = fim_de(eventos(cliente.post("/perguntar", json={"pergunta": "aerodromos"})))
    fichas = fim["fichas"]
    if fichas:
        assert fichas[0]["dados_atualizados_em"] is None
        assert "metadados_atualizados_em" in fichas[0]


# --- roteamento ----------------------------------------------------------


def _rec(nome, pontuacao):
    return Recuperado("i", 1, pontuacao, nome, nome, "o", "alta", "r")


def test_correspondencia_direta_quando_destacada():
    rota = decidir(
        [_rec("a", 30.0), _rec("b", 5.0)],
        limiar_template=18.0, margem_template=2.0, limiar_relevancia=3.0,
    )
    assert rota.origem is Origem.TEMPLATE


def test_pontuacoes_proximas_acionam_o_modelo():
    rota = decidir(
        [_rec("a", 30.0), _rec("b", 29.5)],
        limiar_template=18.0, margem_template=2.0, limiar_relevancia=3.0,
    )
    assert rota.origem is Origem.MODELO


def test_primeiro_abaixo_do_limiar_aciona_o_modelo():
    rota = decidir(
        [_rec("a", 10.0)],
        limiar_template=18.0, margem_template=2.0, limiar_relevancia=3.0,
    )
    assert rota.origem is Origem.MODELO


def test_nada_relevante_vira_ausencia():
    rota = decidir(
        [_rec("a", 1.0)],
        limiar_template=18.0, margem_template=2.0, limiar_relevancia=3.0,
    )
    assert rota.origem is Origem.AUSENCIA
    assert rota.fichas == []


def test_sem_resultado_vira_ausencia():
    rota = decidir([], limiar_template=18.0, margem_template=2.0, limiar_relevancia=3.0)
    assert rota.origem is Origem.AUSENCIA


def test_limiares_configuraveis_mudam_a_rota():
    fichas = [_rec("a", 10.0), _rec("b", 1.0)]
    conservador = decidir(
        fichas, limiar_template=18.0, margem_template=2.0, limiar_relevancia=3.0
    )
    frouxo = decidir(
        fichas, limiar_template=5.0, margem_template=2.0, limiar_relevancia=3.0
    )
    assert conservador.origem is Origem.MODELO
    assert frouxo.origem is Origem.TEMPLATE


# --- guarda de saída -----------------------------------------------------


def _ficha_com_link():
    f = Recuperado("1", 1, 9.0, "arboviroses-dengue", "T", "o", "alta", "r")
    f.recursos = [Recurso("a", "https://exemplo.gov.br/deng23.csv", "csv", True)]
    return f


def test_url_fabricada_reprova():
    v = guarda.verificar("veja https://inventado.gov.br/x.csv", [_ficha_com_link()])
    assert not v.aprovada
    assert v.urls_fabricadas == ["https://inventado.gov.br/x.csv"]


def test_url_do_contexto_aprova():
    v = guarda.verificar("veja https://exemplo.gov.br/deng23.csv", [_ficha_com_link()])
    assert v.aprovada


def test_url_da_pagina_do_portal_aprova():
    f = _ficha_com_link()
    v = guarda.verificar(f"acesse {f.url_portal}", [f])
    assert v.aprovada


def test_pontuacao_final_nao_faz_parte_da_url():
    f = _ficha_com_link()
    v = guarda.verificar(f"acesse {f.url_portal}.", [f])
    assert v.aprovada


def test_conjunto_nao_recuperado_reprova():
    texto = "veja https://dados.gov.br/dados/conjuntos-dados/outro-conjunto"
    v = guarda.verificar(texto, [_ficha_com_link()])
    assert not v.aprovada
    assert v.conjuntos_inventados == ["outro-conjunto"]


def test_texto_sem_url_aprova():
    assert guarda.verificar("nenhum link aqui", [_ficha_com_link()]).aprovada


# --- redação sem token ---------------------------------------------------


def test_template_traz_link_do_portal_e_marca_indisponivel(conexao):
    item = buscar(conexao, "dengue")[0]
    texto = redacao.montar_template(item)
    assert item.url_portal in texto
    assert "fora do ar" in texto
    assert "Dengue 2010" in texto


def test_template_avisa_quando_confianca_e_baixa():
    f = Recuperado("2", 1, 9.0, "x", "X", "o", "baixa", "resumo")
    assert "pouca descrição" in redacao.montar_template(f)


def test_ausencia_nao_menciona_conjunto():
    texto = redacao.montar_ausencia()
    assert "não encontrei" in texto.lower()
    assert "dados.gov.br/dados/conjuntos-dados" not in texto


# --- stub ----------------------------------------------------------------


async def test_stub_nao_consome_tokens_nem_importa_o_cliente(monkeypatch):
    def explodir(*a, **k):
        raise AssertionError("o stub não pode instanciar o cliente da Anthropic")

    monkeypatch.setattr(geracao, "gerar_com_modelo", explodir)
    pedacos = [p async for p in geracao.gerar_stub("q", [], intervalo=0)]
    assert "".join(pedacos).strip()


async def test_modelo_sem_chave_ergue_indisponivel():
    with pytest.raises(geracao.ModeloIndisponivel):
        async for _ in geracao.gerar_com_modelo("q", [], chave="", modelo="m"):
            pass


def test_contexto_contem_so_as_fichas_recuperadas():
    f = _ficha_com_link()
    contexto = geracao.montar_contexto([f])
    assert "arboviroses-dengue" in contexto
    assert "aerodromos" not in contexto


def test_contexto_marca_ficha_de_confianca_baixa():
    f = Recuperado("2", 1, 9.0, "x", "X", "o", "baixa", "r")
    assert "ATENÇÃO" in geracao.montar_contexto([f])


# --- serviço -------------------------------------------------------------


def test_saude_responde(cliente):
    dados = cliente.get("/saude").json()
    assert dados["ok"] is True and dados["fichas"] == 2


def test_perguntar_usa_sse_com_cabecalhos_contra_buffer(cliente):
    r = cliente.post("/perguntar", json={"pergunta": "dengue"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"


def test_template_sai_pelo_mesmo_canal_sse(cliente):
    evs = eventos(cliente.post("/perguntar", json={"pergunta": "dengue"}))
    nomes = [n for n, _ in evs]
    assert nomes[0] == "inicio" and nomes[-1] == "fim"
    assert "fragmento" in nomes


def test_resposta_declara_a_origem(cliente):
    fim = fim_de(eventos(cliente.post("/perguntar", json={"pergunta": "dengue"})))
    assert fim["origem"] in {o.value for o in Origem}
    assert "latencia_ms" in fim


def test_pergunta_sem_resposta_diz_que_nao_encontrou(cliente):
    evs = eventos(cliente.post("/perguntar", json={"pergunta": "criptomoeda"}))
    assert fim_de(evs)["origem"] == Origem.AUSENCIA.value
    assert "não encontrei" in texto_de(evs).lower()
    assert fim_de(evs)["fichas"] == []


def test_pergunta_vazia_e_rejeitada(cliente):
    assert cliente.post("/perguntar", json={"pergunta": ""}).status_code == 422


# --- contenção no serviço ------------------------------------------------


@pytest.fixture
def cliente_contido(catalogo, tmp_path, monkeypatch):
    """Serviço com teto de 1 chamada e limite de 2 por origem."""
    from app.configuracao import configuracao as cfg
    import app.principal as principal

    cfg.cache_clear()
    principal._contencao = None
    monkeypatch.setenv("BANCO", str(catalogo))
    monkeypatch.setenv("MODO_STUB", "1")
    monkeypatch.setenv("LIMIAR_RELEVANCIA", "0.0")
    monkeypatch.setenv("ESTADO_DIR", str(tmp_path / "estado"))
    monkeypatch.setenv("TETO_DIARIO_MODELO", "1")
    monkeypatch.setenv("LIMITE_ORIGEM_MAXIMO", "2")
    monkeypatch.setenv("LIMITE_ORIGEM_JANELA", "3600")

    with TestClient(principal.app) as c:
        yield c
    if principal._contencao:
        principal._contencao.fechar()
    principal._contencao = None
    cfg.cache_clear()


def _perguntar(cliente, texto="dengue", ip="1.2.3.4"):
    return cliente.post(
        "/perguntar", json={"pergunta": texto}, headers={"x-origem-real": ip}
    )


def test_teto_estourado_nunca_devolve_erro(cliente_contido):
    from app.principal import contencao

    contencao().registrar_chamada()  # atinge o teto de 1
    r = _perguntar(cliente_contido)
    assert r.status_code == 200
    evs = eventos(r)
    assert fim_de(evs)["origem"] == Origem.REDUZIDO.value
    # A recuperação continua inteira: os conjuntos vêm com seus links.
    assert fim_de(evs)["fichas"]
    assert "volta amanhã" in texto_de(evs)


def test_origem_excedida_recebe_429_com_retry_after(cliente_contido):
    _perguntar(cliente_contido)
    _perguntar(cliente_contido)
    r = _perguntar(cliente_contido)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


def test_origens_diferentes_tem_baldes_proprios(cliente_contido):
    _perguntar(cliente_contido, ip="1.1.1.1")
    _perguntar(cliente_contido, ip="1.1.1.1")
    assert _perguntar(cliente_contido, ip="1.1.1.1").status_code == 429
    assert _perguntar(cliente_contido, ip="2.2.2.2").status_code == 200


def test_endereco_vem_do_cabecalho_nao_do_socket(cliente_contido):
    # Sem o cabeçalho, o TestClient seria sempre o mesmo socket e os dois
    # visitantes cairiam no mesmo balde.
    _perguntar(cliente_contido, ip="10.0.0.1")
    _perguntar(cliente_contido, ip="10.0.0.1")
    assert _perguntar(cliente_contido, ip="10.0.0.1").status_code == 429
    assert _perguntar(cliente_contido, ip="10.0.0.2").status_code == 200


def test_stub_nao_consome_o_teto(cliente_contido):
    from app.principal import contencao

    antes = contencao().consumo_do_dia()
    _perguntar(cliente_contido, ip="7.7.7.7")
    # Em modo stub nenhuma chamada ao modelo acontece, então nada é debitado.
    assert contencao().consumo_do_dia() == antes


def test_operacao_expoe_consumo(cliente_contido):
    d = cliente_contido.get("/operacao").json()
    assert d["teto"] == 1
    assert d["limite_por_origem"] == 2
    assert "consumo" in d and "modo_reduzido" in d
