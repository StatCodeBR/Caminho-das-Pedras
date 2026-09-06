# Tarefas — avaliar recuperação

## Conjunto de avaliação

- [ ] Definir formato: pergunta, conjuntos aceitáveis, tema, dificuldade
- [ ] Escrever 50 perguntas em linguagem de cidadão, sem copiar títulos
- [ ] Anotar à mão os conjuntos aceitáveis para cada pergunta
- [ ] Distribuir entre temas e níveis de dificuldade
- [ ] Versionar `avaliacao/perguntas.csv` no Git
- [ ] Alimentar `pipeline/sementes.txt` com os conjuntos citados

## Execução

- [ ] Implementar `avalia.py` executando a recuperação para cada pergunta
- [ ] Calcular recall@5, recall@10 e MRR
- [ ] Quebrar os resultados por tema e por dificuldade
- [ ] Listar as perguntas que falharam, com os cinco primeiros retornados

## Histórico

- [ ] Gravar cada execução com data, métricas e identificação da versão
- [ ] Comparar automaticamente com a execução anterior
- [ ] Encerrar com código diferente de 0 em regressão acima do limiar

## Verificação

- [ ] Teste: execução é determinística para o mesmo índice
- [ ] Teste: pergunta com múltiplos conjuntos aceitáveis conta acerto
- [ ] Estabelecer a linha de base com a busca léxica da mudança 05
- [ ] `openspec validate --strict`
