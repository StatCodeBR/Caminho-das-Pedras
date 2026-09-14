"""Testes da verificação de saúde. Nenhuma requisição sai da máquina."""

from __future__ import annotations

import asyncio
import json
import socket
import sqlite3
import ssl
from pathlib import Path

import httpx
import pytest
import respx

import normaliza
import saude


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    """Catálogo com quatro recursos: três com link, um sem."""
    detalhe = {
        "id": "id-1",
        "nome": "conjunto-1",
        "titulo": "Conjunto 1",
        "descricao": "Descrição.",
        "organizacao": "orgao",
        "tags": [],
        "temas": [],
        "descontinuado": False,
        "recursos": [
            {"id": "r-ok", "titulo": "Vivo", "link": "https://exemplo.gov.br/vivo.csv"},
            {"id": "r-sumiu", "titulo": "Morto", "link": "https://exemplo.gov.br/morto.csv"},
            {"id": "r-lento", "titulo": "Lento", "link": "https://lento.gov.br/lento.csv"},
            {"id": "r-sem-link", "titulo": "Sem link", "link": None},
        ],
    }
    entrada = tmp_path / "conjuntos.jsonl"
    entrada.write_text(
        json.dumps({"id": "id-1", "nome": "conjunto-1", "detalhe": detalhe}, ensure_ascii=False),
        encoding="utf-8",
    )
    caminho = tmp_path / "dados.db"
    normaliza.normalizar(entrada, caminho, tmp_path / "quarentena.jsonl")
    return caminho


def estado(banco: Path) -> dict[str, sqlite3.Row]:
    conexao = sqlite3.connect(banco)
    conexao.row_factory = sqlite3.Row
    try:
        return {linha["id"]: linha for linha in conexao.execute("SELECT * FROM recurso")}
    finally:
        conexao.close()


async def _verificar(banco: Path, **kwargs) -> saude.Relatorio:
    async with httpx.AsyncClient(
        timeout=saude.TIMEOUT_SEGUNDOS,
        follow_redirects=True,
        max_redirects=saude.MAX_REDIRECIONAMENTOS,
        headers={"User-Agent": saude.user_agent()},
    ) as cliente:
        return await saude.verificar_tudo(banco=banco, cliente=cliente, **kwargs)


# --- classificação -------------------------------------------------------


def test_classificacao_por_status():
    """Cenários: disponível, removido, servidor lento ou intermitente."""
    assert saude.classificar(200) == "disponivel"
    assert saude.classificar(206) == "disponivel"
    assert saude.classificar(404) == "indisponivel"
    assert saude.classificar(410) == "indisponivel"
    assert saude.classificar(500) == "instavel"
    assert saude.classificar(503) == "instavel"
    # Excesso de requisições é o servidor pedindo calma, não arquivo removido.
    assert saude.classificar(429) == "instavel"


async def test_servidor_que_aceita_head_nao_gera_segunda_requisicao(banco):
    """Cenário: servidor que aceita HEAD."""
    with respx.mock(assert_all_called=False) as mock:
        head = mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        get = mock.get(url__startswith="https://").mock(return_value=httpx.Response(200))
        await _verificar(banco)

    assert head.call_count == 3
    assert get.call_count == 0
    assert estado(banco)["r-ok"]["classe_saude"] == "disponivel"


async def test_servidor_que_rejeita_head_e_verificado_por_get(banco):
    """Cenário: servidor que rejeita HEAD."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(405))
        get = mock.get(url__startswith="https://").mock(return_value=httpx.Response(206))
        await _verificar(banco)

    assert get.call_count == 3
    # O Range evita baixar o arquivo inteiro só para saber se ele existe.
    assert get.calls[0].request.headers["Range"] == f"bytes=0-{saude.BYTES_DO_RANGE - 1}"
    assert estado(banco)["r-ok"]["classe_saude"] == "disponivel"
    assert estado(banco)["r-ok"]["status_http"] == 206


async def test_head_recusado_com_403_cai_para_get(banco):
    """Cenário: recusa de método não é arquivo removido.

    www.gov.br responde 403 a HEAD e 206 ao mesmo endereço via GET, com
    qualquer User-Agent. Tratar isso como link morto perderia 717 recursos.
    """
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(403))
        get = mock.get(url__startswith="https://").mock(return_value=httpx.Response(206))
        await _verificar(banco)

    assert get.call_count == 3
    recurso = estado(banco)["r-ok"]
    assert recurso["status_http"] == 206
    assert recurso["classe_saude"] == "disponivel"


async def test_403_persistente_no_get_continua_indisponivel(banco):
    """A queda para GET não pode transformar bloqueio real em disponível."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(403))
        mock.get(url__startswith="https://").mock(return_value=httpx.Response(403))
        await _verificar(banco)

    assert estado(banco)["r-ok"]["classe_saude"] == "indisponivel"


async def test_timeout_vira_instavel_e_nao_indisponivel(banco):
    """Cenário: servidor lento — não é tratado como removido."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://lento").mock(
            side_effect=httpx.ReadTimeout("demorou")
        )
        mock.head(url__startswith="https://exemplo").mock(return_value=httpx.Response(200))
        await _verificar(banco)

    lento = estado(banco)["r-lento"]
    assert lento["classe_saude"] == "instavel"
    assert lento["classe_saude"] != "indisponivel"
    assert lento["status_http"] is None
    assert lento["latencia_ms"] is not None


async def test_recurso_sem_url_nao_gera_requisicao(banco):
    """Cenário: recurso sem URL."""
    with respx.mock(assert_all_called=False) as mock:
        rota = mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        await _verificar(banco)

    # Três recursos com link; o quarto não encosta na rede.
    assert rota.call_count == 3
    sem_link = estado(banco)["r-sem-link"]
    assert sem_link["classe_saude"] == "nao_verificado"
    assert sem_link["status_http"] is None
    assert sem_link["latencia_ms"] is None


async def test_link_que_nao_e_url_nao_gera_requisicao(banco):
    """O portal guarda frases no campo de link; elas não podem derrubar a coleta."""
    conexao = sqlite3.connect(banco)
    conexao.execute(
        "UPDATE recurso SET link = ? WHERE id = ?",
        ("http://Dissertação, tese, TCC, memorial.", "r-ok"),
    )
    conexao.commit()
    conexao.close()

    with respx.mock(assert_all_called=False) as mock:
        rota = mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        relatorio = await _verificar(banco)

    assert rota.call_count == 2  # o link torto não vira requisição
    assert estado(banco)["r-ok"]["classe_saude"] == "nao_verificado"
    assert relatorio.verificados == 4  # e nada é perdido pelo caminho


def test_reconhecimento_de_url_utilizavel():
    assert saude.url_utilizavel("https://dados.gov.br/a.csv")
    assert not saude.url_utilizavel("http://Dissertação, tese, TCC.")
    assert not saude.url_utilizavel("https://www.anatel.gov.br\\dadosabertos\\PDA")
    assert not saude.url_utilizavel("URL: https://dadosabertos.ifba.edu.br/x")
    assert not saude.url_utilizavel("ftp://arquivo.gov.br/a.csv")


async def test_redirecionamento_registra_o_status_final(banco):
    """Cenário: redirecionamento."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url="https://exemplo.gov.br/vivo.csv").mock(
            return_value=httpx.Response(302, headers={"Location": "https://exemplo.gov.br/novo.csv"})
        )
        mock.head(url="https://exemplo.gov.br/novo.csv").mock(return_value=httpx.Response(200))
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(404))
        await _verificar(banco)

    assert estado(banco)["r-ok"]["status_http"] == 200
    assert estado(banco)["r-ok"]["classe_saude"] == "disponivel"


# --- carimbo e contenção -------------------------------------------------


async def test_checado_em_esta_em_utc(banco):
    """Cenário: carimbo sempre em UTC."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        await _verificar(banco)

    for recurso in estado(banco).values():
        assert recurso["checado_em"].endswith("+00:00")


async def test_no_maximo_duas_requisicoes_simultaneas_por_host(tmp_path):
    """Cenário: muitos recursos do mesmo órgão."""
    simultaneas = {"agora": 0, "pico": 0}

    async def responder(requisicao: httpx.Request) -> httpx.Response:
        simultaneas["agora"] += 1
        simultaneas["pico"] = max(simultaneas["pico"], simultaneas["agora"])
        await asyncio.sleep(0.01)
        simultaneas["agora"] -= 1
        return httpx.Response(200)

    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(side_effect=responder)
        async with httpx.AsyncClient() as cliente:
            verificador = saude.Verificador(cliente)
            await asyncio.gather(
                *(
                    verificador.verificar(f"https://mesmo-orgao.gov.br/{n}.csv")
                    for n in range(20)
                )
            )

    assert simultaneas["pico"] <= saude.CONCORRENCIA_POR_HOST


async def test_hosts_diferentes_seguem_em_paralelo():
    """Cenário: outros domínios continuam sendo verificados em paralelo."""
    simultaneas = {"agora": 0, "pico": 0}

    async def responder(requisicao: httpx.Request) -> httpx.Response:
        simultaneas["agora"] += 1
        simultaneas["pico"] = max(simultaneas["pico"], simultaneas["agora"])
        await asyncio.sleep(0.01)
        simultaneas["agora"] -= 1
        return httpx.Response(200)

    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(side_effect=responder)
        async with httpx.AsyncClient() as cliente:
            verificador = saude.Verificador(cliente)
            await asyncio.gather(
                *(verificador.verificar(f"https://orgao-{n}.gov.br/a.csv") for n in range(10))
            )

    # Dez hosts distintos: o limite por host não deve serializar o conjunto.
    assert simultaneas["pico"] > saude.CONCORRENCIA_POR_HOST


def test_user_agent_identifica_projeto_e_contato(monkeypatch):
    """Cenário: identificação do agente."""
    monkeypatch.setenv("SAUDE_CONTATO", "equipe@exemplo.org")
    agente = saude.user_agent()

    assert saude.PROJETO in agente
    assert "equipe@exemplo.org" in agente


def test_user_agent_sem_contato_configurado_e_explicito(monkeypatch):
    monkeypatch.delenv("SAUDE_CONTATO", raising=False)
    assert saude.CONTATO_NAO_INFORMADO in saude.user_agent()


# --- reverificação seletiva ---------------------------------------------


async def test_idade_maxima_pula_o_que_foi_checado_ha_pouco(banco):
    """Cenário: execução incremental."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        await _verificar(banco)

    with respx.mock(assert_all_called=False) as mock:
        rota = mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        relatorio = await _verificar(banco, idade_maxima=7)

    assert rota.call_count == 0
    assert relatorio.verificados == 0
    assert relatorio.pulados == 4


async def test_somente_falhas_reprocessa_apenas_os_nao_disponiveis(banco):
    """Cenário: reprocessar apenas falhas."""
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url="https://exemplo.gov.br/vivo.csv").mock(return_value=httpx.Response(200))
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(404))
        await _verificar(banco)

    antes = estado(banco)
    assert antes["r-ok"]["classe_saude"] == "disponivel"
    assert antes["r-sumiu"]["classe_saude"] == "indisponivel"

    with respx.mock(assert_all_called=False) as mock:
        rota = mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        relatorio = await _verificar(banco, somente_falhas=True)

    # Só o disponível fica de fora. O sem-URL entra por exclusão, e custa zero
    # requisição: a verificação devolve `nao_verificado` antes de tocar a rede.
    # Entrar é o certo — uma coleta posterior pode ter dado link a ele, e uma
    # lista enumerada o deixaria fora para sempre.
    assert rota.call_count == 2
    assert relatorio.verificados == 3
    assert estado(banco)["r-ok"]["status_http"] == 200


async def test_relatorio_traz_distribuicao_por_classe(banco):
    with respx.mock(assert_all_called=False) as mock:
        mock.head(url="https://exemplo.gov.br/vivo.csv").mock(return_value=httpx.Response(200))
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(404))
        relatorio = await _verificar(banco)

    assert relatorio.verificados == 4
    assert relatorio.classes["disponivel"] == 1
    assert relatorio.classes["indisponivel"] == 2
    assert relatorio.classes["nao_verificado"] == 1


async def test_motivo_e_persistido_para_o_raio_x(banco):
    """Link malformado precisa ficar consultável, não só classificado."""
    conexao = sqlite3.connect(banco)
    conexao.execute(
        "UPDATE recurso SET link = ? WHERE id = ?",
        ("http://Dissertação, tese, TCC, memorial.", "r-ok"),
    )
    conexao.commit()
    conexao.close()

    with respx.mock(assert_all_called=False) as mock:
        mock.head(url__startswith="https://").mock(return_value=httpx.Response(200))
        await _verificar(banco)

    atual = estado(banco)
    assert atual["r-ok"]["motivo_saude"] == "link não é uma URL"
    assert atual["r-sem-link"]["motivo_saude"] == "recurso sem URL"
    # Quem respondeu não precisa de motivo: o status já explica.
    assert atual["r-lento"]["motivo_saude"] is None


def test_glossario_cobre_todas_as_classes():
    """O relatório não pode publicar uma classe sem dizer o que ela significa."""
    assert set(saude.GLOSSARIO) == set(saude.CLASSES)


# --- causa da falha de conexão -------------------------------------------

CADEIAS = json.loads(
    (Path(__file__).parent / "fixtures" / "cadeias_tls.json").read_text(encoding="utf-8")
)


def _embrulhar(interno: BaseException) -> httpx.ConnectError:
    """Reproduz o embrulho do httpx: a causa real fica no fundo da cadeia."""
    try:
        try:
            raise interno
        except BaseException as erro:
            raise httpx.ConnectError("falha de conexão") from erro
    except httpx.ConnectError as topo:
        return topo


def _erro_do_caso(caso: dict) -> BaseException:
    if caso["erro"] == "gaierror":
        return socket.gaierror(caso["errno"], caso["verify_message"])
    erro = ssl.SSLCertVerificationError(1, caso["verify_message"])
    erro.verify_code = caso["verify_code"]
    erro.verify_message = caso["verify_message"]
    return erro


@pytest.mark.parametrize("caso", CADEIAS["casos"], ids=lambda c: c["host"])
def test_causa_da_falha_de_conexao_vem_da_cadeia_de_excecoes(caso):
    """Cenários: cadeia incompleta, certificado inválido, domínio que não resolve.

    As quatro chegam ao httpx como o mesmo ConnectError. O que as separa é o
    tipo lá no fundo da cadeia e, no certificado, o código numérico.
    """
    classe, _ = saude.classificar_falha_de_conexao(_embrulhar(_erro_do_caso(caso)))
    assert classe == caso["classe"]


def test_cadeia_incompleta_nao_e_confundida_com_certificado_vencido():
    """Cenário: certificado inválido.

    O vencido é defeito real que o navegador também denuncia; a cadeia faltando
    o navegador resolve sozinho. Tratá-los igual apagaria a diferença entre
    'este link avisa o usuário' e 'este link abre normalmente'.
    """
    incompleta = next(c for c in CADEIAS["casos"] if c.get("verify_code") == 20)
    vencido = next(c for c in CADEIAS["casos"] if c.get("verify_code") == 10)

    assert saude.classificar_falha_de_conexao(_embrulhar(_erro_do_caso(incompleta)))[0] == (
        "cadeia_incompleta"
    )
    assert saude.classificar_falha_de_conexao(_embrulhar(_erro_do_caso(vencido)))[0] == "instavel"


def test_causa_desconhecida_nao_vira_palpite():
    """Recusa de TCP não é cadeia, nem DNS, nem certificado: fica instável."""
    classe, motivo = saude.classificar_falha_de_conexao(
        _embrulhar(ConnectionRefusedError(111, "Connection refused"))
    )
    assert classe == "instavel"
    assert motivo == "ConnectionRefusedError"


def test_cadeia_profunda_nao_entra_em_laco():
    """Cadeia circular não pode travar o verificador."""
    a = ValueError("a")
    b = ValueError("b")
    a.__cause__ = b
    b.__cause__ = a
    classe, _ = saude.classificar_falha_de_conexao(a)
    assert classe == "instavel"


# --- reconhecimento de host que bloqueia ---------------------------------


def banco_de_hosts(tmp_path: Path, especificacao: list[tuple[str, int, int]]) -> Path:
    """Banco com recursos já verificados: (host, status, quantidade)."""
    caminho = tmp_path / "hosts.db"
    bruto = sqlite3.connect(caminho)
    bruto.execute(
        "CREATE TABLE recurso (id TEXT PRIMARY KEY, conjunto_id TEXT,"
        " titulo TEXT, link TEXT, formato TEXT)"
    )
    bruto.close()

    conexao = saude.abrir_banco(caminho)
    contador = 0
    for host, status, quantidade in especificacao:
        for _ in range(quantidade):
            contador += 1
            conexao.execute(
                "INSERT INTO recurso (id, conjunto_id, titulo, link, formato,"
                " status_http, classe_saude, checado_em)"
                " VALUES (?, 'c-1', 't', ?, 'csv', ?, ?, ?)",
                (
                    f"r-{contador}",
                    f"https://{host}/arquivo-{contador}.csv",
                    status,
                    saude.classificar(status),
                    saude.agora_utc(),
                ),
            )
    conexao.commit()
    conexao.close()
    return caminho


def classes_por_host(caminho: Path) -> dict[str, set[str]]:
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    saida: dict[str, set[str]] = {}
    for linha in conexao.execute("SELECT link, classe_saude FROM recurso"):
        host = saude._host(linha["link"])
        saida.setdefault(host, set()).add(linha["classe_saude"])
    conexao.close()
    return saida


def test_host_que_recusa_toda_a_verificacao_vira_bloqueado(tmp_path):
    """Cenário: host que recusa toda a verificação.

    Proporções do `cdn.tse.jus.br`, que devolveu 403 a 5.257 de 5.257.
    """
    caminho = banco_de_hosts(tmp_path, [("cdn.tse.jus.br", 403, 60)])
    conexao = saude.abrir_banco(caminho)
    try:
        corrigidos = saude.reconhecer_bloqueios(conexao)
    finally:
        conexao.close()

    assert corrigidos == {"cdn.tse.jus.br": 60}
    assert classes_por_host(caminho)["cdn.tse.jus.br"] == {"bloqueado"}


def test_host_que_responde_e_nega_arquivos_continua_ausencia(tmp_path):
    """Cenário: host que responde e nega arquivos específicos.

    O `www.gov.br` negou 452 e respondeu a milhares. Os 339 recursos com 403 em
    hosts assim são negativa por arquivo, e perdê-los para `bloqueado` apagaria
    ausência real.
    """
    caminho = banco_de_hosts(
        tmp_path, [("www.gov.br", 200, 40), ("www.gov.br", 403, 30)]
    )
    conexao = saude.abrir_banco(caminho)
    try:
        corrigidos = saude.reconhecer_bloqueios(conexao)
    finally:
        conexao.close()

    assert corrigidos == {}
    assert classes_por_host(caminho)["www.gov.br"] == {"disponivel", "indisponivel"}


def test_volume_abaixo_do_minimo_nao_acusa_bloqueio(tmp_path):
    """Cenário: poucos recursos não bastam como evidência.

    O `doi.org` tem um único 403 no catálogo inteiro. Acusá-lo de bloquear a
    partir de uma observação seria a afirmação sem sustentação que esta classe
    existe para evitar.
    """
    caminho = banco_de_hosts(
        tmp_path,
        [("doi.org", 403, 1), ("mapa.cultura.gov.br", 403, 11)],
    )
    conexao = saude.abrir_banco(caminho)
    try:
        corrigidos = saude.reconhecer_bloqueios(conexao)
    finally:
        conexao.close()

    assert corrigidos == {}
    classes = classes_por_host(caminho)
    assert classes["doi.org"] == {"indisponivel"}
    # Onze negativas provavelmente são bloqueio, e seguem contadas como
    # ausência. É o custo assumido do limiar, medido e registrado na 09.
    assert classes["mapa.cultura.gov.br"] == {"indisponivel"}


def test_host_no_limiar_exato_e_acusado(tmp_path):
    """O `www.marinha.mil.br` tinha 24 recursos, e entrou por pouco."""
    caminho = banco_de_hosts(
        tmp_path, [("www.marinha.mil.br", 403, saude.MINIMO_PARA_ACUSAR_BLOQUEIO)]
    )
    conexao = saude.abrir_banco(caminho)
    try:
        corrigidos = saude.reconhecer_bloqueios(conexao)
    finally:
        conexao.close()

    assert corrigidos == {"www.marinha.mil.br": saude.MINIMO_PARA_ACUSAR_BLOQUEIO}


def test_maioria_de_403_e_exigida(tmp_path):
    """Zero sucessos não basta: 404 em massa é catálogo podre, não bloqueio."""
    caminho = banco_de_hosts(tmp_path, [("portal.morto.gov.br", 404, 40)])
    conexao = saude.abrir_banco(caminho)
    try:
        corrigidos = saude.reconhecer_bloqueios(conexao)
    finally:
        conexao.close()

    assert corrigidos == {}
    assert classes_por_host(caminho)["portal.morto.gov.br"] == {"indisponivel"}


def test_reclassificacao_nao_emite_requisicao(tmp_path):
    """Cenário: reclassificação sem repetir a rede.

    O respx recusa qualquer requisição não declarada, então o teste falha se
    uma sair.
    """
    caminho = banco_de_hosts(tmp_path, [("cdn.tse.jus.br", 403, 40)])
    with respx.mock:
        relatorio = saude.reclassificar(caminho)

    assert relatorio.bloqueadores == {"cdn.tse.jus.br": 40}
    assert relatorio.classes == {"bloqueado": 40}


# --- diagnóstico ---------------------------------------------------------


def test_diagnostico_lista_hosts_bloqueadores(tmp_path, capsys):
    """Cenário: varredura com host bloqueado."""
    caminho = banco_de_hosts(tmp_path, [("cdn.tse.jus.br", 403, 40)])
    relatorio = saude.reclassificar(caminho)
    saude.imprimir_relatorio(relatorio, caminho)
    saida = capsys.readouterr().err

    assert "cdn.tse.jus.br" in saida
    assert "sem verificação possível: 40" in saida
    assert "ausência confirmada:      0" in saida


def test_diagnostico_declara_quando_nao_ha_bloqueio(tmp_path, capsys):
    """Cenário: varredura sem host bloqueado.

    O silêncio seria ambíguo: quem lê não saberia se não houve bloqueio ou se
    ninguém procurou.
    """
    caminho = banco_de_hosts(tmp_path, [("www.gov.br", 200, 30)])
    relatorio = saude.reclassificar(caminho)
    saude.imprimir_relatorio(relatorio, caminho)
    saida = capsys.readouterr().err

    assert "nenhum host recusou a verificação inteira" in saida


def test_diagnostico_nunca_mostra_ausencia_sozinha(tmp_path, capsys):
    """A proporção de links mortos não pode ser lida sem o que ficou cego.

    Na varredura de 2026-09-12 a diferença era o dobro: 9,1% contra 4,8%.
    """
    caminho = banco_de_hosts(
        tmp_path, [("cdn.tse.jus.br", 403, 40), ("outro.gov.br", 404, 30)]
    )
    relatorio = saude.reclassificar(caminho)
    saude.imprimir_relatorio(relatorio, caminho)
    saida = capsys.readouterr().err

    assert "ausência confirmada:      30" in saida
    assert "sem verificação possível: 40" in saida


def test_glossario_descreve_as_classes_novas():
    for classe in ("bloqueado", "cadeia_incompleta", "dominio_inexistente"):
        assert classe in saude.GLOSSARIO
        assert len(saude.GLOSSARIO[classe]) > 20


# --- reverificação por classe -------------------------------------------


async def test_reverificacao_restrita_a_uma_classe(tmp_path):
    """Cenário: reprocessar uma classe só.

    Host que voltou a responder não deve obrigar a reprocessar o catálogo.
    """
    caminho = banco_de_hosts(
        tmp_path, [("cdn.tse.jus.br", 403, 40), ("outro.gov.br", 404, 5)]
    )
    saude.reclassificar(caminho)

    with respx.mock(assert_all_called=False) as mock:
        rota = mock.head(url__startswith="https://").mock(
            return_value=httpx.Response(200)
        )
        relatorio = await saude.verificar_tudo(banco=caminho, classe="bloqueado")

    assert rota.call_count == 40
    assert relatorio.verificados == 40

    classes = classes_por_host(caminho)
    assert classes["cdn.tse.jus.br"] == {"disponivel"}
    # A outra classe não foi tocada.
    assert classes["outro.gov.br"] == {"indisponivel"}
