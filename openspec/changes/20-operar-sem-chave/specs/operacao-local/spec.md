# Operação local

## ADDED Requirements

### Requirement: Utilidade plena sem chave configurada

O aplicativo SHALL responder perguntas em modo de recuperação sem exigir chave
de API, e NÃO SHALL bloquear nenhum acesso a dados por ausência de credencial.

#### Scenario: primeira execução

- **WHEN** o aplicativo é aberto pela primeira vez, sem chave configurada
- **THEN** a tela de perguntas é apresentada imediatamente
- **AND** nenhum assistente de configuração bloqueia o uso
- **AND** perguntas são respondidas por correspondência direta

#### Scenario: conjuntos sempre acessíveis

- **WHEN** uma pergunta é feita sem chave configurada
- **THEN** os conjuntos recuperados são apresentados com nome, órgão e link
- **AND** os formatos dos recursos são informados
- **AND** recursos indisponíveis aparecem sinalizados

#### Scenario: convite discreto e dispensável

- **WHEN** o aplicativo opera sem chave
- **THEN** um aviso explica o que a configuração da chave acrescentaria
- **AND** o aviso pode ser dispensado permanentemente

### Requirement: Recuperação integralmente local

O aplicativo SHALL executar busca léxica, busca semântica e fusão de rankings
no próprio dispositivo, sem qualquer requisição de rede.

#### Scenario: uso sem conexão

- **WHEN** o dispositivo está sem acesso à internet
- **AND** o catálogo local já foi obtido
- **THEN** perguntas continuam sendo respondidas por recuperação
- **AND** nenhuma mensagem de erro de rede é exibida

#### Scenario: ausência de tráfego sem chave

- **WHEN** o aplicativo opera sem chave configurada
- **THEN** nenhuma requisição de rede é emitida ao responder perguntas

### Requirement: Paridade de comportamento com a versão web

O núcleo local SHALL aplicar os mesmos critérios de roteamento, ancoragem e
sinalização definidos para a versão servidor.

#### Scenario: roteamento equivalente

- **WHEN** o primeiro resultado supera o limiar e a margem configurados
- **THEN** a resposta é montada por template
- **AND** o campo de origem indica correspondência direta

#### Scenario: ancoragem preservada

- **WHEN** o modelo é acionado e cita URL ausente do contexto
- **THEN** a resposta é descartada
- **AND** o usuário recebe mensagem de indisponibilidade temporária

#### Scenario: mesmo contrato de streaming

- **WHEN** qualquer resposta é produzida
- **THEN** os fragmentos chegam à interface pelo mesmo formato de evento usado
  na versão web
