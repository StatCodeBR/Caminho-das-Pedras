# Design — limitar consumo

## Decisão: dois limites com naturezas opostas

Há dois riscos diferentes, e tratá-los do mesmo jeito estragaria os dois.

**O teto diário protege o orçamento.** Ele é global, vale para todo mundo junto,
e quando estoura **ninguém recebe erro**: o serviço passa a responder por
template. Devolver 500 ou 429 ao atingir o teto seria transformar um problema
nosso — a conta acabou — em falha na cara de quem perguntou. O produto fica
menos conversacional, não indisponível.

**O limite por origem protege contra abuso.** Ele é por endereço, e quando
estoura a requisição **é recusada com 429** e `Retry-After`. Aqui recusar é
correto: quem dispara 20 perguntas numa hora não é visitante, é script, e
atendê-lo em modo reduzido só transferiria o custo para o resto.

Valores iniciais: **400 chamadas ao modelo por dia**, **20 requisições por
endereço por hora** em janela deslizante. Ambos por variável de ambiente.

Janela deslizante, não balde por hora cheia: com balde, quem chega às 10h59
gasta 20 e às 11h00 gasta mais 20, dobrando o limite na virada.

## Decisão: o endereço vem do proxy, e a cadeia importa

O caminho real de uma requisição é:

```
navegador → Cloudflare → Traefik → web (SvelteKit) → api
```

A `api` **nunca vê o visitante**. Ela é chamada pela rota de servidor do
SvelteKit, então o endereço do socket dela é sempre o container do `web`.
Limitar por socket limitaria um IP só — o nosso — e derrubaria o serviço
inteiro na vigésima pergunta do dia.

Duas consequências.

**No `web`, o endereço vem de cabeçalho, e a direção da leitura é o que importa.**
O `X-Forwarded-For` é uma lista, e o cliente controla o começo dela: qualquer um
pode mandar `X-Forwarded-For: 1.2.3.4` e a lista chega como
`1.2.3.4, <ip-real>`. Ler da esquerda é confiar no atacante. O adapter-node lê
da direita — `addresses[addresses.length - XFF_DEPTH]` —, contando quantos
proxies confiáveis pular.

Isso torna `XFF_DEPTH` dependente da topologia, e errar o número tem efeitos
opostos e igualmente ruins:

| topologia | `X-Forwarded-For` que chega | configuração correta |
|---|---|---|
| só Traefik | `<cliente>` | `XFF_DEPTH=1` |
| Cloudflare + Traefik | `<cliente>, <cloudflare>` | `XFF_DEPTH=2` |

Com Cloudflare na frente e `XFF_DEPTH=1`, o limite passaria a contar **a
Cloudflare** como origem: todos os visitantes viram um só endereço e o serviço
se autolimita em 20 perguntas por hora no mundo inteiro. Com `XFF_DEPTH=2` sem
Cloudflare, o adapter lê uma posição que o cliente controla, e o limite deixa de
valer.

Por isso o padrão é `ADDRESS_HEADER=cf-connecting-ip` quando houver Cloudflare:
esse cabeçalho tem um valor só, é escrito pela Cloudflare e não é uma lista onde
se possa injetar nada. Ele só é confiável se a origem não for alcançável por
fora da Cloudflare — o que é verdade aqui, porque o Traefik é o único caminho.

**No `api`, o endereço chega por cabeçalho interno.** O `web` resolve o endereço
e o repassa em `X-Origem-Real`. A `api` confia nesse cabeçalho porque ela não é
alcançável de fora: `expose` sem `ports`, só na rede interna. Se um dia ela for
publicada, essa confiança deixa de valer — está anotado no código.

## Decisão: o estado sobrevive a reinício

Contador em memória zera a cada deploy, e um teto de gasto que se apaga sozinho
não é teto. Durante uma semana de ajustes, dez deploys dariam dez vezes o
orçamento do dia.

O estado vai para um SQLite próprio, em volume, separado do `dados.db` — que é
somente leitura por decisão da mudança 09 e não pode virar gravável para isto.

Duas tabelas: consumo por dia, e as requisições recentes por origem. As
requisições antigas são podadas na própria escrita; sem poda, a tabela cresceria
para sempre guardando janelas que já passaram.

## Decisão: o dia vira em UTC

O contador reinicia à meia-noite UTC, não no fuso de Brasília. É a mesma regra
que o resto do projeto usa para armazenamento, e evita a ambiguidade de horário
de verão — uma hora que acontece duas vezes daria duas viradas de contador.

Efeito prático: para quem está no Brasil, o orçamento reinicia às 21h. É
aceitável e previsível; converter para fuso local traria a ambiguidade de volta
sem benefício real.

## Decisão: modo reduzido continua sendo resposta, não aviso

Em modo reduzido a recuperação roda inteira — busca, ancoragem, sinalização de
link morto. O que some é a redação pelo modelo. Se a recuperação for conclusiva,
sai o mesmo template de sempre; se não for, sai a lista dos conjuntos
encontrados.

Nos dois casos a resposta diz, em português simples, que o detalhamento voltará
no dia seguinte. Não dizer nada faria o usuário achar que o sistema piorou; dizer
"limite de API excedido" seria despejar nosso problema operacional em cima dele.

## Riscos aceitos

**O limite por origem é por endereço, e endereço não é pessoa.** Uma escola ou um
órgão atrás de NAT compartilha um IP: vinte perguntas por hora podem ser pouco
para uma sala de aula. Aceitamos porque a alternativa é cadastro, que o projeto
recusa por escolha de produto. Se aparecer na prática, o caminho é subir o limite,
não identificar o usuário.

**Um atacante com muitos endereços contorna o limite por origem.** É por isso que
o teto diário existe: ele é o piso de proteção que não depende de identificar
ninguém. O pior caso deixa de ser "gastou o orçamento do mês" e passa a ser
"gastou o orçamento do dia e o serviço ficou em modo reduzido até amanhã".

**O volume de estado é local ao servidor.** Se um dia houver mais de uma réplica
da `api`, cada uma terá seu contador e o teto efetivo dobra. Com uma réplica —
que é o caso — não há problema; com duas, o teto precisa ir para um armazenamento
compartilhado.
