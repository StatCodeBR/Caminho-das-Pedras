# Catálogo local

## ADDED Requirements

### Requirement: Catálogo distribuído separadamente do aplicativo

O aplicativo SHALL obter catálogo, vetores e modelo por download na primeira
execução, e o instalador NÃO SHALL embutir esses artefatos.

#### Scenario: primeira execução com conexão

- **WHEN** o aplicativo é aberto sem catálogo local
- **THEN** o download é iniciado com indicação de progresso
- **AND** pode ser cancelado pelo usuário

#### Scenario: primeira execução sem conexão

- **WHEN** o aplicativo é aberto sem catálogo local e sem rede
- **THEN** a situação é explicada em linguagem clara
- **AND** o aplicativo orienta tentar novamente quando houver conexão
- **AND** nenhuma mensagem de erro técnica é exibida

#### Scenario: execuções seguintes sem conexão

- **WHEN** o aplicativo é aberto com catálogo local já presente e sem rede
- **THEN** ele opera normalmente em modo de recuperação

### Requirement: Verificação de integridade antes da ativação

O aplicativo SHALL verificar a soma de verificação de cada artefato baixado e
NÃO SHALL ativar um catálogo que falhe na verificação.

#### Scenario: download íntegro

- **WHEN** todas as somas conferem
- **THEN** o catálogo é promovido a ativo

#### Scenario: soma divergente

- **WHEN** a soma de um artefato não confere
- **THEN** o artefato é descartado
- **AND** o catálogo anterior permanece ativo
- **AND** o usuário é informado da falha

#### Scenario: banco ilegível

- **WHEN** o banco baixado não abre ou a consulta FTS5 falha
- **THEN** o catálogo não é promovido
- **AND** o estado anterior é preservado

### Requirement: Substituição atômica do catálogo

A promoção do novo catálogo SHALL ocorrer por renomeação após todas as
verificações, de modo que interrupções nunca deixem o aplicativo sem catálogo
utilizável.

#### Scenario: interrupção durante o download

- **WHEN** o processo é encerrado no meio de uma atualização
- **THEN** o catálogo anterior continua íntegro e ativo
- **AND** nenhum banco parcialmente escrito é utilizado

#### Scenario: remoção do anterior

- **WHEN** a promoção é concluída com sucesso
- **THEN** o catálogo anterior é removido
- **AND** o espaço em disco é liberado

### Requirement: Atualização mediante consentimento

O aplicativo SHALL verificar automaticamente a existência de catálogo mais
recente, mas SHALL aguardar consentimento do usuário antes de baixá-lo, exceto
quando não houver catálogo algum.

#### Scenario: nova versão disponível

- **WHEN** uma versão mais recente é detectada
- **THEN** o usuário é avisado sem interrupção do uso
- **AND** o download ocorre apenas após confirmação

#### Scenario: ausência total de catálogo

- **WHEN** não há catálogo local
- **THEN** o download ocorre sem solicitar confirmação
- **AND** o progresso é exibido

#### Scenario: aviso não repetitivo

- **WHEN** o usuário dispensa o aviso de atualização
- **THEN** ele não é reapresentado na mesma sessão

### Requirement: Versão do catálogo visível e rastreável

O aplicativo SHALL exibir a versão e a data do catálogo em uso, SHALL associá-la
às respostas produzidas e SHALL usá-la como chave do cache local.

#### Scenario: consulta da versão

- **WHEN** o usuário consulta as informações do aplicativo
- **THEN** vê a versão e a data do catálogo ativo

#### Scenario: resposta rastreável

- **WHEN** uma resposta é produzida
- **THEN** ela informa a versão do catálogo que a originou

#### Scenario: cache invalidado por versão

- **WHEN** um catálogo de versão diferente é promovido
- **THEN** nenhuma resposta em cache da versão anterior é servida

### Requirement: Alternativa quando a busca não encontra

Quando nenhuma ficha relevante for recuperada, o aplicativo SHALL informar a
data do catálogo local e SHALL oferecer o acesso ao portal para consulta direta.

#### Scenario: conjunto publicado após o catálogo local

- **WHEN** a busca não retorna resultado pertinente
- **THEN** a resposta informa a data do catálogo em uso
- **AND** oferece link para busca no dados.gov.br
