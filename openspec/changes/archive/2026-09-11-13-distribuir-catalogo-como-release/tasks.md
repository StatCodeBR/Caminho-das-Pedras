# Tarefas — distribuir o catálogo como release

## Tirar do Git

- [x] Remover `pipeline/dados/dados.db` do rastreio, preservando o arquivo local
- [x] Ignorar os artefatos gerados do pipeline: bancos, `.npy`, JSONL bruto
- [x] Remover a exceção `!pipeline/dados/dados.db` e o comentário que a explicava

## Manifesto e soma

- [x] Definir o formato do manifesto: versão, data, conjuntos, fichas, modelo
- [x] Gerar manifesto e soma SHA-256 a partir de um `dados.db` local
- [x] Versionar manifesto e soma; o artefato nunca

## Publicação

- [x] Alvo que comprime o banco, gera manifesto e soma, e publica a release
- [x] Publicar por `curl` com token do ambiente, sem `gh`
- [x] Nunca imprimir o token em log ou mensagem de erro
- [x] Recusar publicação se a árvore do Git estiver suja

## Build da imagem

- [x] Baixar o artefato da release declarada durante o build
- [x] Conferir a soma e falhar quando divergir, dizendo esperada e recebida
- [x] Falhar quando o download falhar, dizendo qual versão era esperada
- [x] Descomprimir com o Python da própria imagem, sem instalar pacote
- [x] Aceitar artefato local no lugar do download, para desenvolvimento

## Documentação

- [x] README: como obter o catálogo depois de clonar
- [x] `.env.example`: a variável do token de publicação
- [x] Registrar em `docs/limitacoes-conhecidas.md` que o histórico ainda carrega
      os bancos antigos

## Verificação

- [x] Teste: soma divergente reprova o artefato
- [x] Teste: manifesto reflete o conteúdo real do banco
- [x] Construir a imagem com artefato local e confirmar que sobe
- [x] Construir a imagem baixando a release e confirmar que sobe
- [x] Confirmar que `git status` fica limpo após rodar o pipeline
- [x] `openspec validate --changes --strict`
