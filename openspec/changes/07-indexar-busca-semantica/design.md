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
