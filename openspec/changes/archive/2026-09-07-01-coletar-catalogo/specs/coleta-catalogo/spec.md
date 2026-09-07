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
até confirmar o fim da listagem. Como a API responde com página vazia de forma
intermitente, o pipeline SHALL tratar página vazia como sinal ambíguo e SHALL
confirmá-lo antes de encerrar.

#### Scenario: listagem paginada até o fim

- **WHEN** a coleta é executada sem limite
- **THEN** as páginas são requisitadas em sequência crescente
- **AND** o total de conjuntos gravados é registrado no log final

#### Scenario: página incompleta encerra a listagem

- **WHEN** uma página retorna menos itens que o tamanho de página da API
- **THEN** os itens são gravados normalmente
- **AND** a coleta encerra sem pedir a página seguinte

#### Scenario: página vazia é confirmada antes de encerrar

- **WHEN** uma página retorna vazia
- **THEN** a mesma página é repetida até 6 vezes com recuo
- **AND** a coleta prossegue se qualquer repetição trouxer itens
- **AND** o fim só é declarado quando a página seguinte também vier vazia

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
SHALL sempre incluir os conjuntos identificados em `pipeline/sementes.txt`
quando esse arquivo existir. Cada linha é um identificador do portal — o slug
que aparece na URL do conjunto ou o UUID — resolvido diretamente no endpoint
de detalhe, sem passar pela busca.

#### Scenario: amostra pequena com sementes garantidas

- **WHEN** a coleta é executada com `--limite 500` e `sementes.txt` existe
- **THEN** os conjuntos das sementes são coletados antes da listagem geral
- **AND** todos os identificadores que resolvem estão entre os gravados
- **AND** no máximo 500 conjuntos são gravados
- **AND** o restante da amostra vem da listagem paginada

#### Scenario: semente que não resolve não interrompe a amostra

- **WHEN** um identificador de semente não é encontrado no portal
- **THEN** o identificador e o motivo são gravados em `falhas.jsonl`
- **AND** a coleta prossegue para as demais sementes

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
