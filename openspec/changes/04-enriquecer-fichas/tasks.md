# Tarefas — enriquecer fichas

## Esquema

- [x] Criar tabela `ficha` com resumo, perguntas_json, temas_json,
      abrangencia, granularidade, confianca, texto_indexavel, hash_entrada
- [x] Definir a lista fechada de temas em `pipeline/temas.py`

## Prompt

- [x] Escrever o prompt exigindo JSON puro, sem cercas de markdown
- [x] Incluir instrução explícita de não inferir além dos metadados
- [x] Incluir a lista fechada de temas no prompt
- [x] Versionar o prompt em arquivo próprio, para que o hash o inclua

## Provedor

- [x] Interface única de provedor, com lote como capacidade opcional
- [x] Gravar em `ficha.modelo` quem escreveu, no formato provedor/modelo
- [x] Incluir o identificador do provedor e do modelo no hash do cache

## Execução

- [x] Montar o texto de entrada de forma determinística por conjunto
- [x] Calcular hash e consultar o cache antes de submeter
- [x] Submeter em lote e persistir o identificador do lote
- [x] Retomar coleta de resultados quando o processo for reexecutado
- [x] Validar cada resposta com Pydantic, com até 2 tentativas

## Degradação

- [x] Ficha de fallback com confianca baixa quando o JSON não validar
- [x] Rebaixar confiança para baixa quando a descrição de origem for curta
- [x] Registrar em log os conjuntos que caíram no fallback
- [x] Emitir relatório final com distribuição de confiança

## Derivação

- [x] Gerar `texto_indexavel` por concatenação, sem chamar o modelo
- [x] Teste: reconstruir o texto indexável não consome tokens

## Verificação

- [x] Teste: resposta malformada aciona nova tentativa e depois o fallback
- [x] Teste: item já em cache não gera chamada
- [x] Teste: mudar o prompt invalida o cache
- [x] Teste: descrição curta força confiança baixa, e a trava nunca promove
- [x] Rodar sobre a amostra de 500 e revisar 20 fichas à mão
- [x] `openspec validate --changes --strict`
