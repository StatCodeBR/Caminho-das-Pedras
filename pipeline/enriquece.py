"""Enriquece os conjuntos do catálogo com fichas legíveis, offline.

Quarta camada do pipeline, e o diferencial técnico do projeto: o modelo escreve
uma vez, aqui, o texto que fecha a distância entre a linguagem do cidadão e a do
catálogo. Em tempo de resposta nada disso roda — só se lê o que ficou gravado.

O que não se pode afirmar a partir dos metadados não é afirmado: o conjunto
recebe confiança baixa e a busca o despriorizará. Descartar esconderia um dado
que existe; inventar seria mentir.
"""

from __future__ import annotations

import hashlib
import json
import random
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import unquote, urlparse

import typer
from pydantic import BaseModel, Field, ValidationError, field_validator

import provedores
import temas as temas_modulo
from provedores import Provedor, SemCredencial

RAIZ = Path(__file__).resolve().parent
DIRETORIO_DADOS = RAIZ / "dados"
DIRETORIO_CACHE = RAIZ / "cache"
ARQUIVO_PROMPT = RAIZ / "prompts" / "ficha.md"
ARQUIVO_LOTE = DIRETORIO_CACHE / "lote.json"

MAX_TENTATIVAS_VALIDACAO = 2
MAX_RECURSOS_NO_PROMPT = 20
MAX_CARACTERES_DESCRICAO = 1500
CONFIANCAS = ("alta", "media", "baixa")
# Abaixo disto a descrição não sustenta afirmação nenhuma sobre o conteúdo.
LIMIAR_DESCRICAO_POBRE = 60

# Estruturado no nível da API: o modelo não tem como devolver cerca de markdown.
ESQUEMA_FICHA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resumo": {"type": "string"},
        "perguntas": {"type": "array", "items": {"type": "string"}},
        "temas": {"type": "array", "items": {"type": "string"}},
        "abrangencia": {"type": "string"},
        "granularidade": {"type": "string"},
        "confianca": {"type": "string", "enum": list(CONFIANCAS)},
    },
    "required": [
        "resumo",
        "perguntas",
        "temas",
        "abrangencia",
        "granularidade",
        "confianca",
    ],
    "additionalProperties": False,
}


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def carregar_env() -> None:
    for arquivo in (RAIZ / ".env", RAIZ.parent / ".env"):
        if not arquivo.is_file():
            continue
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            nome, _, valor = linha.partition("=")
            os.environ.setdefault(nome.strip(), valor.strip().strip("\"'"))


# --- modelo da ficha -----------------------------------------------------


class FichaGerada(BaseModel):
    """O que o modelo devolve, antes de virar linha no banco."""

    resumo: str
    perguntas: list[str] = Field(default_factory=list)
    temas: list[str] = Field(default_factory=list)
    abrangencia: Optional[str] = None
    granularidade: Optional[str] = None
    confianca: str

    @field_validator("confianca")
    @classmethod
    def confianca_conhecida(cls, valor: str) -> str:
        chave = str(valor).strip().lower()
        if chave not in CONFIANCAS:
            raise ValueError(f"confiança fora da lista: {valor!r}")
        return chave

    @field_validator("resumo")
    @classmethod
    def resumo_nao_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("resumo vazio")
        return valor.strip()

    @field_validator("temas")
    @classmethod
    def apenas_temas_da_lista(cls, valor: list[str]) -> list[str]:
        # Tema fora da lista é descartado; os válidos restantes sobrevivem.
        return temas_modulo.filtrar(valor)

    def normalizada(self) -> "FichaGerada":
        """Aplica os limites que a spec impõe depois da validação de forma."""
        limite = 2 if self.confianca == "baixa" else 5
        perguntas = [p.strip() for p in self.perguntas if str(p).strip()][:limite]
        return self.model_copy(update={"perguntas": perguntas})


def travar_confianca(conjunto: dict[str, Any], ficha: FichaGerada) -> FichaGerada:
    """Descrição pobre força `baixa`, diga o modelo o que disser.

    Entre 20 e 40 caracteres de descrição o modelo tem *quase* informação, e é
    aí que ele completa o vazio: um conjunto chamado "11. Mortalidade Materna"
    com 27 caracteres virou ficha afirmando indicadores de *near miss*, que a
    origem não sustenta. Instrução funciona mal nessa faixa; trava funciona.

    A consequência não é cosmética. O resumo alimenta o `texto_indexavel`, então
    uma afirmação inventada vira falso positivo permanente na busca — o usuário
    procura por um assunto e chega a um conjunto que talvez não o trate. Com
    `baixa`, a ficha perde perguntas e a busca a desprioriza, contendo o dano.

    A verificação é do pipeline, não do modelo: a ficha nunca declara mais
    confiança do que a fonte sustenta.
    """
    if ficha.confianca == "baixa":
        return ficha
    descricao = (conjunto.get("descricao") or "").strip()
    if len(descricao) >= LIMIAR_DESCRICAO_POBRE:
        return ficha
    return ficha.model_copy(update={"confianca": "baixa"}).normalizada()


def ficha_de_fallback(conjunto: dict[str, Any]) -> FichaGerada:
    """Quando o modelo não entrega JSON válido, o conjunto ainda recebe ficha."""
    titulo = conjunto.get("titulo") or conjunto.get("nome") or "Conjunto sem título"
    orgao = conjunto.get("organizacao") or "órgão não informado"
    return FichaGerada(
        resumo=f"{titulo}. Publicado por {orgao}. Não foi possível descrever o "
        "conteúdo com os metadados disponíveis.",
        perguntas=[],
        temas=[],
        abrangencia="nao_informada",
        granularidade="nao_informada",
        confianca="baixa",
    )


# --- entrada determinística ---------------------------------------------


def nomes_das_tags(bruto: str | None) -> list[str]:
    """As tags vêm do portal como objetos; aqui só interessa o nome."""
    if not bruto:
        return []
    try:
        dados = json.loads(bruto)
    except ValueError:
        return []
    nomes: list[str] = []
    for item in dados if isinstance(dados, list) else []:
        if isinstance(item, dict):
            nome = item.get("name") or item.get("nome")
        else:
            nome = item
        if isinstance(nome, str) and nome.strip():
            nomes.append(nome.strip())
    return nomes


def nome_do_arquivo(link: str | None) -> str:
    """O nome de arquivo da URL. 56% deles trazem o ano que o título omite."""
    if not link:
        return ""
    caminho = unquote(urlparse(link).path)
    base = os.path.basename(caminho).strip()
    return base if "." in base else ""


def _comparavel(texto: str) -> str:
    return "".join(ch for ch in texto.lower() if ch.isalnum())


def descrever_recurso(titulo: str | None, link: str | None) -> str:
    """Título mais nome de arquivo, quando o arquivo acrescenta informação."""
    titulo = (titulo or "").strip()
    arquivo = nome_do_arquivo(link)
    if not arquivo:
        return titulo
    if not titulo:
        return arquivo
    # `GESAC` + `GESAC_dadosabertos_abril_2023.csv`: o arquivo revela o período.
    # Já `leitos.csv` dentro de "Leitos" não acrescenta nada e sai.
    raiz = _comparavel(arquivo.rsplit(".", 1)[0])
    if raiz and raiz in _comparavel(titulo):
        return titulo
    return f"{titulo} ({arquivo})"


def amostrar_recursos(recursos: list[str]) -> list[str]:
    """Ordena e mostra as duas pontas: é a faixa que informa o período coberto.

    Um conjunto com 83 arquivos anuais truncado nos 20 primeiros esconderia os
    anos recentes. Ordenado, as duas pontas revelam de 2001 a 2025 — que é
    justamente o que o prompt proíbe o modelo de supor sem evidência.
    """
    ordenados = sorted(recursos)
    if len(ordenados) <= MAX_RECURSOS_NO_PROMPT:
        return ordenados
    metade = MAX_RECURSOS_NO_PROMPT // 2
    ocultos = len(ordenados) - 2 * metade
    return [
        *ordenados[:metade],
        f"[…] e mais {ocultos} entre estes e os seguintes",
        *ordenados[-metade:],
    ]


def montar_entrada(conjunto: dict[str, Any]) -> str:
    """O texto exato enviado ao modelo. Determinístico: é a chave do cache."""
    descricao = (conjunto.get("descricao") or "").strip()
    if len(descricao) > MAX_CARACTERES_DESCRICAO:
        descricao = descricao[:MAX_CARACTERES_DESCRICAO].rstrip() + " […]"

    tags = nomes_das_tags(conjunto.get("tags"))
    # 37% dos conjuntos repetem o mesmo título em todos os recursos. Repetição
    # não informa nada ao modelo e é paga por token, então some — a ordem da
    # primeira ocorrência é preservada para manter o hash estável.
    recursos = list(dict.fromkeys(t.strip() for t in (conjunto.get("recursos") or []) if t))

    linhas = [
        f"nome: {conjunto.get('nome') or '(sem slug)'}",
        f"titulo: {conjunto.get('titulo') or '(sem título)'}",
        f"orgao: {conjunto.get('organizacao') or '(não informado)'}",
        f"descricao: {descricao or '(vazia)'}",
        f"tags: {', '.join(tags) if tags else '(nenhuma)'}",
    ]
    if recursos:
        linhas.append(f"recursos ({len(recursos)}):")
        linhas.extend(f"  - {titulo}" for titulo in amostrar_recursos(recursos))
    else:
        linhas.append("recursos: (nenhum)")

    return "\n".join(linhas)


def carregar_prompt() -> str:
    modelo = ARQUIVO_PROMPT.read_text(encoding="utf-8")
    return modelo.replace("{temas}", temas_modulo.para_prompt())


def calcular_hash(prompt: str, entrada: str, identificador: str) -> str:
    """Prompt, metadados e identificador do provedor, os três no hash.

    Mudar o prompt invalida o cache inteiro, e deve mesmo. Trocar de provedor
    ou de modelo também: ficha escrita por outro modelo é outra ficha, e servir
    a antiga esconderia de quem audita quem de fato a escreveu.
    """
    digestor = hashlib.sha256()
    digestor.update(prompt.encode("utf-8"))
    digestor.update(b"\x00")
    digestor.update(entrada.encode("utf-8"))
    digestor.update(b"\x00")
    digestor.update(identificador.encode("utf-8"))
    return digestor.hexdigest()


def texto_indexavel(conjunto: dict[str, Any], ficha: FichaGerada) -> str:
    """Derivado por concatenação. Nunca custa uma chamada ao modelo."""
    partes = [
        conjunto.get("titulo") or "",
        conjunto.get("nome") or "",
        ficha.resumo,
        " ".join(ficha.perguntas),
        conjunto.get("organizacao") or "",
        " ".join(nomes_das_tags(conjunto.get("tags"))),
        " ".join(temas_modulo.TEMAS[t] for t in ficha.temas),
    ]
    return "\n".join(parte.strip() for parte in partes if parte and parte.strip())


# --- cache ---------------------------------------------------------------


def caminho_cache(hash_entrada: str) -> Path:
    return DIRETORIO_CACHE / f"{hash_entrada}.json"


def ler_cache(hash_entrada: str) -> FichaGerada | None:
    caminho = caminho_cache(hash_entrada)
    if not caminho.is_file():
        return None
    try:
        return FichaGerada.model_validate_json(caminho.read_text(encoding="utf-8"))
    except (ValidationError, ValueError):
        return None


def gravar_cache(hash_entrada: str, ficha: FichaGerada) -> None:
    DIRETORIO_CACHE.mkdir(parents=True, exist_ok=True)
    caminho_cache(hash_entrada).write_text(
        ficha.model_dump_json(indent=2), encoding="utf-8"
    )


# --- banco ---------------------------------------------------------------

DDL_FICHA = """
CREATE TABLE IF NOT EXISTS ficha (
    conjunto_id     TEXT PRIMARY KEY REFERENCES conjunto(id) ON DELETE CASCADE,
    resumo          TEXT NOT NULL,
    perguntas_json  TEXT NOT NULL DEFAULT '[]',
    temas_json      TEXT NOT NULL DEFAULT '[]',
    abrangencia     TEXT,
    granularidade   TEXT,
    confianca       TEXT NOT NULL,
    texto_indexavel TEXT NOT NULL,
    hash_entrada    TEXT NOT NULL,
    -- Quem escreveu esta ficha, no formato provedor/modelo. Sem isso não há
    -- como auditar depois por que uma ficha ficou boa e outra não.
    modelo          TEXT NOT NULL DEFAULT '',
    origem          TEXT NOT NULL,
    gerada_em       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ficha_confianca ON ficha(confianca);
CREATE INDEX IF NOT EXISTS idx_ficha_hash      ON ficha(hash_entrada);
"""


COLUNAS_FICHA_MIGRAVEIS = {
    # Acrescentada depois que a tabela já existia em bancos de desenvolvimento;
    # `CREATE TABLE IF NOT EXISTS` não migra o que já está lá.
    "modelo": "TEXT NOT NULL DEFAULT ''",
}


def abrir_banco(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.executescript(DDL_FICHA)
    existentes = {linha[1] for linha in conexao.execute("PRAGMA table_info(ficha)")}
    for coluna, tipo in COLUNAS_FICHA_MIGRAVEIS.items():
        if coluna not in existentes:
            conexao.execute(f"ALTER TABLE ficha ADD COLUMN {coluna} {tipo}")
    conexao.commit()
    return conexao


def ler_conjuntos(conexao: sqlite3.Connection, limite: int | None) -> list[dict[str, Any]]:
    sql = """
        SELECT c.id, c.nome, c.titulo, c.descricao, c.organizacao, c.tags
        FROM conjunto c ORDER BY c.nome
    """
    if limite:
        sql += f" LIMIT {int(limite)}"
    conjuntos = [dict(linha) for linha in conexao.execute(sql)]
    for conjunto in conjuntos:
        conjunto["recursos"] = [
            descrever_recurso(linha[0], linha[1])
            for linha in conexao.execute(
                "SELECT titulo, link FROM recurso WHERE conjunto_id = ? ORDER BY id",
                (conjunto["id"],),
            )
        ]
    return conjuntos


FAIXAS_DESCRICAO = (
    ("sem", 0, 40),
    ("curta", 40, 200),
    ("media", 200, 800),
    ("longa", 800, 10**9),
)


def sortear_variado(
    conexao: sqlite3.Connection, quantidade: int, semente: int = 0
) -> list[dict[str, Any]]:
    """Amostra espalhada por órgão e por riqueza de metadado.

    Os primeiros N conjuntos por slug são quase todos do mesmo hospital, e uma
    revisão feita sobre eles não diz nada sobre o catálogo. Aqui a amostra
    percorre as faixas de descrição em rodízio e nunca repete órgão enquanto
    houver órgão novo disponível. Determinística: a mesma semente devolve a
    mesma amostra, para que a revisão seja reproduzível.
    """
    todos = ler_conjuntos(conexao, None)
    aleatorio = random.Random(semente)

    por_faixa: dict[str, list[dict[str, Any]]] = {nome: [] for nome, _, _ in FAIXAS_DESCRICAO}
    for conjunto in todos:
        tamanho = len(conjunto.get("descricao") or "")
        for nome, minimo, maximo in FAIXAS_DESCRICAO:
            if minimo <= tamanho < maximo:
                por_faixa[nome].append(conjunto)
                break
    for lista in por_faixa.values():
        aleatorio.shuffle(lista)

    escolhidos: list[dict[str, Any]] = []
    orgaos_usados: set[str] = set()
    nomes_faixas = [nome for nome, _, _ in FAIXAS_DESCRICAO if por_faixa[nome]]

    # Duas passadas: a primeira recusa repetir órgão, a segunda completa.
    for exigir_orgao_novo in (True, False):
        indice = 0
        while len(escolhidos) < quantidade and nomes_faixas:
            faixa = nomes_faixas[indice % len(nomes_faixas)]
            indice += 1
            candidatos = por_faixa[faixa]
            achou = False
            for conjunto in list(candidatos):
                orgao = conjunto.get("organizacao") or ""
                if exigir_orgao_novo and orgao in orgaos_usados:
                    continue
                candidatos.remove(conjunto)
                orgaos_usados.add(orgao)
                escolhidos.append(conjunto)
                achou = True
                break
            if not achou and indice % len(nomes_faixas) == 0:
                if all(not por_faixa[n] for n in nomes_faixas):
                    break
                if exigir_orgao_novo and not any(
                    (c.get("organizacao") or "") not in orgaos_usados
                    for n in nomes_faixas
                    for c in por_faixa[n]
                ):
                    break

    return escolhidos[:quantidade]


def gravar_ficha(
    conexao: sqlite3.Connection,
    conjunto: dict[str, Any],
    ficha: FichaGerada,
    hash_entrada: str,
    modelo: str,
    origem: str,
) -> None:
    conexao.execute(
        """
        INSERT INTO ficha (conjunto_id, resumo, perguntas_json, temas_json,
                           abrangencia, granularidade, confianca, texto_indexavel,
                           hash_entrada, modelo, origem, gerada_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(conjunto_id) DO UPDATE SET
            resumo=excluded.resumo, perguntas_json=excluded.perguntas_json,
            temas_json=excluded.temas_json, abrangencia=excluded.abrangencia,
            granularidade=excluded.granularidade, confianca=excluded.confianca,
            texto_indexavel=excluded.texto_indexavel,
            hash_entrada=excluded.hash_entrada, modelo=excluded.modelo,
            origem=excluded.origem, gerada_em=excluded.gerada_em
        """,
        (
            conjunto["id"],
            ficha.resumo,
            json.dumps(ficha.perguntas, ensure_ascii=False),
            json.dumps(ficha.temas, ensure_ascii=False),
            ficha.abrangencia,
            ficha.granularidade,
            ficha.confianca,
            texto_indexavel(conjunto, ficha),
            hash_entrada,
            modelo,
            origem,
            agora_utc(),
        ),
    )


# --- chamada ao modelo ---------------------------------------------------


def interpretar_resposta(texto: str) -> FichaGerada:
    """Valida a saída do modelo. Ergue ValidationError/ValueError se não presta."""
    return FichaGerada.model_validate_json(texto).normalizada()


def pedir_ficha(provedor: Provedor, prompt: str, entrada: str) -> FichaGerada:
    """Uma ficha, com as repetições que a spec permite antes do fallback."""
    ultimo_erro: Exception | None = None
    for _ in range(MAX_TENTATIVAS_VALIDACAO + 1):
        try:
            texto = provedor.gerar(prompt, entrada, ESQUEMA_FICHA)
            return interpretar_resposta(texto)
        except (ValidationError, ValueError) as erro:
            ultimo_erro = erro
    raise ultimo_erro or ValueError("resposta inválida")


# --- relatório -----------------------------------------------------------


@dataclass
class Relatorio:
    total: int = 0
    do_cache: int = 0
    do_modelo: int = 0
    de_fallback: int = 0
    confianca: dict[str, int] = field(default_factory=dict)

    def contar(self, ficha: FichaGerada) -> None:
        self.confianca[ficha.confianca] = self.confianca.get(ficha.confianca, 0) + 1

    @property
    def aproveitamento_cache(self) -> float:
        return self.do_cache / self.total if self.total else 0.0


def imprimir_relatorio(relatorio: Relatorio, banco: Path, identificador: str = "") -> None:
    log("")
    log("relatório de enriquecimento")
    if identificador:
        log(f"  gerado por:            {identificador}")
    log(f"  conjuntos processados: {relatorio.total}")
    log(f"  vindos do cache:       {relatorio.do_cache} "
        f"({relatorio.aproveitamento_cache:.0%})")
    log(f"  gerados pelo modelo:   {relatorio.do_modelo}")
    log(f"  caíram no fallback:    {relatorio.de_fallback}")
    log("  distribuição de confiança:")
    for nivel in CONFIANCAS:
        quantidade = relatorio.confianca.get(nivel, 0)
        percentual = quantidade / relatorio.total if relatorio.total else 0.0
        log(f"    {nivel:6s} {quantidade:5d}  ({percentual:.0%})")
    log(f"  banco:                 {banco}")


# --- orquestração --------------------------------------------------------


def enriquecer(
    *,
    banco: Path,
    provedor: Provedor,
    limite: int | None = None,
    sortear: bool = False,
) -> Relatorio:
    """Processa conjuntos um a um, de forma síncrona. Usado na amostra."""
    prompt = carregar_prompt()
    identificador = provedor.identificador
    conexao = abrir_banco(banco)
    relatorio = Relatorio()

    try:
        selecionados = (
            sortear_variado(conexao, limite or 15)
            if sortear
            else ler_conjuntos(conexao, limite)
        )
        for conjunto in selecionados:
            entrada = montar_entrada(conjunto)
            hash_entrada = calcular_hash(prompt, entrada, identificador)
            relatorio.total += 1

            ficha = ler_cache(hash_entrada)
            if ficha is not None:
                relatorio.do_cache += 1
                origem = "cache"
            else:
                try:
                    ficha = pedir_ficha(provedor, prompt, entrada)
                    relatorio.do_modelo += 1
                    origem = "modelo"
                except (ValidationError, ValueError) as erro:
                    log(f"fallback em {conjunto.get('nome')}: {erro}")
                    ficha = ficha_de_fallback(conjunto)
                    relatorio.de_fallback += 1
                    origem = "fallback"
                gravar_cache(hash_entrada, ficha)

            ficha = travar_confianca(conjunto, ficha)
            gravar_ficha(conexao, conjunto, ficha, hash_entrada, identificador, origem)
            relatorio.contar(ficha)
            # Commit periódico: uma execução de meia hora não pode perder tudo
            # porque caiu no minuto 28. O cache já protege os tokens gastos;
            # isto protege o banco.
            if relatorio.total % 25 == 0:
                conexao.commit()
        conexao.commit()
    finally:
        conexao.close()

    return relatorio


def _pendentes(
    conexao: sqlite3.Connection, prompt: str, identificador: str, limite: int | None
) -> tuple[list[tuple[dict, str, str]], Relatorio]:
    """Separa o que já está em cache do que precisa ir ao modelo."""
    relatorio = Relatorio()
    pendentes: list[tuple[dict, str, str]] = []

    for conjunto in ler_conjuntos(conexao, limite):
        entrada = montar_entrada(conjunto)
        hash_entrada = calcular_hash(prompt, entrada, identificador)
        relatorio.total += 1

        ficha = ler_cache(hash_entrada)
        if ficha is not None:
            relatorio.do_cache += 1
            ficha = travar_confianca(conjunto, ficha)
            gravar_ficha(conexao, conjunto, ficha, hash_entrada, identificador, "cache")
            relatorio.contar(ficha)
        else:
            pendentes.append((conjunto, entrada, hash_entrada))

    return pendentes, relatorio


def ler_lote_pendente() -> dict[str, Any] | None:
    if not ARQUIVO_LOTE.is_file():
        return None
    try:
        return json.loads(ARQUIVO_LOTE.read_text(encoding="utf-8"))
    except ValueError:
        return None


def gravar_lote_pendente(estado: dict[str, Any]) -> None:
    DIRETORIO_CACHE.mkdir(parents=True, exist_ok=True)
    ARQUIVO_LOTE.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def enriquecer_em_lote(
    *,
    banco: Path,
    provedor: Provedor,
    limite: int | None = None,
    espera: float = 30.0,
) -> Relatorio:
    """Submete tudo de uma vez e coleta depois, retomando lote interrompido.

    Provedor sem lote cai para o caminho síncrono: mais lento e mais caro, mas
    correto. É a diferença entre não suportar e fingir que suporta.
    """
    if not provedor.suporta_lote():
        log(f"{provedor.nome} não oferece lote; usando chamadas uma a uma")
        return enriquecer(banco=banco, provedor=provedor, limite=limite)

    prompt = carregar_prompt()
    identificador = provedor.identificador
    conexao = abrir_banco(banco)

    try:
        pendentes, relatorio = _pendentes(conexao, prompt, identificador, limite)
        conexao.commit()

        if not pendentes:
            log("nada a enriquecer: tudo veio do cache")
            return relatorio

        por_id = {c["id"]: (c, e, h) for c, e, h in pendentes}

        estado = ler_lote_pendente()
        if estado and estado.get("modelo") == identificador:
            log(f"retomando lote {estado['lote_id']} — não resubmetendo")
            lote_id = estado["lote_id"]
        else:
            lote_id = provedor.submeter_lote(
                [(conjunto["id"], entrada) for conjunto, entrada, _ in pendentes],
                prompt,
                ESQUEMA_FICHA,
            )
            gravar_lote_pendente(
                {
                    "lote_id": lote_id,
                    "modelo": identificador,
                    "itens": len(pendentes),
                    "submetido_em": agora_utc(),
                }
            )
            log(f"lote {lote_id} submetido com {len(pendentes)} itens")

        while not provedor.lote_concluido(lote_id):
            log(f"lote {lote_id} em andamento, aguardando...")
            time.sleep(espera)

        for custom_id, texto in provedor.resultados_lote(lote_id):
            alvo = por_id.get(custom_id)
            if alvo is None:
                continue
            conjunto, entrada, hash_entrada = alvo

            ficha: FichaGerada | None = None
            if texto:
                try:
                    ficha = interpretar_resposta(texto)
                except (ValidationError, ValueError) as erro:
                    log(f"resposta inválida em {conjunto.get('nome')}: {erro}")

            if ficha is None:
                # O lote não repete por si; a retentativa é síncrona e limitada.
                try:
                    ficha = pedir_ficha(provedor, prompt, entrada)
                    origem = "modelo"
                    relatorio.do_modelo += 1
                except (ValidationError, ValueError) as erro:
                    log(f"fallback em {conjunto.get('nome')}: {erro}")
                    ficha = ficha_de_fallback(conjunto)
                    origem = "fallback"
                    relatorio.de_fallback += 1
            else:
                origem = "modelo"
                relatorio.do_modelo += 1

            gravar_cache(hash_entrada, ficha)
            ficha = travar_confianca(conjunto, ficha)
            gravar_ficha(conexao, conjunto, ficha, hash_entrada, identificador, origem)
            relatorio.contar(ficha)

        conexao.commit()
        ARQUIVO_LOTE.unlink(missing_ok=True)
    finally:
        conexao.close()

    return relatorio


# --- interface de linha de comando --------------------------------------

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    limite: Optional[int] = typer.Option(
        None, "--limite", min=1, help="Processa apenas os N primeiros conjuntos."
    ),
    provedor: str = typer.Option(
        provedores.PROVEDOR_PADRAO,
        "--provedor",
        help=f"Provedor do modelo: {', '.join(sorted(provedores.PROVEDORES))}.",
    ),
    modelo: Optional[str] = typer.Option(
        None, "--modelo", help="Identificador do modelo. Padrão: o do provedor."
    ),
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="SQLite com o catálogo."
    ),
    simular: bool = typer.Option(
        False,
        "--simular",
        help="Mostra o texto que iria ao modelo e encerra, sem gastar tokens.",
    ),
    sincrono: bool = typer.Option(
        False,
        "--sincrono",
        help="Uma chamada por conjunto, sem lote. Para amostras pequenas.",
    ),
    sortear: bool = typer.Option(
        False,
        "--sortear",
        help="Amostra espalhada por órgão e por riqueza de descrição, em vez"
        " dos N primeiros por slug. Determinística.",
    ),
) -> None:
    """Gera as fichas dos conjuntos do catálogo."""
    carregar_env()

    if not banco.is_file():
        log(f"banco não encontrado: {banco}")
        log("rode a normalização antes: uv run python normaliza.py")
        raise typer.Exit(code=2)

    try:
        escolhido = provedores.criar_provedor(provedor, modelo)
    except ValueError as erro:
        log(str(erro))
        raise typer.Exit(code=2)

    if simular:
        prompt = carregar_prompt()
        conexao = abrir_banco(banco)
        try:
            conjuntos = (
                sortear_variado(conexao, limite or 3)
                if sortear
                else ler_conjuntos(conexao, limite or 3)
            )
        finally:
            conexao.close()
        log(f"prompt: {ARQUIVO_PROMPT} ({len(prompt)} caracteres)")
        for conjunto in conjuntos:
            entrada = montar_entrada(conjunto)
            print("=" * 72)
            print(f"# {conjunto['nome']}  (hash {calcular_hash(prompt, entrada, escolhido.identificador)[:12]})")
            print(entrada)
        return

    executar = enriquecer if sincrono else enriquecer_em_lote
    try:
        relatorio = (
            enriquecer(banco=banco, provedor=escolhido, limite=limite, sortear=True)
            if sortear
            else executar(banco=banco, provedor=escolhido, limite=limite)
        )
    except SemCredencial as erro:
        log(str(erro))
        raise typer.Exit(code=2)

    imprimir_relatorio(relatorio, banco, escolhido.identificador)


if __name__ == "__main__":
    app()
