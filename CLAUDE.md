# Caminho das Pedras

Assistente de descoberta de dados públicos brasileiros. O usuário pergunta em
linguagem comum onde encontrar um dado; o sistema busca no catálogo do Portal
Brasileiro de Dados Abertos e responde com os conjuntos, os formatos e os links.

## Processo de trabalho

Este projeto usa OpenSpec 1.7.0. **Não implemente nada sem uma mudança aprovada
em `openspec/changes/`.**

O ciclo é: `/opsx:propose` → revisão humana da spec → `/opsx:apply` →
`openspec validate --changes --strict` → `/opsx:archive`.

O formato de spec e os comandos vêm das skills OpenSpec instaladas em `.claude/`
e de `openspec/config.yaml`. Não existe `openspec/AGENTS.md` nesta versão.

Uma mudança por vez. Não comece a próxima antes de arquivar a anterior.

## Escopo atual: versão web

A entrega em curso é a **aplicação web**: pipeline em Python, serviço FastAPI e
interface SvelteKit, publicados em containers via Dokploy.

As mudanças **20, 21 e 22 pertencem a uma trilha desktop com Tauri e núcleo em
Rust, e estão adiadas**. Elas ficam versionadas como intenção de produto, mas
**não devem ser aplicadas** sem decisão explícita. Se uma tarefa parecer exigir
Rust, keyring, rusqlite ou comandos `invoke`, pare e pergunte — você está na
trilha errada.

## Arquitetura em uma frase

Um pipeline offline coleta e enriquece o catálogo, gerando `dados.db` e
`vectors.npy`. Um serviço de consulta lê esses artefatos, recupera as fichas
relevantes e responde. O modelo de linguagem escreve o catálogo uma vez, offline;
em tempo de resposta ele só redige, e apenas quando necessário.

## Regras invioláveis

1. **Nada de LLM em tempo de resposta sem necessidade.** Se a recuperação é
   conclusiva, a resposta sai por template, sem consumir tokens.
2. **Ancoragem estrita.** A resposta só pode citar conjuntos e URLs presentes nas
   fichas recuperadas. Resposta com URL fabricada é descartada, não corrigida.
3. **O pipeline nunca roda em produção.** Ele é offline, na máquina do mantenedor.
4. **`pipeline/` e `api/` são projetos Python separados.** O primeiro carrega
   torch; o segundo não pode carregar. Nunca unifique as dependências.
5. **Datas sempre em UTC** no armazenamento. Fuso só na apresentação.
6. **Segredos nunca em log, arquivo versionado ou resposta.**

## Ambiente

Desenvolvimento em NixOS via `nix develop` ou direnv. Produção em containers
Debian e Alpine. Nunca copie `.venv/` ou `node_modules/` para dentro de imagem —
eles contêm caminhos do `/nix/store`.

Comandos usuais estão no `justfile`. Prefira `just <alvo>` a comandos soltos.

**No `web/` use pnpm, nunca npm.** O projeto foi inicializado com pnpm e tem
`pnpm-lock.yaml`; misturar os dois quebra a resolução de dependências.

Use `--limite 500` no pipeline durante o desenvolvimento. Nunca rode a coleta ou
o enriquecimento completos sem pedido explícito: consomem horas e dinheiro.

## Stack

- Pipeline: Python, httpx, tenacity, pydantic, sentence-transformers
- Consulta: Python, FastAPI, SQLite com FTS5, fastembed, numpy
- Interface: SvelteKit com Svelte 5 (runes), shadcn-svelte, Tailwind
- Deploy: Docker via Dokploy, atrás de Traefik

Ao mexer em biblioteca cuja API você não tem certeza, consulte o Context7 antes
de escrever código. Svelte 5 com runes e shadcn-svelte mudaram bastante e são
onde o risco de código desatualizado é maior.

## Estilo

Código e identificadores em português quando forem do domínio (conjunto,
recurso, ficha, saude), em inglês quando forem técnicos genéricos.

Mensagens ao usuário final em português simples, sem jargão. O público inclui
pessoas que nunca ouviram falar em API, CSV ou dados abertos.
