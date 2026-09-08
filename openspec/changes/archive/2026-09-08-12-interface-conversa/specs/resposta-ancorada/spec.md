# Resposta ancorada

## MODIFIED Requirements

### Requirement: Transparência sobre a origem da resposta

Toda resposta SHALL declarar como foi produzida, entre correspondência direta,
redação por modelo ou modo reduzido.

O evento final SHALL descrever cada conjunto recuperado com identificador,
título, órgão, confiança da ficha, endereço da página no portal, formatos e
recursos com sua situação de disponibilidade, e SHALL incluir a data de
atualização dos dados e a data de atualização dos metadados como campos
distintos.

As duas datas são distintas porque significam coisas diferentes: um conjunto
cujo registro foi editado ontem e cujos dados são de 2019 não é um conjunto
atualizado ontem. Fundi-las num campo só obrigaria quem consome a escolher entre
omitir a informação ou anunciar um frescor que o dado não tem. Ambas podem estar
ausentes, e ausente é um valor legítimo — no catálogo atual a data dos dados
falta em cerca de um quinto dos conjuntos.

#### Scenario: origem informada ao usuário

- **WHEN** qualquer resposta é entregue
- **THEN** o evento SSE final contém o campo de origem
- **AND** a interface pode exibi-lo ao usuário

#### Scenario: origem registrada em telemetria

- **WHEN** qualquer resposta é entregue
- **THEN** origem, latência e número de fichas recuperadas são registrados

#### Scenario: datas no resumo do conjunto

- **WHEN** o evento final descreve um conjunto recuperado
- **THEN** ele traz a data de atualização dos dados e a dos metadados em campos
      separados
- **AND** cada campo ausente é declarado como ausente, não omitido nem
      substituído pelo outro
