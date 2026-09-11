# Tarefas — indexar busca semântica

## Geração

- [x] Implementar módulo de embedding que aplica os prefixos internamente
- [x] Gerar vetores para o texto indexável de todas as fichas
- [x] Normalizar para norma unitária antes de gravar
- [x] Gravar `vectors.npy` e a lista de identificadores na mesma ordem

## Consulta

- [x] Implementar embedding de consulta com o runtime ONNX leve
- [x] Implementar similaridade por produto escalar contra a matriz
- [x] Retornar identificador, posição e pontuação, no mesmo formato da léxica

## Paridade

- [x] Teste comparando vetores dos dois runtimes para o mesmo texto
- [x] Exigir similaridade acima de 0,999 entre eles
- [x] Executar esse teste antes de qualquer publicação de catálogo

## Integridade

- [x] Validar na carga que o número de vetores corresponde ao de fichas
- [x] Recusar iniciar quando vetores e banco forem de versões diferentes
- [x] Subir com a semântica desligada quando os vetores não existem, informando
      no `/saude`

## Verificação

- [x] Teste: consulta sem prefixo é impossível pela interface do módulo
- [x] Teste: vetores normalizados têm norma 1 dentro da tolerância
- [x] Rodar a avaliação da mudança 06 e comparar com a linha de base léxica
- [x] `openspec validate --strict`
