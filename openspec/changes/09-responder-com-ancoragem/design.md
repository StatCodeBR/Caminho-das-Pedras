# Design — resposta ancorada

## Decisão: ancoragem por construção, não por instrução

Instruir o modelo a não inventar é necessário mas insuficiente. A garantia real
vem de duas medidas estruturais: o modelo só recebe as fichas recuperadas, e a
saída é verificada antes de chegar ao usuário.

A verificação é mecânica: extrai-se toda URL do texto gerado e confere-se
pertencimento ao conjunto de URLs enviadas no contexto. Uma URL fora da lista
significa fabricação, e a resposta inteira é descartada. É preferível falhar
visivelmente a entregar um link inventado.

## Decisão: roteamento entre template e modelo

Depois da recuperação, o sistema decide:

- primeiro resultado acima do limiar de pontuação **e** margem suficiente sobre
  o segundo → resposta por template, sem tokens;
- caso contrário → resposta gerada pelo modelo.

Os dois limiares são configuráveis por ambiente porque só a avaliação da
mudança 06 dirá onde eles devem ficar. Começam conservadores: é melhor gastar
token à toa do que servir template para pergunta ambígua.

Efeito colateral desejável: o produto continua útil mesmo sem o modelo
disponível, o que sustenta a degradação graciosa da mudança 10.

## Decisão: streaming mesmo na resposta por template

A resposta por template é instantânea e poderia ser enviada de uma vez. Ainda
assim ela usa o mesmo canal SSE, para que a interface tenha um único caminho de
renderização. Simplifica o frontend e elimina uma classe de bug que só apareceria
em produção.

## Decisão: transparência sobre a origem da resposta

Cada resposta declara como foi produzida — correspondência direta, redigida pelo
modelo, ou modo reduzido. Isso é honestidade com o usuário e, ao mesmo tempo, a
telemetria que mede a eficiência de custo da arquitetura.

## Decisão: recursos indisponíveis não somem, são sinalizados

Um recurso com link morto continua aparecendo, marcado como indisponível, com o
link para a página do conjunto no portal. Esconder seria enganoso: o dado foi
catalogado e o cidadão tem direito de saber que existe e está inacessível.

## Riscos aceitos

O modelo pode parafrasear o resumo de uma ficha de confiança baixa e soar mais
seguro do que a fonte permite. Mitigação parcial: fichas de confiança baixa são
marcadas no contexto e o prompt exige que a resposta explicite a incerteza. A
avaliação qualitativa da mudança 06 monitora isso.
