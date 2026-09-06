# Saúde dos recursos

## ADDED Requirements

### Requirement: Verificação HTTP com degradação para GET

O verificador SHALL tentar `HEAD` e, quando o servidor responder 405 ou 501,
SHALL repetir com `GET` limitado por cabeçalho `Range`, sem baixar o arquivo
inteiro.

#### Scenario: servidor que aceita HEAD

- **WHEN** a URL responde 200 a um HEAD
- **THEN** o status registrado é 200
- **AND** nenhuma requisição adicional é feita

#### Scenario: servidor que rejeita HEAD

- **WHEN** a URL responde 405 a um HEAD
- **THEN** uma requisição GET com Range de poucos bytes é feita
- **AND** o status dessa segunda requisição é o registrado

#### Scenario: redirecionamento

- **WHEN** a URL responde 302 para outro endereço
- **THEN** o redirecionamento é seguido até o limite de 5 saltos
- **AND** o status final é o registrado

### Requirement: Classificação estável do estado

O verificador SHALL classificar cada recurso em `disponivel`, `indisponivel`,
`instavel` ou `nao_verificado`, e SHALL distinguir falha do servidor de falha
de tempo de resposta.

#### Scenario: recurso disponível

- **WHEN** o status final está entre 200 e 299
- **THEN** a classe é `disponivel`

#### Scenario: recurso removido

- **WHEN** o status final é 404 ou 410
- **THEN** a classe é `indisponivel`

#### Scenario: servidor lento ou intermitente

- **WHEN** a requisição excede 10 segundos ou retorna 5xx
- **THEN** a classe é `instavel`
- **AND** o recurso NÃO é tratado como removido

#### Scenario: recurso sem URL

- **WHEN** o recurso não possui URL
- **THEN** a classe é `nao_verificado`
- **AND** nenhuma requisição de rede é feita

### Requirement: Registro do momento da checagem

O verificador SHALL gravar `checado_em` em UTC e `latencia_ms` para cada
recurso verificado.

#### Scenario: carimbo sempre em UTC

- **WHEN** um recurso é verificado
- **THEN** `checado_em` está em UTC ISO 8601
- **AND** independe do fuso da máquina que executou o pipeline

### Requirement: Contenção de carga por host

O verificador SHALL limitar a 2 requisições simultâneas por host e a 20 no
total, e SHALL identificar-se por User-Agent com nome do projeto e contato.

#### Scenario: muitos recursos do mesmo órgão

- **WHEN** 500 recursos pertencem ao mesmo domínio
- **THEN** no máximo 2 requisições simultâneas atingem esse domínio
- **AND** outros domínios continuam sendo verificados em paralelo

#### Scenario: identificação do agente

- **WHEN** qualquer requisição é emitida
- **THEN** o cabeçalho User-Agent identifica o projeto e um endereço de contato

### Requirement: Reverificação seletiva

O verificador SHALL aceitar `--idade-maxima DIAS` e verificar apenas recursos
cuja última checagem seja mais antiga que o limite, e SHALL aceitar
`--somente-falhas` para reprocessar apenas os não disponíveis.

#### Scenario: execução incremental

- **WHEN** executado com `--idade-maxima 7`
- **THEN** recursos checados há menos de 7 dias são ignorados
- **AND** o log informa quantos foram pulados

#### Scenario: reprocessar apenas falhas

- **WHEN** executado com `--somente-falhas`
- **THEN** apenas recursos com classe `indisponivel` ou `instavel` são checados
