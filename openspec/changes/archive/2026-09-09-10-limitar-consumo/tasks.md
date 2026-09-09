# Tarefas — limitar consumo

## Contador

- [x] Implementar contador diário de chamadas ao modelo
- [x] Persistir o contador fora da memória do processo
- [x] Reiniciar o contador na virada do dia em UTC
- [x] Teste: reinício do serviço preserva o consumo do dia

## Modo reduzido

- [x] Alternar automaticamente para template ao atingir o teto
- [x] Informar o usuário de forma clara e sem jargão
- [x] Garantir que nenhuma requisição resulte em erro por causa do teto
- [x] Retornar ao modo pleno na virada do dia

## Limite por origem

- [x] Implementar janela deslizante por endereço de origem
- [x] Extrair o endereço real considerando o proxy do Traefik
- [x] Responder 429 com `Retry-After` ao exceder
- [x] Não exigir cadastro nem autenticação em nenhum caminho

## Operação

- [x] Endpoint interno com consumo do dia, teto e modo corrente
- [x] Registrar em log toda entrada e saída do modo reduzido

## Verificação

- [x] Teste: teto atingido resulta em resposta por template, não em erro
- [x] Teste: excesso por origem resulta em 429 com Retry-After
- [x] Teste: endereço real é lido do cabeçalho de proxy, não do socket
- [x] `openspec validate --strict`
