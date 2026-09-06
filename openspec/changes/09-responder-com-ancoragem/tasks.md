# Tarefas — responder com ancoragem

## Serviço

- [ ] Criar projeto `api/` separado do `pipeline/`, sem torch nas dependências
- [ ] Implementar `POST /perguntar` com resposta `text/event-stream`
- [ ] Implementar `GET /saude` para o healthcheck do container
- [ ] Abrir `dados.db` em modo somente leitura

## Roteamento

- [ ] Implementar decisão entre template e modelo por limiar e margem
- [ ] Tornar os dois limiares configuráveis por variável de ambiente
- [ ] Montar template de resposta a partir da ficha, com formatos e link

## Geração

- [ ] Montar o contexto apenas com as fichas recuperadas
- [ ] Marcar no contexto as fichas de confiança baixa
- [ ] Escrever o prompt de resposta, versionado em arquivo próprio
- [ ] Repassar o streaming do SDK para o SSE sem bufferizar

## Guarda de saída

- [ ] Extrair URLs do texto gerado e validar pertencimento ao contexto
- [ ] Descartar resposta com URL fabricada e registrar o evento
- [ ] Teste dedicado para o caso de URL fabricada

## Telemetria

- [ ] Registrar origem da resposta: template, modelo ou reduzido
- [ ] Registrar latência e número de fichas recuperadas

## Modo stub

- [ ] Implementar `MODO_STUB=1` emitindo resposta pré-gravada token a token
- [ ] Garantir que o stub não importa o cliente da Anthropic

## Verificação

- [ ] Teste: nenhuma ficha relevante resulta em resposta de "não encontrei"
- [ ] Teste: recurso indisponível aparece sinalizado, não omitido
- [ ] Teste: stub não consome tokens
- [ ] `openspec validate --strict`
