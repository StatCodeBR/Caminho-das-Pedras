# Tarefas — operar sem chave

## Núcleo

- [ ] Implementar `busca.rs` com FTS5 via rusqlite com feature bundled
- [ ] Confirmar que o SQLite compilado inclui FTS5
- [ ] Implementar embedding da pergunta com fastembed-rs sobre ONNX
- [ ] Implementar produto escalar contra a matriz de vetores
- [ ] Implementar fusão RRF entre os dois rankings

## Resposta sem modelo

- [ ] Montar resposta por template a partir da ficha, com formatos e link
- [ ] Sinalizar recursos indisponíveis em vez de omiti-los
- [ ] Emitir o campo de origem indicando correspondência direta

## Transporte

- [ ] Expor comando `perguntar` via invoke
- [ ] Usar Channel para emitir fragmentos, mantendo o mesmo contrato da web
- [ ] Abstrair o transporte no frontend para servir web e desktop

## Primeira execução

- [ ] Abrir direto na tela de perguntas, sem assistente de configuração
- [ ] Exibir aviso discreto e dispensável sobre o que a chave acrescenta
- [ ] Garantir que nenhuma ação exija chave para acessar dados

## Verificação

- [ ] Teste: aplicativo sem chave responde perguntas normalmente
- [ ] Teste: nenhuma chamada de rede é feita quando não há chave
- [ ] Teste: busca funciona com a máquina desconectada
- [ ] `openspec validate --strict`
