# Tarefas — verificar saúde dos recursos

## Esquema

- [ ] Migrar `recurso` acrescentando `status_http`, `classe_saude`,
      `checado_em`, `latencia_ms`
- [ ] Criar índice por `classe_saude` para consulta rápida na busca

## Verificação

- [ ] Implementar checagem com HEAD e queda para GET com Range quando o
      servidor não aceitar HEAD
- [ ] Definir timeout de 10 segundos por requisição
- [ ] Classificar em disponivel, indisponivel, instavel, nao_verificado
- [ ] Seguir redirecionamentos e registrar o status final

## Educação de rede

- [ ] Limitar a 2 requisições simultâneas por host
- [ ] Limitar a 20 requisições simultâneas no total
- [ ] Enviar User-Agent identificando o projeto e um contato

## Reverificação

- [ ] Implementar `--idade-maxima DIAS` para checar apenas o que está vencido
- [ ] Implementar `--somente-falhas` para reprocessar indisponíveis

## Verificação

- [ ] Teste: servidor que rejeita HEAD é verificado por GET
- [ ] Teste: timeout resulta em instavel, não em indisponivel
- [ ] Teste: recurso sem URL fica nao_verificado sem gerar requisição
- [ ] `openspec validate --strict`
