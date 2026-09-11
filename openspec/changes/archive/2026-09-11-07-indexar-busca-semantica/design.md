# Design — busca semântica

## Decisão: dois runtimes para o mesmo modelo

O pipeline usa sentence-transformers, que traz PyTorch junto e pesa quase dois
gigabytes. Isso é irrelevante numa máquina de desenvolvimento e inaceitável no
serviço de consulta, onde inflaria a imagem e o consumo de memória.

O serviço usa um runtime ONNX enxuto sobre o mesmo modelo. O código executado é
diferente; os vetores produzidos precisam ser equivalentes. Daí o requisito de
paridade: se divergirem, a busca não quebra de forma visível — ela apenas
degrada, silenciosamente, e o erro seria atribuído ao prompt ou aos dados.

## Decisão: prefixos obrigatórios

A família de modelos escolhida foi treinada com prefixos que distinguem
documento de consulta. Indexar sem `passage:` ou consultar sem `query:` produz
resultados visivelmente piores, e o modo de falha é sutil o bastante para passar
despercebido.

O código não deve permitir que a chamada aconteça sem prefixo. Ele é
responsabilidade do módulo de embedding, nunca de quem o chama.

## Decisão: normalizar na geração

Os vetores são normalizados para norma unitária no momento da gravação. Assim a
similaridade de cosseno vira produto escalar puro, e a consulta é uma
multiplicação de matriz sem divisão nem raiz.

## Decisão: força bruta, sem índice aproximado

Dezenove mil vetores de 384 dimensões ocupam cerca de 29 MB em float32, e o
produto escalar contra todos eles responde em poucos milissegundos. Um índice
aproximado acrescentaria dependência, parâmetros de ajuste e erro de recuperação
para resolver um problema que não existe nesta escala.

Se o catálogo crescer uma ordem de grandeza, a decisão se revisita.

## Decisão: ordem dos vetores é contrato

O arquivo binário não guarda identificadores. A correspondência entre linha e
conjunto vem de uma lista de identificadores gravada junto, na mesma ordem.
Qualquer regeneração precisa produzir as duas coisas ao mesmo tempo — vetores
órfãos de uma versão anterior do banco apontariam para conjuntos errados sem
nenhum sintoma óbvio.

Por isso a versão do catálogo cobre os dois artefatos em conjunto.

## Riscos aceitos

Modelos multilíngues pequenos são mais fracos em português que em inglês. A
mitigação é que o texto indexado foi escrito por um modelo forte, em português
claro — o embedding trabalha sobre texto de boa qualidade, não sobre metadado
burocrático. A avaliação da mudança 06 dirá se é suficiente.

## Decisão: o modelo entra no fastembed como modelo customizado

O fastembed não traz o e5 pequeno na sua lista nativa — o único e5 multilíngue
dele é o grande, com 1024 dimensões e 2,2 GB. O repositório do modelo publica um
export ONNX próprio (`onnx/model.onnx`, 470 MB), e o fastembed o aceita por
`add_custom_model`, com pooling por média, que é o do sentence-transformers.

A paridade medida entre os dois runtimes foi de cosseno 1,000000 em todos os
textos de referência, inclusive o mais longo do corpus.

## Decisão: semântica opcional no serviço até a fusão

A imagem de produção não tem os vetores (31 MB) nem o modelo ONNX (470 MB), e
nenhuma resposta usa a busca semântica antes da fusão da mudança 08. Tornar os
vetores obrigatórios agora faria o próximo deploy não subir, ou faria a imagem
crescer meio gigabyte sem ganho visível para ninguém.

O serviço, então, confere os vetores quando eles existem e recusa iniciar se
estiverem inconsistentes; sem eles, sobe com a semântica desligada e informa isso
no `/saude`. Levar vetores e modelo até a imagem — o vetor como asset da release,
com soma própria, e o modelo baixado no build — passa a ser tarefa da 08, que é
quando a produção passa a precisar deles.

## Medições

Sobre as 19.958 fichas, numa GTX 1650 de 4 GB:

| | tempo | taxa |
|---|---:|---:|
| projeção a partir de 200 fichas | 143 s | 139/s |
| geração real | 132 s | 151/s |
| mesma geração em CPU, projetada | ~620 s | 32/s |

`vectors.npy`: 30.655.616 bytes (19.958 × 384 × 4, mais 128 de cabeçalho). O
texto indexável tem 139 tokens em média e 258 no máximo; nenhum passa do limite de
512 do modelo, então nada é truncado.

Contra a linha de base léxica, nas 14 perguntas curadas:

| | recall@5 | recall@10 | MRR |
|---|---:|---:|---:|
| léxica | 50,0% | 57,1% | 0,427 |
| semântica | 42,9% | 57,1% | 0,392 |
| união das duas | 64,3% | 64,3% | — |

Sozinha, a semântica não supera a léxica. As duas erram em lugares diferentes —
a semântica resgata "internadas na UTI" (7º → 1º) e "enchente registrada" (fora
→ 1º); a léxica vence "quantos hospitais" (1º contra 7º) —, e a união mostra o
teto que a fusão pode buscar.

