# Busca semântica

## Purpose

Encontrar o conjunto certo quando a pessoa e o catálogo usam palavras diferentes
para a mesma coisa — "remédio de graça" contra "assistência farmacêutica",
"creche" contra "educação infantil". É complemento da busca léxica, não seu
substituto: perde para ela em sigla, nome próprio e termo exato, e acerta
justamente onde ela erra. As duas convivem, e a fusão as combina.

Os vetores são gerados offline, no pipeline, sobre o texto indexável das fichas.
O serviço de consulta só vetoriza a pergunta, com um runtime leve verificado como
equivalente ao de geração.

## Requirements

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

O serviço de consulta SHALL recusar-se a iniciar quando os vetores estiverem
ausentes, quando o número de vetores não corresponder ao número de fichas,
quando os artefatos forem de versões diferentes, ou quando os vetores tiverem
sido gerados por um modelo diferente do usado para vetorizar a consulta.

A busca semântica SHALL estar ativa sempre que o serviço estiver em operação. A
fusão de rankings depende dela: um serviço que subisse sem ela responderia só
com a busca léxica, no mesmo formato, sem sinal nenhum de que metade da
recuperação sumiu — a degradação que a fusão existe para evitar, tornada
invisível. A opcionalidade que vigorou até a fusão existia porque nenhuma
resposta usava a busca semântica; com a fusão, toda resposta usa.

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
- **THEN** o serviço não inicia
- **AND** a mensagem indica que a busca semântica é obrigatória e que os vetores
      não foram encontrados

#### Scenario: estado informado na verificação de saúde

- **WHEN** o serviço está em operação
- **THEN** a verificação de saúde informa a busca semântica ativa, com o número
      de vetores carregados e o modelo que os gerou

### Requirement: Resultado no mesmo formato da busca léxica

A busca semântica SHALL retornar identificador, posição e pontuação, no mesmo
formato da busca léxica, para permitir fusão posterior.

#### Scenario: consumo pela fusão

- **WHEN** a fusão de rankings solicita os resultados semânticos
- **THEN** cada item traz identificador, posição e pontuação

### Requirement: Consulta semântica sem dependência externa em tempo de resposta

O serviço SHALL conter, desde a construção da imagem, o runtime e o modelo
usados para vetorizar a pergunta, e NÃO SHALL baixar modelo nem acessar serviço
externo para vetorizar uma consulta.

O modelo SHALL ser o mesmo cuja equivalência com o runtime de geração foi
verificada pelo teste de paridade.

Baixar o modelo na primeira pergunta faria a resposta depender da
disponibilidade de um terceiro, custaria dezenas de segundos à primeira consulta
de cada container e colocaria em produção um arquivo que o build nunca viu.

#### Scenario: primeira consulta após a subida

- **WHEN** a primeira pergunta chega a um serviço recém-iniciado
- **THEN** ela é vetorizada sem acesso à rede externa

#### Scenario: runtime ausente

- **WHEN** os vetores estão presentes mas o runtime da consulta semântica não
      está disponível
- **THEN** o serviço não inicia

#### Scenario: modelo ausente

- **WHEN** o modelo de consulta não está presente na imagem
- **THEN** o serviço não inicia
