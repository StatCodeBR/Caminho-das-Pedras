# Enriquecer as fichas dos conjuntos de dados

## Por que

Existe um abismo entre a linguagem do cidadão e a do catálogo. A pessoa
pergunta "quantos leitos de UTI tem na minha cidade"; o conjunto que responde
isso se chama algo como "CNES — Estabelecimentos". Nenhuma busca textual
atravessa essa distância, e boa parte dos conjuntos tem descrição vazia ou de
uma linha.

A solução é gerar, uma única vez e offline, uma camada de metadados legíveis
sobre cada conjunto: um resumo em português simples e uma lista de perguntas
reais que aquele conjunto responde. É esse texto que vai para os índices de
busca, não o original.

Este é o diferencial técnico do projeto. Também é o ponto de maior risco: um
modelo pedido para descrever um conjunto com metadados pobres tende a inventar
conteúdo plausível. As salvaguardas abaixo existem para isso.

## O que muda

- Novo comando `enriquece.py` que processa conjuntos em lote via API da
  Anthropic.
- Nova tabela `ficha` com resumo, perguntas, temas, abrangência, granularidade,
  confiança e texto indexável derivado.
- Cache local por hash do conteúdo de entrada.

## Fora de escopo

- Indexação e busca (mudanças 05 a 08).
- Qualquer chamada a modelo em tempo de resposta ao usuário (mudança 09).

## Impacto

- Passa a exigir `ANTHROPIC_API_KEY` no pipeline.
- Custo proporcional ao número de conjuntos, pago uma vez e amortizado pelo
  cache em execuções seguintes.
- Execução completa na ordem de horas; deve rodar fora do ciclo de trabalho.
