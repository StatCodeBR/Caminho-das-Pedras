# Recuperação híbrida

## ADDED Requirements

### Requirement: Fusão por Reciprocal Rank Fusion

A recuperação SHALL combinar os rankings léxico e semântico somando, para cada
conjunto, o inverso de `RRF_K` mais a posição em cada ranking em que ele aparece.

#### Scenario: presença nos dois rankings

- **WHEN** um conjunto aparece em ambos os rankings
- **THEN** sua pontuação final soma as contribuições dos dois

#### Scenario: vantagem da concordância

- **WHEN** um conjunto está em posição intermediária nos dois rankings
- **AND** outro está em primeiro em apenas um deles
- **THEN** a fusão pode classificar o primeiro acima do segundo

#### Scenario: independência de escala

- **WHEN** as pontuações brutas dos rankings variam de magnitude
- **THEN** a fusão depende apenas das posições
- **AND** nenhuma normalização de pontuação é necessária

### Requirement: Profundidade de candidatos maior que o retorno

A recuperação SHALL consultar de cada ranking uma quantidade de candidatos
maior que a quantidade final retornada, configurável por
`PROFUNDIDADE_BUSCA`.

#### Scenario: candidatos além do corte final

- **WHEN** a fusão é executada
- **THEN** cada ranking contribui com a profundidade configurada
- **AND** o resultado final é truncado apenas após a fusão

### Requirement: Resiliência à falha de um dos rankings

A recuperação SHALL retornar resultado útil quando um dos rankings falhar,
usando o ranking restante.

#### Scenario: falha da busca semântica

- **WHEN** a busca semântica não pode ser executada
- **THEN** o resultado é composto apenas pelo ranking léxico
- **AND** a ocorrência é registrada em log

#### Scenario: falha da busca léxica

- **WHEN** a busca léxica não pode ser executada
- **THEN** o resultado é composto apenas pelo ranking semântico

#### Scenario: falha dos dois

- **WHEN** ambos os rankings falham
- **THEN** a recuperação retorna vazio
- **AND** o consumidor trata como ausência de resultado, não como erro

### Requirement: Proveniência de cada resultado

Cada resultado SHALL registrar de quais rankings veio e a posição ocupada em
cada um.

#### Scenario: consumo pela camada de resposta

- **WHEN** a camada de resposta recebe os finalistas
- **THEN** cada item traz os rankings de origem e as posições

#### Scenario: diagnóstico na avaliação

- **WHEN** uma pergunta falha na avaliação
- **THEN** o relatório mostra em quais rankings os conjuntos esperados
  apareceram, se em algum

### Requirement: Determinismo do resultado

A recuperação SHALL produzir a mesma ordem para a mesma consulta sobre o mesmo
índice, com desempate determinístico entre pontuações idênticas.

#### Scenario: consultas repetidas

- **WHEN** a mesma pergunta é consultada duas vezes
- **THEN** a ordem dos resultados é idêntica

#### Scenario: empate de pontuação

- **WHEN** dois conjuntos obtêm pontuação final idêntica
- **THEN** o desempate segue critério fixo e documentado
- **AND** não depende da ordem de conclusão das buscas paralelas

### Requirement: Ganho comprovado sobre os rankings isolados

A fusão SHALL ser avaliada contra a busca léxica isolada e a semântica isolada,
e NÃO SHALL ser adotada se apresentar recall@5 inferior ao melhor dos dois.

#### Scenario: avaliação comparativa

- **WHEN** a fusão é implementada
- **THEN** a avaliação é executada nas três configurações
- **AND** as três medições são registradas no histórico

#### Scenario: fusão inferior

- **WHEN** o recall@5 da fusão é inferior ao melhor ranking isolado
- **THEN** a mudança não é arquivada
- **AND** a configuração isolada superior permanece em uso
