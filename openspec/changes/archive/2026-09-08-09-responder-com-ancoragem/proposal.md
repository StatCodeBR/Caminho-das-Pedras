# Responder perguntas com ancoragem estrita nas fichas

## Por que

Esta é a camada que o usuário efetivamente toca, e é onde o projeto pode se
destruir sozinho. Um assistente sobre dados públicos que inventa o nome de um
conjunto, ou que devolve uma URL plausível e inexistente, é pior que nenhum
assistente: ele desperdiça o tempo de quem confiou nele e desmoraliza a própria
ideia de reúso de dados abertos.

A resposta precisa ser derivada exclusivamente das fichas recuperadas pela
camada de busca, e toda afirmação precisa levar o usuário ao registro original
no dados.gov.br. É a camada "Confira" da proposta.

Há também uma decisão de custo com efeito direto no produto: boa parte das
perguntas tem resposta óbvia depois da recuperação. Nesses casos, montar a
resposta por template é mais rápido, mais barato e mais previsível que gerar
texto. O modelo entra quando a recuperação é ambígua.

## O que muda

- Novo serviço FastAPI em `api/` com o endpoint `POST /perguntar`, respondendo
  por streaming SSE.
- Roteamento entre resposta por template e resposta gerada, conforme a
  confiança da recuperação.
- Guarda de saída que bloqueia qualquer resposta citando URL ausente do
  contexto.
- Modo stub, sem consumo de API, para desenvolvimento de interface.

## Fora de escopo

- Limites de consumo e teto de gasto (mudança 10).
- Cache de respostas (mudança 11).
- Interface web (mudança 12).

## Impacto

- Passa a exigir `ANTHROPIC_API_KEY` no serviço da API.
- O serviço lê `dados.db` e `vectors.npy` em modo somente leitura.
- Introduz a telemetria de origem da resposta, base das métricas de custo.
