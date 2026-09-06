# Busca léxica

## ADDED Requirements

### Requirement: Índice de texto completo sobre as fichas

O pipeline SHALL manter uma tabela virtual FTS5 indexando nome, perguntas de
exemplo, resumo, órgão e tags de cada ficha em colunas distintas.

#### Scenario: índice construído a partir das fichas

- **WHEN** a indexação é executada após o enriquecimento
- **THEN** existe uma entrada no índice para cada ficha do catálogo
- **AND** nenhuma chamada a modelo de linguagem é feita

#### Scenario: reconstrução idempotente

- **WHEN** a indexação é executada duas vezes seguidas
- **THEN** o índice anterior é descartado e reconstruído
- **AND** as mesmas consultas retornam os mesmos resultados

### Requirement: Insensibilidade a acento e caixa

A busca SHALL usar tokenização que remova diacríticos, de modo que a grafia com
ou sem acento produza os mesmos resultados.

#### Scenario: consulta sem acento

- **WHEN** o usuário busca por `saude`
- **THEN** fichas contendo `saúde` são recuperadas

#### Scenario: consulta com acento

- **WHEN** o usuário busca por `SAÚDE`
- **THEN** fichas contendo `saude` são recuperadas

### Requirement: Ordenação por relevância com ponderação por campo

A busca SHALL ordenar por BM25 com pesos configuráveis por coluna, atribuindo
maior peso a perguntas de exemplo e ao nome do conjunto.

#### Scenario: termo presente em pergunta de exemplo

- **WHEN** o termo consultado aparece em uma pergunta de exemplo de um conjunto
- **AND** aparece apenas no resumo de outro
- **THEN** o primeiro é classificado acima do segundo

#### Scenario: pesos configuráveis

- **WHEN** os pesos por coluna são alterados na configuração
- **THEN** a ordenação passa a refletir os novos pesos sem alteração de código

### Requirement: Despriorização de fichas de baixa confiança

A busca SHALL aplicar penalização às fichas marcadas com confiança baixa,
mantendo-as recuperáveis mas abaixo de fichas equivalentes de maior confiança.

#### Scenario: empate entre confianças diferentes

- **WHEN** duas fichas têm pontuação bruta semelhante
- **AND** uma tem confiança alta e a outra baixa
- **THEN** a de confiança alta é classificada acima

#### Scenario: ficha de baixa confiança ainda recuperável

- **WHEN** apenas fichas de confiança baixa correspondem à consulta
- **THEN** elas são retornadas normalmente

### Requirement: Entrada do usuário tratada como texto, não como sintaxe

A busca SHALL escapar a consulta do usuário de modo que caracteres com
significado sintático no FTS5 não provoquem erro nem alterem o comportamento.

#### Scenario: aspas na consulta

- **WHEN** a consulta contém aspas desbalanceadas
- **THEN** a busca é executada tratando-as como texto literal
- **AND** nenhum erro é retornado

#### Scenario: operadores digitados por engano

- **WHEN** a consulta contém termos como `AND`, `OR`, `NEAR` ou asteriscos
- **THEN** eles são tratados como texto comum

#### Scenario: consulta vazia

- **WHEN** a consulta é vazia ou só contém espaços
- **THEN** nenhum resultado é retornado
- **AND** nenhum erro é gerado

### Requirement: Resultado com posição e pontuação explícitas

A busca SHALL retornar, para cada resultado, o identificador do conjunto, a
posição no ranking e a pontuação, para permitir fusão e avaliação posteriores.

#### Scenario: consumo pela fusão

- **WHEN** a fusão de rankings solicita os resultados léxicos
- **THEN** cada item traz identificador, posição e pontuação

#### Scenario: inspeção durante desenvolvimento

- **WHEN** a busca é executada pela linha de comando
- **THEN** os dez primeiros são exibidos com pontuação e termos casados
