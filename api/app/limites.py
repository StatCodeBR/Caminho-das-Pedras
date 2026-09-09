"""Contenção de consumo: teto diário e limite por origem.

Dois limites com naturezas opostas, de propósito.

O **teto diário** protege o orçamento e nunca produz erro: ao estourar, o
serviço passa a responder por template. Devolver falha ao atingir o teto seria
transformar um problema nosso — a conta acabou — em erro na cara de quem
perguntou.

O **limite por origem** protege contra abuso e recusa com 429. Quem dispara
vinte perguntas numa hora não é visitante; atendê-lo em modo reduzido só
transferiria o custo para o resto.

O estado mora num SQLite próprio, gravável, separado do `dados.db` — que é
somente leitura por decisão da mudança 09. Contador em memória zeraria a cada
deploy, e um teto de gasto que se apaga sozinho não é teto.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS consumo_diario (
    dia      TEXT PRIMARY KEY,
    chamadas INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS requisicao (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    origem TEXT NOT NULL,
    quando REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requisicao_origem ON requisicao(origem, quando);
"""


def dia_utc() -> str:
    """O dia corrente em UTC.

    Não é o fuso de Brasília de propósito: horário de verão faz uma hora
    acontecer duas vezes, o que daria duas viradas de contador no mesmo dia.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class Veredito:
    """O que a contenção decidiu sobre esta requisição."""

    permitida: bool
    reduzido: bool
    espera_s: int = 0
    motivo: str = ""


class Contencao:
    """Guarda o consumo e decide quem passa.

    O acesso é serializado por um lock: o SQLite aceita escrita concorrente mal,
    e o volume aqui é baixo — centenas de requisições por dia, não milhares por
    segundo. Correção vale mais que paralelismo neste ponto.
    """

    def __init__(
        self,
        caminho: Path,
        *,
        teto_diario: int,
        maximo_por_origem: int,
        janela_s: int,
    ):
        self.caminho = caminho
        self.teto_diario = teto_diario
        self.maximo_por_origem = maximo_por_origem
        self.janela_s = janela_s
        self._trava = threading.Lock()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(caminho, check_same_thread=False)
        self._conexao.executescript(DDL)
        self._conexao.commit()

    # --- teto diário -----------------------------------------------------

    def consumo_do_dia(self) -> int:
        linha = self._conexao.execute(
            "SELECT chamadas FROM consumo_diario WHERE dia = ?", (dia_utc(),)
        ).fetchone()
        return linha[0] if linha else 0

    def em_modo_reduzido(self) -> bool:
        return self.consumo_do_dia() >= self.teto_diario

    def registrar_chamada(self) -> int:
        """Conta uma chamada ao modelo. Só é chamada quando o modelo é usado."""
        with self._trava:
            self._conexao.execute(
                """INSERT INTO consumo_diario (dia, chamadas) VALUES (?, 1)
                   ON CONFLICT(dia) DO UPDATE SET chamadas = chamadas + 1""",
                (dia_utc(),),
            )
            self._conexao.commit()
            return self.consumo_do_dia()

    # --- limite por origem -----------------------------------------------

    def _podar(self, agora: float) -> None:
        """Descarta requisições fora da janela.

        Sem isto a tabela cresceria para sempre guardando janelas que já
        passaram, e a contagem ficaria cada vez mais lenta.
        """
        self._conexao.execute(
            "DELETE FROM requisicao WHERE quando < ?", (agora - self.janela_s,)
        )

    def _espera_ate_liberar(self, origem: str, agora: float) -> int:
        """Quantos segundos até a requisição mais antiga sair da janela."""
        linha = self._conexao.execute(
            "SELECT MIN(quando) FROM requisicao WHERE origem = ? AND quando >= ?",
            (origem, agora - self.janela_s),
        ).fetchone()
        if not linha or linha[0] is None:
            return 0
        return max(1, int(linha[0] + self.janela_s - agora) + 1)

    # --- decisão ---------------------------------------------------------

    def avaliar(self, origem: str) -> Veredito:
        """Decide e já contabiliza a requisição, quando ela passa.

        Janela deslizante, não balde por hora cheia: com balde, quem chega às
        10h59 gasta o limite e às 11h00 gasta tudo de novo, dobrando o teto na
        virada.
        """
        agora = time.time()
        with self._trava:
            self._podar(agora)
            usadas = self._conexao.execute(
                "SELECT count(*) FROM requisicao WHERE origem = ? AND quando >= ?",
                (origem, agora - self.janela_s),
            ).fetchone()[0]

            if usadas >= self.maximo_por_origem:
                espera = self._espera_ate_liberar(origem, agora)
                self._conexao.commit()
                return Veredito(
                    permitida=False,
                    reduzido=False,
                    espera_s=espera,
                    motivo=f"origem excedeu {self.maximo_por_origem} em {self.janela_s}s",
                )

            self._conexao.execute(
                "INSERT INTO requisicao (origem, quando) VALUES (?, ?)", (origem, agora)
            )
            self._conexao.commit()

        reduzido = self.em_modo_reduzido()
        return Veredito(
            permitida=True,
            reduzido=reduzido,
            motivo="teto diário atingido" if reduzido else "",
        )

    # --- operação --------------------------------------------------------

    def estado(self) -> dict:
        consumo = self.consumo_do_dia()
        return {
            "dia": dia_utc(),
            "consumo": consumo,
            "teto": self.teto_diario,
            "restante": max(0, self.teto_diario - consumo),
            "modo_reduzido": consumo >= self.teto_diario,
            "limite_por_origem": self.maximo_por_origem,
            "janela_s": self.janela_s,
        }

    def fechar(self) -> None:
        self._conexao.close()
