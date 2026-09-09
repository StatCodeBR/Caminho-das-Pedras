# Tarefas — avaliar recuperação

## Conjunto de avaliação

- [x] Definir formato: pergunta, conjuntos aceitáveis, tema, dificuldade
- [ ] Escrever 50 perguntas em linguagem de cidadão, sem copiar títulos
- [x] Anotar à mão os conjuntos aceitáveis para cada pergunta
- [x] Distribuir entre temas e níveis de dificuldade
- [x] Versionar `avaliacao/perguntas.csv` no Git
- [x] Alimentar `pipeline/sementes.txt` com os conjuntos citados

## Execução

- [x] Implementar `avalia.py` executando a recuperação para cada pergunta
- [x] Calcular recall@5, recall@10 e MRR
- [x] Quebrar os resultados por tema e por dificuldade
- [x] Listar as perguntas que falharam, com os cinco primeiros retornados

## Histórico

- [x] Gravar cada execução com data, métricas e identificação da versão
- [x] Comparar automaticamente com a execução anterior
- [x] Encerrar com código diferente de 0 em regressão acima do limiar

## Verificação

- [x] Teste: execução é determinística para o mesmo índice
- [x] Teste: pergunta com múltiplos conjuntos aceitáveis conta acerto
- [x] Teste: pergunta de ausência conta acerto quando nada é recuperado
- [x] Estabelecer a linha de base com a busca léxica da mudança 05
- [x] `openspec validate --strict`
