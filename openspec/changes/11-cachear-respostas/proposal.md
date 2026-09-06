# Cachear respostas por equivalência semântica

## Por que

Numa ferramenta pública sobre dados abertos, as perguntas repetem muito. Pessoas
diferentes buscam a mesma coisa com palavras diferentes: "onde acho dados de
leitos", "quantos leitos de UTI existem", "dados sobre leitos hospitalares". Hoje
cada uma dessas variações consumiria uma geração completa.

O embedding da pergunta já é calculado para a busca, então comparar com
perguntas anteriores custa praticamente nada. Aproveitar isso reduz o consumo do
modelo e melhora a latência percebida, sem alterar a qualidade da resposta.

O risco é servir resposta desatualizada apontando para recurso que mudou de
estado. Por isso o cache é atrelado à versão do catálogo.

## O que muda

- Cache de respostas chaveado pela versão do catálogo, consultado por
  similaridade de embedding antes de decidir gerar.
- Registro da origem "cache" na telemetria já existente.
- Descarte integral do cache quando o catálogo é regenerado.

## Fora de escopo

- Cache do resultado da recuperação, que já é rápido e não justifica.
- Persistência do cache entre versões do catálogo, deliberadamente descartada.

## Impacto

- Novas variáveis: `CACHE_LIMIAR_SIMILARIDADE`, `CACHE_TAMANHO_MAXIMO`.
- Interação com a mudança 10: acertos de cache não contam para o teto diário,
  por não consumirem o modelo.
