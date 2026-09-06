# Indexar o catálogo para busca léxica

## Por que

Com as fichas enriquecidas prontas, o sistema precisa encontrá-las. A busca
léxica é o primeiro degrau e, para metadados curtos em português, ela é
surpreendentemente difícil de superar: quando o usuário digita o nome de um
órgão, uma sigla ou um termo técnico exato, BM25 acerta onde a busca semântica
hesita.

Esta é também a mudança que torna o projeto demonstrável pela primeira vez.
Depois dela existe algo que responde a uma pergunta, ainda que por linha de
comando. Se todo o resto falhar, há produto.

O índice se apoia no `texto_indexavel` derivado na mudança 04, que já reúne
nome, resumo em linguagem simples, perguntas de exemplo, órgão e tags. É esse
texto que fecha a distância entre o vocabulário do cidadão e o do catálogo.

## O que muda

- Nova tabela virtual FTS5 sobre o texto indexável das fichas.
- Ponderação por campo, priorizando perguntas de exemplo e nome do conjunto.
- Despriorização de fichas de confiança baixa.
- Comando de busca por linha de comando, para inspeção durante o
  desenvolvimento.

## Fora de escopo

- Busca semântica (mudança 07) e fusão de rankings (mudança 08).
- Qualquer geração de texto em tempo de consulta.

## Impacto

- Acrescenta a tabela virtual ao `dados.db`, aumentando seu tamanho.
- A reconstrução do índice passa a ser etapa obrigatória após enriquecimento.
