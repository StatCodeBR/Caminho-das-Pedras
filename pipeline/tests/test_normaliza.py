"""Testes da normalização. Trabalham sobre JSONL sintético e SQLite temporário."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import normaliza


def registro(identificador: str = "id-1", **sobrepoe) -> dict:
    """Um registro no formato que a coleta grava: topo enxuto e detalhe cheio."""
    detalhe = {
        "id": identificador,
        "nome": f"slug-{identificador}",
        "titulo": f"Conjunto {identificador}",
        "descricao": "Descrição qualquer",
        "organizacao": "ministerio-da-saude",
        "periodicidade": "Mensal",
        "temas": [],
        "tags": [],
        "descontinuado": False,
        "dataCatalogacao": "07/05/2025 16:42:55",
        "dataUltimaAtualizacaoMetadados": "05/09/2026 10:19:29",
        "dataUltimaAtualizacaoArquivo": "Indisponível",
        "recursos": [
            {
                "id": f"{identificador}-r1",
                "titulo": "Planilha de 2024",
                "formato": "csv",
                "link": "https://exemplo.gov.br/a.csv",
                "tamanho": 1234,
                "dataCatalogacao": "09/12/2020",
            }
        ],
    }
    detalhe.update(sobrepoe.pop("detalhe", {}))
    base = {
        "id": identificador,
        "nome": detalhe.get("nome"),
        "detalhe": detalhe,
        "coletado_em": "2026-09-07T02:14:30+00:00",
        "pagina_origem": 1,
    }
    base.update(sobrepoe)
    return base


@pytest.fixture
def caminhos(tmp_path: Path):
    return {
        "entrada": tmp_path / "conjuntos-dev.jsonl",
        "banco": tmp_path / "dados.db",
        "quarentena": tmp_path / "quarentena.jsonl",
    }


def escrever(caminho: Path, registros: list[dict]) -> None:
    caminho.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n", encoding="utf-8"
    )


def consultar(banco: Path, sql: str, *params):
    conexao = sqlite3.connect(banco)
    try:
        return conexao.execute(sql, params).fetchall()
    finally:
        conexao.close()


def test_registro_sem_descricao_e_ingerido_normalmente(caminhos):
    """Cenário: campos opcionais ausentes."""
    magro = registro("sem-desc", detalhe={"descricao": None, "periodicidade": None, "temas": None})
    escrever(caminhos["entrada"], [magro])

    relatorio = normaliza.normalizar(**caminhos)

    assert relatorio.conjuntos == 1
    assert relatorio.rejeitados == 0
    linha = consultar(caminhos["banco"], "SELECT descricao, periodicidade, temas FROM conjunto")[0]
    assert linha[0] is None
    assert linha[1] is None
    assert linha[2] == "[]"


def test_registro_sem_identificador_vai_para_quarentena(caminhos):
    """Cenário: registro sem identificador."""
    quebrado = registro("sem-id", id="", detalhe={"id": ""})
    escrever(caminhos["entrada"], [quebrado, registro("bom")])

    relatorio = normaliza.normalizar(**caminhos)

    assert relatorio.rejeitados == 1
    # O registro seguinte continuou sendo processado.
    assert relatorio.conjuntos == 1
    assert consultar(caminhos["banco"], "SELECT id FROM conjunto") == [("bom",)]

    quarentenados = [
        json.loads(linha)
        for linha in caminhos["quarentena"].read_text(encoding="utf-8").splitlines()
    ]
    assert "identificador" in quarentenados[0]["motivo"]


def test_reingestao_nao_duplica_recursos(caminhos):
    """Cenário: reexecução sobre o mesmo JSONL."""
    escrever(caminhos["entrada"], [registro("a"), registro("b")])

    primeira = normaliza.normalizar(**caminhos)
    segunda = normaliza.normalizar(**caminhos)

    assert (primeira.conjuntos, primeira.recursos) == (segunda.conjuntos, segunda.recursos)
    assert consultar(caminhos["banco"], "SELECT COUNT(*) FROM conjunto")[0][0] == 2
    assert consultar(caminhos["banco"], "SELECT COUNT(*) FROM recurso")[0][0] == 2


def test_recurso_removido_na_origem_some_do_banco(caminhos):
    """Cenário: conjunto que perdeu um recurso."""
    dois = registro("a")
    dois["detalhe"]["recursos"].append(
        {"id": "a-r2", "titulo": "Segundo arquivo", "formato": "JSON"}
    )
    escrever(caminhos["entrada"], [dois])
    normaliza.normalizar(**caminhos)
    assert consultar(caminhos["banco"], "SELECT COUNT(*) FROM recurso")[0][0] == 2

    escrever(caminhos["entrada"], [registro("a")])
    normaliza.normalizar(**caminhos)

    restantes = consultar(caminhos["banco"], "SELECT id FROM recurso")
    assert restantes == [("a-r1",)]


def test_conjunto_sem_recursos_ainda_e_ingerido(caminhos):
    """Cenário: conjunto sem recursos."""
    escrever(caminhos["entrada"], [registro("vazio", detalhe={"recursos": []})])

    relatorio = normaliza.normalizar(**caminhos)

    assert relatorio.conjuntos == 1
    assert relatorio.recursos == 0
    assert consultar(caminhos["banco"], "SELECT COUNT(*) FROM recurso")[0][0] == 0


def test_conjunto_com_tres_recursos(caminhos):
    """Cenário: conjunto com múltiplos recursos."""
    tres = registro("a")
    tres["detalhe"]["recursos"] = [
        {"id": f"a-r{n}", "titulo": f"Arquivo {n}", "formato": "CSV"} for n in range(3)
    ]
    escrever(caminhos["entrada"], [tres])

    normaliza.normalizar(**caminhos)

    assert consultar(caminhos["banco"], "SELECT COUNT(*) FROM conjunto")[0][0] == 1
    vinculados = consultar(
        caminhos["banco"], "SELECT COUNT(*) FROM recurso WHERE conjunto_id = ?", "a"
    )
    assert vinculados[0][0] == 3


def test_datas_gravadas_sem_deslocar_o_instante(caminhos):
    """Cenário: data sem fuso declarado."""
    escrever(caminhos["entrada"], [registro("a")])

    normaliza.normalizar(**caminhos)

    catalogado, metadados, dados = consultar(
        caminhos["banco"],
        "SELECT catalogado_em, metadados_atualizados_em, dados_atualizados_em FROM conjunto",
    )[0]
    # A origem não declara fuso: 16:42:55 continua 16:42:55, marcado como UTC.
    assert catalogado == "2025-05-07T16:42:55+00:00"
    assert metadados == "2026-09-05T10:19:29+00:00"
    # Cenário: data irrecuperável — "Indisponível" vira nulo, sem quarentena.
    assert dados is None


def test_formato_do_recurso_normalizado(caminhos):
    """Cenário: formato escrito de maneiras diferentes."""
    variado = registro("a")
    variado["detalhe"]["recursos"] = [
        {"id": "r-minusculo", "formato": "csv"},
        {"id": "r-espaco", "formato": "CSV "},
        {"id": "r-ponto", "formato": ".csv"},
        {"id": "r-vazio", "formato": "  "},
    ]
    escrever(caminhos["entrada"], [variado])

    normaliza.normalizar(**caminhos)

    formatos = dict(consultar(caminhos["banco"], "SELECT id, formato FROM recurso"))
    assert formatos["r-minusculo"] == "CSV"
    assert formatos["r-espaco"] == "CSV"
    assert formatos["r-ponto"] == "CSV"
    assert formatos["r-vazio"] is None


def test_url_do_portal_nunca_fica_nula(caminhos):
    """Cenário: URL ausente na origem."""
    escrever(
        caminhos["entrada"],
        [registro("com-slug"), registro("sem-slug", nome=None, detalhe={"nome": None})],
    )

    normaliza.normalizar(**caminhos)

    urls = dict(consultar(caminhos["banco"], "SELECT id, url_portal FROM conjunto"))
    assert urls["com-slug"] == "https://dados.gov.br/dados/conjuntos-dados/slug-com-slug"
    # Sem slug, a URL cai no identificador — mas nunca fica nula.
    assert urls["sem-slug"] == "https://dados.gov.br/dados/conjuntos-dados/sem-slug"


def test_taxa_de_rejeicao_acima_do_limiar_encerra_com_erro(caminhos, monkeypatch, tmp_path):
    """Cenário: degradação da fonte."""
    ruins = [registro(f"ruim-{n}", id="", detalhe={"id": ""}) for n in range(3)]
    escrever(caminhos["entrada"], [*ruins, registro("bom")])

    monkeypatch.setattr(normaliza, "ARQUIVO_QUARENTENA", caminhos["quarentena"])
    from typer.testing import CliRunner

    resultado = CliRunner().invoke(
        normaliza.app,
        ["--entrada", str(caminhos["entrada"]), "--banco", str(caminhos["banco"])],
    )

    assert resultado.exit_code == 1
    assert str(caminhos["quarentena"]) in resultado.output


def test_ingestao_saudavel_encerra_com_zero(caminhos, monkeypatch):
    """Cenário: ingestão saudável."""
    escrever(caminhos["entrada"], [registro(f"c{n}") for n in range(30)])
    monkeypatch.setattr(normaliza, "ARQUIVO_QUARENTENA", caminhos["quarentena"])
    from typer.testing import CliRunner

    resultado = CliRunner().invoke(
        normaliza.app,
        ["--entrada", str(caminhos["entrada"]), "--banco", str(caminhos["banco"])],
    )

    assert resultado.exit_code == 0
    assert "conjuntos ingeridos: 30" in resultado.output
