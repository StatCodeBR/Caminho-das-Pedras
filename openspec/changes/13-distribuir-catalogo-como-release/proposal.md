# Distribuir o catálogo como release verificada

## Why

O `dados.db` está versionado no Git porque o Dokploy constrói a imagem a partir
de um clone do repositório, e o Dockerfile copia o banco de dentro dele. Isso
funcionou com 4,8 MB e já não funciona: a coleta parcial levou o arquivo a
26,7 MB, e o catálogo completo dá cerca de 155 MB — acima do limite de 100 MB
por arquivo que o GitHub recusa.

O problema não é só o teto. SQLite não comprime bem entre versões: as páginas se
reorganizam a cada escrita, então o Git guarda cada recoleta inteira, para
sempre. Cinco atualizações do catálogo completo somariam quase um gigabyte de
histórico que ninguém vai querer clonar.

Banco de dados gerado não é código-fonte. Ele é resultado de uma execução, tem
procedência própria e ciclo de vida próprio — e é isso que uma release expressa
melhor que um commit.

## What Changes

- O `dados.db` e os demais artefatos gerados do pipeline saem do rastreio do Git
  e entram no `.gitignore`.
- O banco passa a ser publicado como **asset de release**, comprimido.
- O repositório passa a guardar apenas a **soma de verificação** e o
  **manifesto** do catálogo esperado: quem gerou, quando, quantos conjuntos,
  quantas fichas e por qual modelo.
- O `Dockerfile` da `api` baixa o artefato durante o build e **falha se a soma
  não conferir**.
- Novo alvo para publicar uma release do catálogo a partir de uma execução local
  do pipeline.
- **BREAKING**: quem clonar o repositório não terá mais um `dados.db` pronto.
  Rodar o pipeline ou baixar a release passa a ser passo explícito.

## Capabilities

### New Capabilities

- `distribuicao-do-catalogo`: como o artefato gerado pelo pipeline chega à
  imagem de produção — publicação, verificação de integridade e reprodutibilidade
  da imagem.

### Modified Capabilities

<!-- Nenhuma. A containerização nunca teve spec própria; esta mudança cobre
     apenas a parte de distribuição do artefato, e o restante segue como dívida
     registrada. -->

## Impact

- `.gitignore`, `pipeline/dados/` e `api/Dockerfile`.
- O build da imagem passa a exigir rede, e a falhar quando a release não estiver
  publicada — o que é preferível a construir uma imagem com catálogo errado.
- Publicar uma release exige credencial do GitHub. O `gh` não está instalado no
  ambiente de desenvolvimento; a publicação usará `curl` com token.
- O histórico do Git deixa de crescer com o catálogo.

## Fora de escopo

- Reescrever o histórico para remover os `dados.db` já commitados. Os arquivos
  passados continuam no histórico; só param de crescer daqui em diante.
- Migrar a `api` para imagem publicada em registry, que resolve outro problema
  (tempo de build) e continua em aberto.
- O `vectors.npy` da mudança 07, que terá o mesmo tratamento quando existir.
