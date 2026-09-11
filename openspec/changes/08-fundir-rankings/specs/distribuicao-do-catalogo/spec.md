# Distribuição do catálogo

## MODIFIED Requirements

### Requirement: Catálogo publicado como release verificável

O catálogo SHALL ser publicado como assets de release — o banco comprimido e os
vetores da busca semântica, cada um como asset próprio, na mesma release — e o
repositório SHALL guardar a soma de verificação SHA-256 de cada asset e um
manifesto com a procedência do catálogo.

O manifesto SHALL declarar quando o catálogo foi gerado, quantos conjuntos e
quantas fichas contém, qual provedor e modelo escreveram as fichas, e qual
modelo gerou os vetores.

Sem manifesto, saber o que há dentro de uma release exige baixá-la e abri-la; e
a procedência do catálogo é o que permite auditar por que uma resposta saiu como
saiu.

Os vetores são publicados na mesma release do banco que os originou. Vetor de
outra versão do catálogo apontaria para o conjunto errado sem sintoma nenhum;
publicar os dois juntos, sob uma só versão, é o que impede montar essa
combinação por acidente.

#### Scenario: release publicada

- **WHEN** um catálogo é publicado
- **THEN** o banco e os vetores ficam disponíveis na release como assets
      distintos
- **AND** a soma de cada asset e o manifesto são gravados no repositório

#### Scenario: manifesto descreve o conteúdo

- **WHEN** alguém consulta o manifesto
- **THEN** vê data de geração, contagem de conjuntos, contagem de fichas, o
      identificador do modelo que escreveu as fichas e o do modelo que gerou os
      vetores
- **AND** não precisa baixar os artefatos para saber o que eles contêm

#### Scenario: vetores que não correspondem ao banco

- **WHEN** os vetores a publicar foram gerados sobre outra versão do banco
- **THEN** a publicação é recusada
- **AND** nenhuma release é criada

### Requirement: Integridade verificada antes do uso

O build da imagem SHALL baixar cada asset do catálogo, conferir a soma de
verificação de cada um contra a registrada no repositório e SHALL falhar quando
qualquer uma divergir.

O build NÃO SHALL prosseguir com banco ou vetores ausentes, truncados ou
divergentes, nem substituí-los por vazios.

Uma imagem construída com catálogo errado responde com aparência de normalidade:
os links continuam bem formados e as fichas continuam legíveis. O erro só
apareceria para quem procurasse um conjunto que deveria existir — tarde demais.

#### Scenario: somas conferem

- **WHEN** o banco e os vetores baixados têm as somas registradas
- **THEN** o build prossegue e os dois entram na imagem

#### Scenario: soma diverge

- **WHEN** algum asset baixado tem soma diferente da registrada
- **THEN** o build falha com mensagem dizendo qual asset divergiu, qual soma era
      esperada e qual veio
- **AND** nenhuma imagem é produzida

#### Scenario: download falha

- **WHEN** a release ou algum de seus assets não existe, ou a rede falha
- **THEN** o build falha
- **AND** a mensagem diz qual versão do catálogo e qual asset eram esperados

### Requirement: Desenvolvimento local sem depender da release

O build SHALL permitir usar artefatos locais — banco e vetores — em vez dos
publicados, para que desenvolver e testar não dependam de publicar release nem
de acesso à rede.

#### Scenario: catálogo local

- **WHEN** o build é feito indicando artefatos locais
- **THEN** eles são usados no lugar do download
- **AND** a verificação de soma não é exigida

#### Scenario: banco local sem vetores locais

- **WHEN** o build indica um banco local sem indicar vetores locais
- **THEN** o build falha, dizendo que os vetores também precisam ser indicados

#### Scenario: padrão continua sendo o publicado

- **WHEN** nenhum artefato local é indicado
- **THEN** o build baixa e verifica a release declarada
