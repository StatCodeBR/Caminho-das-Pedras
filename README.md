# Caminho das Pedras

Assistente de descoberta de dados públicos brasileiros. A pessoa pergunta em
linguagem comum onde encontrar um dado; o sistema busca no catálogo do Portal
Brasileiro de Dados Abertos e responde com os conjuntos, os formatos e os links.

Um pipeline offline coleta e enriquece o catálogo, gerando `dados.db`. Um
serviço de consulta lê esse artefato, recupera as fichas relevantes e responde.
O modelo de linguagem escreve o catálogo uma vez, offline; em tempo de resposta
ele só redige, e apenas quando necessário.

## Depois de clonar, o catálogo não vem junto

O repositório **não versiona** o `dados.db`. Ele tem 186 MB — acima do limite de
100 MB por arquivo do GitHub — e banco gerado não é código-fonte: o Git guardaria
cada versão inteira para sempre, porque o SQLite reorganiza as páginas a cada
escrita e não delta-comprime.

O que o repositório guarda é o [`catalogo.json`](catalogo.json): a versão da
release, a soma SHA-256 e a procedência — quantos conjuntos, quantas fichas e
qual modelo as escreveu. Os bytes ficam na release.

**Para obter o catálogo:**

```sh
just catalogo-baixa
```

Baixa o artefato declarado, confere a soma e descomprime em
`pipeline/dados/dados.db`. Se a soma divergir, ele recusa — catálogo trocado
responde com aparência de normalidade, e o defeito só apareceria depois.

A alternativa é gerar o seu, com `just dados-full`. Leva horas e gasta dinheiro
no enriquecimento; só faz sentido se você for mexer no pipeline.

## Rodar

```sh
just setup        # dependências dos três projetos
just catalogo-baixa
just tudo-stub    # API e interface, sem gastar token
```

`just tudo-stub` responde com texto pré-gravado e não exige credencial. Para
respostas de verdade, `just api` e `just web` em terminais separados, com
`ANTHROPIC_API_KEY` no `.env`.

## Atualizar o catálogo publicado

```sh
just dados-full          # coleta, normaliza, enriquece, indexa
just catalogo            # comprime e gera o manifesto, sem publicar
just catalogo-publica    # publica a release (exige GITHUB_TOKEN)
git commit catalogo.json
```

O commit final é o que importa: a imagem serve a versão declarada no
`catalogo.json`, nunca "a mais recente". Publicar catálogo novo não muda nenhum
build existente, e trocar o catálogo de uma imagem exige um commit com autor e
data.

## Estrutura

| | |
|---|---|
| `pipeline/` | coleta, normalização, enriquecimento, índice e avaliação |
| `api/` | serviço de resposta em FastAPI |
| `web/` | interface em SvelteKit |
| `openspec/` | especificações e mudanças; nada se implementa sem mudança aprovada |
| `avaliacao/` | conjunto de avaliação curado — [leia o README de lá](avaliacao/README.md) antes de editar |
| `docs/limitacoes-conhecidas.md` | o que não funciona, e por quê |

`pipeline/` e `api/` são projetos Python separados de propósito: o primeiro
carrega torch, o segundo não pode carregar.

Comandos em `just --list`. Convenções e regras do projeto em
[CLAUDE.md](CLAUDE.md).
