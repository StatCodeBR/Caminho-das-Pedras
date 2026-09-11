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
- Distribuição da busca semântica em produção, pendente da mudança 07: vetores
  publicados como asset da release, com soma própria no manifesto; runtime e
  modelo de consulta dentro da imagem; o serviço passa a exigir a busca
  semântica ativa em vez de operar sem ela.

## Fora de escopo

- Reordenação por modelo de linguagem, adiada até haver evidência de que o
  ganho compensa a latência e o custo.
- Ajuste automático de parâmetros.

## Impacto

- Passa a ser o ponto único de entrada da recuperação, consumido pelas mudanças
  09 e seguintes.
- Introduz `RRF_K` e `PROFUNDIDADE_BUSCA` como parâmetros configuráveis.
- Modifica as capacidades `busca-semantica`, cujos vetores deixam de ser
  opcionais, e `distribuicao-do-catalogo`, cujo catálogo passa a ter dois assets.
- A imagem da api cresce de 472 MB para cerca de 1,1 GB: runtime de consulta
  (~120 MB), modelo ONNX (470 MB) e vetores (31 MB).
- O build da imagem passa a depender também do Hugging Face, de onde o modelo
  é baixado.
- **BREAKING** para o deploy: sem vetores publicados na release declarada, a
  imagem não se constrói, e sem a semântica ativa o serviço não sobe.
