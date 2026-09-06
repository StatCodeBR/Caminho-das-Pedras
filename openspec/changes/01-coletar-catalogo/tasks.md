# Tarefas — coletar catálogo

## Preparação

- [ ] Criar `pipeline/pyproject.toml` com httpx, tenacity, pydantic, typer
- [ ] Rodar `uv sync` e confirmar que o interpretador é o do flake
- [ ] Criar `pipeline/.env.example` com `DADOS_GOV_API_KEY=`
- [ ] Adicionar `pipeline/bruto/` e `pipeline/.env` ao `.gitignore`

## Cliente da API

- [ ] Implementar cliente httpx assíncrono com header `chave-api-dados-abertos`
- [ ] Aplicar tenacity com recuo exponencial para 429 e 5xx, máximo 5 tentativas
- [ ] Limitar concorrência com semáforo de 10
- [ ] Garantir que a chave nunca é incluída em mensagens de log

## Coleta

- [ ] Implementar percurso paginado da listagem de conjuntos
- [ ] Buscar o detalhe de cada conjunto e anexar ao registro
- [ ] Gravar JSONL com `coletado_em` e `pagina_origem`
- [ ] Gravar falhas em `falhas.jsonl` sem abortar o processo

## Retomada

- [ ] Manter `pipeline/bruto/progresso.json` com a última página confirmada
- [ ] Retomar a partir do progresso na reexecução
- [ ] Encerrar cedo quando a coleta já estiver concluída

## Amostra

- [ ] Implementar `--limite N`
- [ ] Ler `sementes.txt` e garantir inclusão dos identificadores listados
- [ ] Direcionar a saída para `conjuntos-dev.jsonl` quando houver limite

## Verificação

- [ ] Teste: reexecução não duplica registros
- [ ] Teste: 429 aciona recuo e a coleta continua
- [ ] Teste: ausência de credencial encerra com código diferente de 0
- [ ] Executar `--limite 500` de ponta a ponta e conferir a contagem
- [ ] `openspec validate --strict`
