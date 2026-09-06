# Operar sem chave de API configurada

## Por que

Na versão desktop o usuário fornece a própria chave da API. A tentação óbvia é
bloquear o aplicativo até que ela seja informada — e isso destruiria o produto.

Quem instala uma ferramenta de descoberta de dados públicos quer descobrir dados
públicos. Uma tela de configuração como primeira experiência afasta exatamente o
público que o projeto existe para alcançar: servidor de prefeitura pequena,
jornalista local, estudante, conselheiro municipal. Nenhum deles tem chave de
API, e a maioria nem sabe o que é isso.

A boa notícia é que a arquitetura já resolve isso. A mudança 09 estabeleceu que
respostas conclusivas são montadas por template, sem modelo. A mudança 10
estabeleceu o modo reduzido. Na versão desktop, esse modo deixa de ser
degradação de emergência e passa a ser o estado inicial legítimo do aplicativo.

A chave, quando configurada, desbloqueia a redação em linguagem natural. Não o
acesso aos dados.

## O que muda

- O núcleo Rust opera integralmente sem credencial: busca léxica, busca
  semântica, fusão e resposta por template.
- A configuração de chave é apresentada como melhoria opcional, nunca como
  barreira.
- A interface distingue com clareza o que está disponível e o que a chave
  acrescenta.

## Fora de escopo

- Armazenamento e validação da chave (mudança 21).
- Obtenção e atualização do catálogo (mudança 22).

## Impacto

- Reaproveita o roteamento e o modo reduzido já especificados nas mudanças
  09 e 10.
- Torna o aplicativo utilizável offline para descoberta, o que é o argumento
  central da versão desktop.
