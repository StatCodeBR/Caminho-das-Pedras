# Interface. Duas etapas: a primeira instala tudo e compila, a segunda leva só
# o resultado — a imagem final não carrega o toolchain nem as dependências de
# desenvolvimento.
FROM node:22-slim AS build

ENV LANG=C.UTF-8
WORKDIR /app

# `corepack` usa a versão de pnpm declarada no package.json quando houver;
# instalar pnpm por fora arriscaria divergir do lockfile.
RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build


FROM node:22-slim AS run

ENV LANG=C.UTF-8 \
    NODE_ENV=production \
    PORT=3000
WORKDIR /app

# O adapter-node entrega um servidor com as dependências já embutidas, então a
# imagem final não precisa de node_modules nem de gerenciador de pacote.
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json

# Roda sem privilégio: a imagem do Node já traz o usuário `node`.
USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "build/index.js"]
