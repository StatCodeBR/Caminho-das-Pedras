# Tarefas — indexar busca semântica

## Geração

- [ ] Implementar módulo de embedding que aplica os prefixos internamente
- [ ] Gerar vetores para o texto indexável de todas as fichas
- [ ] Normalizar para norma unitária antes de gravar
- [ ] Gravar `vectors.npy` e a lista de identificadores na mesma ordem

## Consulta

- [ ] Implementar embedding de consulta com o runtime ONNX leve
- [ ] Implementar similaridade por produto escalar contra a matriz
- [ ] Retornar identificador, posição e pontuação, no mesmo formato da léxica

## Paridade

- [ ] Teste comparando vetores dos dois runtimes para o mesmo texto
- [ ] Exigir similaridade acima de 0,999 entre eles
- [ ] Executar esse teste antes de qualquer publicação de catálogo

## Integridade

- [ ] Validar na carga que o número de vetores corresponde ao de fichas
- [ ] Recusar iniciar quando vetores e banco forem de versões diferentes

## Verificação

- [ ] Teste: consulta sem prefixo é impossível pela interface do módulo
- [ ] Teste: vetores normalizados têm norma 1 dentro da tolerância
- [ ] Rodar a avaliação da mudança 06 e comparar com a linha de base léxica
- [ ] `openspec validate --strict`
