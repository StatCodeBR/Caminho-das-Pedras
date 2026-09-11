# Busca semântica

## ADDED Requirements

### Requirement: Vetores gerados para todas as fichas

O pipeline SHALL gerar um vetor para o texto indexável de cada ficha e SHALL
persistir os vetores junto de uma lista de identificadores na mesma ordem.

#### Scenario: geração completa

- **WHEN** a indexação semântica é executada
- **THEN** existe exatamente um vetor por ficha do catálogo
- **AND** a lista de identificadores tem o mesmo comprimento

#### Scenario: regeneração conjunta

- **WHEN** os vetores são regenerados
- **THEN** a lista de identificadores é regravada na mesma execução
- **AND** os dois artefatos correspondem à mesma versão do banco

### Requirement: Prefixos aplicados pelo próprio módulo

O módulo de embedding SHALL aplicar internamente o prefixo de documento na
indexação e o de consulta na busca, sem depender de quem o chama.

#### Scenario: indexação

- **WHEN** o texto de uma ficha é vetorizado para o índice
- **THEN** o prefixo de documento é aplicado pelo módulo

#### Scenario: consulta

- **WHEN** a pergunta do usuário é vetorizada
- **THEN** o prefixo de consulta é aplicado pelo módulo

#### Scenario: impossibilidade de omissão

- **WHEN** a interface pública do módulo é utilizada
- **THEN** não existe caminho que gere embedding sem prefixo

### Requirement: Vetores normalizados para produto escalar

Os vetores SHALL ser normalizados para norma unitária na geração, de modo que a
similaridade de cosseno seja obtida por produto escalar.

#### Scenario: norma dos vetores gravados

- **WHEN** os vetores são carregados
- **THEN** a norma de cada um é 1 dentro da tolerância numérica

#### Scenario: cálculo da similaridade

- **WHEN** a busca semântica é executada
- **THEN** a pontuação é o produto escalar entre consulta e candidatos
- **AND** nenhuma divisão por norma é feita em tempo de consulta

### Requirement: Equivalência entre os runtimes de geração e consulta

O projeto SHALL verificar que o runtime usado no pipeline e o usado na consulta
produzem vetores equivalentes para o mesmo texto.

#### Scenario: verificação de paridade

- **WHEN** o teste de paridade é executado sobre um texto de referência
- **THEN** a similaridade entre os dois vetores é superior a 0,999

#### Scenario: divergência detectada

- **WHEN** a similaridade fica abaixo do limiar
- **THEN** o teste falha
- **AND** nenhuma publicação de catálogo prossegue

### Requirement: Consistência entre vetores e banco

O serviço de consulta SHALL recusar-se a iniciar quando o número de vetores não
corresponder ao número de fichas ou quando os artefatos forem de versões
diferentes.

Até que a fusão de rankings passe a consumir a busca semântica, os vetores SHALL
ser opcionais no serviço: ausentes, ele inicia com a busca semântica desligada e
informa esse estado na verificação de saúde. A recusa vale para vetores
presentes e inconsistentes. Ausência não é inconsistência, e derrubar o serviço
por uma capacidade que nenhuma resposta usa ainda trocaria disponibilidade por
nada.

#### Scenario: contagem divergente

- **WHEN** o número de vetores difere do número de fichas
- **THEN** o serviço não inicia
- **AND** a mensagem indica a inconsistência

#### Scenario: artefatos de versões diferentes

- **WHEN** vetores e banco declaram versões distintas do catálogo
- **THEN** o serviço não inicia

#### Scenario: vetores de outro modelo

- **WHEN** os vetores declaram um modelo diferente do usado para vetorizar a
      consulta
- **THEN** o serviço não inicia

#### Scenario: vetores ausentes

- **WHEN** o serviço inicia sem os arquivos de vetores
- **THEN** ele inicia normalmente, com a busca semântica desligada
- **AND** a verificação de saúde informa que a busca semântica está desligada

### Requirement: Resultado no mesmo formato da busca léxica

A busca semântica SHALL retornar identificador, posição e pontuação, no mesmo
formato da busca léxica, para permitir fusão posterior.

#### Scenario: consumo pela fusão

- **WHEN** a fusão de rankings solicita os resultados semânticos
- **THEN** cada item traz identificador, posição e pontuação
