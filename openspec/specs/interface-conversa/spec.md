# Interface de conversa

## Purpose

A tela onde o cidadão pergunta e confere. Recebe a pergunta em linguagem comum,
mostra a resposta sendo escrita e apresenta os conjuntos recuperados de forma que
a pessoa possa verificar cada afirmação no portal de origem — sem cadastro, sem
instalação, funcionando no telefone.

## Requirements

### Requirement: Uso sem cadastro e sem estado

A interface SHALL permitir perguntar e receber resposta sem qualquer cadastro,
login ou identificação, e NÃO SHALL exigir persistência entre sessões.

#### Scenario: primeira visita

- **WHEN** uma pessoa abre o endereço pela primeira vez
- **THEN** o campo de pergunta está disponível imediatamente
- **AND** nenhuma tela de cadastro, aviso de cookie ou permissão é apresentada

#### Scenario: recarregar a página

- **WHEN** a pessoa recarrega a página
- **THEN** a interface volta ao estado inicial sem erro
- **AND** nenhuma informação da sessão anterior é exigida

### Requirement: Resposta apresentada enquanto chega

A interface SHALL consumir o fluxo de eventos da API e SHALL exibir o texto da
resposta à medida que os fragmentos chegam, sem esperar o fim da transmissão.

#### Scenario: fragmentos chegando

- **WHEN** a API emite fragmentos de texto
- **THEN** o texto visível cresce conforme eles chegam

#### Scenario: transmissão concluída

- **WHEN** o evento final chega
- **THEN** a interface para de indicar que está respondendo
- **AND** apresenta os conjuntos recuperados

#### Scenario: falha no meio da transmissão

- **WHEN** a conexão cai antes do evento final
- **THEN** a interface informa que a resposta foi interrompida
- **AND** oferece repetir a pergunta
- **AND** NÃO apresenta a resposta parcial como se estivesse completa

### Requirement: Conjuntos apresentados de forma conferível

A interface SHALL apresentar cada conjunto recuperado com título, órgão
publicador, formatos disponíveis, data de atualização e endereço da página do
conjunto no portal de origem.

O endereço é o que torna a resposta verificável: sem ele o usuário precisa
acreditar no sistema, que é exatamente o que este projeto recusa.

#### Scenario: conjunto recuperado

- **WHEN** a resposta cita conjuntos recuperados
- **THEN** cada um aparece com título, órgão, formatos e data de atualização
- **AND** traz um link para a página do conjunto no portal
- **AND** o link abre o registro original

#### Scenario: nenhum conjunto recuperado

- **WHEN** a resposta não traz conjunto algum
- **THEN** nenhum cartão é exibido
- **AND** a interface não apresenta área vazia ou espaço reservado

### Requirement: Distinção entre atualização do dado e do registro

A interface SHALL rotular a data exibida conforme sua natureza, distinguindo a
data em que os dados foram atualizados da data em que os metadados foram
editados, e NÃO SHALL apresentar uma como se fosse a outra.

Um conjunto cujo registro foi editado ontem e cujos dados são de 2019 não é um
conjunto atualizado ontem. Confundir as duas datas anunciaria frescor que o dado
não tem, que é uma forma de mentir com informação verdadeira.

#### Scenario: data dos dados conhecida

- **WHEN** o conjunto declara quando os dados foram atualizados
- **THEN** essa data é exibida identificada como atualização dos dados

#### Scenario: apenas a data do registro é conhecida

- **WHEN** o conjunto não declara quando os dados foram atualizados
- **AND** declara quando o registro foi editado
- **THEN** a data exibida é identificada como atualização do registro no portal

#### Scenario: nenhuma data conhecida

- **WHEN** o conjunto não declara data alguma
- **THEN** a interface informa que a data não foi declarada
- **AND** NÃO exibe data inventada, vazia ou traço sem explicação

### Requirement: Recursos indisponíveis sinalizados, não escondidos

A interface SHALL exibir recursos cujo link foi verificado como indisponível,
marcados como tal, em vez de omiti-los, e SHALL sempre oferecer o caminho para a
página do conjunto no portal.

#### Scenario: recurso com link fora do ar

- **WHEN** um recurso está marcado como indisponível
- **THEN** ele aparece na lista com indicação visível de que o link não respondeu
- **AND** o link para a página do conjunto continua disponível

#### Scenario: ordem de apresentação

- **WHEN** um conjunto tem recursos disponíveis e indisponíveis
- **THEN** os disponíveis aparecem primeiro

### Requirement: Origem da resposta visível ao usuário

A interface SHALL informar como a resposta foi produzida, entre correspondência
direta, redação por modelo e modo reduzido.

#### Scenario: qualquer resposta entregue

- **WHEN** a resposta termina de chegar
- **THEN** a origem declarada pela API é apresentada ao usuário
- **AND** em linguagem compreensível para quem não conhece o sistema

### Requirement: Uso em telefone

A interface SHALL ser utilizável em tela estreita, com o campo de pergunta
alcançável e os conjuntos legíveis sem rolagem horizontal.

#### Scenario: tela estreita

- **WHEN** a página é aberta em viewport de 360 pixels de largura
- **THEN** nenhum conteúdo exige rolagem horizontal
- **AND** o campo de pergunta e o botão de enviar permanecem alcançáveis

#### Scenario: texto longo sem quebra

- **WHEN** um título ou endereço não contém espaços
- **THEN** ele é quebrado ou truncado sem alargar a página

### Requirement: Estados de espera e de erro explícitos

A interface SHALL indicar quando está aguardando resposta e SHALL apresentar
mensagem compreensível quando a API estiver indisponível.

#### Scenario: aguardando

- **WHEN** a pergunta foi enviada e nada chegou ainda
- **THEN** a interface indica que está buscando
- **AND** impede o envio duplicado da mesma pergunta

#### Scenario: serviço fora do ar

- **WHEN** a API não responde
- **THEN** a interface informa a indisponibilidade em linguagem simples
- **AND** NÃO exibe código de erro, rastreamento de pilha ou jargão técnico

#### Scenario: pergunta vazia

- **WHEN** a pessoa envia o formulário sem escrever nada
- **THEN** nenhuma requisição é feita
