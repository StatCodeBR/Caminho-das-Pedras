default:
    @just --list

# --- setup ---------------------------------------------------------------

setup:
    cd pipeline && uv sync
    cd api && uv sync
    cd web && pnpm install

# --- desenvolvimento -----------------------------------------------------

# O módulo é app.principal, não app.main.
api:
    cd api && uv run uvicorn app.principal:app --reload --reload-dir app --port 8000

# A API sem consumir token nem exigir credencial da Anthropic.
api-stub:
    cd api && MODO_STUB=1 uv run uvicorn app.principal:app --reload --reload-dir app --port 8000

# Só a interface. Precisa da API já rodando em outro terminal.
web:
    cd web && API_URL=http://localhost:8000 pnpm run dev

# Tudo de uma vez, sem gastar nada: API em stub e interface, num terminal só.
# Ctrl-C derruba os dois.
[no-cd]
tudo-stub:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{justfile_directory()}}"
    ( cd api && MODO_STUB=1 uv run uvicorn app.principal:app --port 8000 ) &
    api=$!
    trap 'kill $api 2>/dev/null || true' EXIT INT TERM
    until curl -sf http://localhost:8000/saude >/dev/null; do sleep 0.5; done
    echo "API no ar em http://localhost:8000"
    cd web && API_URL=http://localhost:8000 pnpm run dev

# --- pipeline ------------------------------------------------------------

# Gasta dinheiro: o enriquecimento dos 500 custa cerca de US$ 0,90 quando o
# cache está frio. Repetido sem mudar prompt nem metadados, sai de graça.
dados-dev:
    cd pipeline && uv run python coleta.py --limite 500
    cd pipeline && uv run python normaliza.py
    cd pipeline && uv run python enriquece.py --limite 500
    cd pipeline && uv run python indexa.py

# Busca por linha de comando, para inspeção. Uso: just busca "sua pergunta"
busca PERGUNTA:
    cd pipeline && uv run python busca.py "{{PERGUNTA}}"

dados-full:
    cd pipeline && uv run python coleta.py
    cd pipeline && uv run python normaliza.py
    cd pipeline && uv run python saude.py
    cd pipeline && uv run python enriquece.py
    cd pipeline && uv run python indexa.py

# --- qualidade -----------------------------------------------------------

avalia:
    cd pipeline && uv run python avalia.py

spec:
    openspec validate --changes --strict

testes:
    cd pipeline && uv run pytest -q
    cd api && uv run pytest -q
    cd web && pnpm run test

paridade:
    docker compose -f compose.dev.yml up --build
