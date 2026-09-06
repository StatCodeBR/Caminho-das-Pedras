# Design — avaliação da recuperação

## Decisão: perguntas escritas como o cidadão escreveria

A tentação é gerar as perguntas a partir dos títulos dos conjuntos. Isso
produziria um conjunto de avaliação fácil e inútil, que mede a capacidade do
sistema de casar texto com ele mesmo.

As perguntas precisam vir do vocabulário de quem não conhece o catálogo:
"quantos leitos tem no hospital da minha cidade", não "estabelecimentos de saúde
por município". A distância entre as duas formulações é exatamente o problema
que o projeto resolve, e é ela que a avaliação precisa medir.

Consequência prática: as perguntas são escritas à mão. É trabalho chato de uma
tarde e é o investimento de maior retorno do projeto inteiro.

## Decisão: recall como métrica principal

O que importa é se o conjunto certo chega ao contexto do modelo. Se ele está
entre os cinco primeiros, a resposta pode ser boa; se não está, nenhuma redação
salva. Por isso recall@5 é a métrica que dirige decisões.

MRR entra como métrica secundária, porque distingue o sistema que coloca o
resultado certo em primeiro daquele que o coloca em quinto — diferença que
importa para o roteamento entre template e modelo da mudança 09.

Precisão não é medida: com apenas um conjunto correto anotado por pergunta, ela
seria mecânica e pouco informativa.

## Decisão: múltiplos conjuntos aceitáveis por pergunta

Algumas perguntas são legitimamente respondidas por mais de um conjunto. O
formato permite listar vários identificadores aceitáveis, e o acerto ocorre
quando qualquer um deles aparece. Forçar resposta única penalizaria o sistema por
acertos verdadeiros.

## Decisão: falhar diante de regressão

A avaliação retorna código diferente de zero quando o recall cai além do limiar
configurado em relação à última execução registrada. Assim uma alteração
aparentemente inofensiva no prompt de enriquecimento ou nos pesos do BM25 não
degrada a busca silenciosamente.

## Riscos aceitos

Cinquenta perguntas é pouco para significância estatística, e o conjunto reflete
o viés de quem o escreveu. É melhor que nada por uma margem enorme, e o formato
permite crescer. Mitigação parcial: distribuir as perguntas entre temas e níveis
de dificuldade, registrando essa classificação em coluna própria.
