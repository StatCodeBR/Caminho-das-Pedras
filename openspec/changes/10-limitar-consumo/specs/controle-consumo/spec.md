# Controle de consumo

## ADDED Requirements

### Requirement: Teto diário de chamadas ao modelo

A API SHALL manter um contador diário de chamadas ao modelo e SHALL entrar em
modo reduzido ao atingir o teto configurado em `TETO_DIARIO_MODELO`.

#### Scenario: teto atingido

- **WHEN** o consumo do dia alcança o teto
- **THEN** as respostas seguintes são montadas por template
- **AND** nenhuma requisição resulta em erro por causa do teto
- **AND** a entrada em modo reduzido é registrada em log

#### Scenario: retorno ao modo pleno

- **WHEN** o dia vira em UTC
- **THEN** o contador reinicia
- **AND** o serviço volta ao modo pleno sem intervenção manual

#### Scenario: persistência entre reinícios

- **WHEN** o container é reiniciado no meio do dia
- **THEN** o consumo acumulado do dia é preservado
- **AND** o teto continua sendo respeitado

### Requirement: Modo reduzido útil e explicado

Em modo reduzido, a API SHALL continuar respondendo por recuperação e SHALL
informar o usuário, em linguagem simples, que a redação detalhada está
temporariamente indisponível.

#### Scenario: usuário em modo reduzido

- **WHEN** uma pergunta é feita durante o modo reduzido
- **THEN** a resposta apresenta os conjuntos encontrados com seus links
- **AND** informa que o detalhamento retorna no dia seguinte
- **AND** o campo de origem indica modo reduzido

#### Scenario: qualidade mínima preservada

- **WHEN** o modo reduzido está ativo
- **THEN** a recuperação continua operando integralmente
- **AND** a sinalização de recursos indisponíveis é mantida

### Requirement: Limite por origem sem exigir identificação

A API SHALL limitar requisições por endereço de origem em janela deslizante,
configurada por `LIMITE_ORIGEM_JANELA` e `LIMITE_ORIGEM_MAXIMO`, e NÃO SHALL
exigir cadastro, login ou chave de acesso para uso comum.

#### Scenario: uso humano normal

- **WHEN** um visitante faz até o máximo configurado dentro da janela
- **THEN** todas as perguntas são atendidas normalmente
- **AND** nenhuma identificação é solicitada

#### Scenario: uso automatizado

- **WHEN** uma origem excede o máximo dentro da janela
- **THEN** as requisições seguintes recebem 429
- **AND** o cabeçalho `Retry-After` informa quando tentar de novo

#### Scenario: acesso sem barreira

- **WHEN** um visitante acessa o serviço pela primeira vez
- **THEN** ele consegue fazer uma pergunta sem qualquer cadastro

### Requirement: Endereço de origem obtido através do proxy

A API SHALL determinar o endereço de origem a partir dos cabeçalhos
encaminhados pelo proxy reverso, e não do socket da conexão.

#### Scenario: serviço atrás do Traefik

- **WHEN** a requisição chega pelo proxy reverso
- **THEN** o endereço considerado é o do cliente original
- **AND** não o endereço interno do proxy

#### Scenario: cabeçalho ausente

- **WHEN** nenhum cabeçalho de encaminhamento está presente
- **THEN** o endereço do socket é usado como alternativa

### Requirement: Visibilidade operacional do consumo

A API SHALL expor um endpoint interno com o consumo do dia, o teto configurado
e o modo corrente.

#### Scenario: consulta de operação

- **WHEN** o endpoint interno é consultado
- **THEN** retorna consumo do dia, teto e se o modo reduzido está ativo

#### Scenario: endpoint não exposto publicamente

- **WHEN** o serviço está publicado
- **THEN** o endpoint de operação não é acessível pelo domínio público
