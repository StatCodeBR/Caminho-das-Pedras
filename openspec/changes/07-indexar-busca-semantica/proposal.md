# Indexar o catálogo para busca semântica

## Por que

A busca léxica falha quando o usuário e o catálogo usam palavras diferentes para
a mesma coisa. Quem pergunta sobre "remédio de graça" não digita "assistência
farmacêutica"; quem procura "creche" não digita "educação infantil". O
enriquecimento da mudança 04 reduziu esse abismo ao gerar perguntas de exemplo,
mas não o eliminou: as variações possíveis são infinitas e as geradas são poucas.

Embeddings resolvem a parte restante ao aproximar significados em vez de
palavras. Eles não substituem o BM25 — perdem para ele em sigla, nome próprio e
termo exato — mas cobrem justamente onde ele erra. Por isso os dois convivem, e
a fusão vem na mudança seguinte.

A linha de base já está medida pela mudança 06. Esta mudança precisa provar seu
valor contra ela.

## O que muda

- Geração de vetores para o texto indexável de cada ficha, no pipeline.
- Persistência dos vetores em arquivo binário alinhado à ordem dos
  identificadores.
- Busca por similaridade de cosseno em memória.
- Teste de paridade entre o runtime de geração e o de consulta.

## Fora de escopo

- Fusão com a busca léxica (mudança 08).
- Reordenação por modelo, deliberadamente adiada.

## Impacto

- Introduz o modelo de embedding como artefato distribuído junto do catálogo.
- O pipeline passa a depender de sentence-transformers; o serviço de consulta,
  de um runtime ONNX leve. São bibliotecas diferentes para o mesmo modelo, o que
  exige verificação de equivalência.
