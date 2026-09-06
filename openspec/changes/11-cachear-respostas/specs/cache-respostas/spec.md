# Cache de respostas

## ADDED Requirements

### Requirement: Reuso de resposta por equivalência semântica

A API SHALL comparar o embedding da pergunta com as perguntas já respondidas e
SHALL servir a resposta armazenada quando a similaridade exceder
`CACHE_LIMIAR_SIMILARIDADE`.

#### Scenario: pergunta reformulada

- **WHEN** a similaridade com uma pergunta em cache excede o limiar
- **THEN** a resposta armazenada é servida
- **AND** nenhuma chamada ao modelo é feita
- **AND** o campo de origem indica cache

#### Scenario: pergunta próxima porém distinta

- **WHEN** a similaridade fica abaixo do limiar
- **THEN** o fluxo normal de resposta é executado

#### Scenario: reuso do embedding da busca

- **WHEN** o cache é consultado
- **THEN** ele usa o embedding já calculado para a recuperação
- **AND** nenhum embedding adicional é gerado

### Requirement: Invalidação por versão do catálogo

O cache SHALL ser chaveado pela versão do `dados.db` e entradas de versões
anteriores NÃO SHALL ser servidas.

#### Scenario: novo catálogo publicado

- **WHEN** uma imagem com catálogo de versão diferente entra em produção
- **THEN** nenhuma resposta gerada sob o catálogo anterior é servida
- **AND** o cache volta a ser preenchido do zero

#### Scenario: versão exposta para diagnóstico

- **WHEN** o endpoint de saúde é consultado
- **THEN** ele informa a versão do catálogo em uso

### Requirement: Exclusão de respostas inadequadas ao cache

A API NÃO SHALL armazenar respostas de "não encontrei", respostas descartadas
pela guarda de ancoragem, nem respostas emitidas em modo reduzido.

#### Scenario: recuperação sem resultado

- **WHEN** a resposta informa que nada foi encontrado
- **THEN** ela não é armazenada no cache

#### Scenario: resposta descartada pela guarda

- **WHEN** a guarda de ancoragem descarta uma resposta
- **THEN** nada é armazenado no cache

#### Scenario: resposta em modo reduzido

- **WHEN** o serviço está em modo reduzido
- **THEN** as respostas produzidas não são armazenadas

### Requirement: Limite de tamanho do cache

O cache SHALL respeitar `CACHE_TAMANHO_MAXIMO` e SHALL descartar as entradas
mais antigas ao atingir o limite.

#### Scenario: limite atingido

- **WHEN** uma nova entrada é gravada com o cache cheio
- **THEN** a entrada mais antiga é removida
- **AND** o número de entradas permanece dentro do limite

### Requirement: Acerto de cache não consome orçamento

Acertos de cache NÃO SHALL incrementar o contador diário de chamadas ao modelo.

#### Scenario: resposta servida do cache

- **WHEN** uma resposta é servida do cache
- **THEN** o contador do teto diário permanece inalterado

#### Scenario: cache prolonga o modo pleno

- **WHEN** parte das perguntas do dia é atendida pelo cache
- **THEN** o serviço demora mais para atingir o teto diário
