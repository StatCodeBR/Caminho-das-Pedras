## Why

A classe de saúde afirma hoje mais do que a verificação sustenta. Ela tem quatro
valores, e dois deles carregam juízos que a medição não comprova: `indisponivel`
diz "o arquivo não está lá" e `instavel` diz "é passageiro". A primeira varredura
completa do catálogo mostrou que ambos estão errados em volume grande, e nas duas
direções opostas.

**A varredura** (2026-09-12, 124.820 recursos, 141.942 requisições HTTP, 3h04)
reportou:

| classe | recursos | |
|---|---|---|
| `disponivel` | 98.470 | 78,9% |
| `instavel` | 14.220 | 11,4% |
| `indisponivel` | 11.418 | 9,1% |
| `nao_verificado` | 712 | 0,6% |

**`indisponivel` está inflado por bloqueio de host.** Dos 11.418, os status são
403 em 5.826 casos — mais que os 5.266 de 404. E 5.487 desses 403 vêm de três
hosts que não responderam 2xx uma única vez em toda a varredura:

| host | 403 / verificados |
|---|---|
| `cdn.tse.jus.br` | 5.257 / 5.290 |
| `dadosabertos.mec.gov.br` | 206 / 206 |
| `www.marinha.mil.br` | 24 / 25 |

No TSE o corpo da resposta identifica o bloqueador: `errors.edgesuite.net`, o
WAF da Akamai. Ele nega `HEAD`, `GET` e `GET` com `Range`, com User-Agent de
navegador, sem User-Agent, e com `Referer` do próprio portal. Nega também
`https://www.tse.jus.br/` — a página inicial do tribunal, que **não existe no
catálogo** e portanto nunca foi pedida pela varredura. O bloqueio é política
permanente contra este cliente ou rede, não reação ao nosso volume.

Os outros 339 dos 5.826 são 403 em hosts que também tiveram sucessos. Esses são
negativa por arquivo, não recusa de host, e continuam sendo ausência.

**`instavel` está inflado por defeito de TLS alheio.** Dos 14.220, 8.280 foram
`ConnectError`. Classificando os 149 hosts de origem um a um:

| causa | recursos | hosts |
|---|---|---|
| servidor não envia o certificado intermediário | 6.220 | 25 |
| domínio sem DNS | 1.047 | 75 |
| certificado inválido (nome ou validade) | 819 | 11 |
| recusa de TCP, TLS íntegro, outros | 194 | 38 |

Os 6.220 não são links mortos: são servidores que não enviam a cadeia completa.
O `dadosabertos.iftm.edu.br` manda um intermediário de 2019 quando quem assinou
a folha foi o de 2025; o `dados.anvisa.gov.br` manda só a folha. O `curl` com a
CA do sistema falha igual, então não é o nosso pacote de certificados. Navegador
contorna isso buscando o intermediário pela extensão AIA — **quem clicar nesses
links provavelmente baixa o arquivo.** Chamá-los de instáveis descreve o nosso
cliente, não o link.

E os 1.047 sem DNS são o inverso: `instavel` sugere transitório, mas domínio que
não resolve — `dados.mj.gov.br` sozinho tem 814 recursos — está morto, não de
mau humor.

**A leitura honesta do catálogo,** portanto:

| | recursos | |
|---|---|---|
| confirmado disponível | 98.470 | 78,9% |
| provavelmente bom, falha só em cliente estrito | 6.220 | 5,0% |
| ausência confirmada | 5.931 | 4,8% |
| impossível verificar, o host nos recusa | 5.487 | 4,4% |
| instabilidade real (timeout, 5xx, leitura) | 6.126 | 4,9% |
| domínio morto | 1.047 | 0,8% |
| sem URL ou link que não é endereço | 712 | 0,6% |

Os 9,1% de "link morto" são, na verdade, 4,8% de ausência confirmada mais 4,4%
de cegueira nossa. O produto trata 5.487 recursos em 215 conjuntos como removidos
sem ter evidência disso, e 6.220 recursos em conjuntos ativos como problemáticos
quando o cidadão os baixaria sem perceber nada.

O princípio que a mudança impõe: **a classe de saúde só afirma o que a
verificação sustenta, e distingue "o arquivo não está lá" de "não consegui
verificar".**

## What Changes

- **BREAKING** — `classe_saude` passa a ter sete valores em vez de quatro.
  Consumidores que comparam com a lista fechada precisam ser revistos; o único
  hoje é `INDISPONIVEIS` em `api/app/recuperacao.py`.
- Três classes novas, nomeadas pelo que a verificação constatou:
  - `bloqueado` — o host recusa este cliente; **não se afirma nada sobre o
    arquivo**;
  - `cadeia_incompleta` — o servidor não envia a cadeia de certificação; o
    arquivo é presumido acessível a quem usa navegador;
  - `dominio_inexistente` — o domínio não resolve em DNS.
- `indisponivel` é **estreitada** para ausência confirmada: status HTTP de
  recusa vindo de um host que demonstrou responder. Deixa de absorver bloqueio.
- `instavel` deixa de absorver falha de TLS e de DNS, e volta a significar o que
  a spec já dizia: estado de um instante.
- O reconhecimento de bloqueio é uma **segunda passada** sobre a varredura, não
  uma decisão por recurso: `classificar()` recebe apenas o status e não pode
  saber que o host nunca respondeu. O critério exige volume mínimo, zero
  sucessos e maioria de 403 — calibrado para separar os três hosts bloqueados
  dos 339 recursos com 403 individual.
- A API passa a decidir explicitamente o que cada classe significa para quem lê
  a resposta, em vez de herdar o silêncio de uma lista de um elemento: o que é
  marcado como inacessível, o que é apresentado sem ressalva, e o que ganha
  ressalva própria.
- O diagnóstico impresso ao fim da varredura passa a relatar as sete classes e a
  listar os hosts reconhecidos como bloqueadores, para que o número de manchete
  nunca mais seja lido sem eles.

## Capabilities

### New Capabilities

Nenhuma. A mudança corrige o que duas capacidades existentes afirmam.

### Modified Capabilities

- `saude-recursos`: a classificação passa a distinguir ausência confirmada de
  impedimento de verificação; três classes novas; reconhecimento de host
  bloqueador em segunda passada; diagnóstico relata as sete classes e os hosts
  bloqueados.
- `resposta-ancorada`: a sinalização de recursos ao usuário passa a derivar das
  sete classes, declarando o que cada uma afirma — hoje o requisito fala apenas
  de `indisponivel`, e uma classe nova seria silenciosamente tratada como
  disponível, inclusive `dominio_inexistente`.

## Impact

- `pipeline/saude.py`: `CLASSES`, `classificar()`, `Resultado`, `GLOSSARIO`,
  `imprimir_relatorio()`, e a segunda passada nova sobre o resultado da
  varredura. A classificação de causa de rede exige distinguir os erros de TLS e
  de resolução que hoje caem juntos em `httpx.ConnectError`.
- `pipeline/tests/test_saude.py`: cenários das classes novas e do critério de
  bloqueio, incluindo o caso dos 339 que devem permanecer ausência.
- `api/app/recuperacao.py`: `INDISPONIVEIS` e o campo `disponivel` de `Recurso`.
- `api/app/` na borda da resposta: a ressalva por classe chega ao evento final e
  à interface.
- `web/`: exibição da ressalva nova, se a decisão de design for mostrá-la.
- Nenhuma migração de esquema: as colunas de saúde já existem e os valores são
  texto. O banco atual carrega a classificação antiga, e uma reclassificação
  sobre os dados existentes evita repetir as 141.942 requisições.
- `docs/limitacoes-conhecidas.md`: a limitação de que a saúde nunca rodou sobre o
  catálogo completo deixa de valer; entra a de que bloqueio de host é ponto cego
  permanente deste verificador.
