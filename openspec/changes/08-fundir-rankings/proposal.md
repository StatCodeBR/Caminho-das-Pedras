# Fundir os rankings léxico e semântico

## Por que

As duas buscas erram em lugares diferentes. O BM25 acerta sigla, nome de órgão e
termo técnico exato, e falha quando o vocabulário do usuário não coincide com o
do catálogo. O embedding faz o oposto: aproxima significados e se atrapalha com
identificadores literais.

Usar apenas uma delas significa aceitar de graça a fraqueza correspondente. A
fusão aproveita a complementaridade.

O problema é que as duas produzem pontuações em escalas incomparáveis: BM25 não
tem limite superior e depende do corpus, similaridade de cosseno vive entre menos
um e um. Somar isso com pesos exige calibração frágil, que precisaria ser
refeita a cada mudança no catálogo. A fusão por posição no ranking evita esse
problema inteiro.

## O que muda

- Execução das duas buscas em paralelo, com profundidade configurável.
- Fusão por Reciprocal Rank Fusion.
- Proveniência de cada resultado: de qual ranking veio e em que posição.
- Comparação obrigatória contra a linha de base da mudança 06.

## Fora de escopo

- Reordenação por modelo de linguagem, adiada até haver evidência de que o
  ganho compensa a latência e o custo.
- Ajuste automático de parâmetros.

## Impacto

- Passa a ser o ponto único de entrada da recuperação, consumido pelas mudanças
  09 e seguintes.
- Introduz `RRF_K` e `PROFUNDIDADE_BUSCA` como parâmetros configuráveis.
