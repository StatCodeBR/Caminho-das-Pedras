# Resposta ancorada

## MODIFIED Requirements

### Requirement: Resposta determinística quando a recuperação é conclusiva

A API SHALL responder sem chamar modelo de linguagem quando o primeiro
resultado superar o limiar de pontuação configurado e a margem sobre o segundo
colocado exceder o mínimo configurado.

Os limiares SHALL ser aplicados à pontuação do ranking léxico, e não à pontuação
da fusão. A fusão ordena por posição, e a pontuação que ela produz não exprime
pertinência: medida sobre o conjunto de avaliação, ela fica entre 0,0236 e
0,0328 tanto nos acertos quanto nos erros. Aplicar a ela os limiares calibrados
na escala do BM25 faria o serviço declarar ausência em todas as perguntas.

Um conjunto encontrado apenas pela busca semântica NÃO SHALL disparar a resposta
por template. O template afirma correspondência direta, e isso exige casamento
literal — que é justamente o que a pontuação léxica mede.

#### Scenario: correspondência direta

- **WHEN** o primeiro resultado está acima do limiar na escala léxica
- **AND** a margem sobre o segundo excede o mínimo
- **THEN** a resposta é montada por template a partir da ficha
- **AND** nenhum token é consumido
- **AND** a resposta declara que foi obtida por correspondência direta

#### Scenario: recuperação ambígua

- **WHEN** os primeiros resultados têm pontuações próximas
- **THEN** o modelo é acionado para redigir a resposta

#### Scenario: primeiro colocado veio só da busca semântica

- **WHEN** o primeiro resultado não aparece no ranking léxico
- **THEN** a resposta é redigida pelo modelo, nunca por template

#### Scenario: limiares configuráveis

- **WHEN** as variáveis de limiar e margem são alteradas
- **THEN** o roteamento passa a usar os novos valores sem alteração de código

## ADDED Requirements

### Requirement: Concordância entre rankings sustenta resposta

A API SHALL considerar pertinente o conjunto que aparecer em mais de um ranking
da recuperação, mesmo que sua pontuação léxica fique abaixo do limiar de
relevância.

Concordância entre dois métodos independentes é evidência por si, e não depende
de escala calibrada. A alternativa — um limiar sobre a similaridade semântica —
foi medida e descartada: o cosseno ficou entre 0,84 e 0,90 em todas as perguntas
de avaliação, tanto nas que acertam quanto nas que erram, e não separa nada.

Sem esta regra, a pergunta que só a busca semântica responde seria declarada
ausente, e o ganho da fusão se perderia exatamente onde ele existe.

#### Scenario: conjunto achado pelos dois rankings

- **WHEN** um conjunto aparece no ranking léxico e no semântico
- **AND** sua pontuação léxica está abaixo do limiar de relevância
- **THEN** ele é considerado pertinente e entra no contexto da resposta

#### Scenario: conjunto fraco em um ranking só

- **WHEN** um conjunto aparece em apenas um ranking
- **AND** sua pontuação léxica está abaixo do limiar de relevância
- **THEN** ele não sustenta resposta

#### Scenario: nenhum conjunto pertinente

- **WHEN** nenhum conjunto alcança o limiar léxico nem aparece em dois rankings
- **THEN** a resposta declara que nada foi encontrado
