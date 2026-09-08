# Serviço de resposta. O contexto de build é a raiz do repositório, não `api/`,
# porque a imagem precisa do `dados.db` que o pipeline produz em `pipeline/`.
#
# Python 3.12 e não 3.11: `api/pyproject.toml` declara `requires-python >=3.12`
# e o `uv sync --frozen` recusaria a versão anterior.
FROM python:3.12-slim

# O catálogo é todo em português: sem UTF-8 explícito, acento vira erro de
# codificação na leitura do banco e na resposta ao usuário.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

WORKDIR /app

# Dependências antes do código: mudar um arquivo do app não invalida a camada
# de instalação, que é a cara.
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api/app ./app

# O banco entra na imagem: o serviço lê um artefato pronto e imutável, gerado
# offline. Não há volume porque não há escrita — trocar o catálogo é publicar
# uma imagem nova, o que também dá rastreabilidade de qual catálogo respondeu.
COPY pipeline/dados/dados.db /dados/dados.db

ENV BANCO=/dados/dados.db \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Sem curl na imagem slim, e instalá-lo só para isto engordaria a imagem à toa.
# O healthcheck não depende do modelo: só do catálogo estar legível.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys,json; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=4)); sys.exit(0 if r.get('ok') else 1)"

CMD ["uvicorn", "app.principal:app", "--host", "0.0.0.0", "--port", "8000"]
