"""Registro do que cada resposta custou e de onde veio.

É honestidade com o usuário — a origem vai no evento final — e é a métrica que
diz se a arquitetura está economizando: se quase tudo sai por template, o
roteamento está apertado demais; se quase nada sai, os limiares estão errados.

Nada aqui grava pergunta com dado pessoal nem chave: só o texto da pergunta,
que o usuário digitou para ser respondido, e números.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("caminho-das-pedras")

if not logger.handlers:
    _saida = logging.StreamHandler(sys.stderr)
    _saida.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_saida)
    logger.setLevel(logging.INFO)


@dataclass
class Medicao:
    pergunta: str
    origem: str = ""
    fichas: int = 0
    motivo: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    _inicio: float = field(default_factory=time.monotonic)

    @property
    def latencia_ms(self) -> int:
        return int((time.monotonic() - self._inicio) * 1000)

    def registrar(self) -> None:
        logger.info(
            json.dumps(
                {
                    "evento": "resposta",
                    "pergunta": self.pergunta,
                    "origem": self.origem,
                    "fichas": self.fichas,
                    "latencia_ms": self.latencia_ms,
                    "motivo": self.motivo,
                    **self.extra,
                },
                ensure_ascii=False,
            )
        )


def registrar_fabricacao(pergunta: str, motivo: str, texto: str) -> None:
    """A resposta foi descartada por citar o que não existe.

    Vai para o log inteiro, com a pergunta e o que foi fabricado: sem isso não
    há como saber se a guarda dispara uma vez por mês ou o tempo todo.
    """
    logger.warning(
        json.dumps(
            {
                "evento": "resposta_descartada",
                "pergunta": pergunta,
                "motivo": motivo,
                "texto": texto,
            },
            ensure_ascii=False,
        )
    )
