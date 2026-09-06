# Verificar a saúde dos recursos do catálogo

## Por que

Uma parte relevante dos recursos catalogados aponta para arquivos que não
existem mais. Se o assistente enviar o usuário para um link morto, o produto
perde a confiança na primeira interação — e confiança é justamente o que ele
promete entregar.

A verificação atende dois propósitos. No curto prazo, permite despriorizar ou
sinalizar recursos indisponíveis na resposta ao usuário. No médio, produz o
diagnóstico de saúde do catálogo que sustenta o painel de raio-X, entregando à
CGU uma informação que ela hoje não tem consolidada.

## O que muda

- Novo comando `saude.py` que percorre os recursos e registra o estado de cada
  URL.
- Novas colunas em `recurso`: `status_http`, `classe_saude`, `checado_em`,
  `latencia_ms`.
- Reverificação seletiva por idade da última checagem.

## Fora de escopo

- Download ou inspeção do conteúdo dos arquivos.
- Painel de visualização do diagnóstico (mudança 12).

## Impacto

- Tráfego de rede contra centenas de domínios de órgãos públicos, muitos deles
  lentos. Exige contenção por host para não parecer varredura hostil.
- Execução completa demorada; deve ser rodada fora do ciclo de desenvolvimento.
