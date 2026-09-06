# Chave local

## ADDED Requirements

### Requirement: Chave armazenada no cofre do sistema operacional

O aplicativo SHALL persistir a chave de API no cofre de credenciais do sistema
operacional e NÃO SHALL gravá-la em arquivo de configuração, banco local ou log.

#### Scenario: chave salva

- **WHEN** o usuário informa uma chave e confirma
- **THEN** ela é gravada no cofre do sistema
- **AND** nenhum arquivo do aplicativo contém o valor da chave

#### Scenario: cofre indisponível no Linux

- **WHEN** nenhum serviço de cofre está disponível no sistema
- **THEN** o aplicativo informa a limitação em linguagem clara
- **AND** mantém a chave apenas na memória da sessão
- **AND** NÃO grava a chave em disco

#### Scenario: chave ausente dos registros

- **WHEN** qualquer mensagem de log ou relatório de erro é produzida
- **THEN** o valor da chave não aparece no conteúdo

### Requirement: Chave não atravessa a fronteira para o WebView

Todas as requisições à API do modelo SHALL partir do núcleo nativo, e o valor da
chave NÃO SHALL ser transmitido à camada web em nenhuma circunstância.

#### Scenario: requisição ao modelo

- **WHEN** o modelo é acionado para redigir uma resposta
- **THEN** a requisição é emitida pelo núcleo nativo
- **AND** o WebView recebe apenas os fragmentos de texto da resposta

#### Scenario: consulta de estado da chave

- **WHEN** a interface precisa saber se há chave configurada
- **THEN** recebe apenas um indicador de existência e os últimos caracteres
- **AND** não recebe o valor completo

#### Scenario: ausência de comando de leitura

- **WHEN** a superfície de comandos do aplicativo é inspecionada
- **THEN** não existe comando que retorne o valor da chave ao WebView

### Requirement: Validação no momento da configuração

O aplicativo SHALL validar a chave ao salvá-la, por meio de uma requisição
mínima, e SHALL traduzir o resultado para linguagem compreensível.

#### Scenario: chave inválida

- **WHEN** a validação indica credencial rejeitada
- **THEN** a mensagem informa que a chave não foi aceita
- **AND** orienta onde obter uma chave válida
- **AND** a chave não é gravada

#### Scenario: chave sem crédito

- **WHEN** a validação indica ausência de crédito na conta
- **THEN** a mensagem distingue esse caso de chave inválida

#### Scenario: falha apenas de conexão

- **WHEN** a validação falha por indisponibilidade de rede
- **THEN** a chave é gravada mesmo assim
- **AND** o usuário é informado de que a validação ficou pendente

### Requirement: Remoção da chave com efeito imediato

O aplicativo SHALL permitir remover a chave e SHALL retornar ao modo de
recuperação sem exigir reinício.

#### Scenario: remoção pelo usuário

- **WHEN** o usuário remove a chave
- **THEN** ela é apagada do cofre
- **AND** a próxima pergunta é respondida por correspondência direta

### Requirement: Falha do provedor não interrompe o produto

Quando a chamada ao modelo falhar por qualquer motivo, o aplicativo SHALL
responder por recuperação em vez de exibir erro terminal.

#### Scenario: provedor indisponível

- **WHEN** a requisição ao modelo falha
- **THEN** a resposta é montada por template a partir das fichas recuperadas
- **AND** o usuário é informado de que a redação detalhada não estava disponível

#### Scenario: crédito esgotado durante o uso

- **WHEN** a API rejeita a requisição por ausência de crédito
- **THEN** o aplicativo passa a operar por recuperação
- **AND** informa o motivo uma única vez, sem repetir a cada pergunta

### Requirement: Transparência sobre o custo de uso

O aplicativo SHALL exibir a contagem de chamadas ao modelo na sessão corrente e
SHALL informar que o consumo é cobrado diretamente pelo provedor.

#### Scenario: acompanhamento da sessão

- **WHEN** o usuário consulta as configurações
- **THEN** vê quantas chamadas ao modelo foram feitas na sessão

#### Scenario: aviso na configuração

- **WHEN** a tela de configuração de chave é exibida
- **THEN** informa que os custos são cobrados pelo provedor ao titular da chave
