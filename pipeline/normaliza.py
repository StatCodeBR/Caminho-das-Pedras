"""Normaliza o JSONL bruto da coleta em um SQLite consultável.

Segunda camada do pipeline. O metadado do portal é irregular por natureza:
descrição vazia, data que diz "Indisponível", formato escrito de seis jeitos.
Nada disso pode derrubar a ingestão — o que não entra, entra em quarentena com
o motivo registrado.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import typer
from pydantic import BaseModel, ValidationError, field_validator

RAIZ = Path(__file__).resolve().parent
DIRETORIO_BRUTO = RAIZ / "bruto"
DIRETORIO_DADOS = RAIZ / "dados"
ARQUIVO_QUARENTENA = RAIZ / "quarentena.jsonl"

# O portal serve data e hora no formato brasileiro e sem fuso nenhum. Não
# inferimos qual é: o instante é gravado como veio, marcado como UTC. Deslocar
# sem evidência seria inventar três horas em todo o catálogo.
FORMATOS_DATA = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")

URL_CONJUNTO = "https://dados.gov.br/dados/conjuntos-dados/{}"
LIMIAR_REJEICAO = 0.05


def log(mensagem: object) -> None:
    print(str(mensagem), file=sys.stderr, flush=True)


def agora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- normalizações -------------------------------------------------------


def para_utc(valor: Any) -> str | None:
    """Data do portal para ISO 8601 em UTC. O que não se entende vira nulo."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip()
    if not texto:
        return None
    for formato in FORMATOS_DATA:
        try:
            momento = datetime.strptime(texto, formato)
        except ValueError:
            continue
        return momento.replace(tzinfo=timezone.utc).isoformat()
    # Cobre "Indisponível" e qualquer outra coisa que o portal invente.
    try:
        return datetime.fromisoformat(texto).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def normalizar_formato(valor: Any) -> str | None:
    """`csv`, `CSV ` e `.csv` viram `CSV`. `ZIP SHP` mantém o espaço interno."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip().strip(".").strip()
    return texto.upper() or None


def texto_ou_nulo(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    return valor.strip() or None


# --- modelos -------------------------------------------------------------


class Recurso(BaseModel):
    """Um arquivo ou serviço publicado dentro de um conjunto."""

    id: str
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    formato: Optional[str] = None
    link: Optional[str] = None
    tamanho: Optional[int] = None
    catalogado_em: Optional[str] = None
    arquivo_atualizado_em: Optional[str] = None

    @field_validator("id")
    @classmethod
    def id_nao_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("recurso sem identificador")
        return valor.strip()

    @classmethod
    def de_bruto(cls, bruto: dict[str, Any]) -> "Recurso":
        tamanho = bruto.get("tamanho")
        return cls.model_validate(
            {
                "id": bruto.get("id") or "",
                "titulo": texto_ou_nulo(bruto.get("titulo")),
                "descricao": texto_ou_nulo(bruto.get("descricao")),
                "formato": normalizar_formato(bruto.get("formato")),
                "link": texto_ou_nulo(bruto.get("link")),
                "tamanho": tamanho if isinstance(tamanho, int) else None,
                "catalogado_em": para_utc(bruto.get("dataCatalogacao")),
                "arquivo_atualizado_em": para_utc(bruto.get("dataUltimaAtualizacaoArquivo")),
            }
        )


class Conjunto(BaseModel):
    """Um conjunto de dados do catálogo, com seus recursos."""

    id: str
    nome: Optional[str] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    organizacao: Optional[str] = None
    periodicidade: Optional[str] = None
    granularidade_espacial: Optional[str] = None
    cobertura_espacial: Optional[str] = None
    cobertura_temporal_inicio: Optional[str] = None
    cobertura_temporal_fim: Optional[str] = None
    temas: list[Any] = []
    tags: list[Any] = []
    descontinuado: bool = False
    url_portal: str
    catalogado_em: Optional[str] = None
    metadados_atualizados_em: Optional[str] = None
    dados_atualizados_em: Optional[str] = None
    coletado_em: Optional[str] = None
    recursos: list[Recurso] = []

    @field_validator("id")
    @classmethod
    def id_nao_vazio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("conjunto sem identificador")
        return valor.strip()

    @classmethod
    def de_bruto(cls, bruto: dict[str, Any]) -> "Conjunto":
        # O detalhe é o registro completo e existe em todos os conjuntos; o
        # topo varia conforme o conjunto tenha vindo da listagem ou de semente.
        detalhe = bruto.get("detalhe") if isinstance(bruto.get("detalhe"), dict) else {}
        fonte: dict[str, Any] = {**bruto, **detalhe}

        identificador = str(fonte.get("id") or "").strip()
        slug = texto_ou_nulo(fonte.get("nome"))
        recursos_brutos = fonte.get("recursos")
        recursos = []
        if isinstance(recursos_brutos, list):
            for item in recursos_brutos:
                if isinstance(item, dict):
                    recursos.append(Recurso.de_bruto(item))

        return cls.model_validate(
            {
                "id": identificador,
                "nome": slug,
                "titulo": texto_ou_nulo(fonte.get("titulo")) or texto_ou_nulo(fonte.get("title")),
                "descricao": texto_ou_nulo(fonte.get("descricao")),
                "organizacao": texto_ou_nulo(fonte.get("organizacao"))
                or texto_ou_nulo(fonte.get("nomeOrganizacao")),
                "periodicidade": texto_ou_nulo(fonte.get("periodicidade")),
                "granularidade_espacial": texto_ou_nulo(fonte.get("granularidadeEspacial")),
                "cobertura_espacial": texto_ou_nulo(fonte.get("valorCoberturaEspacial"))
                or texto_ou_nulo(fonte.get("coberturaEspacial")),
                "cobertura_temporal_inicio": para_utc(fonte.get("coberturaTemporalInicio")),
                "cobertura_temporal_fim": para_utc(fonte.get("coberturaTemporalFim")),
                "temas": fonte.get("temas") if isinstance(fonte.get("temas"), list) else [],
                "tags": fonte.get("tags") if isinstance(fonte.get("tags"), list) else [],
                "descontinuado": bool(fonte.get("descontinuado")),
                # Nunca nula: derivada do slug, ou do UUID quando não há slug.
                "url_portal": URL_CONJUNTO.format(slug or identificador),
                "catalogado_em": para_utc(fonte.get("dataCatalogacao"))
                or para_utc(fonte.get("catalogacao")),
                "metadados_atualizados_em": para_utc(fonte.get("dataUltimaAtualizacaoMetadados"))
                or para_utc(fonte.get("ultimaAlteracaoMetadados")),
                "dados_atualizados_em": para_utc(fonte.get("dataUltimaAtualizacaoArquivo"))
                or para_utc(fonte.get("ultimaAtualizacaoDados")),
                "coletado_em": texto_ou_nulo(bruto.get("coletado_em")),
                "recursos": recursos,
            }
        )


# --- banco ---------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS conjunto (
    id                        TEXT PRIMARY KEY,
    nome                      TEXT,
    titulo                    TEXT,
    descricao                 TEXT,
    organizacao               TEXT,
    periodicidade             TEXT,
    granularidade_espacial    TEXT,
    cobertura_espacial        TEXT,
    cobertura_temporal_inicio TEXT,
    cobertura_temporal_fim    TEXT,
    temas                     TEXT NOT NULL DEFAULT '[]',
    tags                      TEXT NOT NULL DEFAULT '[]',
    descontinuado             INTEGER NOT NULL DEFAULT 0,
    url_portal                TEXT NOT NULL,
    catalogado_em             TEXT,
    metadados_atualizados_em  TEXT,
    dados_atualizados_em      TEXT,
    coletado_em               TEXT,
    ingerido_em               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recurso (
    id                    TEXT PRIMARY KEY,
    conjunto_id           TEXT NOT NULL REFERENCES conjunto(id) ON DELETE CASCADE,
    titulo                TEXT,
    descricao             TEXT,
    formato               TEXT,
    link                  TEXT,
    tamanho               INTEGER,
    catalogado_em         TEXT,
    arquivo_atualizado_em TEXT,
    ingerido_em           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recurso_conjunto ON recurso(conjunto_id);
CREATE INDEX IF NOT EXISTS idx_recurso_formato  ON recurso(formato);
CREATE INDEX IF NOT EXISTS idx_conjunto_nome    ON conjunto(nome);
"""

CAMPOS_CONJUNTO = (
    "id, nome, titulo, descricao, organizacao, periodicidade, granularidade_espacial, "
    "cobertura_espacial, cobertura_temporal_inicio, cobertura_temporal_fim, temas, tags, "
    "descontinuado, url_portal, catalogado_em, metadados_atualizados_em, "
    "dados_atualizados_em, coletado_em, ingerido_em"
)

CAMPOS_RECURSO = (
    "id, conjunto_id, titulo, descricao, formato, link, tamanho, catalogado_em, "
    "arquivo_atualizado_em, ingerido_em"
)


def _upsert(tabela: str, campos: str) -> str:
    """Upsert por identificador: reexecutar atualiza, nunca duplica."""
    nomes = [c.strip() for c in campos.split(",")]
    marcadores = ", ".join("?" for _ in nomes)
    atualizacoes = ", ".join(f"{c}=excluded.{c}" for c in nomes if c != "id")
    return (
        f"INSERT INTO {tabela} ({campos}) VALUES ({marcadores}) "
        f"ON CONFLICT(id) DO UPDATE SET {atualizacoes}"
    )


def abrir_banco(caminho: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.executescript(DDL)
    return conexao


def gravar(conexao: sqlite3.Connection, conjunto: Conjunto, quando: str) -> None:
    conexao.execute(
        _upsert("conjunto", CAMPOS_CONJUNTO),
        (
            conjunto.id,
            conjunto.nome,
            conjunto.titulo,
            conjunto.descricao,
            conjunto.organizacao,
            conjunto.periodicidade,
            conjunto.granularidade_espacial,
            conjunto.cobertura_espacial,
            conjunto.cobertura_temporal_inicio,
            conjunto.cobertura_temporal_fim,
            json.dumps(conjunto.temas, ensure_ascii=False),
            json.dumps(conjunto.tags, ensure_ascii=False),
            int(conjunto.descontinuado),
            conjunto.url_portal,
            conjunto.catalogado_em,
            conjunto.metadados_atualizados_em,
            conjunto.dados_atualizados_em,
            conjunto.coletado_em,
            quando,
        ),
    )

    for recurso in conjunto.recursos:
        conexao.execute(
            _upsert("recurso", CAMPOS_RECURSO),
            (
                recurso.id,
                conjunto.id,
                recurso.titulo,
                recurso.descricao,
                recurso.formato,
                recurso.link,
                recurso.tamanho,
                recurso.catalogado_em,
                recurso.arquivo_atualizado_em,
                quando,
            ),
        )

    # Recurso que sumiu da origem some do banco: reingestão não deixa órfão.
    presentes = [recurso.id for recurso in conjunto.recursos]
    marcadores = ", ".join("?" for _ in presentes)
    if presentes:
        conexao.execute(
            f"DELETE FROM recurso WHERE conjunto_id = ? AND id NOT IN ({marcadores})",
            (conjunto.id, *presentes),
        )
    else:
        conexao.execute("DELETE FROM recurso WHERE conjunto_id = ?", (conjunto.id,))


# --- ingestão ------------------------------------------------------------


@dataclass
class Relatorio:
    conjuntos: int = 0
    recursos: int = 0
    rejeitados: int = 0
    lidos: int = 0

    @property
    def taxa_rejeicao(self) -> float:
        return self.rejeitados / self.lidos if self.lidos else 0.0


def ler_jsonl(caminho: Path) -> Iterator[tuple[int, str]]:
    """Em fluxo: o arquivo completo tem 19 mil registros com detalhe embutido."""
    with caminho.open(encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            if linha.strip():
                yield numero, linha


def normalizar(
    entrada: Path, banco: Path, quarentena: Path, limiar: float = LIMIAR_REJEICAO
) -> Relatorio:
    relatorio = Relatorio()
    quando = agora_utc()
    conexao = abrir_banco(banco)

    if quarentena.exists():
        quarentena.unlink()

    def rejeitar(linha_numero: int, conteudo: str, motivo: str) -> None:
        relatorio.rejeitados += 1
        with quarentena.open("a", encoding="utf-8") as arquivo:
            arquivo.write(
                json.dumps(
                    {
                        "linha": linha_numero,
                        "motivo": motivo,
                        "quando": quando,
                        "registro": conteudo.strip()[:2000],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    try:
        for numero, linha in ler_jsonl(entrada):
            relatorio.lidos += 1
            try:
                bruto = json.loads(linha)
            except ValueError as erro:
                rejeitar(numero, linha, f"JSON inválido: {erro}")
                continue
            if not isinstance(bruto, dict):
                rejeitar(numero, linha, "linha não é um objeto JSON")
                continue

            try:
                conjunto = Conjunto.de_bruto(bruto)
            except ValidationError as erro:
                motivos = "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in erro.errors()
                )
                rejeitar(numero, linha, motivos)
                continue

            gravar(conexao, conjunto, quando)
            relatorio.conjuntos += 1
            relatorio.recursos += len(conjunto.recursos)

        conexao.commit()
    finally:
        conexao.close()

    return relatorio


def escolher_entrada() -> Path:
    """A base completa quando existir; a amostra de desenvolvimento se não."""
    completa = DIRETORIO_BRUTO / "conjuntos.jsonl"
    amostra = DIRETORIO_BRUTO / "conjuntos-dev.jsonl"
    return completa if completa.is_file() else amostra


# --- interface de linha de comando --------------------------------------

app = typer.Typer(add_completion=False, help=__doc__)


@app.command()
def main(
    entrada: Optional[Path] = typer.Option(
        None, "--entrada", help="JSONL da coleta. Por padrão usa a base completa, ou a amostra."
    ),
    banco: Path = typer.Option(
        DIRETORIO_DADOS / "dados.db", "--banco", help="Caminho do SQLite de saída."
    ),
    limiar: float = typer.Option(
        LIMIAR_REJEICAO, "--limiar", min=0.0, max=1.0, help="Taxa de rejeição tolerada."
    ),
) -> None:
    """Ingere o JSONL bruto em `dados.db`."""
    origem = entrada or escolher_entrada()
    if not origem.is_file():
        log(f"entrada não encontrada: {origem}")
        log("rode a coleta antes: uv run python coleta.py --limite 500")
        raise typer.Exit(code=2)

    log(f"lendo {origem}")
    relatorio = normalizar(origem, banco, ARQUIVO_QUARENTENA, limiar)

    log("")
    log("relatório de ingestão")
    log(f"  registros lidos:     {relatorio.lidos}")
    log(f"  conjuntos ingeridos: {relatorio.conjuntos}")
    log(f"  recursos ingeridos:  {relatorio.recursos}")
    log(f"  rejeitados:          {relatorio.rejeitados}")
    log(f"  taxa de rejeição:    {relatorio.taxa_rejeicao:.2%}")
    log(f"  banco:               {banco}")

    if relatorio.rejeitados:
        log(f"  quarentena:          {ARQUIVO_QUARENTENA}")

    if relatorio.taxa_rejeicao > limiar:
        log("")
        log(
            f"taxa de rejeição acima do limiar de {limiar:.0%}. "
            f"Os registros recusados estão em {ARQUIVO_QUARENTENA}."
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
