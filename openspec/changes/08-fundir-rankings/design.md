# Design — recuperação híbrida

## Decisão: fusão por posição, não por pontuação

Reciprocal Rank Fusion soma, para cada documento, o inverso de `k` mais a
posição em cada ranking. Só a ordem importa, então não há escalas para
normalizar nem pesos para calibrar.

A alternativa — normalizar as pontuações e somar com pesos — costuma render um
pouco mais quando bem ajustada, mas o ajuste depende do corpus e envelhece a cada
recatalogação. Para um projeto com prazo curto e sem infraestrutura de tuning,
RRF entrega quase o mesmo com três linhas de código e nenhum parâmetro sensível.

O valor de `k` fica configurável por completude, mas o padrão consagrado é
robusto e não deveria ser mexido sem evidência da avaliação.

## Decisão: profundidade maior que o retorno

Cada ranking contribui com bem mais itens do que serão devolvidos. Um documento
que aparece em décimo lugar nos dois rankings costuma ser melhor que um primeiro
colocado em apenas um deles — e truncar cedo demais elimina justamente esses
casos, que são o motivo de fundir.

## Decisão: proveniência preservada

Cada resultado carrega de quais rankings veio e em que posição. Isso serve a três
propósitos: diagnosticar falhas na avaliação, alimentar a camada Confira com uma
explicação honesta de por que aquele conjunto apareceu, e permitir decidir o
roteamento da mudança 09 com mais informação que a pontuação final.

## Decisão: adiar a reordenação por modelo

Reordenar os finalistas com um modelo melhoraria a precisão, mas acrescenta uma
chamada por consulta — latência, custo e uma dependência externa no caminho
crítico da recuperação. Isso contradiz a arquitetura de custo adotada e a
operação sem chave da versão desktop.

Fica registrado como possibilidade futura, condicionada a evidência de que o
recall@5 é insuficiente e de que o gargalo está na ordenação, não na
recuperação.

## Decisão: a fusão precisa provar seu valor

A mudança só é arquivada se a avaliação da mudança 06 mostrar recall igual ou
superior ao melhor dos dois rankings isolados. Fusão que piora existe, sobretudo
quando um dos rankings é muito ruim, e seria fácil adotá-la por elegância sem
verificar.

## Riscos aceitos

RRF trata os dois rankings como igualmente confiáveis. Se a busca semântica se
mostrar consistentemente pior, isso custa alguma precisão. O ajuste possível é
ponderar as contribuições, e só deve ser feito com número da avaliação na mão.
