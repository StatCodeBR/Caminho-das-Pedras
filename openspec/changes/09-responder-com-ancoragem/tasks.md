# Tarefas — responder com ancoragem

## Serviço

- [x] Criar projeto `api/` separado do `pipeline/`, sem torch nas dependências
- [x] Implementar `POST /perguntar` com resposta `text/event-stream`
- [x] Implementar `GET /saude` para o healthcheck do container
- [x] Abrir `dados.db` em modo somente leitura

## Roteamento

- [x] Implementar decisão entre template e modelo por limiar e margem
- [x] Tornar os dois limiares configuráveis por variável de ambiente
- [x] Montar template de resposta a partir da ficha, com formatos e link

## Geração

- [x] Montar o contexto apenas com as fichas recuperadas
- [x] Marcar no contexto as fichas de confiança baixa
- [x] Escrever o prompt de resposta, versionado em arquivo próprio
- [x] Repassar o streaming do SDK para o SSE sem bufferizar

## Guarda de saída

- [x] Extrair URLs do texto gerado e validar pertencimento ao contexto
- [x] Descartar resposta com URL fabricada e registrar o evento
- [x] Teste dedicado para o caso de URL fabricada

## Telemetria

- [x] Registrar origem da resposta: template, modelo ou reduzido
- [x] Registrar latência e número de fichas recuperadas

## Modo stub

- [x] Implementar `MODO_STUB=1` emitindo resposta pré-gravada token a token
- [x] Garantir que o stub não importa o cliente da Anthropic

## Verificação

- [x] Teste: nenhuma ficha relevante resulta em resposta de "não encontrei"
- [x] Teste: recurso indisponível aparece sinalizado, não omitido
- [x] Teste: stub não consome tokens
- [x] `openspec validate --strict`
