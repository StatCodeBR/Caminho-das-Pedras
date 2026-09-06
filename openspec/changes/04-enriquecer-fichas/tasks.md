# Tarefas — enriquecer fichas

## Esquema

- [ ] Criar tabela `ficha` com resumo, perguntas_json, temas_json,
      abrangencia, granularidade, confianca, texto_indexavel, hash_entrada
- [ ] Definir a lista fechada de temas em `pipeline/temas.py`

## Prompt

- [ ] Escrever o prompt exigindo JSON puro, sem cercas de markdown
- [ ] Incluir instrução explícita de não inferir além dos metadados
- [ ] Incluir a lista fechada de temas no prompt
- [ ] Versionar o prompt em arquivo próprio, para que o hash o inclua

## Execução

- [ ] Montar o texto de entrada de forma determinística por conjunto
- [ ] Calcular hash e consultar o cache antes de submeter
- [ ] Submeter em lote e persistir o identificador do lote
- [ ] Retomar coleta de resultados quando o processo for reexecutado
- [ ] Validar cada resposta com Pydantic, com até 2 tentativas

## Degradação

- [ ] Ficha de fallback com confianca baixa quando o JSON não validar
- [ ] Registrar em log os conjuntos que caíram no fallback
- [ ] Emitir relatório final com distribuição de confiança

## Derivação

- [ ] Gerar `texto_indexavel` por concatenação, sem chamar o modelo
- [ ] Teste: reconstruir o texto indexável não consome tokens

## Verificação

- [ ] Teste: resposta malformada aciona nova tentativa e depois o fallback
- [ ] Teste: item já em cache não gera chamada
- [ ] Teste: mudar o prompt invalida o cache
- [ ] Rodar sobre a amostra de 500 e revisar 20 fichas à mão
- [ ] `openspec validate --strict`
