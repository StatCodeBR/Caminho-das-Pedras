# Tarefas — verificar saúde dos recursos

## Esquema

- [x] Migrar `recurso` acrescentando `status_http`, `classe_saude`,
      `checado_em`, `latencia_ms`
- [x] Criar índice por `classe_saude` para consulta rápida na busca

## Verificação

- [x] Implementar checagem com HEAD e queda para GET com Range quando o
      servidor recusar o método (405, 501 ou 403)
- [x] Definir timeout de 10 segundos por requisição
- [x] Classificar em disponivel, indisponivel, instavel, nao_verificado
- [x] Seguir redirecionamentos e registrar o status final

## Educação de rede

- [x] Limitar a 2 requisições simultâneas por host
- [x] Limitar a 20 requisições simultâneas no total
- [x] Enviar User-Agent identificando o projeto e um contato

## Reverificação

- [x] Implementar `--idade-maxima DIAS` para checar apenas o que está vencido
- [x] Implementar `--somente-falhas` para reprocessar indisponíveis

## Verificação

- [x] Teste: servidor que rejeita HEAD por 405 ou por 403 é verificado por GET
- [x] Teste: timeout resulta em instavel, não em indisponivel
- [x] Teste: recurso sem URL fica nao_verificado sem gerar requisição
- [x] `openspec validate --changes --strict`
