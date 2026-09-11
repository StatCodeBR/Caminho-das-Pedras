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

## Decisão: a busca semântica chega à produção nesta mudança

A 07 deixou a semântica opcional no serviço porque nenhuma resposta a usava. A
fusão é a primeira a usá-la, então é aqui que ela precisa existir em produção —
e passa a ser obrigatória: sem ela, o serviço responderia só com a léxica, no
mesmo formato, e o ganho da fusão sumiria sem nenhum alarme.

**Vetores como asset próprio, na mesma release do banco.** Empacotar banco e
vetores num arquivo só daria uma soma única, mas mudaria o formato de um asset
que já está em produção e obrigaria a baixar e descomprimir 186 MB para conferir
31. Como assets distintos, cada um é verificado isoladamente, com mensagem que
diz qual divergiu. O vínculo entre os dois não depende do empacotamento: a
versão do catálogo gravada nos vetores é conferida contra o banco na publicação
e de novo na subida do serviço.

**Modelo no build, não na primeira consulta.** O ONNX de 470 MB é baixado do
repositório do modelo durante a construção da imagem. Na primeira consulta, a
resposta passaria a depender do Hugging Face em tempo real, a primeira pergunta
de cada container levaria dezenas de segundos, e o arquivo em produção seria um
que o build nunca viu.

**fp32, não quantizado.** O repositório também publica uma versão quantizada de
118 MB, que deixaria a imagem perto de 750 MB. A paridade dela nunca foi medida,
e o nome indica otimização para AVX-512 VNNI, que a CPU do servidor pode não
ter. O fp32 é o modelo cuja equivalência com o pipeline foi medida em cosseno
1,000000. Trocar exige medir antes.

**Exigida na subida, degradável por consulta.** O serviço não sobe sem a
semântica — isso pega configuração errada, que é permanente. Uma falha da busca
semântica numa consulta específica continua degradando para o resultado léxico,
como pede o requisito de resiliência: falha transitória não deve virar
indisponibilidade. As duas regras tratam falhas de naturezas diferentes.

## Riscos aceitos

RRF trata os dois rankings como igualmente confiáveis. Se a busca semântica se
mostrar consistentemente pior, isso custa alguma precisão. O ajuste possível é
ponderar as contribuições, e só deve ser feito com número da avaliação na mão. Na medição mais recente, a
semântica isolada ficou 7 pontos abaixo da léxica em recall@5 (50,0% contra
57,1%), e a união das duas acertou 11 de 14 perguntas — o teto que a fusão
persegue.

A imagem da api cresce de 472 MB para cerca de 1,1 GB, e o serviço passa a
carregar o modelo na memória ao subir. É o preço de a primeira consulta não
depender da rede.

O build passa a depender do Hugging Face, além do GitHub. Indisponibilidade de
qualquer um impede construir a imagem; nunca impede a imagem já construída de
responder.
