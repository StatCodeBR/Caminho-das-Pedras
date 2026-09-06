# Design — enriquecimento das fichas

## Decisão: enriquecer offline, nunca em tempo de resposta

O enriquecimento roda no pipeline e o resultado é persistido. Em tempo de
resposta o sistema apenas recupera fichas prontas. Isso mantém a latência
previsível, o custo fixo e o comportamento reproduzível — a mesma pergunta
recupera a mesma ficha hoje e daqui a um mês.

## Decisão: processamento em lote

Como não há usuário esperando, o enriquecimento usa a API de lotes com o modelo
mais barato da família. A alternativa sequencial síncrona seria mais simples de
escrever, mas custa mais e demora mais para dezenas de milhares de itens.

Consequência: o comando precisa lidar com submissão, espera e coleta posterior
dos resultados, incluindo o caso de o processo ser interrompido no meio da
espera. O identificador do lote é persistido para permitir retomada.

## Decisão: cache com chave de conteúdo

A chave é o hash SHA-256 do texto exato enviado ao modelo. Isso significa que
alterar o prompt invalida todo o cache — o que é correto, porque a saída antiga
foi produzida sob outra instrução. Alterar apenas o metadado de um conjunto
invalida somente aquele item.

O cache vive em `pipeline/cache/` como arquivos JSON, fora do Git.

## Decisão: confiança explícita em vez de recusa

Um conjunto com metadados pobres não é descartado. Ele recebe `confianca:
"baixa"`, é enriquecido apenas com o que se pode afirmar do título e do órgão, e
a busca o despriorizará. Descartar significaria esconder do usuário um dado que
existe; inventar significaria mentir. A confiança é o meio-termo honesto e
alimenta a métrica de qualidade do catálogo.

## Decisão: o texto indexável é derivado, não gerado

O campo `texto_indexavel` é a concatenação determinística de nome, resumo,
perguntas, órgão e tags. Não é uma nova chamada ao modelo. Assim, reconstruir os
índices nunca exige reprocessar nada.

## Riscos aceitos

O modelo pode gerar perguntas que o conjunto responde apenas parcialmente. Isso
degrada a precisão da busca, mas não produz afirmação falsa ao usuário, porque a
resposta final (mudança 09) é ancorada nos metadados originais e sempre entrega
o link para a fonte. A avaliação da mudança 06 mede esse efeito.
