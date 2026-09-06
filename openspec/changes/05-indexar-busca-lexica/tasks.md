# Tarefas — indexar busca léxica

## Índice

- [ ] Criar tabela virtual FTS5 com tokenizador `unicode61 remove_diacritics 2`
- [ ] Indexar em colunas separadas: nome, perguntas, resumo, orgao, tags
- [ ] Popular a partir das fichas, sem chamar modelo
- [ ] Reconstruir de forma idempotente, descartando o índice anterior

## Consulta

- [ ] Implementar busca com `bm25()` e pesos por coluna
- [ ] Escapar a entrada do usuário para evitar erro de sintaxe do FTS5
- [ ] Aplicar penalização a fichas de confiança baixa
- [ ] Retornar posição, pontuação e identificador do conjunto

## Ferramenta de inspeção

- [ ] Comando `busca.py "pergunta"` exibindo os 10 primeiros com pontuação
- [ ] Exibir por que cada resultado apareceu, mostrando os termos casados

## Verificação

- [ ] Teste: consulta com acento encontra registro sem acento e vice-versa
- [ ] Teste: aspas e operadores digitados pelo usuário não quebram a consulta
- [ ] Teste: reconstrução do índice não altera resultados
- [ ] Teste: sigla de órgão recupera o conjunto correto
- [ ] `openspec validate --strict`
