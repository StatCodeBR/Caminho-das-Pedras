"""O serviço: recebe a pergunta, recupera, decide, responde por SSE.

Todas as respostas saem pelo mesmo canal `text/event-stream`, inclusive as
montadas por template. A interface ganha um único caminho de renderização, e
some uma classe de bug que só apareceria em produção.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import banco, fusao, geracao, guarda, redacao, semantica, telemetria
from .configuracao import configuracao
from .limites import Contencao
from .recuperacao import Recuperado, buscar
from .roteamento import Origem, decidir

# Estado da busca semântica, decidido na inicialização. Opcional até a fusão
# (mudança 08), que é a primeira a consumi-la: sem vetores, o serviço sobe com
# ela desligada e o /saude diz isso. Com vetores inconsistentes, ele não sobe —
# vetor de outra versão do catálogo apontaria para o conjunto errado sem sintoma
# nenhum, e a fusão trataria esse erro como resultado.
_semantica: semantica.Indice | None = None
_motivo_semantica = "não inicializada"
_vetorizador: semantica.Vetorizador | None = None

# Fábrica do vetorizador, isolada para o teste poder injetar um substituto:
# carregar o modelo de verdade em cada teste que sobe a app custaria segundos e
# não mediria nada que a suíte se proponha a medir.
construir_vetorizador = semantica.Vetorizador


def _preparar_semantica() -> None:
    global _semantica, _motivo_semantica, _vetorizador
    config = configuracao()
    vetores_em = config.vetores
    ids_em = vetores_em.with_suffix(".json")
    _semantica = None
    _vetorizador = None
    # Desde a fusão, a busca semântica é obrigatória: ela entra em toda resposta,
    # e um serviço que subisse sem ela responderia só com a léxica, no mesmo
    # formato, sem sinal nenhum de que metade da recuperação sumiu.
    if not vetores_em.exists() and not ids_em.exists():
        raise RuntimeError(
            f"a busca semântica é obrigatória e os vetores não foram encontrados "
            f"em {vetores_em.parent}: a imagem precisa baixá-los da release, ou "
            f"o desenvolvimento precisa rodar `just vetores`"
        )
    if not semantica.runtime_disponivel():
        # Vetores sem o runtime que vetoriza a pergunta: a semântica se diria
        # ativa e quebraria na primeira consulta, com ImportError. O fastembed
        # fica fora da imagem até a fusão; quem instala vetores instala o grupo.
        raise RuntimeError(
            f"há vetores em {vetores_em.parent}, mas o runtime da busca semântica "
            "não está instalado: uv sync --group semantica"
        )
    try:
        conexao = banco.abrir(config.banco)
    except banco.CatalogoIndisponivel:
        # Sem catálogo não há contra o que conferir. O /saude já reporta o
        # catálogo indisponível; derrubar o serviço aqui esconderia o diagnóstico.
        _motivo_semantica = "catálogo indisponível"
        return
    try:
        # IndiceInconsistente propaga de propósito: é o que impede a subida.
        _semantica = semantica.carregar(conexao, vetores_em, ids_em)
    finally:
        conexao.close()
    _vetorizador = construir_vetorizador()
    try:
        # Aquece o modelo na subida. Se ele não estiver na imagem, o serviço não
        # pode subir anunciando a busca semântica ativa — ele quebraria na
        # primeira pergunta, que é o pior momento para descobrir.
        _vetorizador.consulta("aquecer o modelo")
    except Exception as erro:  # noqa: BLE001 — qualquer falha aqui impede subir
        raise RuntimeError(
            f"o modelo de consulta não está disponível na imagem: {erro}"
        ) from erro
    _motivo_semantica = "ativa"


def estado_semantica() -> dict:
    if _semantica is None:
        return {"ativa": False, "motivo": _motivo_semantica}
    return {"ativa": True, "vetores": len(_semantica.ids), "modelo": _semantica.modelo}


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
    _preparar_semantica()
    yield


app = FastAPI(title="Caminho das Pedras", version="0.1.0", lifespan=_ciclo_de_vida)

# Cabeçalho por onde o `web` repassa o endereço do visitante. A api nunca vê o
# navegador: ela é chamada pela rota de servidor do SvelteKit, então o socket
# dela é sempre o container do web. Confiar neste cabeçalho só é aceitável
# porque a api não é alcançável de fora — `expose` sem `ports`, rede interna.
# Se um dia ela for publicada, esta confiança deixa de valer.
CABECALHO_ORIGEM = "x-origem-real"

_contencao: Contencao | None = None


def contencao() -> Contencao:
    global _contencao
    if _contencao is None:
        c = configuracao()
        _contencao = Contencao(
            c.estado_dir / "consumo.db",
            teto_diario=c.teto_diario_modelo,
            maximo_por_origem=c.limite_origem_maximo,
            janela_s=c.limite_origem_janela,
        )
    return _contencao


def endereco_de(requisicao: Request) -> str:
    """O endereço do visitante, vindo do proxy — nunca do socket."""
    repassado = requisicao.headers.get(CABECALHO_ORIGEM, "").strip()
    if repassado:
        return repassado
    # Sem o cabeçalho, resta o socket. Em produção isso significaria o
    # container do web, então todos cairiam no mesmo balde — por isso o web
    # sempre envia o cabeçalho, e isto é só rede de segurança para uso local.
    return requisicao.client.host if requisicao.client else "desconhecido"

# Tamanho do fragmento ao devolver texto já pronto. Pequeno o bastante para a
# renderização parecer progressiva, grande o bastante para não inundar o canal.
FRAGMENTO = 24


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)


def _conexao() -> sqlite3.Connection:
    return banco.abrir(configuracao().banco)


def _evento(nome: str, dados: dict) -> str:
    return f"event: {nome}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


def _em_fragmentos(texto: str) -> list[str]:
    return [texto[i : i + FRAGMENTO] for i in range(0, len(texto), FRAGMENTO)] or [""]


def _resumo_das_fichas(fichas: list[Recuperado]) -> list[dict]:
    """O que a interface precisa para montar a camada Confira."""
    return [
        {
            "nome": f.nome,
            "titulo": f.titulo,
            "orgao": f.organizacao,
            "confianca": f.confianca,
            "url_portal": f.url_portal,
            "pontuacao": round(f.pontuacao, 3),
            # De qual ranking veio e em que posição. É o que permite à
            # camada Confira explicar por que o conjunto apareceu.
            "origens": f.origens,
            # Sempre presentes como chave, mesmo quando nulas: omitir obrigaria
            # a interface a adivinhar se a data falta ou se o campo sumiu.
            "dados_atualizados_em": f.dados_atualizados_em,
            "metadados_atualizados_em": f.metadados_atualizados_em,
            "recursos": [
                {
                    "titulo": r.titulo,
                    "link": r.link,
                    "formato": r.formato,
                    "disponivel": r.disponivel,
                }
                for r in f.recursos
            ],
        }
        for f in fichas
    ]


def _falha_de_ranking(nome: str, erro: Exception) -> None:
    """Meia recuperação responde; meia recuperação silenciosa esconde o defeito."""
    print(f"ranking {nome} falhou nesta consulta: {erro}", file=sys.stderr, flush=True)


async def _recuperar(
    conexao: sqlite3.Connection, pergunta: str, config: Any
) -> list[Recuperado]:
    """Funde os rankings léxico e semântico, cada um na sua thread.

    Cada ranking recebe a própria conexão: elas rodam em paralelo, e uma
    conexão do SQLite não é para ser usada por duas threads ao mesmo tempo.
    Abrir a segunda custa muito menos que a busca que ela serve.
    """

    def lexico(limite: int) -> list[Recuperado]:
        return buscar(conexao, pergunta, limite)

    semantico = None
    conexao_semantica = None
    if _semantica is not None and _vetorizador is not None:
        conexao_semantica = banco.abrir(config.banco)

        def semantico(limite: int) -> list[Recuperado]:
            return semantica.buscar(
                conexao_semantica, _semantica, _vetorizador, pergunta, limite
            )

    try:
        return await fusao.buscar(
            pergunta,
            config.fichas_no_contexto,
            lexica=lexico,
            semantica=semantico,
            profundidade=config.profundidade_busca,
            k=config.rrf_k,
            registrar=_falha_de_ranking,
        )
    finally:
        if conexao_semantica is not None:
            conexao_semantica.close()


async def _responder(pergunta: str, reduzido: bool = False) -> AsyncIterator[str]:
    config = configuracao()
    medicao = telemetria.Medicao(pergunta=pergunta)
    if reduzido:
        medicao.extra["teto_diario"] = True

    try:
        conexao = _conexao()
    except banco.CatalogoIndisponivel as erro:
        medicao.origem = Origem.REDUZIDO.value
        medicao.motivo = str(erro)
        medicao.registrar()
        yield _evento("erro", {"mensagem": "O catálogo não está disponível agora."})
        return

    try:
        if not banco.tem_indice(conexao):
            medicao.origem = Origem.REDUZIDO.value
            medicao.motivo = "índice ausente"
            medicao.registrar()
            yield _evento("erro", {"mensagem": "O catálogo não está disponível agora."})
            return
        recuperados = await _recuperar(conexao, pergunta, config)
    finally:
        conexao.close()

    rota = decidir(
        recuperados,
        limiar_template=config.limiar_template,
        margem_template=config.margem_template,
        limiar_relevancia=config.limiar_relevancia,
    )
    medicao.fichas = len(rota.fichas)
    medicao.motivo = rota.motivo

    yield _evento("inicio", {"fichas": len(rota.fichas)})

    if rota.origem is Origem.AUSENCIA:
        # Nenhum conjunto é mencionado: oferecer o mais parecido faria a pessoa
        # perder tempo e desconfiar das respostas seguintes.
        async for evento in _emitir_pronto(redacao.montar_ausencia(), rota.origem, [], medicao):
            yield evento
        return

    if rota.origem is Origem.TEMPLATE:
        texto = redacao.montar_template(rota.fichas[0])
        async for evento in _emitir_pronto(texto, rota.origem, rota.fichas[:1], medicao):
            yield evento
        return

    if reduzido:
        # Teto diário atingido. A recuperação rodou inteira; o que some é a
        # redação. Ninguém recebe erro por causa do teto — o produto fica
        # menos conversacional, não indisponível.
        texto = redacao.montar_sem_modelo(rota.fichas)
        async for evento in _emitir_pronto(texto, Origem.REDUZIDO, rota.fichas, medicao):
            yield evento
        return

    async for evento in _emitir_do_modelo(pergunta, rota.fichas, medicao):
        yield evento


async def _emitir_pronto(
    texto: str,
    origem: Origem,
    fichas: list[Recuperado],
    medicao: telemetria.Medicao,
) -> AsyncIterator[str]:
    for pedaco in _em_fragmentos(texto):
        yield _evento("fragmento", {"texto": pedaco})
    medicao.origem = origem.value
    medicao.registrar()
    yield _evento(
        "fim",
        {
            "origem": origem.value,
            "fichas": _resumo_das_fichas(fichas),
            "latencia_ms": medicao.latencia_ms,
        },
    )


async def _emitir_do_modelo(
    pergunta: str, fichas: list[Recuperado], medicao: telemetria.Medicao
) -> AsyncIterator[str]:
    """Gera, confere e só então entrega.

    O texto é acumulado antes de sair porque a ancoragem exige descartar a
    resposta inteira quando ela cita uma URL inventada — e o que já foi
    transmitido não se descarta. Repassar o fluxo do modelo direto ao usuário
    tornaria a guarda decorativa.
    """
    config = configuracao()
    partes: list[str] = []
    try:
        if config.modo_stub:
            fluxo = geracao.gerar_stub(pergunta, fichas)
        else:
            fluxo = geracao.gerar_com_modelo(
                pergunta,
                fichas,
                chave=config.anthropic_api_key,
                modelo=config.modelo,
            )
        async for pedaco in fluxo:
            partes.append(pedaco)
        if not config.modo_stub:
            # Só conta o que de fato consumiu o modelo. Template, ausência e
            # stub não entram no teto porque não custam nada.
            contencao().registrar_chamada()
    except geracao.ModeloIndisponivel as erro:
        # Sem o modelo o produto continua útil: os conjuntos e os links saem da
        # ficha, sem redação. Pior que a resposta gerada, muito melhor que erro.
        medicao.motivo = f"modelo indisponível: {erro}"
        async for evento in _emitir_pronto(
            redacao.montar_reduzido(fichas), Origem.REDUZIDO, fichas, medicao
        ):
            yield evento
        return

    texto = "".join(partes)
    veredito = guarda.verificar(texto, fichas)
    if not veredito.aprovada:
        telemetria.registrar_fabricacao(pergunta, veredito.motivo, texto)
        medicao.origem = Origem.REDUZIDO.value
        medicao.motivo = f"descartada: {veredito.motivo}"
        medicao.registrar()
        yield _evento(
            "fragmento",
            {
                "texto": "Não consegui montar uma resposta confiável para essa "
                "pergunta agora. Tente de novo em instantes."
            },
        )
        yield _evento(
            "fim",
            {
                "origem": Origem.REDUZIDO.value,
                "fichas": [],
                "latencia_ms": medicao.latencia_ms,
            },
        )
        return

    async for evento in _emitir_pronto(texto, Origem.MODELO, fichas, medicao):
        yield evento


@app.post("/perguntar")
async def perguntar(corpo: Pergunta, requisicao: Request) -> StreamingResponse:
    veredito = contencao().avaliar(endereco_de(requisicao))

    if not veredito.permitida:
        # Recusa só acontece por abuso de origem, nunca por teto diário.
        telemetria.logger.info(
            f'{{"evento": "origem_recusada", "motivo": "{veredito.motivo}"}}'
        )
        return JSONResponse(
            status_code=429,
            content={
                "erro": "muitas perguntas em pouco tempo",
                "tente_em_segundos": veredito.espera_s,
            },
            headers={"retry-after": str(veredito.espera_s)},
        )

    return StreamingResponse(
        _responder(corpo.pergunta.strip(), reduzido=veredito.reduzido),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            # Sem isto o Nginx e o Traefik seguram o fluxo até o fim e o
            # streaming vira entrega única, só em produção.
            "x-accel-buffering": "no",
            "connection": "keep-alive",
        },
    )


@app.get("/saude")
async def saude() -> dict:
    """Healthcheck do container. Não depende do modelo, só do catálogo."""
    config = configuracao()
    try:
        conexao = banco.abrir(config.banco)
    except banco.CatalogoIndisponivel as erro:
        return {"ok": False, "motivo": str(erro)}
    try:
        if not banco.tem_indice(conexao):
            return {"ok": False, "motivo": "índice ausente"}
        fichas = conexao.execute("SELECT count(*) FROM ficha").fetchone()[0]
    finally:
        conexao.close()
    return {
        "ok": True,
        "fichas": fichas,
        "modo_stub": config.modo_stub,
        "busca_semantica": estado_semantica(),
    }


@app.get("/operacao")
async def operacao() -> dict:
    """Consumo do dia, teto e modo corrente.

    Não precisa de proteção própria: a api inteira só existe na rede interna,
    sem domínio e sem porta publicada. O dia que ela for exposta, esta rota
    precisa de autenticação antes de qualquer outra.
    """
    return contencao().estado()
