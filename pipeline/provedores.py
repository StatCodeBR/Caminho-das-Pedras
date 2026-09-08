"""O modelo de linguagem atrás de uma interface única.

O enriquecimento não conhece provedor: ele pede uma ficha e recebe texto JSON.
Trocar de fornecedor é trocar a implementação aqui, sem tocar no pipeline — e
sem servir ficha antiga por engano, porque o identificador do provedor e do
modelo entra no hash do cache.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator, Optional

# Preço em dólares por milhão de tokens, (entrada, saída), conferido na tabela
# pública da Anthropic em 2026-09-07. Modelo ausente daqui não tem custo
# calculado: o relatório informa os tokens e cala sobre o dinheiro, em vez de
# apresentar um número inventado como se fosse medido.
PRECOS_USD: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
}

# A API de lotes cobra metade do preço de tabela.
DESCONTO_LOTE = 0.5


@dataclass
class Uso:
    """Tokens consumidos, separados por regime de cobrança.

    Lote e chamada avulsa têm preços diferentes, então somá-los daria um custo
    errado. O enriquecimento mistura os dois — o lote resolve o grosso e a
    retentativa de uma resposta inválida é síncrona.
    """

    entrada: int = 0
    saida: int = 0
    entrada_lote: int = 0
    saida_lote: int = 0

    @property
    def total(self) -> int:
        return self.entrada + self.saida + self.entrada_lote + self.saida_lote


class SemCredencial(RuntimeError):
    """A chave do provedor não foi fornecida pelo ambiente."""


class RespostaVazia(RuntimeError):
    """O provedor respondeu, mas sem texto aproveitável."""


class LimiteDeTaxa(RuntimeError):
    """O provedor recusou por excesso de requisições, mesmo após esperar."""


class Provedor(ABC):
    """Contrato mínimo: gerar uma ficha a partir de instrução e metadados.

    O processamento em lote é capacidade opcional. Um provedor que não o
    ofereça devolve `False` em `suporta_lote()` e o pipeline cai para chamadas
    uma a uma, mais lentas e mais caras, mas corretas.
    """

    nome: str
    modelo: str
    uso: Uso

    def custo_usd(self) -> float | None:
        """O que esta execução custou, ou `None` se o preço não for conhecido."""
        preco = PRECOS_USD.get(self.modelo)
        if preco is None:
            return None
        entrada, saida = preco
        avulso = self.uso.entrada * entrada + self.uso.saida * saida
        lote = (self.uso.entrada_lote * entrada + self.uso.saida_lote * saida)
        return (avulso + lote * DESCONTO_LOTE) / 1_000_000

    def _somar_uso(self, bruto: Any, em_lote: bool = False) -> None:
        """Acumula o que a resposta declarou ter consumido."""
        if bruto is None:
            return
        entrada = getattr(bruto, "input_tokens", 0) or 0
        saida = getattr(bruto, "output_tokens", 0) or 0
        if em_lote:
            self.uso.entrada_lote += entrada
            self.uso.saida_lote += saida
        else:
            self.uso.entrada += entrada
            self.uso.saida += saida

    @property
    def identificador(self) -> str:
        """O que vai para o hash do cache e para a coluna `modelo` da ficha.

        Inclui o provedor, não só o modelo: `command-a-03-2025` servido por
        outro fornecedor não é a mesma coisa, e a ficha precisa dizer quem a
        escreveu para que a decisão possa ser auditada depois.
        """
        return f"{self.nome}/{self.modelo}"

    @abstractmethod
    def gerar(self, sistema: str, entrada: str, esquema: dict[str, Any]) -> str:
        """Devolve o texto da resposta, que o chamador valida como JSON."""

    def suporta_lote(self) -> bool:
        return False

    def submeter_lote(self, itens: list[tuple[str, str]], sistema: str, esquema: dict) -> str:
        raise NotImplementedError(f"{self.nome} não oferece processamento em lote")

    def lote_concluido(self, lote_id: str) -> bool:
        raise NotImplementedError

    def resultados_lote(self, lote_id: str) -> Iterator[tuple[str, Optional[str]]]:
        raise NotImplementedError


# --- Cohere --------------------------------------------------------------


class ProvedorCohere(Provedor):
    """Cohere via ClientV2.

    A saída estruturada usa `response_format` com esquema JSON. A Cohere avisa
    que, em modo JSON, a instrução precisa pedir JSON explicitamente — o prompt
    já faz isso, e o esquema é a garantia de segunda camada.
    """

    nome = "cohere"
    MODELO_PADRAO = "command-a-03-2025"
    VARIAVEL_CHAVE = "COHERE_API_KEY"

    # A chave de avaliação da Cohere permite 20 chamadas por minuto e devolve
    # 429 na 21ª. Ficamos abaixo do teto de propósito: raspar o limite troca
    # uma execução de 28 minutos por uma que morre no meio.
    CHAMADAS_POR_MINUTO = 18
    MAX_TENTATIVAS_429 = 5

    def __init__(self, modelo: str | None = None, cliente: Any = None):
        self.modelo = modelo or self.MODELO_PADRAO
        self._cliente = cliente
        self._proxima_chamada = 0.0
        self.esperas_por_limite = 0
        self.uso = Uso()

    @property
    def _intervalo(self) -> float:
        por_minuto = float(
            os.environ.get("COHERE_CHAMADAS_POR_MINUTO", self.CHAMADAS_POR_MINUTO)
        )
        return 60.0 / max(por_minuto, 1.0)

    def _esperar_a_vez(self) -> None:
        """Espaça as chamadas para não bater no teto da chave."""
        agora = time.monotonic()
        if agora < self._proxima_chamada:
            time.sleep(self._proxima_chamada - agora)
            agora = time.monotonic()
        self._proxima_chamada = agora + self._intervalo

    def _obter_cliente(self) -> Any:
        if self._cliente is None:
            chave = os.environ.get(self.VARIAVEL_CHAVE, "").strip()
            if not chave:
                raise SemCredencial(
                    f"Defina {self.VARIAVEL_CHAVE} antes de enriquecer.\n"
                    "A chave é gerada em https://dashboard.cohere.com/api-keys.\n"
                    "Guarde-a no .env do projeto, que não é versionado."
                )
            import cohere

            self._cliente = cohere.ClientV2(api_key=chave)
        return self._cliente

    def gerar(self, sistema: str, entrada: str, esquema: dict[str, Any]) -> str:
        from cohere.errors import TooManyRequestsError

        cliente = self._obter_cliente()
        for tentativa in range(self.MAX_TENTATIVAS_429):
            self._esperar_a_vez()
            try:
                resposta = cliente.chat(
                    model=self.modelo,
                    messages=[
                        {"role": "system", "content": sistema},
                        {"role": "user", "content": entrada},
                    ],
                    response_format={"type": "json_object", "schema": esquema},
                )
            except TooManyRequestsError:
                # Estourar o limite não é erro de conteúdo: esperar resolve, e
                # abortar aqui jogaria fora as fichas já pagas desta execução.
                self.esperas_por_limite += 1
                espera = self._intervalo * (2**tentativa)
                self._proxima_chamada = time.monotonic() + espera
                continue
            # A Cohere aninha os tokens sob `usage.tokens`; sem preço na tabela
            # eles não viram dinheiro, mas o volume ainda é útil no relatório.
            self._somar_uso(getattr(getattr(resposta, "usage", None), "tokens", None))
            return _texto_da_resposta_cohere(resposta)
        raise LimiteDeTaxa(
            f"a chave da Cohere recusou {self.MAX_TENTATIVAS_429} tentativas seguidas "
            "por excesso de requisições"
        )


def _texto_da_resposta_cohere(resposta: Any) -> str:
    blocos = getattr(getattr(resposta, "message", None), "content", None) or []
    for bloco in blocos:
        texto = getattr(bloco, "text", None)
        if texto:
            return texto
    raise RespostaVazia("a Cohere respondeu sem bloco de texto")


# --- Anthropic -----------------------------------------------------------


class ProvedorAnthropic(Provedor):
    """Anthropic via Messages API, com saída estruturada e lote nativo."""

    nome = "anthropic"
    MODELO_PADRAO = "claude-haiku-4-5"
    VARIAVEL_CHAVE = "ANTHROPIC_API_KEY"

    def __init__(self, modelo: str | None = None, cliente: Any = None):
        self.modelo = modelo or self.MODELO_PADRAO
        self._cliente = cliente
        self.uso = Uso()

    def _obter_cliente(self) -> Any:
        if self._cliente is None:
            chave = os.environ.get(self.VARIAVEL_CHAVE, "").strip()
            if not chave:
                raise SemCredencial(
                    f"Defina {self.VARIAVEL_CHAVE} antes de enriquecer.\n"
                    "A chave é gerada em https://console.anthropic.com/settings/keys.\n"
                    "Guarde-a no .env do projeto, que não é versionado."
                )
            import anthropic

            self._cliente = anthropic.Anthropic(api_key=chave)
        return self._cliente

    def gerar(self, sistema: str, entrada: str, esquema: dict[str, Any]) -> str:
        resposta = self._obter_cliente().messages.create(
            model=self.modelo,
            max_tokens=2000,
            system=sistema,
            output_config={"format": {"type": "json_schema", "schema": esquema}},
            messages=[{"role": "user", "content": entrada}],
        )
        self._somar_uso(getattr(resposta, "usage", None))
        for bloco in resposta.content:
            if getattr(bloco, "type", None) == "text":
                return bloco.text
        raise RespostaVazia("a Anthropic respondeu sem bloco de texto")

    def suporta_lote(self) -> bool:
        return True

    def submeter_lote(self, itens: list[tuple[str, str]], sistema: str, esquema: dict) -> str:
        lote = self._obter_cliente().messages.batches.create(
            requests=[
                {
                    "custom_id": identificador,
                    "params": {
                        "model": self.modelo,
                        "max_tokens": 2000,
                        "system": sistema,
                        "output_config": {
                            "format": {"type": "json_schema", "schema": esquema}
                        },
                        "messages": [{"role": "user", "content": entrada}],
                    },
                }
                for identificador, entrada in itens
            ]
        )
        return lote.id

    def lote_concluido(self, lote_id: str) -> bool:
        lote = self._obter_cliente().messages.batches.retrieve(lote_id)
        return lote.processing_status == "ended"

    def resultados_lote(self, lote_id: str) -> Iterator[tuple[str, Optional[str]]]:
        for resultado in self._obter_cliente().messages.batches.results(lote_id):
            texto: Optional[str] = None
            if resultado.result.type == "succeeded":
                mensagem = resultado.result.message
                self._somar_uso(getattr(mensagem, "usage", None), em_lote=True)
                for bloco in mensagem.content:
                    if getattr(bloco, "type", None) == "text":
                        texto = bloco.text
                        break
            yield resultado.custom_id, texto


# --- seleção -------------------------------------------------------------

PROVEDORES: dict[str, type[Provedor]] = {
    ProvedorCohere.nome: ProvedorCohere,
    ProvedorAnthropic.nome: ProvedorAnthropic,
}

PROVEDOR_PADRAO = ProvedorCohere.nome


def criar_provedor(nome: str | None = None, modelo: str | None = None) -> Provedor:
    """Escolhe o provedor por nome, com `PROVEDOR` no ambiente como padrão."""
    escolhido = (nome or os.environ.get("PROVEDOR") or PROVEDOR_PADRAO).strip().lower()
    if escolhido not in PROVEDORES:
        conhecidos = ", ".join(sorted(PROVEDORES))
        raise ValueError(f"provedor desconhecido: {escolhido!r}. Conhecidos: {conhecidos}")
    return PROVEDORES[escolhido](modelo=modelo)
