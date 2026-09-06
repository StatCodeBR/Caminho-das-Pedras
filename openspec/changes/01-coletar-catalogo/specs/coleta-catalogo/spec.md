# Coleta do catálogo

## ADDED Requirements

### Requirement: Persistência bruta antes de qualquer transformação

O pipeline SHALL gravar a resposta da API exatamente como recebida, em JSONL,
antes de aplicar qualquer transformação, para que etapas posteriores possam ser
reexecutadas sem novas chamadas ao servidor da CGU.

#### Scenario: reprocessamento sem rede

- **WHEN** uma etapa posterior do pipeline é reexecutada
- **THEN** ela lê exclusivamente de `pipeline/bruto/conjuntos.jsonl`
- **AND** nenhuma requisição HTTP é feita à API do portal

#### Scenario: resposta preservada na íntegra

- **WHEN** um conjunto é coletado
- **THEN** a linha gravada contém o objeto JSON original sem campos removidos
- **AND** contém os metadados de coleta `coletado_em` e `pagina_origem`

### Requirement: Percurso completo do catálogo

O pipeline SHALL percorrer todas as páginas do endpoint de conjuntos de dados
até a API sinalizar o fim da listagem.

#### Scenario: listagem paginada até o fim

- **WHEN** a coleta é executada sem limite
- **THEN** as páginas são requisitadas em sequência crescente
- **AND** a coleta termina quando a API retorna uma página vazia
- **AND** o total de conjuntos gravados é registrado no log final

#### Scenario: detalhamento dos recursos

- **WHEN** um conjunto é listado
- **THEN** seu detalhe é requisitado para obter a lista de recursos
- **AND** o detalhe é gravado junto do registro do conjunto

### Requirement: Retomada após interrupção

O pipeline SHALL manter um arquivo de progresso e retomar da última página
confirmada quando reexecutado, sem duplicar registros já gravados.

#### Scenario: interrupção no meio da coleta

- **WHEN** a coleta é interrompida na página 40 e reexecutada
- **THEN** ela retoma a partir da página 40
- **AND** nenhum conjunto aparece duas vezes no JSONL

#### Scenario: coleta já concluída

- **WHEN** a coleta é reexecutada após ter concluído
- **THEN** ela encerra imediatamente informando que não há trabalho pendente
- **AND** o JSONL existente permanece inalterado

### Requirement: Amostra dirigida de desenvolvimento

O pipeline SHALL aceitar `--limite N` para coletar no máximo N conjuntos, e
SHALL sempre incluir os identificadores listados em `pipeline/sementes.txt`
quando esse arquivo existir.

#### Scenario: amostra pequena com sementes garantidas

- **WHEN** a coleta é executada com `--limite 500`
- **THEN** no máximo 500 conjuntos são gravados
- **AND** todos os identificadores de `sementes.txt` estão entre eles

#### Scenario: saída separada da base completa

- **WHEN** a coleta usa `--limite`
- **THEN** a saída é gravada em `pipeline/bruto/conjuntos-dev.jsonl`
- **AND** o arquivo da base completa não é sobrescrito

### Requirement: Contenção de taxa e recuo em erro

O pipeline SHALL limitar a concorrência a no máximo 10 requisições simultâneas
e SHALL aplicar recuo exponencial diante de respostas 429 e 5xx.

#### Scenario: limite de taxa atingido

- **WHEN** a API responde 429
- **THEN** a requisição é repetida com recuo exponencial
- **AND** são feitas no máximo 5 tentativas para o mesmo item

#### Scenario: falha persistente não interrompe a coleta

- **WHEN** um item falha após todas as tentativas
- **THEN** o identificador e o motivo são gravados em `pipeline/bruto/falhas.jsonl`
- **AND** a coleta prossegue para os itens restantes
- **AND** o código de saída do processo continua 0

### Requirement: Credencial fornecida por ambiente

O pipeline SHALL ler a chave da API da variável `DADOS_GOV_API_KEY` e SHALL
falhar imediatamente, com mensagem explicativa, quando ela estiver ausente.

#### Scenario: credencial ausente

- **WHEN** o comando é executado sem `DADOS_GOV_API_KEY`
- **THEN** o processo encerra antes de qualquer requisição
- **AND** a mensagem indica como obter a chave no portal
- **AND** o código de saída é diferente de 0

#### Scenario: credencial nunca registrada em log

- **WHEN** qualquer mensagem de log é emitida
- **THEN** o valor da chave não aparece no texto
