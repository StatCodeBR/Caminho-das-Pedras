# Tarefas — normalizar catálogo

## Modelagem

- [x] Definir modelos Pydantic `Conjunto` e `Recurso` com campos opcionais
      onde a API é irregular
- [x] Escrever o DDL das tabelas `conjunto` e `recurso` com chave estrangeira
- [x] Definir a estratégia de upsert por identificador do portal

## Ingestão

- [x] Ler o JSONL em fluxo, sem carregar tudo em memória
- [x] Validar cada registro e gravar rejeitados em `quarentena.jsonl`
      com o motivo
- [x] Gravar datas em ISO 8601 marcadas como UTC, sem deslocar o instante
- [x] Normalizar formato dos recursos para maiúsculas, sem espaço sobrando
      nem ponto inicial (CSV, JSON)
- [x] Preservar a URL da página do conjunto no portal

## Idempotência

- [x] Usar `INSERT ... ON CONFLICT DO UPDATE` por identificador
- [x] Remover recursos órfãos de conjuntos reingeridos
- [x] Teste: rodar duas vezes produz contagens idênticas

## Relatório

- [x] Emitir ao final: conjuntos ingeridos, recursos ingeridos, rejeitados,
      taxa de rejeição
- [x] Encerrar com código diferente de 0 se a taxa de rejeição passar de 5%

## Verificação

- [x] Teste: registro sem descrição é ingerido normalmente
- [x] Teste: registro sem identificador vai para quarentena
- [x] Teste: reingestão não duplica recursos
- [x] `openspec validate --changes --strict`
