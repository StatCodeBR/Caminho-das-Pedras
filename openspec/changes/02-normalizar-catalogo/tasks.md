# Tarefas — normalizar catálogo

## Modelagem

- [ ] Definir modelos Pydantic `Conjunto` e `Recurso` com campos opcionais
      onde a API é irregular
- [ ] Escrever o DDL das tabelas `conjunto` e `recurso` com chave estrangeira
- [ ] Definir a estratégia de upsert por identificador do portal

## Ingestão

- [ ] Ler o JSONL em fluxo, sem carregar tudo em memória
- [ ] Validar cada registro e gravar rejeitados em `quarentena.jsonl`
      com o motivo
- [ ] Normalizar datas para UTC ISO 8601
- [ ] Normalizar formato dos recursos para maiúsculas sem espaços (CSV, JSON)
- [ ] Preservar a URL da página do conjunto no portal

## Idempotência

- [ ] Usar `INSERT ... ON CONFLICT DO UPDATE` por identificador
- [ ] Remover recursos órfãos de conjuntos reingeridos
- [ ] Teste: rodar duas vezes produz contagens idênticas

## Relatório

- [ ] Emitir ao final: conjuntos ingeridos, recursos ingeridos, rejeitados,
      taxa de rejeição
- [ ] Encerrar com código diferente de 0 se a taxa de rejeição passar de 5%

## Verificação

- [ ] Teste: registro sem descrição é ingerido normalmente
- [ ] Teste: registro sem identificador vai para quarentena
- [ ] Teste: reingestão não duplica recursos
- [ ] `openspec validate --strict`
