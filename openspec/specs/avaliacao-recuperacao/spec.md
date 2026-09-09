# Avaliação da recuperação

## Purpose

Medir se a busca encontra o conjunto certo, e detectar quando ela piora. Sem
isto, uma alteração aparentemente inofensiva nos pesos do BM25 ou no prompt de
enriquecimento degradaria a recuperação em silêncio, e ninguém saberia até um
usuário reclamar.

As perguntas são escritas à mão, no vocabulário de quem não conhece o catálogo.
Gerá-las a partir dos títulos mediria a capacidade do sistema de casar texto
consigo mesmo — o problema fácil, não o que o projeto resolve.

Recall@5 é a métrica que dirige decisões: se o conjunto certo não chega ao
contexto, nenhuma redação salva a resposta.

## Requirements

### Requirement: Conjunto de avaliação em linguagem de cidadão

O projeto SHALL manter um conjunto de perguntas versionado, escritas no
vocabulário de quem não conhece o catálogo, com os conjuntos de dados aceitáveis
anotados para cada uma.

#### Scenario: pergunta não derivada do título

- **WHEN** uma pergunta é adicionada ao conjunto de avaliação
- **THEN** ela não reproduz o título do conjunto esperado
- **AND** usa termos que uma pessoa sem formação técnica empregaria

#### Scenario: múltiplos conjuntos aceitáveis

- **WHEN** uma pergunta pode ser respondida por mais de um conjunto
- **THEN** todos os identificadores aceitáveis são anotados
- **AND** a recuperação de qualquer um deles conta como acerto

#### Scenario: classificação por tema e dificuldade

- **WHEN** o conjunto de avaliação é consultado
- **THEN** cada pergunta possui tema e nível de dificuldade registrados

### Requirement: Caminho de ausência como acerto

O conjunto de avaliação SHALL admitir o valor `nenhum` na coluna de conjuntos
aceitáveis, marcando pergunta que o catálogo não responde. A avaliação NÃO SHALL
tratar esse valor como identificador de conjunto, e SHALL contá-lo como acerto
quando a recuperação não retornar resultado relevante.

Saber calar é parte do produto. Um assistente que sempre devolve alguma coisa
ensina o usuário a desconfiar de tudo que ele devolve; o catálogo brasileiro tem
lacunas reais, e admiti-las é o que separa a resposta honesta da plausível.

Sem esta regra a métrica pune o comportamento certo: uma pergunta sem resposta no
catálogo contaria como falha justamente quando o sistema acerta ao não inventar,
e `nenhum` seria procurado como se fosse um slug.

#### Scenario: pergunta sem resposta no catálogo

- **WHEN** a pergunta tem `nenhum` como único conjunto aceitável
- **AND** a recuperação não retorna nenhum resultado
- **THEN** a pergunta conta como acerto em recall e MRR

#### Scenario: recuperação devolve algo que não deveria

- **WHEN** a pergunta tem `nenhum` como único conjunto aceitável
- **AND** a recuperação retorna ao menos um resultado
- **THEN** a pergunta conta como erro
- **AND** os resultados indevidos são exibidos no diagnóstico

#### Scenario: `nenhum` nunca é resolvido como identificador

- **WHEN** o conjunto de avaliação é carregado
- **THEN** `nenhum` não é procurado no catálogo
- **AND** sua ausência do banco não é reportada como anotação quebrada

### Requirement: Métricas de recall e MRR

A avaliação SHALL calcular recall@5, recall@10 e MRR sobre o conjunto de
perguntas.

#### Scenario: cálculo de recall

- **WHEN** a avaliação é executada
- **THEN** recall@5 e recall@10 são calculados sobre todas as perguntas
- **AND** o resultado é apresentado como proporção do total

#### Scenario: resultados por segmento

- **WHEN** a avaliação é executada
- **THEN** as métricas são apresentadas também quebradas por tema e dificuldade

#### Scenario: diagnóstico das falhas

- **WHEN** uma pergunta não recupera nenhum conjunto aceitável
- **THEN** ela é listada no relatório
- **AND** os cinco primeiros resultados retornados são exibidos

### Requirement: Execução determinística e reprodutível

A avaliação SHALL produzir resultados idênticos quando executada repetidamente
sobre o mesmo índice.

#### Scenario: duas execuções seguidas

- **WHEN** a avaliação roda duas vezes sem alteração no índice
- **THEN** as métricas são idênticas

#### Scenario: independência de ordem

- **WHEN** a ordem das perguntas no arquivo é alterada
- **THEN** as métricas agregadas permanecem as mesmas

### Requirement: Histórico comparável entre execuções

A avaliação SHALL registrar cada execução com data, métricas e identificação da
versão da recuperação avaliada, e SHALL comparar com a execução anterior.

#### Scenario: registro de execução

- **WHEN** a avaliação termina
- **THEN** um registro é acrescentado ao histórico
- **AND** o relatório mostra a variação em relação à execução anterior

#### Scenario: primeira execução

- **WHEN** não existe execução anterior registrada
- **THEN** a execução é registrada como linha de base
- **AND** nenhuma comparação é exibida

### Requirement: Detecção de regressão bloqueante

A avaliação SHALL encerrar com código diferente de 0 quando o recall@5 cair além
do limiar configurado em relação à execução anterior.

#### Scenario: regressão relevante

- **WHEN** o recall@5 cai mais que o limiar configurado
- **THEN** o código de saída é diferente de 0
- **AND** o relatório indica quais perguntas deixaram de acertar

#### Scenario: variação dentro da tolerância

- **WHEN** a variação fica dentro do limiar
- **THEN** o código de saída é 0
- **AND** a variação é registrada no relatório

#### Scenario: melhoria

- **WHEN** o recall@5 aumenta
- **THEN** o código de saída é 0
- **AND** a melhoria é destacada no relatório
