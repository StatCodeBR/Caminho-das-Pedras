# Design — cache semântico

## Decisão: chavear pela versão do catálogo

A chave do cache inclui um identificador da versão do `dados.db`. Quando uma
imagem com catálogo novo entra em produção, o identificador muda e todo o cache
anterior deixa de ser consultável.

A alternativa — invalidação seletiva por conjunto afetado — exigiria rastrear
quais fichas participaram de cada resposta e cruzar com o que mudou. É mais
eficiente e bem mais complexo. Como o catálogo é regenerado raramente, o
descarte integral é o custo certo a pagar.

## Decisão: reaproveitar o embedding da busca

A pergunta já é vetorizada para a recuperação híbrida. O cache consulta esse
mesmo vetor, então o custo adicional é um produto escalar contra algumas
centenas de entradas — irrelevante.

Consequência de ordem: a consulta ao cache acontece depois de calcular o
embedding e antes de decidir entre template e modelo.

## Decisão: limiar conservador

Similaridade alta demais quase nunca acerta; baixa demais serve resposta errada
para pergunta parecida mas distinta — "dados de leitos" e "dados de leitos
pediátricos" são vizinhos no espaço vetorial e têm respostas diferentes.

O limiar começa alto e só é afrouxado com evidência da avaliação da mudança 06.
Servir resposta errada é pior que gastar um token a mais.

## Decisão: não cachear respostas de baixa qualidade

Respostas de "não encontrei", respostas descartadas pela guarda de URL e
respostas emitidas em modo reduzido não entram no cache. Cachear um "não
encontrei" congelaria uma falha de recuperação que poderia ser corrigida por
ajuste de índice.

## Riscos aceitos

Duas perguntas semanticamente próximas mas com intenção distinta podem colidir.
A mitigação é o limiar conservador e o registro da origem na telemetria, que
permite auditar acertos de cache junto com as perguntas que os dispararam.
