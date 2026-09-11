# Busca léxica

## MODIFIED Requirements

### Requirement: Termos comuns demais não sustentam resultado

A busca SHALL descartar da consulta os termos que aparecem em fração excessiva
do índice, medida no próprio corpus, de modo que uma pergunta cujo assunto não
existe no catálogo retorne vazio em vez de um ranking sustentado por palavras
de ligação.

A frequência SHALL ser medida apenas sobre as colunas de texto natural — nome,
perguntas de exemplo, resumo e órgão. A coluna de tags SHALL ser excluída desse
cálculo, permanecendo indexada, buscável e ponderada no BM25.

A regra existe por evidência. Como os termos são unidos por OR, a pergunta
"onde acho dados sobre creche" — sem nenhuma ficha sobre creche no catálogo —
devolvia dez conjuntos com aparência de resposta, casando apenas em `onde`,
`sobre` e `dados`. Devolver o assunto errado com confiança é pior do que
devolver nada, e envenenaria a avaliação de recuperação, que passaria a medir
ruído em vez de acerto.

O corte é relativo ao corpus, não uma lista fixa de palavras: o que é vazio
neste catálogo (`dados`, `qual`, `registro`) não coincide com uma lista de
stopwords do português, e muda conforme o catálogo cresce.

A exclusão da coluna de tags tem causa medida. Ali a indexação escreve os
rótulos do vocabulário controlado de temas, e a frequência passa a refletir a
classificação do próprio sistema em vez do uso da língua: no catálogo completo,
`financas` aparece em 40,2% das fichas com **100%** dessas ocorrências vindas de
tags, e `economia` em 40,5% com **99%**. O mesmo vale para `publicas` (41,5%,
97%), `administracao` (24,4%, 99%), `educacao` (15,7%, 87%) e `tecnologia`
(17,2%, 78%). São todas palavras de assunto — o que o cidadão digita — elevadas
acima do corte por um artefato de rotulagem. O efeito contraria o propósito do
enriquecimento: quanto melhor um tema é classificado, mais o filtro proibiria
buscar por ele.

Recalibrar o limiar não substitui esta correção. A varredura de 0,10 a 0,50
sobre o conjunto de avaliação não apresenta joelho — de 0,15 a 0,50 ganham-se 7
termos úteis ao custo de 28 termos de ruído, em progressão sem ponto de
inflexão. Distribuição sem vão não se conserta movendo a linha de corte.

#### Scenario: assunto ausente do catálogo

- **WHEN** a consulta contém um termo de assunto que não existe no índice
- **AND** os demais termos são palavras comuns a quase todas as fichas
- **THEN** nenhum resultado é retornado

#### Scenario: termo raro sobrevive ao descarte

- **WHEN** a consulta mistura palavras comuns e um termo de assunto raro
- **THEN** o descarte remove apenas as comuns
- **AND** os conjuntos que casam o termo raro são retornados

#### Scenario: consulta só de termos comuns

- **WHEN** todos os termos da consulta são comuns demais
- **THEN** os menos comuns são preservados
- **AND** a busca ainda retorna resultados

#### Scenario: índice pequeno demais para medir frequência

- **WHEN** o índice tem menos fichas que o mínimo configurado
- **THEN** nenhum termo é descartado
- **AND** a consulta é executada com todos os termos

#### Scenario: rótulo de tema não torna o termo comum

- **WHEN** um termo aparece na coluna de tags de grande parte das fichas
- **AND** aparece em poucas fichas nas colunas de texto natural
- **THEN** ele não é descartado como termo comum

#### Scenario: tag continua recuperando

- **WHEN** a consulta usa um termo que só aparece na coluna de tags de uma ficha
- **THEN** essa ficha é retornada
- **AND** o casamento é atribuído à coluna de tags
