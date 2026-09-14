# Tarefas — fundir rankings

## Distribuição (herdada da mudança 07)

A 07 deixou a busca semântica opcional no serviço porque nenhuma resposta a
usava. A fusão é a primeira a usá-la, e com ela a semântica passa a ser
obrigatória em produção — ver os deltas de `busca-semantica` e
`distribuicao-do-catalogo`.

- [x] Estender o `catalogo.json` para declarar cada asset com sua soma, e o
      modelo que gerou os vetores
- [x] Publicar `vectors.npy` e `vectors.json` na mesma release do banco
- [x] Recusar a publicação quando os vetores não corresponderem ao banco
- [x] Baixar e conferir os vetores no build da imagem, dizendo qual asset
      divergiu quando algum divergir
- [x] Aceitar vetores locais no escape de desenvolvimento, e falhar quando só o
      banco for local
- [x] Instalar o grupo `semantica` (fastembed) na imagem
- [x] Levar o modelo ONNX fp32 (470 MB) para a imagem no build, sem download em
      tempo de resposta
- [x] Tornar a semântica obrigatória no serviço: sem vetores, sem runtime ou sem
      modelo, ele não sobe
- [x] Ajustar os testes da api: hoje o `conftest` esconde os vetores de todos os
      testes, e com a semântica obrigatória a app não subiria neles
- [x] Publicar a nova release do catálogo e atualizar o `catalogo.json`
- [x] Construir a imagem baixando banco, vetores e modelo, e confirmar no
      `/saude` a semântica ativa com os 19.958 vetores

## Execução

- [x] Executar busca léxica e semântica em paralelo
- [x] Tornar a profundidade de cada ranking configurável
- [x] Garantir que falha de um ranking não derrube a consulta inteira

## Fusão

- [x] Implementar RRF com `k` configurável
- [x] Somar contribuições de documentos presentes nos dois rankings
- [x] Definir desempate determinístico para pontuações idênticas
- [x] Retornar a quantidade configurada de finalistas

## Roteamento

A ordenação passa a vir do RRF, cuja pontuação fica em torno de 0,03 — e os
limiares foram calibrados na escala do BM25. Medido, aplicá-los à pontuação da
fusão faria zero das catorze perguntas sustentarem resposta.

- [x] Rotear pela pontuação léxica, não pela do RRF
- [x] Aceitar concordância entre rankings como evidência de pertinência
- [x] Impedir que resultado achado só pela semântica dispare template
- [x] Teste: a pontuação do RRF não é confundida com a léxica
- [x] Teste: concordância sustenta resposta com léxica fraca

## Proveniência

- [x] Registrar, por resultado, os rankings de origem e as posições
- [x] Expor essa informação ao consumidor da recuperação

## Validação de ganho

- [x] Executar a avaliação da mudança 06 sobre a fusão
- [x] Comparar com léxica isolada e semântica isolada
- [x] Registrar as três medições no histórico
- [x] Não arquivar a mudança se a fusão for inferior ao melhor isolado

## Verificação

- [x] Teste: documento presente nos dois rankings supera presente em um só
- [x] Teste: resultado é determinístico para a mesma consulta e índice
- [x] Teste: falha da busca semântica degrada para resultado apenas léxico
- [x] Teste: sem vetores, sem runtime ou sem modelo, o serviço não sobe
- [x] Teste: vetores com soma divergente reprovam o build
- [x] Teste: publicação recusa vetores de outra versão do banco
- [x] `openspec validate --strict`
