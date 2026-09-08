# Tarefas — interface de conversa

## API: as duas datas

- [x] Devolver `dados_atualizados_em` e `metadados_atualizados_em` no resumo de
      cada conjunto do evento final
- [x] Teste: conjunto sem data dos dados declara o campo ausente, não omite
- [x] Teste: as duas datas nunca são fundidas nem substituídas uma pela outra

## Projeto web

- [x] Criar `web/` em SvelteKit com pnpm, sem npm em nenhum momento
- [x] Configurar Tailwind
- [x] Adaptador Node, para servir em container
- [x] Endereço da API por variável de ambiente, nunca embutido no código

## Repasse do fluxo

- [x] Rota de servidor que repassa a pergunta à API e devolve o SSE
- [x] Transmitir sem acumular, preservando o streaming da mudança 09
- [x] Traduzir falha da API em mensagem simples, sem vazar detalhe técnico

## Cliente

- [x] Ler o corpo da resposta em fragmentos e decodificar os eventos SSE
- [x] Tratar evento cortado no meio de um fragmento
- [x] Acumular o texto e exibi-lo enquanto chega
- [x] Teste: analisador remonta evento partido entre dois fragmentos

## Tela

- [x] Campo de pergunta, botão de enviar e bloqueio de envio duplicado
- [x] Área de resposta com indicação de que está buscando
- [x] Cartão do conjunto: título, órgão, formatos, data e link para o portal
- [x] Rotular a data conforme sua natureza, com o caso de nenhuma data declarada
- [x] Recursos indisponíveis marcados, disponíveis primeiro
- [x] Traduzir a origem da resposta para linguagem de quem não conhece o sistema
- [x] Mensagem de resposta interrompida, sem apresentar texto parcial como final

## Telefone e acesso

- [x] Layout utilizável a partir de 360 pixels de largura
- [x] Quebrar título e endereço longos sem alargar a página
- [x] Rótulo no campo, foco visível e contraste suficiente

## Verificação

- [x] Teste: resposta em fragmentos aparece antes do evento final
- [x] Teste: conjunto sem data alguma não exibe traço mudo
- [x] Teste: recurso indisponível aparece sinalizado, não omitido
- [x] Teste: pergunta vazia não dispara requisição
- [x] Rodar a tela contra a API em `MODO_STUB=1`, sem consumir tokens
- [x] `openspec validate --changes --strict`
