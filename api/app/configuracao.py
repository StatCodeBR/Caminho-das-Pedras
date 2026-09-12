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
    # O limiar era 20, medido sobre as 505 fichas da amostra. No catálogo
    # completo essa calibração deixou de valer: as pontuações do BM25 subiram,
    # mais conjuntos ultrapassam 20, e o template passou a disparar sobre
    # casamento acidental — "minha cidade já teve enchente registrada" era
    # respondida, sem chamar o modelo, com um conjunto de depósitos de patentes
    # por cidade, que casou em "cidade".
    #
    # Remedido sobre as 19.958 fichas, e o resultado é que nenhum limiar serve:
    #
    #   limiar  templates  certos  errados
    #     20        5         2       3
    #     25        2         1       1
    #     30        1         0       1
    #     35        0         0       0
    #
    # A pontuação não separa certo de errado. Os acertos vão de 18,2 a 29,7 e os
    # erros de 14,6 a 33,0 — a maior pontuação de todas as catorze é um erro. A
    # margem sobre o segundo também não separa. Não há corte que preserve os
    # acertos e elimine os erros.
    #
    # Por isso 35: acima de qualquer pontuação observada, o que desliga o caminho
    # do template neste catálogo. É a escolha que a regra do projeto impõe —
    # resposta confiante e errada custa confiança, token à toa custa centavos.
    # Baixar para 25 devolve o template com 50% de precisão, e é decisão de quem
    # opera, não deste arquivo.
    limiar_template: float = 35.0
    margem_template: float = 2.0

    # Abaixo disto a recuperação não sustenta resposta nenhuma e o serviço diz
    # que não encontrou, em vez de redigir sobre fichas que não vêm ao caso.
    #
    # Era 3,0, e no catálogo completo isso nunca disparava: a única pergunta de
    # avaliação sem resposta — "quantos professores tem no Brasil" — ia ao
    # modelo, que gastava token para dizer que não encontrou. Com 12 ela sai por
    # ausência, sem custo, e nenhuma outra das catorze é afetada.
    #
    # Ressalva honesta: 12 foi escolhido para excluir uma pontuação observada de
    # 11,7, num único caso. É calibração sobre n=1 dentro de n=14, e a primeira
    # coisa a revisar quando o conjunto de avaliação crescer.
    limiar_relevancia: float = 12.0

    # Fusão dos rankings. `k` é o valor consagrado do RRF: grande demais achata
    # as contribuições e aproxima a fusão de uma votação simples, pequeno demais
    # faz o primeiro lugar de cada ranking dominar. A profundidade é quantos
    # candidatos pedir a cada ranking antes de fundir, maior que o retorno de
    # propósito — truncar cedo elimina o conjunto que aparece em décimo nos dois,
    # que é o que a fusão existe para encontrar.
    rrf_k: float = 60.0
    # Medida, não convencionada: com 50 o recall@5 da fusão cai para 64,3% e com
    # 10 sobe para 78,6%, porque dois lugares medianos somam mais que um primeiro
    # lugar isolado. Ver pipeline/fusao.py, que traz a tabela inteira.
    profundidade_busca: int = 10

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
