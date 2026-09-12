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
# Sem o grupo `dev`, com o grupo `semantica`: a fusão consome a busca semântica
# em toda resposta, então o runtime que vetoriza a pergunta deixou de ser peso
# morto e passou a ser requisito.
RUN uv sync --frozen --no-default-groups --group semantica --no-install-project

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
# São dois artefatos, com soma própria cada um: o banco e o pacote dos vetores
# da busca semântica. Os dois vêm da mesma release, e é isso que impede servir
# vetor de uma versão do catálogo sobre o banco de outra.
#
# Para desenvolver sem publicar release, os dois precisam ser indicados:
#   docker build --build-arg CATALOGO_LOCAL=pipeline/dados/dados.db.gz \
#                --build-arg VETORES_LOCAIS=pipeline/dados/vetores.tar.gz ...
# Indicar só um falha de propósito: misturaria banco local com vetores da
# release. Nesse caminho a soma não é conferida, e o padrão continua sendo o
# publicado, para que o descuido leve ao caminho seguro.
ARG CATALOGO_LOCAL=""
ARG VETORES_LOCAIS=""

COPY catalogo.json /tmp/catalogo.json
COPY api/obter_catalogo.py /tmp/obter_catalogo.py
# O padrão cobre o caso sem artefato local: o COPY não traz nada além do que já
# está no contexto, e o script decide pelos build-args.
COPY ${CATALOGO_LOCAL:-catalogo.json} ${VETORES_LOCAIS:-catalogo.json} /tmp/local/

RUN BANCO_LOCAL=""; VET_LOCAIS=""; \
    if [ -n "$CATALOGO_LOCAL" ]; then \
        BANCO_LOCAL="/tmp/local/$(basename "$CATALOGO_LOCAL")"; \
    fi; \
    if [ -n "$VETORES_LOCAIS" ]; then \
        VET_LOCAIS="/tmp/local/$(basename "$VETORES_LOCAIS")"; \
    fi; \
    python /tmp/obter_catalogo.py /tmp/catalogo.json /dados/dados.db \
        "$BANCO_LOCAL" "$VET_LOCAIS" \
    && rm -rf /tmp/local /tmp/obter_catalogo.py /tmp/catalogo.json

ENV BANCO=/dados/dados.db \
    VETORES=/dados/vectors.npy \
    FASTEMBED_CACHE_PATH=/modelo \
    PATH="/app/.venv/bin:$PATH"

# O modelo entra no build, não na primeira pergunta. Baixá-lo em tempo de
# resposta faria a resposta depender do Hugging Face estar de pé, custaria
# dezenas de segundos à primeira consulta de cada container, e poria em produção
# um arquivo que o build nunca viu. Aqui ele é baixado uma vez e fica na camada.
RUN python -c "from app import semantica; semantica.Vetorizador().consulta('aquecer o cache')" \
    && du -sh /modelo

EXPOSE 8000

# Sem curl na imagem slim, e instalá-lo só para isto engordaria a imagem à toa.
# O healthcheck não depende do modelo: só do catálogo estar legível.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys,json; r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=4)); sys.exit(0 if r.get('ok') else 1)"

CMD ["uvicorn", "app.principal:app", "--host", "0.0.0.0", "--port", "8000"]
