# Distribuição do catálogo

## Purpose

Levar o artefato que o pipeline gera até a imagem de produção sem versioná-lo, e
sem que ninguém precise confiar que o arquivo baixado é o certo. O repositório
guarda a soma de verificação; a release guarda os bytes. A imagem só se constrói
quando os dois concordam.

## ADDED Requirements

### Requirement: Artefatos gerados fora do controle de versão

O repositório NÃO SHALL versionar `dados.db`, `vectors.npy`, o JSONL bruto nem
qualquer outro artefato produzido por execução do pipeline.

Banco de dados gerado não é código-fonte: é resultado de uma execução, e o Git
guarda cada versão dele para sempre sem conseguir comprimir entre elas.

#### Scenario: clone limpo

- **WHEN** o repositório é clonado
- **THEN** nenhum artefato gerado do pipeline vem junto
- **AND** o `.gitignore` impede que uma execução local os reintroduza

#### Scenario: execução local do pipeline

- **WHEN** o pipeline é executado e grava os artefatos
- **THEN** o estado do Git permanece limpo

### Requirement: Catálogo publicado como release verificável

O catálogo SHALL ser publicado como asset de release, comprimido, e o
repositório SHALL guardar a soma de verificação SHA-256 do artefato e um
manifesto com a procedência do catálogo.

O manifesto SHALL declarar quando o catálogo foi gerado, quantos conjuntos e
quantas fichas contém, e qual provedor e modelo escreveram as fichas.

Sem manifesto, saber o que há dentro de uma release exige baixá-la e abri-la; e
a procedência do catálogo é o que permite auditar por que uma resposta saiu como
saiu.

#### Scenario: release publicada

- **WHEN** um catálogo é publicado
- **THEN** o asset comprimido fica disponível na release
- **AND** a soma de verificação e o manifesto são gravados no repositório

#### Scenario: manifesto descreve o conteúdo

- **WHEN** alguém consulta o manifesto
- **THEN** vê data de geração, contagem de conjuntos, contagem de fichas e o
      identificador do modelo que as escreveu
- **AND** não precisa baixar o artefato para saber o que ele contém

### Requirement: Integridade verificada antes do uso

O build da imagem SHALL baixar o artefato, conferir a soma de verificação contra
a registrada no repositório e SHALL falhar quando elas divergirem.

O build NÃO SHALL prosseguir com catálogo ausente, truncado ou divergente, nem
substituí-lo por um vazio.

Uma imagem construída com catálogo errado responde com aparência de normalidade:
os links continuam bem formados e as fichas continuam legíveis. O erro só
apareceria para quem procurasse um conjunto que deveria existir — tarde demais.

#### Scenario: soma confere

- **WHEN** o artefato baixado tem a soma registrada
- **THEN** o build prossegue e o catálogo entra na imagem

#### Scenario: soma diverge

- **WHEN** o artefato baixado tem soma diferente da registrada
- **THEN** o build falha com mensagem dizendo qual soma era esperada e qual veio
- **AND** nenhuma imagem é produzida

#### Scenario: download falha

- **WHEN** a release não existe ou a rede falha
- **THEN** o build falha
- **AND** a mensagem diz qual versão do catálogo era esperada

### Requirement: Versão do catálogo fixada pelo repositório

O build SHALL usar a versão de catálogo declarada no repositório, e NÃO SHALL
resolver a release por referência móvel como "a mais recente".

Duas construções do mesmo commit precisam produzir a mesma imagem. Com
referência móvel, publicar um catálogo novo mudaria silenciosamente o conteúdo
de builds antigos, e uma reconstrução para corrigir outra coisa traria junto um
catálogo que ninguém pediu.

#### Scenario: reconstrução do mesmo commit

- **WHEN** a imagem é construída duas vezes a partir do mesmo commit
- **THEN** o mesmo catálogo é usado nas duas
- **AND** mesmo que uma release mais nova exista

#### Scenario: atualização do catálogo

- **WHEN** um catálogo novo é publicado
- **THEN** passar a usá-lo exige um commit alterando a versão e a soma
- **AND** esse commit registra qual catálogo a imagem passou a servir

### Requirement: Desenvolvimento local sem depender da release

O build SHALL permitir usar um artefato local em vez do publicado, para que
desenvolver e testar não dependam de publicar release nem de acesso à rede.

#### Scenario: catálogo local

- **WHEN** o build é feito indicando um artefato local
- **THEN** ele é usado no lugar do download
- **AND** a verificação de soma não é exigida

#### Scenario: padrão continua sendo o publicado

- **WHEN** nenhum artefato local é indicado
- **THEN** o build baixa e verifica a release declarada
