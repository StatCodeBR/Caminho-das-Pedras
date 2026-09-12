"""Testes da publicação do catálogo.

O que precisa ser verdade aqui é que o manifesto descreve os artefatos que ele
diz descrever, que soma divergente reprova cada um deles, e que banco e vetores
nunca são publicados desencontrados. As três coisas são a única defesa contra
uma imagem servir um catálogo que ninguém pediu — e esse defeito não se
manifesta como erro: as respostas continuam bem formadas, só faltam conjuntos,
ou pior, falam do conjunto errado.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path

import numpy as np
import pytest

import publica
import semantica
import vetoriza

OBTENTOR = Path(__file__).resolve().parents[2] / "api" / "obter_catalogo.py"


def _banco(caminho: Path, conjuntos: int = 3, fichas: int = 3, modelo: str = "prov/m") -> Path:
    conexao = sqlite3.connect(caminho)
    conexao.executescript(
        """
        CREATE TABLE conjunto (id TEXT PRIMARY KEY, nome TEXT);
        CREATE TABLE recurso (id INTEGER PRIMARY KEY, conjunto_id TEXT);
        CREATE TABLE ficha (conjunto_id TEXT PRIMARY KEY, modelo TEXT,
                            gerada_em TEXT, texto_indexavel TEXT);
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
        "INSERT INTO ficha VALUES (?,?,?,?)",
        [(str(i), modelo, "2026-09-11T00:00:00+00:00", f"texto {i}") for i in range(fichas)],
    )
    conexao.commit()
    conexao.close()
    return caminho


def _vetores(banco: Path, diretorio: Path, versao: str | None = None) -> tuple[Path, Path]:
    """Vetores coerentes com o banco, a menos que se peça outra versão."""
    conexao = sqlite3.connect(banco)
    fichas = semantica.ler_fichas(conexao)
    conexao.close()
    matriz = np.eye(len(fichas), 4, dtype=np.float32)
    npy, ids = diretorio / "vectors.npy", diretorio / "vectors.json"
    vetoriza.gravar(
        matriz,
        [i for i, _ in fichas],
        versao or semantica.versao_do_catalogo(fichas),
        npy,
        ids,
    )
    return npy, ids


def _publicavel(tmp_path):
    """Banco, vetores, e os dois artefatos prontos para publicar."""
    banco = _banco(tmp_path / "dados.db")
    npy, ids = _vetores(banco, tmp_path)
    artefato = publica.comprimir(banco, tmp_path / publica.ASSET_BANCO)
    pacote = publica.empacotar_vetores(npy, ids, tmp_path / publica.ASSET_VETORES)
    meta = publica.conferir_vetores(banco, ids)
    manifesto = publica.montar_manifesto(
        banco, artefato, pacote, meta, "catalogo-teste", repo="dono/repo"
    )
    return banco, artefato, pacote, manifesto


# --- manifesto -----------------------------------------------------------


def test_manifesto_reflete_o_conteudo_real_do_banco(tmp_path):
    banco, artefato, pacote, m = _publicavel(tmp_path)
    assert m["conjuntos"] == 3
    assert m["fichas"] == 3
    assert m["recursos"] == 6
    assert m["modelos"] == ["prov/m"]
    assert m["gerado_em"] == "2026-09-11T00:00:00+00:00"
    assert m["vetores"] == 3
    assert m["modelo_embedding"] == "intfloat/multilingual-e5-small"


def test_cada_asset_tem_soma_propria(tmp_path):
    banco, artefato, pacote, m = _publicavel(tmp_path)
    assert m["assets"]["banco"]["sha256"] == publica.soma_sha256(artefato)
    assert m["assets"]["vetores"]["sha256"] == publica.soma_sha256(pacote)
    assert m["assets"]["banco"]["sha256"] != m["assets"]["vetores"]["sha256"]
    assert m["assets"]["banco"]["bytes"] == artefato.stat().st_size
    assert m["assets"]["banco"]["bytes_descomprimido"] == banco.stat().st_size


def test_url_de_cada_asset_aponta_para_a_versao_declarada(tmp_path):
    _, _, _, m = _publicavel(tmp_path)
    for nome, asset in m["assets"].items():
        # Versão fixa na URL: nunca "latest", ou reconstruir um commit antigo
        # traria um catálogo que ninguém pediu.
        assert asset["origem"].endswith(f"/download/catalogo-teste/{asset['arquivo']}")
        assert "latest" not in asset["origem"]


def test_compressao_e_empacotamento_sao_deterministicos(tmp_path):
    """Regerar sobre os mesmos dados precisa dar a mesma soma.

    Sem isto o manifesto não seria reproduzível: cada regeração exigiria um
    commit novo sem nada ter mudado.
    """
    banco = _banco(tmp_path / "dados.db")
    npy, ids = _vetores(banco, tmp_path)
    um = publica.soma_sha256(publica.comprimir(banco, tmp_path / "a.gz"))
    dois = publica.soma_sha256(publica.comprimir(banco, tmp_path / "b.gz"))
    assert um == dois
    tar_um = publica.soma_sha256(publica.empacotar_vetores(npy, ids, tmp_path / "a.tar.gz"))
    tar_dois = publica.soma_sha256(publica.empacotar_vetores(npy, ids, tmp_path / "b.tar.gz"))
    assert tar_um == tar_dois


def test_o_pacote_traz_os_dois_arquivos_dos_vetores(tmp_path):
    banco = _banco(tmp_path / "dados.db")
    npy, ids = _vetores(banco, tmp_path)
    pacote = publica.empacotar_vetores(npy, ids, tmp_path / "v.tar.gz")
    with tarfile.open(pacote, "r:gz") as arquivo:
        assert sorted(arquivo.getnames()) == ["vectors.json", "vectors.npy"]


def test_o_artefato_descomprime_no_banco_original(tmp_path):
    banco = _banco(tmp_path / "dados.db")
    artefato = publica.comprimir(banco, tmp_path / "dados.db.gz")
    with gzip.open(artefato, "rb") as entrada:
        assert entrada.read() == banco.read_bytes()


# --- vetores desencontrados ---------------------------------------------


def test_vetores_de_outra_versao_impedem_a_publicacao(tmp_path):
    banco = _banco(tmp_path / "dados.db")
    _, ids = _vetores(banco, tmp_path, versao="0" * 64)
    with pytest.raises(publica.ErroDePublicacao, match="outra versão do catálogo"):
        publica.conferir_vetores(banco, ids)


def test_vetores_coerentes_liberam_a_publicacao(tmp_path):
    banco = _banco(tmp_path / "dados.db")
    _, ids = _vetores(banco, tmp_path)
    assert publica.conferir_vetores(banco, ids)["total"] == 3


def test_banco_alterado_depois_da_vetorizacao_e_recusado(tmp_path):
    banco = _banco(tmp_path / "dados.db")
    _, ids = _vetores(banco, tmp_path)
    conexao = sqlite3.connect(banco)
    conexao.execute("UPDATE ficha SET texto_indexavel = 'outro' WHERE conjunto_id = '1'")
    conexao.commit()
    conexao.close()
    with pytest.raises(publica.ErroDePublicacao, match="outra versão do catálogo"):
        publica.conferir_vetores(banco, ids)


# --- verificação, do lado de quem consome -------------------------------


def _obter(manifesto: dict, tmp_path: Path, locais: tuple[str, str] | None = None):
    caminho = tmp_path / "catalogo.json"
    caminho.write_text(json.dumps(manifesto), encoding="utf-8")
    destino = tmp_path / "saida" / "dados.db"
    return (
        subprocess.run(
            [sys.executable, str(OBTENTOR), str(caminho), str(destino),
             *(locais or ("", ""))],
            capture_output=True,
            text=True,
        ),
        destino,
    )


def _manifesto_local(tmp_path, artefato: Path, pacote: Path, manifesto: dict) -> dict:
    """O manifesto com as origens apontando para os arquivos locais, via file://."""
    manifesto = json.loads(json.dumps(manifesto))
    manifesto["assets"]["banco"]["origem"] = artefato.as_uri()
    manifesto["assets"]["vetores"]["origem"] = pacote.as_uri()
    return manifesto


def test_somas_corretas_aprovam_os_dois_artefatos(tmp_path):
    banco, artefato, pacote, m = _publicavel(tmp_path)
    resultado, destino = _obter(_manifesto_local(tmp_path, artefato, pacote, m), tmp_path)
    assert resultado.returncode == 0, resultado.stderr
    assert destino.read_bytes() == banco.read_bytes()
    assert (destino.parent / "vectors.npy").is_file()
    assert (destino.parent / "vectors.json").is_file()
    # Os comprimidos intermediários não ficam na imagem.
    assert not (destino.parent / "vetores.tar.gz").exists()
    assert not destino.with_name(destino.name + ".gz").exists()


def test_soma_divergente_do_banco_reprova(tmp_path):
    _, artefato, pacote, m = _publicavel(tmp_path)
    m = _manifesto_local(tmp_path, artefato, pacote, m)
    m["assets"]["banco"]["sha256"] = "0" * 64
    resultado, destino = _obter(m, tmp_path)
    assert resultado.returncode == 1
    assert "BANCO" in resultado.stderr
    assert publica.soma_sha256(artefato) in resultado.stderr


def test_soma_divergente_dos_vetores_reprova(tmp_path):
    """A mensagem precisa dizer qual asset divergiu, não só que algo divergiu."""
    _, artefato, pacote, m = _publicavel(tmp_path)
    m = _manifesto_local(tmp_path, artefato, pacote, m)
    m["assets"]["vetores"]["sha256"] = "0" * 64
    resultado, _ = _obter(m, tmp_path)
    assert resultado.returncode == 1
    assert "VETORES" in resultado.stderr


def test_download_que_falha_diz_qual_versao_e_qual_asset(tmp_path):
    _, artefato, pacote, m = _publicavel(tmp_path)
    m = _manifesto_local(tmp_path, artefato, pacote, m)
    m["assets"]["vetores"]["origem"] = (tmp_path / "nao-existe.tar.gz").as_uri()
    resultado, _ = _obter(m, tmp_path)
    assert resultado.returncode == 1
    assert "catalogo-teste" in resultado.stderr
    assert "VETORES" in resultado.stderr


def test_manifesto_sem_asset_e_recusado(tmp_path):
    _, _, _, m = _publicavel(tmp_path)
    del m["assets"]["vetores"]
    resultado, _ = _obter(m, tmp_path)
    assert resultado.returncode == 1
    assert "vetores" in resultado.stderr


def test_artefatos_locais_dispensam_a_soma(tmp_path):
    banco, artefato, pacote, m = _publicavel(tmp_path)
    m = json.loads(json.dumps(m))
    m["assets"]["banco"]["origem"] = "https://exemplo.invalido/x.gz"
    m["assets"]["banco"]["sha256"] = "0" * 64
    resultado, destino = _obter(m, tmp_path, locais=(str(artefato), str(pacote)))
    assert resultado.returncode == 0, resultado.stderr
    assert destino.read_bytes() == banco.read_bytes()
    assert (destino.parent / "vectors.npy").is_file()


def test_banco_local_sem_vetores_locais_falha(tmp_path):
    """Misturar banco local com vetores da release daria um par desencontrado."""
    _, artefato, pacote, m = _publicavel(tmp_path)
    resultado, _ = _obter(m, tmp_path, locais=(str(artefato), ""))
    assert resultado.returncode == 1
    assert "PELA METADE" in resultado.stderr


def test_sem_locais_o_padrao_e_baixar_e_conferir(tmp_path):
    """O descuido precisa levar ao caminho seguro, não ao permissivo."""
    _, artefato, pacote, m = _publicavel(tmp_path)
    m = _manifesto_local(tmp_path, artefato, pacote, m)
    m["assets"]["banco"]["sha256"] = "0" * 64
    resultado, _ = _obter(m, tmp_path)
    assert resultado.returncode == 1
    assert "DIVERGENTE" in resultado.stderr


def test_pacote_de_vetores_com_conteudo_inesperado_e_recusado(tmp_path):
    """Extrair nome vindo do arquivo sem conferir deixaria escrever onde quisesse."""
    _, artefato, _, m = _publicavel(tmp_path)
    intruso = tmp_path / "intruso.tar.gz"
    with tarfile.open(intruso, "w:gz") as pacote:
        alvo = tmp_path / "outro.txt"
        alvo.write_text("nada a ver", encoding="utf-8")
        pacote.add(alvo, arcname="outro.txt")
    m = _manifesto_local(tmp_path, artefato, intruso, m)
    m["assets"]["vetores"]["sha256"] = publica.soma_sha256(intruso)
    resultado, _ = _obter(m, tmp_path)
    assert resultado.returncode == 1
    assert "CONTEÚDO INESPERADO" in resultado.stderr


# --- porta de paridade ---------------------------------------------------


def test_paridade_divergente_impede_a_publicacao(monkeypatch):
    chamadas = []

    def run_falso(argumentos, **opcoes):
        chamadas.append((argumentos, opcoes.get("cwd")))
        return subprocess.CompletedProcess(argumentos, 1, stdout="1 failed", stderr="")

    monkeypatch.setattr(publica.subprocess, "run", run_falso)
    with pytest.raises(publica.ErroDePublicacao, match="paridade"):
        publica.verificar_paridade()
    assert chamadas[0][0] == ["uv", "run", "pytest", "-m", "paridade", "-q"]


def test_paridade_confirmada_nos_dois_projetos_libera(monkeypatch):
    projetos = []

    def run_falso(argumentos, **opcoes):
        projetos.append(opcoes.get("cwd").name)
        return subprocess.CompletedProcess(argumentos, 0, stdout="1 passed", stderr="")

    monkeypatch.setattr(publica.subprocess, "run", run_falso)
    publica.verificar_paridade()
    assert projetos == ["pipeline", "api"]
