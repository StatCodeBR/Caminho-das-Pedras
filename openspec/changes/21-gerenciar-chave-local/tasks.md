# Tarefas — gerenciar chave local

## Armazenamento

- [ ] Implementar `chave.rs` com a crate keyring
- [ ] Definir identificador de serviço estável para o cofre
- [ ] Detectar ausência de Secret Service no Linux e degradar para memória
- [ ] Nunca gravar a chave em arquivo de configuração ou log

## Fronteira com o WebView

- [ ] Expor comando de escrita da chave, sem comando de leitura
- [ ] Expor consulta booleana de existência e os últimos caracteres
- [ ] Auditar o código para garantir que a chave não é serializada ao frontend

## Validação

- [ ] Validar a chave com requisição mínima ao salvar
- [ ] Traduzir erros para linguagem comum: inválida, sem crédito, sem conexão
- [ ] Não bloquear o salvamento quando a falha for apenas de conexão

## Remoção

- [ ] Implementar remoção da chave com efeito imediato
- [ ] Confirmar retorno ao modo de recuperação após remoção

## Transparência de custo

- [ ] Contar chamadas da sessão e exibir na interface
- [ ] Informar na tela de configuração que o consumo é cobrado pelo provedor

## Verificação

- [ ] Teste: chave não aparece em nenhuma mensagem de log
- [ ] Teste: falha da API recai no modo de recuperação sem erro fatal
- [ ] Teste: remoção da chave devolve o aplicativo ao estado sem credencial
- [ ] `openspec validate --strict`
