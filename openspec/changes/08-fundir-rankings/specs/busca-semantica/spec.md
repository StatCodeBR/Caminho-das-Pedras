# Busca semântica

## MODIFIED Requirements

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

## ADDED Requirements

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
