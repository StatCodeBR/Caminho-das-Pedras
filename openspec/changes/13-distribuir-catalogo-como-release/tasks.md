# Tarefas — distribuir o catálogo como release

## Tirar do Git

- [x] Remover `pipeline/dados/dados.db` do rastreio, preservando o arquivo local
- [x] Ignorar os artefatos gerados do pipeline: bancos, `.npy`, JSONL bruto
- [x] Remover a exceção `!pipeline/dados/dados.db` e o comentário que a explicava

## Manifesto e soma

- [ ] Definir o formato do manifesto: versão, data, conjuntos, fichas, modelo
- [ ] Gerar manifesto e soma SHA-256 a partir de um `dados.db` local
- [ ] Versionar manifesto e soma; o artefato nunca

## Publicação

- [ ] Alvo que comprime o banco, gera manifesto e soma, e publica a release
- [ ] Publicar por `curl` com token do ambiente, sem `gh`
- [ ] Nunca imprimir o token em log ou mensagem de erro
- [ ] Recusar publicação se a árvore do Git estiver suja

## Build da imagem

- [ ] Baixar o artefato da release declarada durante o build
- [ ] Conferir a soma e falhar quando divergir, dizendo esperada e recebida
- [ ] Falhar quando o download falhar, dizendo qual versão era esperada
- [ ] Descomprimir com o Python da própria imagem, sem instalar pacote
- [ ] Aceitar artefato local no lugar do download, para desenvolvimento

## Documentação

- [ ] README: como obter o catálogo depois de clonar
- [ ] `.env.example`: a variável do token de publicação
- [ ] Registrar em `docs/limitacoes-conhecidas.md` que o histórico ainda carrega
      os bancos antigos

## Verificação

- [ ] Teste: soma divergente reprova o artefato
- [ ] Teste: manifesto reflete o conteúdo real do banco
- [ ] Construir a imagem com artefato local e confirmar que sobe
- [ ] Construir a imagem baixando a release e confirmar que sobe
- [ ] Confirmar que `git status` fica limpo após rodar o pipeline
- [ ] `openspec validate --changes --strict`
