# Tarefas — coletar catálogo

## Preparação

- [x] Criar `pipeline/pyproject.toml` com httpx, tenacity, pydantic, typer
- [x] Rodar `uv sync` e confirmar que o interpretador é o do flake
- [x] Criar `pipeline/.env.example` com `DADOS_GOV_API_KEY=`
- [x] Adicionar `pipeline/bruto/` e `pipeline/.env` ao `.gitignore`

## Cliente da API

- [x] Implementar cliente httpx assíncrono com header `chave-api-dados-abertos`
- [x] Aplicar tenacity com recuo exponencial para 429 e 5xx, máximo 5 tentativas
- [x] Limitar concorrência com semáforo de 10
- [x] Garantir que a chave nunca é incluída em mensagens de log

## Coleta

- [x] Implementar percurso paginado da listagem de conjuntos
- [x] Buscar o detalhe de cada conjunto e anexar ao registro
- [x] Gravar JSONL com `coletado_em` e `pagina_origem`
- [x] Gravar falhas em `falhas.jsonl` sem abortar o processo
- [x] Confirmar página vazia por repetição; encerrar direto em página parcial

## Retomada

- [x] Manter `pipeline/bruto/progresso.json` com a última página confirmada
- [x] Retomar a partir do progresso na reexecução
- [x] Encerrar cedo quando a coleta já estiver concluída

## Amostra

- [x] Implementar `--limite N`
- [x] Ler `sementes.txt` e resolver cada identificador no endpoint de detalhe
- [x] Direcionar a saída para `conjuntos-dev.jsonl` quando houver limite

## Verificação

- [x] Teste: reexecução não duplica registros
- [x] Teste: 429 aciona recuo e a coleta continua
- [x] Teste: página vazia intermitente não encerra a coleta
- [x] Teste: ausência de credencial encerra com código diferente de 0
- [x] Executar `--limite 500` de ponta a ponta e conferir a contagem
- [x] `openspec validate --changes --strict`
