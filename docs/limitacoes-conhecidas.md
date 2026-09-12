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

## 4. A pontuação léxica não distingue "é do assunto" de "responde à pergunta"

**O que acontece.** O BM25 mede sobreposição de vocabulário. Uma pergunta pode
casar fortemente com um conjunto do tema certo que não contém o dado pedido, e a
pontuação alta não sinaliza nenhuma diferença.

**Caso observado.** "quanto ganha um professor em média no Brasil" — que o
catálogo não responde — recupera `indicadores-educacionais-da-educao-bsica` com
19,18, acima de conjuntos legítimos de outras perguntas. Com o limiar de template
em 18, essa pergunta sairia por correspondência direta: uma resposta confiante,
montada da ficha, sobre um conjunto que não traz salário nenhum.

**Consequência para o roteamento.** O caminho de template não tem como julgar
pertinência: ele confia na pontuação. Na amostra de 505 fichas isso se contornava
com um limiar de 20, e das 14 perguntas 12 iam ao modelo e 2 saíam por template,
ambas corretas.

**No catálogo completo essa calibração ruiu.** Com 19.958 fichas as pontuações
subiram, mais conjuntos ultrapassam 20, e o template passou a disparar sobre
casamento acidental: "minha cidade já teve enchente registrada" era respondida,
sem chamar o modelo, com um conjunto de depósitos de patentes por cidade — que
casou em "cidade". Remedido, nenhum limiar resolve:

| limiar | templates | certos | errados |
|---:|---:|---:|---:|
| 20 | 5 | 2 | 3 |
| 25 | 2 | 1 | 1 |
| 30 | 1 | 0 | 1 |
| 35 | 0 | 0 | 0 |

A pontuação não separa certo de errado: os acertos vão de 18,2 a 29,7 e os erros
de 14,6 a 33,0 — a maior pontuação das catorze é um erro. A margem sobre o
segundo também não separa. O limiar ficou em 35, acima de qualquer pontuação
observada, o que na prática desliga o template neste catálogo. É mais caro e é o
certo: gastar token à toa custa centavos, servir resposta confiante e errada
custa a confiança.

**Onde isso é tratado.** No prompt de resposta, que instrui explicitamente a
dizer que não encontrou quando as fichas não respondem — inclusive com o exemplo
do conjunto sobre hospitais que não traz a contagem pedida. É julgamento, e só o
modelo pode fazê-lo.

**Limitação da calibração.** Os limiares foram medidos sobre 14 perguntas. É
amostra pequena demais para ser lei, e o de relevância é pior: 12 foi escolhido
para excluir uma pontuação observada de 11,7, num único caso — calibração sobre
n=1 dentro de n=14. Revisar quando o conjunto de avaliação crescer.

## 5. Os slugs do portal não são deriváveis do título

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

## 6. A frequência de termo mede o autor do corpus, não a língua

**O que acontece.** O filtro de termo comum decide o que descartar da pergunta
pela fração de fichas em que a palavra aparece. Com 505 fichas essa medida
separava limpo palavra de função de palavra de assunto. Com 19.958 o vão fechou,
e três causas distintas se somaram.

A primeira foi corrigida: os rótulos do vocabulário controlado de temas, que a
indexação escreve na coluna `tags`, inflavam palavras de assunto até acima do
corte — `financas` em 40,2% das fichas com 100% disso vindo de tags, `economia`
em 40,5% com 99%. A frequência passou a ser medida só nas colunas de texto
natural, e `financas` caiu para 0,2%.

**As duas que continuam.**

*Cacoete do modelo.* `longo` aparece em 25,5% das fichas, 4.377 delas com a
palavra numa pergunta de exemplo: é "ao longo do tempo", escrito milhares de
vezes pelo mesmo modelo com o mesmo prompt. Um corpus de 19.455 documentos de
autoria única tem tiques que a estatística lê como gramática. Só se resolve
variando prompt ou modelo, e o efeito é pequeno: são palavras que de fato não
discriminam.

*Concentração real do catálogo.* `banco` em 22,9% e `central` em 21,5%, quase
tudo em nome de órgão — o BCB publica mesmo um quinto do acervo. Aqui o filtro
está certo em agir, mas quem busca "banco central" recebe pouco. É limite da
recuperação léxica, e é parte do que a busca semântica da mudança 07 existe para
cobrir.

**Por que não se conserta com o limiar.** A varredura de 0,10 a 0,50 sobre o
conjunto de avaliação não tem joelho: de 0,15 a 0,50 ganham-se 7 termos úteis ao
custo de 28 de ruído, em progressão sem ponto de inflexão. Distribuição sem vão
não se conserta movendo a linha de corte.

## 7. O caminho de ausência envelhece com o catálogo

**O que acontece.** Três das 14 perguntas de avaliação estão anotadas com
`nenhum` — não há resposta no catálogo. Com 505 fichas as três retornavam vazio
e contavam como acerto. Com 19.958 as três retornam resultados, e contam como
erro.

**Mas não é ruído.** "quantos hospitais tem na minha cidade" devolve
`hospitais-e-leitos` com pontuação 23,6, casando em `hospitais`. "quanto ganha um
professor em média no Brasil" devolve `indicadores-educacionais-da-educao-bsica`
com 17,2. São conjuntos que não existiam na amostra de 505 e agora existem.

**Consequência para a medição.** A queda de recall@5 de 57,1% para 35,7% ao
passar de 505 para 19.958 fichas é, em três de três casos, exatamente essas
perguntas mudando de acerto para erro — 8 acertos viraram 5, e as três que
mudaram são as três de ausência. A recuperação não piorou; a anotação envelheceu.

**O que fazer.** As anotações `nenhum` precisam de revisão humana contra o
catálogo completo. Decidir se `hospitais-e-leitos` responde "quantos hospitais
tem na minha cidade" é curadoria, não medição, e o conjunto de avaliação é
curado à mão de propósito.

## 8. O histórico do Git ainda carrega os bancos antigos

**O que acontece.** O `dados.db` saiu do rastreio e o catálogo passou a ser
distribuído como release. Isso impede o repositório de **continuar** crescendo,
mas não desfaz o que já está lá: as versões commitadas antes da mudança 13
seguem no histórico, e um `git clone` as baixa todas.

**Por que não foi reescrito.** Reescrever histórico de repositório já publicado
invalida todo clone existente e todo commit referenciado em qualquer lugar — e o
ganho é espaço em disco, não correção. O peso já foi pago; o que importava era
parar a hemorragia.

**Quando revisitar.** Se o clone ficar lento a ponto de atrapalhar, aí vale um
`git filter-repo` planejado, com aviso a quem tiver clone e reescrita em uma
janela combinada. Até lá é custo conhecido, não defeito.

**O que não muda.** Nada disso afeta o que a imagem serve: ela baixa a release
declarada no `catalogo.json` e confere a soma. O histórico é peso de clone, não
fonte de catálogo.
