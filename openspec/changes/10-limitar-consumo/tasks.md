# Tarefas — limitar consumo

## Contador

- [ ] Implementar contador diário de chamadas ao modelo
- [ ] Persistir o contador fora da memória do processo
- [ ] Reiniciar o contador na virada do dia em UTC
- [ ] Teste: reinício do serviço preserva o consumo do dia

## Modo reduzido

- [ ] Alternar automaticamente para template ao atingir o teto
- [ ] Informar o usuário de forma clara e sem jargão
- [ ] Garantir que nenhuma requisição resulte em erro por causa do teto
- [ ] Retornar ao modo pleno na virada do dia

## Limite por origem

- [ ] Implementar janela deslizante por endereço de origem
- [ ] Extrair o endereço real considerando o proxy do Traefik
- [ ] Responder 429 com `Retry-After` ao exceder
- [ ] Não exigir cadastro nem autenticação em nenhum caminho

## Operação

- [ ] Endpoint interno com consumo do dia, teto e modo corrente
- [ ] Registrar em log toda entrada e saída do modo reduzido

## Verificação

- [ ] Teste: teto atingido resulta em resposta por template, não em erro
- [ ] Teste: excesso por origem resulta em 429 com Retry-After
- [ ] Teste: endereço real é lido do cabeçalho de proxy, não do socket
- [ ] `openspec validate --strict`
