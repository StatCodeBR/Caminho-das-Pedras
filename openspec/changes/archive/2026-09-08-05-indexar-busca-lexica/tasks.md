# Tarefas — indexar busca léxica

## Índice

- [x] Criar tabela virtual FTS5 com tokenizador `unicode61 remove_diacritics 2`
- [x] Indexar em colunas separadas: nome, perguntas, resumo, orgao, tags
- [x] Popular a partir das fichas, sem chamar modelo
- [x] Reconstruir de forma idempotente, descartando o índice anterior

## Consulta

- [x] Implementar busca com `bm25()` e pesos por coluna
- [x] Escapar a entrada do usuário para evitar erro de sintaxe do FTS5
- [x] Aplicar penalização a fichas de confiança baixa
- [x] Retornar posição, pontuação e identificador do conjunto

## Ferramenta de inspeção

- [x] Comando `busca.py "pergunta"` exibindo os 10 primeiros com pontuação
- [x] Exibir por que cada resultado apareceu, mostrando os termos casados

## Verificação

- [x] Teste: consulta com acento encontra registro sem acento e vice-versa
- [x] Teste: aspas e operadores digitados pelo usuário não quebram a consulta
- [x] Teste: reconstrução do índice não altera resultados
- [x] Teste: sigla de órgão recupera o conjunto correto
- [x] Teste: assunto ausente do catálogo retorna vazio, não ruído
- [x] `openspec validate --strict`
