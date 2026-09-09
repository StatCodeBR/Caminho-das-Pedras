"""Testes da coleta bruta. Nenhum deles toca a rede: tudo passa pelo respx."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

import coleta

URL_BASE = "https://portal.teste/api/publico"
LISTAGEM = f"{URL_BASE}/conjuntos-dados"


@pytest.fixture(autouse=True)
def recuo_rapido(monkeypatch):
    """Recuo microscópico: o teste verifica a repetição, não a espera."""
    monkeypatch.setenv("COLETA_RECUO_BASE", "0.001")


@pytest.fixture
def caminhos(tmp_path: Path):
    return {
        "destino": tmp_path / "conjuntos.jsonl",
        "caminho_progresso": tmp_path / "progresso.json",
        "caminho_falhas": tmp_path / "falhas.jsonl",
    }


def conjunto(identificador: str) -> dict:
    return {"id": identificador, "title": f"Conjunto {identificador}"}


def detalhe(identificador: str) -> dict:
    return {
        "id": identificador,
        "title": f"Conjunto {identificador}",
        "recursos": [{"url": f"https://exemplo.gov.br/{identificador}.csv"}],
    }


def registrar_catalogo(mock, paginas: dict[int, list[dict]]) -> None:
    """Responde a listagem por página e o detalhe de qualquer identificador."""

    def responder_listagem(requisicao: httpx.Request) -> httpx.Response:
        pagina = int(requisicao.url.params.get("pagina", 1))
        return httpx.Response(200, json=paginas.get(pagina, []))

    mock.get(url=LISTAGEM).mock(side_effect=responder_listagem)
    mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(
        side_effect=lambda req: httpx.Response(
            200, json=detalhe(req.url.path.rsplit("/", 1)[-1])
        )
    )


def ler_jsonl(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines() if linha.strip()]


async def test_reexecucao_nao_duplica_registros(caminhos):
    """Cenário: coleta já concluída — o JSONL existente fica inalterado."""
    paginas = {1: [conjunto("a"), conjunto("b"), conjunto("c")], 2: []}

    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, paginas)
        primeira = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    assert primeira.gravados == 3
    conteudo_inicial = caminhos["destino"].read_text(encoding="utf-8")

    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, paginas)
        segunda = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    assert segunda.ja_concluida is True
    assert caminhos["destino"].read_text(encoding="utf-8") == conteudo_inicial

    identificadores = [registro["id"] for registro in ler_jsonl(caminhos["destino"])]
    assert identificadores == ["a", "b", "c"]
    assert len(identificadores) == len(set(identificadores))


async def test_retomada_nao_regrava_o_que_ja_esta_no_arquivo(caminhos):
    """Interrupção na página 2: retoma da 2 sem repetir os registros da 1."""
    paginas = {1: [conjunto("a"), conjunto("b")], 2: [conjunto("c")], 3: []}

    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, {1: paginas[1], 2: []})
        await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    # Simula a interrupção: a página 1 está confirmada, a coleta não terminou.
    progresso = coleta.Progresso.carregar(caminhos["caminho_progresso"])
    progresso.confirmar("completa", 1, concluida=False)

    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, paginas)
        retomada = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    identificadores = [registro["id"] for registro in ler_jsonl(caminhos["destino"])]
    assert identificadores == ["a", "b", "c"]
    assert retomada.gravados == 3


async def test_429_aciona_recuo_e_a_coleta_continua(caminhos):
    """Cenário: limite de taxa atingido — repete com recuo e não perde o item."""
    tentativas = {"listagem": 0}

    def responder_listagem(requisicao: httpx.Request) -> httpx.Response:
        pagina = int(requisicao.url.params.get("pagina", 1))
        if pagina == 1:
            tentativas["listagem"] += 1
            if tentativas["listagem"] <= 2:
                return httpx.Response(429)
            return httpx.Response(200, json=[conjunto("a"), conjunto("b")])
        return httpx.Response(200, json=[])

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url=LISTAGEM).mock(side_effect=responder_listagem)
        mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(
            side_effect=lambda req: httpx.Response(
                200, json=detalhe(req.url.path.rsplit("/", 1)[-1])
            )
        )
        resultado = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    assert tentativas["listagem"] == 3
    assert resultado.recuos == 2
    assert resultado.gravados == 2
    assert [registro["id"] for registro in ler_jsonl(caminhos["destino"])] == ["a", "b"]


async def test_falha_persistente_vai_para_falhas_sem_abortar(caminhos):
    """Cenário: falha persistente — anota, segue em frente e termina bem."""

    def responder_detalhe(requisicao: httpx.Request) -> httpx.Response:
        identificador = requisicao.url.path.rsplit("/", 1)[-1]
        if identificador == "b":
            return httpx.Response(500)
        return httpx.Response(200, json=detalhe(identificador))

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url=LISTAGEM).mock(
            side_effect=lambda req: httpx.Response(
                200,
                json=[conjunto("a"), conjunto("b")]
                if int(req.url.params.get("pagina", 1)) == 1
                else [],
            )
        )
        mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(side_effect=responder_detalhe)
        resultado = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    assert resultado.falhas == 1
    falhas = ler_jsonl(caminhos["caminho_falhas"])
    assert falhas[0]["identificador"] == "b"
    assert "500" in falhas[0]["motivo"]

    registros = {registro["id"]: registro for registro in ler_jsonl(caminhos["destino"])}
    assert registros["a"]["detalhe"] is not None
    assert registros["b"]["detalhe"] is None


async def test_amostra_garante_sementes_resolvidas_por_identificador(caminhos):
    """Cenário: amostra pequena com sementes garantidas."""

    def responder_detalhe(requisicao: httpx.Request) -> httpx.Response:
        identificador = requisicao.url.path.rsplit("/", 1)[-1]
        # O slug não resolve pelo título: é o endpoint de detalhe que o aceita.
        if identificador == "slug-que-nao-existe":
            return httpx.Response(404)
        return httpx.Response(200, json=detalhe(identificador))

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url=LISTAGEM).mock(
            side_effect=lambda req: httpx.Response(
                200,
                json=[
                    conjunto(f"p{req.url.params.get('pagina', 1)}-{n}") for n in range(15)
                ],
            )
        )
        mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(side_effect=responder_detalhe)
        resultado = await coleta.coletar(
            chave="chave-falsa",
            url_base=URL_BASE,
            limite=6,
            sementes=["arboviroses-dengue", "ideb-por-estados", "slug-que-nao-existe"],
            **caminhos,
        )

    registros = ler_jsonl(caminhos["destino"])
    identificadores = {registro["id"] for registro in registros}
    assert resultado.gravados == 6
    assert {"arboviroses-dengue", "ideb-por-estados"}.issubset(identificadores)

    # A semente que não resolve vira falha registrada, não some em silêncio.
    assert resultado.sementes_nao_resolvidas == 1
    falhas = [f["identificador"] for f in ler_jsonl(caminhos["caminho_falhas"])]
    assert "slug-que-nao-existe" in falhas

    origens = {registro["id"]: registro["pagina_origem"] for registro in registros}
    assert origens["arboviroses-dengue"] == "semente:arboviroses-dengue"
    # O resto da amostra vem da listagem geral.
    assert any(isinstance(origem, int) for origem in origens.values())


async def test_pagina_vazia_intermitente_nao_encerra_a_coleta(caminhos):
    """Cenário: página vazia é confirmada antes de encerrar."""
    vistas: dict[int, int] = {}

    def responder_listagem(requisicao: httpx.Request) -> httpx.Response:
        pagina = int(requisicao.url.params.get("pagina", 1))
        vistas[pagina] = vistas.get(pagina, 0) + 1
        if pagina >= 4:
            return httpx.Response(200, json=[])
        # A página 2 mente duas vezes antes de entregar o conteúdo real.
        if pagina == 2 and vistas[pagina] <= 2:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[conjunto(f"p{pagina}-{n}") for n in range(15)])

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url=LISTAGEM).mock(side_effect=responder_listagem)
        mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(
            side_effect=lambda req: httpx.Response(
                200, json=detalhe(req.url.path.rsplit("/", 1)[-1])
            )
        )
        resultado = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    # Sem a confirmação, a coleta teria parado na página 2 com 15 registros.
    assert resultado.gravados == 45
    assert resultado.vazios_repetidos >= 2
    assert vistas[2] >= 3


async def test_pagina_incompleta_encerra_a_listagem(caminhos):
    """Cenário: página incompleta encerra a listagem."""
    paginas = {1: [conjunto(f"a{n}") for n in range(15)], 2: [conjunto("b0"), conjunto("b1")]}

    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, paginas)
        resultado = await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    assert resultado.gravados == 17
    assert resultado.paginas == 2
    # Encerrou pela página parcial, sem gastar as repetições de confirmação.
    assert resultado.vazios_repetidos == 0


async def test_metadados_de_coleta_e_objeto_original_preservados(caminhos):
    """Cenário: resposta preservada na íntegra, com os metadados de coleta."""
    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, {1: [conjunto("a")], 2: []})
        await coleta.coletar(chave="chave-falsa", url_base=URL_BASE, **caminhos)

    registro = ler_jsonl(caminhos["destino"])[0]
    assert registro["title"] == "Conjunto a"
    assert registro["pagina_origem"] == 1
    assert registro["coletado_em"].endswith("+00:00")
    assert registro["detalhe"]["recursos"][0]["url"].endswith("a.csv")


def test_ausencia_de_credencial_encerra_com_codigo_diferente_de_zero(monkeypatch, tmp_path):
    """Cenário: credencial ausente — sai antes de qualquer requisição."""
    monkeypatch.setenv("DADOS_GOV_API_KEY", "")
    monkeypatch.setattr(coleta, "carregar_env", lambda: None)
    monkeypatch.setattr(coleta, "DIRETORIO_BRUTO", tmp_path / "bruto")

    with respx.mock(assert_all_called=False) as mock:
        rota = mock.get(url__startswith="https://").mock(return_value=httpx.Response(200, json=[]))
        resultado = CliRunner().invoke(coleta.app, [])

    assert resultado.exit_code != 0
    assert rota.call_count == 0
    assert "dados.gov.br" in resultado.output


def test_chave_nunca_aparece_no_log(capsys):
    """Cenário: credencial nunca registrada em log."""
    coleta.registrar_segredo("chave-ultrassecreta")
    coleta.log("falhou ao usar a chave chave-ultrassecreta na requisição")

    saida = capsys.readouterr().err
    assert "chave-ultrassecreta" not in saida
    assert "***" in saida


# --- falha de página: recuo, retentativa e encerramento honesto ----------


async def test_405_e_repetivel_nao_permanente():
    """O 405 que derrubou a coleta era limite de taxa vestido de erro."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url=LISTAGEM).mock(
            side_effect=[
                httpx.Response(405, html="<html>bloqueado</html>"),
                httpx.Response(405, html="<html>bloqueado</html>"),
                httpx.Response(200, json=[conjunto("a")]),
            ]
        )
        async with httpx.AsyncClient(base_url=URL_BASE) as http:
            portal = coleta.ClientePortal(http)
            itens = await portal.listar({"pagina": 1})
    # Insistiu e passou, em vez de desistir na primeira recusa.
    assert [i["id"] for i in itens] == ["a"]
    assert portal.recuos == 2


async def test_html_no_lugar_de_json_e_repetivel():
    """Corpo HTML numa API JSON é proxy respondendo pelo servidor."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url=LISTAGEM).mock(
            side_effect=[
                httpx.Response(200, html="<html>WAF</html>"),
                httpx.Response(200, json=[conjunto("b")]),
            ]
        )
        async with httpx.AsyncClient(base_url=URL_BASE) as http:
            portal = coleta.ClientePortal(http)
            itens = await portal.listar({"pagina": 1})
    assert [i["id"] for i in itens] == ["b"]


async def test_404_continua_permanente():
    """Conjunto inexistente não melhora com repetição; insistir é desperdício."""
    with respx.mock(assert_all_called=False) as mock:
        rota = mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(
            return_value=httpx.Response(404)
        )
        async with httpx.AsyncClient(base_url=URL_BASE) as http:
            portal = coleta.ClientePortal(http)
            with pytest.raises(coleta.ErroPermanente):
                await portal.detalhar("sumido")
        assert rota.call_count == 1


async def test_falha_persistente_marca_coleta_como_truncada(caminhos, monkeypatch):
    """Esgotadas as tentativas, a coleta para dizendo que parou por falha."""
    monkeypatch.setenv("COLETA_PAUSA_PAGINA", "0")
    with respx.mock(assert_all_called=False) as mock:
        def responder(requisicao: httpx.Request) -> httpx.Response:
            if int(requisicao.url.params.get("pagina", 1)) == 1:
                return httpx.Response(200, json=[conjunto("x")])
            return httpx.Response(405, html="<html>bloqueado</html>")

        mock.get(url=LISTAGEM).mock(side_effect=responder)
        mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(
            side_effect=lambda req: httpx.Response(
                200, json=detalhe(req.url.path.rsplit("/", 1)[-1])
            )
        )
        resultado = await coleta.coletar(chave="k", url_base=URL_BASE, **caminhos)

    assert resultado.truncada is True
    assert resultado.pagina_da_falha == 2
    assert "405" in resultado.motivo_da_falha
    # O progresso NÃO é marcado como concluído: a próxima execução retoma.
    estado = json.loads(caminhos["caminho_progresso"].read_text(encoding="utf-8"))
    assert estado["completa"]["concluida"] is False
    assert estado["completa"]["ultima_pagina"] == 1


async def test_fim_de_listagem_nao_e_falha(caminhos, monkeypatch):
    """Fim legítimo continua sendo sucesso, com progresso concluído."""
    monkeypatch.setenv("COLETA_PAUSA_PAGINA", "0")
    with respx.mock(assert_all_called=False) as mock:
        registrar_catalogo(mock, {1: [conjunto("x")]})
        resultado = await coleta.coletar(chave="k", url_base=URL_BASE, **caminhos)

    assert resultado.truncada is False
    estado = json.loads(caminhos["caminho_progresso"].read_text(encoding="utf-8"))
    assert estado["completa"]["concluida"] is True


def test_coleta_truncada_sai_com_codigo_diferente_de_zero(caminhos, monkeypatch):
    """Sair com zero faria a normalização seguir com catálogo pela metade."""
    monkeypatch.setenv("COLETA_PAUSA_PAGINA", "0")
    monkeypatch.setenv("DADOS_GOV_API_KEY", "k")
    monkeypatch.setattr(coleta, "DIRETORIO_BRUTO", caminhos["destino"].parent)
    with respx.mock(assert_all_called=False) as mock:
        def responder(requisicao: httpx.Request) -> httpx.Response:
            if int(requisicao.url.params.get("pagina", 1)) == 1:
                return httpx.Response(200, json=[conjunto("x")])
            return httpx.Response(405, html="<html>bloqueado</html>")

        mock.get(url=LISTAGEM).mock(side_effect=responder)
        mock.get(url__regex=rf"{LISTAGEM}/[^/?]+$").mock(
            side_effect=lambda req: httpx.Response(
                200, json=detalhe(req.url.path.rsplit("/", 1)[-1])
            )
        )
        monkeypatch.setenv("DADOS_GOV_API_URL", URL_BASE)
        resultado = CliRunner().invoke(coleta.app, [])

    assert resultado.exit_code != 0
    assert "POR FALHA" in resultado.output.upper()
    assert "retoma" in resultado.output


# --- contenção de taxa ---------------------------------------------------


def test_concorrencia_padrao_e_duas():
    """Dez simultâneas derrubaram o acesso; duas é a lição registrada."""
    assert coleta.CONCORRENCIA == 2


def test_concorrencia_ajustavel_por_ambiente(monkeypatch):
    monkeypatch.setenv("COLETA_CONCORRENCIA", "1")
    assert coleta.concorrencia_configurada() == 1
    monkeypatch.setenv("COLETA_CONCORRENCIA", "lixo")
    assert coleta.concorrencia_configurada() == coleta.CONCORRENCIA


def test_pausa_entre_paginas_existe_por_padrao(monkeypatch):
    monkeypatch.delenv("COLETA_PAUSA_PAGINA", raising=False)
    monkeypatch.setenv("COLETA_RECUO_BASE", "1")
    assert coleta.pausa_configurada() >= 1.0


def test_pausa_zeravel_para_teste(monkeypatch):
    monkeypatch.setenv("COLETA_PAUSA_PAGINA", "0")
    assert coleta.pausa_configurada() == 0.0
