# Limitações conhecidas

Registro honesto do que o sistema ainda erra, e por que decidimos conviver com
cada coisa em vez de corrigi-la. Serve ao critério de transparência: quem avalia
o projeto deve encontrar os defeitos aqui antes de encontrá-los no uso.

Cada item diz o que acontece, o tamanho do estrago e a razão da decisão. Item
sem razão registrada é dívida escondida, não limitação assumida.

---

## 1. Confiança alta sobre fonte que se contradiz

**O que acontece.** A trava de confiança rebaixa a ficha quando a descrição de
origem é curta demais (menos de 60 caracteres). Ela não alcança o caso em que a
descrição é longa **e** contradiz o título.

**Caso observado.** `aerodromos---lista-de-aerodromos-publicos-v2`, da ANAC: o
título diz "Aeródromos **Públicos**", a primeira linha da descrição diz "Dados
cadastrais de aeródromos **privados**". A descrição tem 1.160 caracteres, então
a trava não age. O modelo resolveu a contradição pelo título, marcou `alta`, e
resumiu como "Relação oficial de aeródromos públicos do Brasil" — quando os
únicos recursos do conjunto são *Posições de Estacionamento*.

**Por que não construímos uma trava.** A trava de comprimento funciona porque é
objetiva: conta caracteres, não julga. Detectar contradição interna exige
julgamento, e o único julgador disponível seria o próprio modelo — pedir a ele
que avalie a confiabilidade da fonte é exatamente onde ele já falhou. Seria
complexidade alta com retorno baixo.

**Por que o dano é contido.** Uma ficha otimista sobre aeródromos ainda é
recuperada por buscas sobre aeródromos, e o conjunto *é* sobre aeródromos. O
usuário chega numa página do assunto certo com dados mais limitados do que o
resumo prometia. Isso é decepção, não desinformação — e a camada de conferência,
que mostra os recursos reais e seus links, existe para que ele veja o que há de
fato antes de confiar.

**Diferença para o caso que travamos.** Na faixa de 20 a 40 caracteres o modelo
inventava *conteúdo que não existe* — indicadores de *near miss* num conjunto
que só tem taxa de mortalidade materna. Isso é falso positivo permanente no
índice. Aqui ele exagera o alcance de conteúdo que existe. As duas falhas não
têm o mesmo peso.

---

## 2. Erro de digitação do modelo entra no índice

**O que acontece.** O `texto_indexavel` é concatenação determinística do resumo e
das perguntas. Não há passo de revisão ortográfica entre o que o modelo escreve e
o que vai para a busca, então um typo do modelo vira termo indexado.

**Caso observado.** Na ficha do conjunto de aeródromos, a pergunta "onde posso
encontrar informações sobre os **aeroporlos** e aeródromos de uma região?".

**Tamanho do estrago.** Pequeno e assimétrico: o termo errado não é procurado por
ninguém, então ele não gera falso positivo — apenas ocupa espaço no índice. A
pergunta segue legível para quem a lê.

**Decisão.** Corrigir é barato e não exige modelo: um passo de normalização
ortográfica sobre o texto derivado resolveria. Fica anotado como trabalho futuro,
fora do caminho crítico.

---

## 3. A calibração de confiança depende do provedor

**O que acontece.** O nível de `confianca` que o modelo declara não é comparável
entre fornecedores. Medido sobre as mesmas 10 entradas:

| descrição de origem | Cohere `command-a` | Anthropic `haiku-4-5` |
|---|---|---|
| vazia | `baixa` | `media` |
| 26–27 caracteres | `media` | `media` |
| 92–321 caracteres | `alta` | `media` |
| mais de 1.100 caracteres | `alta` | `alta` |

A inversão é o achado: a Haiku é **mais conservadora com metadado rico** e **mais
confiante com metadado vazio** — o oposto da Cohere.

**Consequência.** A confiança declarada pelo modelo não é uma medida estável do
catálogo. Comparar a distribuição de confiança entre duas execuções de provedores
diferentes não diz nada sobre a qualidade dos dados; diz sobre o temperamento do
modelo. A coluna `modelo` da tabela `ficha` existe para que essa comparação nunca
seja feita às cegas.

**Por que isso não nos preocupa.** A trava mecânica é justamente o que torna a
medida comparável de novo, porque ela não consulta o modelo: nos dois conjuntos
sem descrição alguma, a Haiku declarou `media` e a trava rebaixou para `baixa`
nos dois. Ela pegou 4 de 4 dos conjuntos abaixo do limiar. A proteção foi
construída contra a alucinação da Cohere numa faixa estreita e acabou cobrindo
uma falha diferente, de outro fornecedor — que é o argumento a favor de travar no
pipeline em vez de instruir no prompt.

---

## 4. Os slugs do portal não são deriváveis do título

**O que acontece.** O portal gera o identificador removendo acentos em vez de
transliterá-los, preservando espaços duplos como hífens duplos, e distingue
maiúsculas de minúsculas. "Lista de Espera  Cirúrgica" vira
`lista-de-espera--cirrgica-`, com dois hífens e sem o `ú`.

**Consequência.** Um identificador escrito à mão quase nunca resolve. Não há
regra segura para construí-lo a partir do título: ele precisa vir da API.

**Como isso já custou.** Quatro das 67 sementes estavam malformadas e falhavam
com 404 — duas por caixa alta, uma por espaço duplo, uma com fragmento de URL
colado no valor. Os conjuntos correspondentes nunca entraram na amostra, e como
as quatro eram citadas em `perguntas.csv`, mediriam recall artificialmente baixo
por erro de digitação, não por falha da busca. Corrigido em 2026-09-07; as 67
sementes resolvem.
