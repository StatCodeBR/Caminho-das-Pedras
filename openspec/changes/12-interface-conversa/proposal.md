# Interface de conversa

## Why

O produto responde, mas ninguém consegue usá-lo: a resposta ancorada da mudança
09 só existe atrás de `curl`. Esta é a mudança que transforma o trabalho até aqui
em endereço que se abre no celular — e é a última que falta para haver produto.

O público não tem conta, não vai instalar nada e provavelmente chega pelo
telefone: servidor de prefeitura pequena, jornalista local, estudante. A tela
precisa funcionar para essa pessoa, na primeira visita, sem explicação.

## What Changes

- Novo projeto `web/` em SvelteKit com Tailwind, servido como aplicação estática
  com adaptador Node.
- Tela única: campo de pergunta, resposta transmitida token a token por SSE, e
  cartões dos conjuntos recuperados.
- Cada cartão traz título, órgão, formatos disponíveis, data de atualização e
  link para a página do conjunto no `dados.gov.br` — é a camada "Confira".
- Recursos com link fora do ar aparecem marcados, nunca omitidos.
- A origem da resposta é exibida ao usuário: correspondência direta, redigida
  pelo modelo ou modo reduzido.
- **A API passa a devolver a data de atualização de cada conjunto**, que hoje
  existe no banco mas não sai no evento `fim`.

## Capabilities

### New Capabilities

- `interface-conversa`: a tela que recebe a pergunta, transmite a resposta e
  apresenta os conjuntos de forma conferível, em telefone ou computador, sem
  cadastro.

### Modified Capabilities

- `resposta-ancorada`: o resumo das fichas no evento `fim` passa a incluir a data
  de atualização dos dados e a data de atualização dos metadados, campos
  distintos que a interface precisa distinguir para não anunciar frescor que o
  conjunto não tem.

## Impact

- Novo projeto Node em `web/`, com pnpm. Não existe hoje, apesar de o `CLAUDE.md`
  afirmar que já foi inicializado.
- `api/app/principal.py` ganha dois campos no resumo das fichas; nenhum
  comportamento de roteamento ou de ancoragem muda.
- Introduz CORS na API, ou um proxy no SvelteKit, para que o navegador possa
  consumir o SSE.
- O deploy passa a ter dois containers atrás do Traefik, não um.

## Fora de escopo

- Histórico de conversa, contas e persistência entre sessões.
- shadcn-svelte: esta versão usa Tailwind puro, para não acoplar a decisão de
  design a uma biblioteca antes de haver tela funcionando.
- Busca semântica e fusão de rankings (mudanças 07 e 08), que a interface
  consome sem saber.
