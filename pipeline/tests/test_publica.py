"""Testes da publicação do catálogo.

O que precisa ser verdade aqui é que o manifesto descreve o banco que ele diz
descrever, e que soma divergente reprova o artefato. As duas coisas são a única
defesa contra uma imagem servir um catálogo que ninguém pediu — e esse defeito
não se manifesta como erro: as respostas continuam bem formadas, só faltam
conjuntos.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import publica

OBTENTOR = Path(__file__).resolve().parents[2] / "api" / "obter_catalogo.py"


def _banco(caminho: Path, conjuntos: int, fichas: int, modelo: str) -> Path:
    conexao = sqlite3.connect(caminho)
    conexao.executescript(
        """
        CREATE TABLE conjunto (id TEXT PRIMARY KEY, nome TEXT);
        CREATE TABLE recurso (id INTEGER PRIMARY KEY, conjunto_id TEXT);
        CREATE TABLE ficha (conjunto_id TEXT PRIMARY KEY, modelo TEXT,
                            gerada_em TEXT);
        """
    )
    conexao.executemany(
        "INSERT INTO conjunto VALUES (?,?)",
        [(str(i), f"conjunto-{i}") for i in range(conjuntos)],
    )
    conexao.executemany(
        "INSERT INTO recurso (conjunto_id) VALUES (?)",
        [(str(i),) for i in range(conjuntos * 2)],
    )
    conexao.executemany(
        "INSERT INTO ficha VALUES (?,?,?)",
        [(str(i), modelo, "2026-09-11T00:00:00+00:00") for i in range(fichas)],
    )
    conexao.commit()
    conexao.close()
    return caminho


# --- manifesto -----------------------------------------------------------


def test_manifesto_reflete_o_conteudo_real_do_banco(tmp_path):
    banco = _banco(tmp_path / "dados.db", conjuntos=7, fichas=5, modelo="prov/modelo-x")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")

    m = publica.montar_manifesto(banco, artefato, "catalogo-teste", repo="dono/repo")

    assert m["conjuntos"] == 7
    assert m["fichas"] == 5
    assert m["recursos"] == 14
    assert m["modelos"] == ["prov/modelo-x"]
    assert m["gerado_em"] == "2026-09-11T00:00:00+00:00"
    assert m["bytes"] == artefato.stat().st_size
    assert m["bytes_descomprimido"] == banco.stat().st_size


def test_soma_do_manifesto_e_a_do_artefato(tmp_path):
    banco = _banco(tmp_path / "dados.db", 3, 3, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")
    m = publica.montar_manifesto(banco, artefato, "v", repo="dono/repo")
    assert m["sha256"] == publica.soma_sha256(artefato)


def test_compressao_e_deterministica(tmp_path):
    """Duas execuções sobre o mesmo banco dão a mesma soma.

    Sem isto o manifesto não seria reproduzível: regerar o artefato mudaria a
    soma sem mudar o catálogo, e cada regeração exigiria um commit novo.
    """
    banco = _banco(tmp_path / "dados.db", 4, 4, "prov/m")
    um = publica.soma_sha256(publica.comprimir(banco, tmp_path / "a.gz"))
    dois = publica.soma_sha256(publica.comprimir(banco, tmp_path / "b.gz"))
    assert um == dois


def test_o_artefato_descomprime_no_banco_original(tmp_path):
    banco = _banco(tmp_path / "dados.db", 5, 5, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")
    with gzip.open(artefato, "rb") as entrada:
        assert entrada.read() == banco.read_bytes()


def test_url_de_origem_aponta_para_a_versao_declarada(tmp_path):
    banco = _banco(tmp_path / "dados.db", 2, 2, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")
    m = publica.montar_manifesto(banco, artefato, "catalogo-2026-01-02", repo="o/r")
    # Versão fixa na URL: nunca "latest", ou reconstruir um commit antigo
    # traria um catálogo que ninguém pediu.
    assert m["origem"].endswith("/releases/download/catalogo-2026-01-02/dados.db.gz")
    assert "latest" not in m["origem"]


# --- verificação, do lado de quem consome -------------------------------


def _obter(
    manifesto: dict, tmp_path: Path, local: str = "", destino: Path | None = None
) -> subprocess.CompletedProcess:
    caminho = tmp_path / "catalogo.json"
    caminho.write_text(json.dumps(manifesto), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(OBTENTOR), str(caminho),
         str(destino or tmp_path / "saida.db"), local],
        capture_output=True,
        text=True,
    )


def test_baixa_para_diretorio_que_ainda_nao_existe(tmp_path):
    """O destino na imagem é `/dados/dados.db`, e `/dados` não existe no build.

    O caminho local passava porque `descomprimir` cria o diretório; o de
    download escrevia o `.gz` antes disso e quebrava com "No such file or
    directory". A divergência só apareceu quando o build baixou de verdade —
    daí este teste existir.
    """
    banco = _banco(tmp_path / "dados.db", 3, 3, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")
    destino = tmp_path / "ainda" / "nao" / "existe" / "dados.db"

    resultado = _obter(
        {
            "versao": "v",
            "origem": artefato.as_uri(),
            "sha256": publica.soma_sha256(artefato),
        },
        tmp_path,
        destino=destino,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert destino.read_bytes() == banco.read_bytes()
    # O intermediário é removido: a imagem não carrega 35 MB comprimidos além
    # dos 186 MB do banco.
    assert not destino.with_name(destino.name + ".gz").exists()


def test_soma_divergente_reprova_o_artefato(tmp_path):
    banco = _banco(tmp_path / "dados.db", 3, 3, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")
    errada = "0" * 64

    resultado = _obter(
        {"versao": "catalogo-teste", "origem": artefato.as_uri(), "sha256": errada},
        tmp_path,
    )

    assert resultado.returncode == 1
    assert not (tmp_path / "saida.db").exists()
    # A mensagem precisa dizer as duas somas: sem isso, quem depura não
    # distingue artefato trocado de artefato truncado.
    assert errada in resultado.stderr
    assert publica.soma_sha256(artefato) in resultado.stderr


def test_soma_correta_aprova_o_artefato(tmp_path):
    banco = _banco(tmp_path / "dados.db", 3, 3, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")

    resultado = _obter(
        {
            "versao": "catalogo-teste",
            "origem": artefato.as_uri(),
            "sha256": publica.soma_sha256(artefato),
        },
        tmp_path,
    )

    assert resultado.returncode == 0
    assert (tmp_path / "saida.db").read_bytes() == banco.read_bytes()


def test_download_que_falha_diz_qual_versao_era_esperada(tmp_path):
    resultado = _obter(
        {
            "versao": "catalogo-2026-01-02",
            "origem": (tmp_path / "nao-existe.gz").as_uri(),
            "sha256": "0" * 64,
        },
        tmp_path,
    )
    assert resultado.returncode == 1
    assert "catalogo-2026-01-02" in resultado.stderr


def test_artefato_local_dispensa_a_soma(tmp_path):
    banco = _banco(tmp_path / "dados.db", 3, 3, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")

    resultado = _obter(
        {"versao": "v", "origem": "https://exemplo.invalido/x.gz", "sha256": "0" * 64},
        tmp_path,
        local=str(artefato),
    )

    assert resultado.returncode == 0
    assert (tmp_path / "saida.db").read_bytes() == banco.read_bytes()


def test_sem_artefato_local_o_padrao_e_baixar_e_conferir(tmp_path):
    """O descuido precisa levar ao caminho seguro, não ao permissivo."""
    banco = _banco(tmp_path / "dados.db", 3, 3, "prov/m")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")

    resultado = _obter(
        {"versao": "v", "origem": artefato.as_uri(), "sha256": "0" * 64}, tmp_path
    )

    assert resultado.returncode == 1
    assert "DIVERGENTE" in resultado.stderr


def test_manifesto_sem_soma_e_recusado(tmp_path):
    resultado = _obter({"versao": "v", "origem": "https://exemplo.invalido/x"}, tmp_path)
    assert resultado.returncode == 1
    assert "sha256" in resultado.stderr
