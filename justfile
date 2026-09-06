default:
    @just --list

# --- setup ---------------------------------------------------------------

setup:
    cd pipeline && uv sync
    cd api && uv sync
    cd web && pnpm install

# --- desenvolvimento -----------------------------------------------------

api:
    cd api && uv run uvicorn app.main:app --reload --reload-dir app --port 8000

api-stub:
    cd api && MODO_STUB=1 uv run uvicorn app.main:app --reload --reload-dir app --port 8000

web:
    cd web && pnpm dev

# --- pipeline ------------------------------------------------------------

dados-dev:
    cd pipeline && uv run python coleta.py --limite 500
    cd pipeline && uv run python normaliza.py
    cd pipeline && uv run python indexa.py

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

paridade:
    docker compose -f compose.dev.yml up --build
