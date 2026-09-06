# Resposta ancorada

## ADDED Requirements

### Requirement: Ancoragem estrita nas fichas recuperadas

A API SHALL compor a resposta exclusivamente a partir das fichas enviadas ao
modelo e SHALL descartar qualquer resposta que cite URL ausente desse conjunto.

#### Scenario: URL fabricada

- **WHEN** o texto gerado contém uma URL que não está entre as fichas enviadas
- **THEN** a resposta é descartada antes de chegar ao usuário
- **AND** o usuário recebe mensagem de indisponibilidade temporária
- **AND** o evento é registrado em log com a pergunta e a URL fabricada

#### Scenario: conjunto não presente no contexto

- **WHEN** o texto gerado menciona um conjunto que não foi recuperado
- **THEN** a resposta é descartada
- **AND** o evento é registrado em log

#### Scenario: nenhuma ficha relevante

- **WHEN** a recuperação não retorna conjunto pertinente
- **THEN** a resposta declara que nada foi encontrado
- **AND** sugere termos alternativos de busca
- **AND** nenhum conjunto de dados é mencionado

### Requirement: Resposta determinística quando a recuperação é conclusiva

A API SHALL responder sem chamar modelo de linguagem quando o primeiro
resultado superar o limiar de pontuação configurado e a margem sobre o segundo
colocado exceder o mínimo configurado.

#### Scenario: correspondência direta

- **WHEN** o primeiro resultado está acima do limiar
- **AND** a margem sobre o segundo excede o mínimo
- **THEN** a resposta é montada por template a partir da ficha
- **AND** nenhum token é consumido
- **AND** a resposta declara que foi obtida por correspondência direta

#### Scenario: recuperação ambígua

- **WHEN** os primeiros resultados têm pontuações próximas
- **THEN** o modelo é acionado para redigir a resposta

#### Scenario: limiares configuráveis

- **WHEN** as variáveis de limiar e margem são alteradas
- **THEN** o roteamento passa a usar os novos valores sem alteração de código

### Requirement: Transparência sobre a origem da resposta

Toda resposta SHALL declarar como foi produzida, entre correspondência direta,
redação por modelo ou modo reduzido.

#### Scenario: origem informada ao usuário

- **WHEN** qualquer resposta é entregue
- **THEN** o evento SSE final contém o campo de origem
- **AND** a interface pode exibi-lo ao usuário

#### Scenario: origem registrada em telemetria

- **WHEN** qualquer resposta é entregue
- **THEN** origem, latência e número de fichas recuperadas são registrados

### Requirement: Sinalização de recursos indisponíveis

A API SHALL incluir recursos com link indisponível na resposta, marcados como
tal, em vez de omiti-los, e SHALL sempre oferecer o link da página do conjunto
no portal.

#### Scenario: conjunto com recurso removido

- **WHEN** um conjunto recuperado tem recursos classificados como indisponivel
- **THEN** esses recursos aparecem marcados como indisponíveis
- **AND** o link para a página do conjunto no dados.gov.br é apresentado

#### Scenario: preferência por recursos disponíveis

- **WHEN** um conjunto possui recursos disponíveis e indisponíveis
- **THEN** os disponíveis são apresentados primeiro

### Requirement: Entrega por streaming em canal único

A API SHALL entregar todas as respostas por `text/event-stream`, inclusive as
montadas por template, para que a interface tenha um único caminho de
renderização.

#### Scenario: resposta por template

- **WHEN** a resposta é montada por template
- **THEN** ela é transmitida pelo mesmo canal SSE da resposta gerada

#### Scenario: cabeçalhos contra bufferização

- **WHEN** a resposta é iniciada
- **THEN** são enviados `cache-control: no-cache` e `x-accel-buffering: no`

### Requirement: Modo stub sem consumo de API

A API SHALL, quando `MODO_STUB=1`, emitir resposta pré-gravada token a token,
sem qualquer chamada à Anthropic.

#### Scenario: desenvolvimento de interface

- **WHEN** o serviço roda com `MODO_STUB=1`
- **THEN** as respostas são pré-gravadas
- **AND** nenhuma credencial da Anthropic é exigida para iniciar o serviço

#### Scenario: emissão gradual

- **WHEN** o stub responde
- **THEN** os fragmentos são emitidos com intervalo, simulando geração real
