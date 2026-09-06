# Tarefas — cachear respostas

## Versionamento do catálogo

- [ ] Gerar identificador de versão ao construir `dados.db`
- [ ] Expor a versão no endpoint de saúde
- [ ] Incluir a versão na chave do cache

## Consulta

- [ ] Reaproveitar o embedding já calculado para a recuperação
- [ ] Comparar contra as perguntas em cache por produto escalar
- [ ] Servir a resposta armazenada acima do limiar configurado
- [ ] Registrar origem "cache" na telemetria

## Escrita

- [ ] Armazenar pergunta, embedding, resposta e versão do catálogo
- [ ] Não cachear respostas de "não encontrei"
- [ ] Não cachear respostas descartadas pela guarda de URL
- [ ] Não cachear respostas do modo reduzido
- [ ] Descartar as entradas mais antigas ao atingir o tamanho máximo

## Invalidação

- [ ] Ignorar entradas de versões anteriores do catálogo
- [ ] Teste: catálogo novo não serve resposta antiga

## Verificação

- [ ] Teste: pergunta reformulada acima do limiar serve do cache
- [ ] Teste: acerto de cache não incrementa o contador do teto diário
- [ ] Teste: pergunta próxima porém distinta não colide no limiar configurado
- [ ] `openspec validate --strict`
