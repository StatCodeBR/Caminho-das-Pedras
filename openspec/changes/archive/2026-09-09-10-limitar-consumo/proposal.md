# Limitar consumo e degradar com elegância

## Por que

Um endpoint público que chama modelo de linguagem é uma conta bancária aberta
na internet. Sem contenção, um único script pode consumir o orçamento de meses
em uma noite — e o serviço cai justamente quando alguém da comissão avaliadora
resolve testá-lo.

A resposta usual do mercado é exigir cadastro. Aqui isso seria contraproducente:
o produto existe para derrubar a barreira de acesso a dados públicos, e
inclusividade é critério avaliado no concurso. Um avaliador obrigado a criar
conta para testar já começa mal.

A saída é conter sem identificar: limite por origem, teto diário global e, o
mais importante, um modo reduzido que mantém o serviço útil quando o teto é
atingido. O produto não cai — ele fica menos conversacional.

Esta mudança é pré-requisito para publicar a URL, não item de polimento.

## O que muda

- Contador diário de chamadas ao modelo, persistido e reiniciado por dia.
- Modo reduzido automático ao atingir o teto: todas as respostas passam a ser
  montadas por template.
- Limite por endereço de origem em janela deslizante, sem exigir autenticação.
- Endpoint interno de operação com o consumo corrente.

## Fora de escopo

- Autenticação de usuários, deliberadamente descartada.
- Cache de respostas (mudança 11), que reduz consumo por outro caminho.

## Impacto

- Novas variáveis: `TETO_DIARIO_MODELO`, `LIMITE_ORIGEM_JANELA`,
  `LIMITE_ORIGEM_MAXIMO`.
- O estado do contador precisa sobreviver a reinício de container.
