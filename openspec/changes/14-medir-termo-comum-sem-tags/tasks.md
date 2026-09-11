# Tarefas — medir termo comum sem a coluna de tags

## Pipeline

- [x] Restringir `frequencia()` às colunas de texto natural, sem tocar no índice
- [x] Declarar as colunas medidas como constante, ao lado das colunas indexadas
- [x] Corrigir a docstring de `descartar_comuns`, que ainda dizia "mais de 30%"

## API

- [x] Aplicar a mesma correção em `api/app/recuperacao.py`
- [x] Conferir que os dois lados descartam os mesmos termos para a mesma consulta
      — 14 consultas reais, 0 divergências

## Testes

- [x] Termo frequente só em tags não é descartado
- [x] Termo frequente em texto natural continua sendo descartado
- [x] Consulta por termo exclusivo de tags ainda recupera a ficha
- [x] Teste equivalente no lado da api

## Medição

- [x] Rodar a avaliação e comparar com a linha de base de 57,1%
- [x] Registrar a execução no histórico
- [x] Anotar em `docs/limitacoes-conhecidas.md` as duas causas não tratadas:
      cacoete do modelo e concentração real de órgão

## Achado que esta mudança não resolve

A avaliação não se moveu: 35,7% antes e depois. O reparo altera a seleção de
termos em 2 das 14 perguntas (`públicas` 41,5% → 2,4%, `governo` 28,6% → 9,8%),
mas nenhuma das duas mudava de resultado por causa disso.

A queda de 57,1% para 35,7% tem outra causa, identificada aqui e registrada como
limitação 7: são exatamente as três perguntas anotadas com `nenhum`, que com 505
fichas retornavam vazio e com 19.958 retornam conjuntos pertinentes. 8 acertos
viraram 5, e os 3 perdidos são os 3 de ausência.

- [ ] Revisar as anotações `nenhum` contra o catálogo completo — curadoria
      humana, fora do escopo desta mudança
