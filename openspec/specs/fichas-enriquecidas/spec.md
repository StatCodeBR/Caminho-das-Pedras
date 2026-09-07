# Fichas enriquecidas

## Purpose

Atravessar o abismo entre a linguagem do cidadão e a do catálogo. A pessoa
pergunta "quantos leitos de UTI tem na minha cidade"; o conjunto que responde
isso se chama "CNES — Estabelecimentos". Nenhuma busca textual vence essa
distância sozinha, e boa parte dos conjuntos tem descrição vazia ou de uma linha.

A ficha é uma camada de metadados legíveis — resumo em português simples e
perguntas reais que o conjunto responde — gerada **uma única vez e offline**. É
esse texto que alimenta os índices de busca, não o original.

É o diferencial técnico do projeto e também seu maior risco: um modelo pedido
para descrever um conjunto de metadados pobres tende a inventar conteúdo
plausível, e o resumo inventado vira falso positivo permanente na busca. Os
requisitos abaixo existem por causa disso.

## Requirements

### Requirement: Saída estritamente estruturada

O enriquecedor SHALL exigir do modelo um objeto JSON válido contendo `resumo`,
`perguntas`, `temas`, `abrangencia`, `granularidade` e `confianca`, e SHALL
validar essa estrutura antes de persistir.

#### Scenario: resposta válida

- **WHEN** o modelo retorna JSON com todos os campos exigidos
- **THEN** a ficha é persistida na tabela `ficha`
- **AND** `hash_entrada` é gravado junto

#### Scenario: resposta malformada

- **WHEN** a resposta não é JSON válido
- **THEN** a chamada é repetida no máximo 2 vezes
- **AND** persistindo a falha, é gravada uma ficha de fallback

#### Scenario: tema fora da lista fechada

- **WHEN** o modelo retorna um tema que não consta da lista definida
- **THEN** esse tema é descartado
- **AND** os temas válidos restantes são preservados

### Requirement: Proibição de inferência não fundamentada

O enriquecedor SHALL marcar `confianca` como `baixa` quando os metadados forem
insuficientes para descrever o conteúdo, e o resumo NÃO SHALL afirmar nada que
não esteja presente nos metadados fornecidos.

#### Scenario: conjunto sem descrição

- **WHEN** o conjunto possui apenas título e órgão
- **THEN** `confianca` é `baixa`
- **AND** o resumo se limita ao que título e órgão permitem afirmar

#### Scenario: conjunto bem documentado

- **WHEN** o conjunto possui descrição extensa e recursos nomeados
- **THEN** `confianca` pode ser `alta`
- **AND** o resumo descreve o conteúdo em linguagem simples

#### Scenario: conjunto nunca descartado

- **WHEN** os metadados são insuficientes
- **THEN** o conjunto ainda assim recebe uma ficha
- **AND** permanece recuperável pela busca

### Requirement: Confiança verificada pelo pipeline, não declarada pelo modelo

O pipeline SHALL rebaixar `confianca` para `baixa` quando a descrição de origem
for curta demais para sustentar afirmação sobre o conteúdo, independentemente do
valor que o modelo tenha retornado. O pipeline NÃO SHALL elevar a confiança em
nenhuma circunstância.

A trava existe porque a falha se concentra numa faixa estreita: com descrição
entre 20 e 40 caracteres o modelo tem *quase* informação e completa o vazio — um
conjunto chamado "11. Mortalidade Materna", com 27 caracteres de descrição,
produziu ficha afirmando indicadores de *near miss* que a origem não menciona.
Instrução no prompt funciona mal nessa faixa.

A consequência não é cosmética: o resumo alimenta o `texto_indexavel`, então
afirmação inventada vira falso positivo permanente na busca. Confiança baixa
limita as perguntas e desprioriza a ficha, contendo o dano.

#### Scenario: descrição curta demais

- **WHEN** a descrição de origem tem menos caracteres que o limiar
- **AND** o modelo retorna `confianca` `alta` ou `media`
- **THEN** a confiança gravada é `baixa`
- **AND** valem os limites de `baixa`, inclusive o máximo de 2 perguntas

#### Scenario: a trava só rebaixa

- **WHEN** o modelo retorna `confianca` `baixa` para um conjunto bem descrito
- **THEN** a confiança gravada continua `baixa`

### Requirement: Perguntas exemplo em linguagem de cidadão

O enriquecedor SHALL gerar até 5 perguntas que uma pessoa sem formação técnica
faria e que o conjunto responde, escritas sem jargão administrativo.

#### Scenario: conjunto de estabelecimentos de saúde

- **WHEN** o conjunto trata de estabelecimentos de saúde
- **THEN** as perguntas usam termos cotidianos como hospital, posto ou leito
- **AND** não repetem literalmente o título do conjunto

#### Scenario: confiança baixa

- **WHEN** `confianca` é `baixa`
- **THEN** são geradas no máximo 2 perguntas
- **AND** nenhuma afirma cobertura geográfica ou temporal não documentada

### Requirement: Provedor de modelo atrás de interface única

O enriquecedor SHALL acessar o modelo de linguagem por uma interface única, sem
conhecer o fornecedor, e SHALL gravar na ficha o identificador do provedor e do
modelo que a gerou, para que a decisão possa ser auditada depois.

#### Scenario: troca de fornecedor

- **WHEN** o provedor configurado muda
- **THEN** apenas a implementação do provedor muda
- **AND** o restante do pipeline permanece intacto

#### Scenario: procedência registrada

- **WHEN** uma ficha é persistida
- **THEN** a coluna `modelo` guarda o identificador de quem a escreveu

### Requirement: Cache por hash do conteúdo de entrada

O enriquecedor SHALL indexar resultados pelo hash SHA-256 do texto enviado ao
modelo — instrução, metadados e identificador do provedor e modelo — e SHALL
pular itens já processados cujo hash não tenha mudado.

O identificador do modelo entra no hash porque a mesma entrada respondida por
outro modelo não é a mesma ficha; sem isso, trocar de fornecedor serviria
silenciosamente fichas antigas.

#### Scenario: reexecução sem alterações

- **WHEN** o pipeline é reexecutado sem mudança nos metadados nem no prompt
- **THEN** nenhuma chamada ao modelo é feita
- **AND** o relatório informa 100% de aproveitamento de cache

#### Scenario: prompt alterado

- **WHEN** o arquivo de prompt é modificado
- **THEN** o hash de todas as entradas muda
- **AND** todos os conjuntos são reprocessados

#### Scenario: metadado de um conjunto alterado

- **WHEN** apenas um conjunto tem sua descrição atualizada na origem
- **THEN** apenas esse conjunto é reprocessado

#### Scenario: modelo trocado

- **WHEN** o mesmo conjunto é enriquecido por outro provedor ou modelo
- **THEN** o hash muda e a ficha é gerada de novo

### Requirement: Processamento em lote retomável quando o provedor o oferece

Quando o provedor selecionado oferecer processamento em lote, o enriquecedor
SHALL submeter os itens em lote e SHALL persistir o identificador do lote,
permitindo retomar a coleta dos resultados após interrupção. Quando o provedor
não o oferecer, o enriquecedor SHALL processar item a item, sem perder o
trabalho já pago.

#### Scenario: interrupção durante a espera

- **WHEN** o processo é encerrado enquanto aguarda um lote
- **AND** o comando é executado novamente
- **THEN** ele reconecta ao lote pendente pelo identificador persistido
- **AND** não submete os mesmos itens outra vez

#### Scenario: provedor sem lote

- **WHEN** o provedor não anuncia a capacidade de lote
- **THEN** os conjuntos são processados um a um
- **AND** as fichas já geradas são persistidas periodicamente, não só ao final

### Requirement: Texto indexável derivado sem custo

O campo `texto_indexavel` SHALL ser produzido por concatenação determinística de
nome, resumo, perguntas, órgão e tags, sem qualquer chamada a modelo.

#### Scenario: reconstrução dos índices

- **WHEN** o texto indexável é regerado para todo o catálogo
- **THEN** nenhuma chamada a provedor de modelo é feita
- **AND** o resultado é idêntico para a mesma ficha

### Requirement: Relatório de confiança do catálogo

Ao final, o enriquecedor SHALL informar a distribuição de `confianca` entre
alta, média e baixa, por ser a métrica base do diagnóstico de qualidade do
catálogo.

#### Scenario: execução concluída

- **WHEN** o enriquecimento termina
- **THEN** o relatório exibe contagem e percentual por nível de confiança
- **AND** exibe quantas fichas caíram no fallback
