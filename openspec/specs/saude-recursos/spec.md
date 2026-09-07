# Saúde dos recursos

## Purpose

Saber quais links do catálogo realmente abrem, para que a resposta ao usuário
nunca aponte para um arquivo removido. O portal registra o endereço declarado
pelo órgão publicador e não o verifica; sem essa etapa, o sistema herdaria links
mortos e os apresentaria como se fossem bons.

A verificação também alimenta o diagnóstico de qualidade do catálogo: distinguir
link ausente de link malformado, e servidor fora do ar de arquivo apagado, é o
que permite cobrar do órgão certo — ou apenas esperar.

## Requirements

### Requirement: Verificação HTTP com degradação para GET

O verificador SHALL tentar `HEAD` e, quando o servidor recusar o método,
SHALL repetir com `GET` limitado por cabeçalho `Range`, sem ler o corpo da
resposta. Recusa de método inclui 405 e 501, mas também **403**.

O 403 está nessa lista por evidência, não por precaução: o `www.gov.br` — o
host com mais recursos no catálogo — responde 403 a `HEAD` e 206 ao mesmo
endereço via `GET` com `Range`, com qualquer User-Agent e também sem nenhum
(verificado em 2026-09-07). Tratar esse 403 como acesso negado marcaria como
link morto centenas de arquivos intactos. **Não remova o 403 desta lista sem
antes reverificar esse comportamento.**

#### Scenario: servidor que aceita HEAD

- **WHEN** a URL responde 200 a um HEAD
- **THEN** o status registrado é 200
- **AND** nenhuma requisição adicional é feita

#### Scenario: servidor que rejeita HEAD

- **WHEN** a URL responde 405, 501 ou 403 a um HEAD
- **THEN** uma requisição GET com Range de poucos bytes é feita
- **AND** o status dessa segunda requisição é o registrado

#### Scenario: recusa de método não é arquivo removido

- **WHEN** o HEAD responde 403 e o GET com Range responde 206
- **THEN** a classe é `disponivel`
- **AND** o recurso NÃO é marcado como indisponível

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

#### Scenario: link que não é uma URL

- **WHEN** o campo de link contém texto que não é endereço — frase, caminho com
      barra invertida, ou prefixo `URL:` esquecido no valor
- **THEN** a classe é `nao_verificado` e o motivo é registrado
- **AND** nenhuma requisição de rede é feita
- **AND** o valor original NÃO é corrigido por inferência

### Requirement: Registro do momento da checagem

O verificador SHALL gravar `checado_em` em UTC e `latencia_ms` para cada
recurso verificado, e SHALL gravar o motivo quando a classe não vier de um
status HTTP, para que o diagnóstico de qualidade do catálogo possa distinguir
link ausente de link malformado e de tempo esgotado.

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
