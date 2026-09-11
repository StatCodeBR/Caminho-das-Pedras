"""Configuração do serviço, lida do ambiente.

Os limiares de roteamento moram aqui porque só a avaliação diz onde eles devem
ficar, e mudar de opinião não pode exigir alteração de código.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent
BANCO_PADRAO = RAIZ.parent / "pipeline" / "dados" / "dados.db"
VETORES_PADRAO = RAIZ.parent / "pipeline" / "dados" / "vectors.npy"


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    banco: Path = BANCO_PADRAO

    # Vetores da busca semântica; a lista de identificadores mora ao lado, com
    # o mesmo nome e extensão `.json`. Opcionais até a fusão (mudança 08): sem
    # eles o serviço sobe com a semântica desligada e diz isso no /saude.
    # Presentes e inconsistentes com o banco, o serviço não sobe — vetor de outra
    # versão do catálogo apontaria para o conjunto errado sem sintoma nenhum.
    vetores: Path = VETORES_PADRAO
    modo_stub: bool = False
    anthropic_api_key: str = ""
    modelo: str = "claude-haiku-4-5"

    # Quantas fichas entram no contexto do modelo. Poucas o bastante para o
    # prompt caber e caro não ficar; muitas o bastante para a resposta certa
    # estar entre elas — a avaliação mostrou recall@5 igual a recall@10, então
    # olhar além do quinto não acrescenta nada.
    fichas_no_contexto: int = 5

    # Roteamento entre template e modelo. Deliberadamente conservadores: a
    # avaliação mediu MRR 0,133 nas perguntas difíceis, ou seja, acertar fora do
    # primeiro lugar é comum. Servir template para pergunta ambígua entrega uma
    # resposta confiante e errada; gastar token à toa custa centavos.
    #
    # O limiar é 20 e não 18 por medição, não por gosto: com 18, a pergunta
    # "quanto ganha um professor em média no Brasil" — que o catálogo não
    # responde — saía por template, apresentando `indicadores-educacionais` (19,18)
    # como se fosse a resposta. A pontuação léxica não distingue "é do assunto"
    # de "responde à pergunta"; só o modelo faz isso. Com 20, sobram as duas
    # correspondências de fato inequívocas das 14 perguntas.
    #
    # Calibrado sobre n=14: revisar quando o conjunto de avaliação crescer.
    limiar_template: float = 20.0
    margem_template: float = 2.0

    # Abaixo disto a recuperação não sustenta resposta nenhuma e o serviço diz
    # que não encontrou, em vez de redigir sobre fichas que não vêm ao caso.
    limiar_relevancia: float = 3.0

    # Estado gravável da contenção. Separado do dados.db, que é somente leitura
    # por decisão da mudança 09 e não pode virar gravável para isto.
    estado_dir: Path = RAIZ / "estado"

    # Teto global de chamadas ao modelo por dia UTC. Ao estourar, o serviço
    # responde por template — nunca com erro.
    teto_diario_modelo: int = 400

    # Limite por endereço, em janela deslizante. Ao estourar, 429: quem faz
    # vinte perguntas numa hora não é visitante, é script.
    limite_origem_maximo: int = 20
    limite_origem_janela: int = 3600


@lru_cache
def configuracao() -> Configuracao:
    return Configuracao()
