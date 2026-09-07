# Normalizar o catálogo em banco relacional

## Por que

O JSONL bruto é fiel à API, mas é inconsultável: campos aninhados, nomes
inconsistentes entre registros e ausência de tipos. Todas as etapas seguintes —
saúde dos recursos, enriquecimento, indexação e busca — precisam de acesso
tabular e estável.

O metadado de portal público é irregular por natureza: descrições vazias, datas
em formatos variados, recursos sem URL. Uma ingestão que aborta no primeiro
registro estranho inviabilizaria o projeto. A normalização precisa ser tolerante
e auditável: o que não entra, entra em quarentena com o motivo registrado.

## O que muda

- Novo comando `normaliza.py` que lê o JSONL e materializa `dados.db` (SQLite).
- Duas tabelas: `conjunto` e `recurso`.
- Validação com Pydantic, com quarentena para registros rejeitados.
- Relatório de ingestão ao final, com contagens e taxa de rejeição.

## Fora de escopo

- Índices de busca (mudanças 05 e 07).
- Campos derivados de enriquecimento (mudança 04), cuja tabela é criada depois.

## Impacto

- Cria `pipeline/dados/dados.db`, artefato somente leitura para as etapas
  seguintes e para a imagem de produção.
- Cria `pipeline/quarentena.jsonl`, não versionado.
