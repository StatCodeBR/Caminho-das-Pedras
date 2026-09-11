# Tarefas — fundir rankings

## Distribuição (herdada da mudança 07)

A 07 deixou a busca semântica opcional no serviço: sem vetores, ele sobe com ela
desligada. A fusão é a primeira a consumi-la em produção, então é aqui que
vetores e modelo precisam chegar à imagem. A spec desta mudança ainda não cobre
isso e precisa ser emendada antes da implementação.

- [ ] Publicar `vectors.npy` e `vectors.json` na release, com soma própria no
      `catalogo.json`
- [ ] Baixar e conferir os vetores no build da imagem, como já se faz com o banco
- [ ] Levar o modelo ONNX (470 MB) para a imagem no build, sem download em
      tempo de resposta
- [ ] Tornar os vetores obrigatórios no serviço: ausentes, ele não sobe

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
- [ ] `openspec validate --strict`
