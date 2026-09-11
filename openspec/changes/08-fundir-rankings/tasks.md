# Tarefas — fundir rankings

## Distribuição (herdada da mudança 07)

A 07 deixou a busca semântica opcional no serviço porque nenhuma resposta a
usava. A fusão é a primeira a usá-la, e com ela a semântica passa a ser
obrigatória em produção — ver os deltas de `busca-semantica` e
`distribuicao-do-catalogo`.

- [ ] Estender o `catalogo.json` para declarar cada asset com sua soma, e o
      modelo que gerou os vetores
- [ ] Publicar `vectors.npy` e `vectors.json` na mesma release do banco
- [ ] Recusar a publicação quando os vetores não corresponderem ao banco
- [ ] Baixar e conferir os vetores no build da imagem, dizendo qual asset
      divergiu quando algum divergir
- [ ] Aceitar vetores locais no escape de desenvolvimento, e falhar quando só o
      banco for local
- [ ] Instalar o grupo `semantica` (fastembed) na imagem
- [ ] Levar o modelo ONNX fp32 (470 MB) para a imagem no build, sem download em
      tempo de resposta
- [ ] Tornar a semântica obrigatória no serviço: sem vetores, sem runtime ou sem
      modelo, ele não sobe
- [ ] Ajustar os testes da api: hoje o `conftest` esconde os vetores de todos os
      testes, e com a semântica obrigatória a app não subiria neles
- [ ] Publicar a nova release do catálogo e atualizar o `catalogo.json`
- [ ] Construir a imagem baixando banco, vetores e modelo, e confirmar no
      `/saude` a semântica ativa com os 19.958 vetores

## Execução

- [ ] Executar busca léxica e semântica em paralelo
- [ ] Tornar a profundidade de cada ranking configurável
- [ ] Garantir que falha de um ranking não derrube a consulta inteira

## Fusão

- [ ] Implementar RRF com `k` configurável
- [ ] Somar contribuições de documentos presentes nos dois rankings
- [ ] Definir desempate determinístico para pontuações idênticas
- [ ] Retornar a quantidade configurada de finalistas

## Proveniência

- [ ] Registrar, por resultado, os rankings de origem e as posições
- [ ] Expor essa informação ao consumidor da recuperação

## Validação de ganho

- [ ] Executar a avaliação da mudança 06 sobre a fusão
- [ ] Comparar com léxica isolada e semântica isolada
- [ ] Registrar as três medições no histórico
- [ ] Não arquivar a mudança se a fusão for inferior ao melhor isolado

## Verificação

- [ ] Teste: documento presente nos dois rankings supera presente em um só
- [ ] Teste: resultado é determinístico para a mesma consulta e índice
- [ ] Teste: falha da busca semântica degrada para resultado apenas léxico
- [ ] Teste: sem vetores, sem runtime ou sem modelo, o serviço não sobe
- [ ] Teste: vetores com soma divergente reprovam o build
- [ ] Teste: publicação recusa vetores de outra versão do banco
- [ ] `openspec validate --strict`
