# Serviço de resposta. O contexto de build é a raiz do repositório, não `api/`,
# porque a imagem precisa do `catalogo.json`, que declara qual catálogo servir.
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
# Só as dependências do projeto, sem grupo nenhum — nem `dev`, nem `semantica`.
# O runtime da busca semântica entra na imagem com a fusão (mudança 08); até lá
# ela está desligada em produção e ele seria peso morto.
RUN uv sync --frozen --no-default-groups --no-install-project

COPY api/app ./app

# O banco entra na imagem: o serviço lê um artefato pronto e imutável, gerado
# offline. Não há volume porque não há escrita — trocar o catálogo é publicar
# uma imagem nova, o que também dá rastreabilidade de qual catálogo respondeu.
#
# Ele não vem do repositório: o `dados.db` tem 186 MB e o GitHub recusa arquivo
# acima de 100 MB. O que o repositório guarda é o `catalogo.json`, com a versão
# da release e a soma SHA-256; os bytes vêm da release e são conferidos aqui.
# A versão é fixa, nunca "a mais recente" — reconstruir este commit amanhã
# precisa produzir a mesma imagem.
#
# Para desenvolver sem publicar release:
#   docker build --build-arg CATALOGO_LOCAL=pipeline/dados/dados.db.gz ...
# Nesse caminho a soma não é conferida, e o padrão continua sendo o publicado.
ARG CATALOGO_LOCAL=""

COPY catalogo.json /tmp/catalogo.json
COPY api/obter_catalogo.py /tmp/obter_catalogo.py
# O `.` cobre os dois casos: sem CATALOGO_LOCAL o COPY não traz nada além do
# que já está no contexto, e o script decide pelo build-arg.
COPY ${CATALOGO_LOCAL:-catalogo.json} /tmp/local/

RUN CAMINHO=""; \
    if [ -n "$CATALOGO_LOCAL" ]; then \
        CAMINHO="/tmp/local/$(basename "$CATALOGO_LOCAL")"; \
    fi; \
    python /tmp/obter_catalogo.py /tmp/catalogo.json /dados/dados.db "$CAMINHO" \
    && rm -rf /tmp/local /tmp/obter_catalogo.py /tmp/catalogo.json

ENV BANCO=/dados/dados.db \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Sem curl na imagem slim, e instalá-lo só para isto engordaria a imagem à toa.
# O healthcheck não depende do modelo: só do catálogo estar legível.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys,json; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=4)); sys.exit(0 if r.get('ok') else 1)"

CMD ["uvicorn", "app.principal:app", "--host", "0.0.0.0", "--port", "8000"]
