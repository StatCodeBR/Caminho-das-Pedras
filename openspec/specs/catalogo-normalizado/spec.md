# Catálogo normalizado

## Purpose

Transformar o JSONL fiel à API em um banco consultável, tolerando a
irregularidade do metadado público: o que não passa na validação vai para
quarentena com o motivo, e a ingestão segue. É a base tabular sobre a qual o
enriquecimento, os índices e a busca trabalham.

## Requirements

### Requirement: Esquema relacional de conjuntos e recursos

O pipeline SHALL materializar o catálogo em SQLite com as tabelas `conjunto` e
`recurso`, ligadas por chave estrangeira, e SHALL preservar o identificador
original do portal como chave natural.

#### Scenario: conjunto com múltiplos recursos

- **WHEN** um conjunto do JSONL possui três recursos
- **THEN** uma linha é criada em `conjunto`
- **AND** três linhas são criadas em `recurso` referenciando esse conjunto

#### Scenario: conjunto sem recursos

- **WHEN** um conjunto não possui nenhum recurso
- **THEN** ele ainda assim é ingerido na tabela `conjunto`
- **AND** nenhuma linha é criada em `recurso`

### Requirement: Idempotência da ingestão

A ingestão SHALL produzir estado equivalente quando executada repetidamente
sobre a mesma entrada, sem duplicar linhas.

#### Scenario: reexecução sobre o mesmo JSONL

- **WHEN** a normalização roda duas vezes seguidas
- **THEN** as contagens de `conjunto` e `recurso` são idênticas nas duas execuções

#### Scenario: conjunto que perdeu um recurso

- **WHEN** um conjunto é reingerido com menos recursos que antes
- **THEN** os recursos ausentes são removidos do banco
- **AND** nenhum recurso órfão permanece

### Requirement: Quarentena em vez de interrupção

Registros que falharem na validação SHALL ser gravados em
`pipeline/quarentena.jsonl` com o motivo, e a ingestão SHALL prosseguir.

#### Scenario: registro sem identificador

- **WHEN** um registro do JSONL não possui identificador
- **THEN** ele é gravado na quarentena com o motivo
- **AND** os registros seguintes continuam sendo processados

#### Scenario: campos opcionais ausentes

- **WHEN** um conjunto não possui descrição, tema ou periodicidade
- **THEN** ele é ingerido normalmente com esses campos nulos
- **AND** não é enviado para quarentena

### Requirement: Normalização de datas e formatos

O pipeline SHALL gravar todas as datas em ISO 8601 marcadas como UTC, sem
deslocar o instante quando a origem não declara fuso, e SHALL normalizar o
campo de formato dos recursos para maiúsculas, sem espaço sobrando nem ponto
inicial.

#### Scenario: data sem fuso declarado

- **WHEN** a API fornece uma data sem deslocamento de fuso
- **THEN** o instante gravado é idêntico ao da origem
- **AND** o valor é marcado como UTC em ISO 8601

#### Scenario: formato escrito de maneiras diferentes

- **WHEN** recursos declaram formato como `csv`, `CSV ` ou `.csv`
- **THEN** todos são gravados como `CSV`
- **AND** o espaço interno de um formato como `ZIP SHP` é preservado

#### Scenario: data irrecuperável

- **WHEN** uma data não pode ser interpretada
- **THEN** o campo é gravado como nulo
- **AND** o registro não vai para quarentena por causa disso

### Requirement: Preservação da URL do conjunto no portal

O pipeline SHALL armazenar, para cada conjunto, a URL da sua página no
dados.gov.br, pois é o endereço apresentado ao usuário final e o exigido na
inscrição do concurso.

#### Scenario: URL ausente na origem

- **WHEN** o registro não traz a URL da página
- **THEN** ela é derivada do identificador segundo o padrão do portal
- **AND** o campo nunca fica nulo

### Requirement: Relatório de ingestão com limiar de falha

Ao final, o pipeline SHALL emitir contagens de ingeridos e rejeitados, e SHALL
encerrar com código diferente de 0 quando a taxa de rejeição exceder 5%.

#### Scenario: ingestão saudável

- **WHEN** menos de 5% dos registros são rejeitados
- **THEN** o relatório é exibido
- **AND** o código de saída é 0

#### Scenario: degradação da fonte

- **WHEN** mais de 5% dos registros são rejeitados
- **THEN** o código de saída é diferente de 0
- **AND** a mensagem indica o caminho do arquivo de quarentena
