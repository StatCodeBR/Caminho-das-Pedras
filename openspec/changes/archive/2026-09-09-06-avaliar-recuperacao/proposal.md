# Avaliar a qualidade da recuperação

## Por que

Sem medição, todas as decisões seguintes viram opinião. O enriquecimento
melhorou a busca ou só gastou dinheiro? Os embeddings acrescentam algo ao BM25?
A fusão de rankings ajuda ou atrapalha? Sem número, cada uma dessas perguntas se
resolve por intuição — e intuição sobre busca é notoriamente ruim.

Por isso esta mudança vem antes da busca semântica e da fusão, e não depois. Ela
estabelece a linha de base contra a qual as duas serão julgadas. Invertida a
ordem, você implementaria embeddings e nunca saberia se valeram a pena.

Há um segundo motivo, ligado ao concurso: um projeto que apresenta recall medido
sobre um conjunto de perguntas reais demonstra rigor que a maioria dos
concorrentes não terá.

## O que muda

- Conjunto de avaliação versionado com perguntas escritas em linguagem de
  cidadão e o conjunto esperado para cada uma.
- Métricas recall@5, recall@10 e MRR.
- Histórico de execuções, para comparar versões da recuperação.
- Detecção de regressão, com falha quando a queda excede o limiar.

## Fora de escopo

- Avaliação da qualidade do texto gerado, que é qualitativa e feita à mão.
- Métricas de latência e custo, tratadas na telemetria da mudança 09.

## Impacto

- Cria `avaliacao/perguntas.csv`, versionado no Git — é ativo de projeto, não
  artefato descartável.
- Toda mudança na recuperação passa a exigir execução da avaliação antes do
  arquivamento.
