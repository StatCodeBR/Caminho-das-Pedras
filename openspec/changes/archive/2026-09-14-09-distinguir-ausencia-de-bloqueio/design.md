## Context

Ver proposal.md — Why para a motivação e os números da varredura de 2026-09-12.

O que restringe o desenho:

- **`classificar()` recebe só o status.** A evidência de bloqueio é a ausência de
  qualquer sucesso no host inteiro, que nenhuma requisição isolada revela. Por
  isso a classe `bloqueado` não pode sair da função que classifica um recurso.
- **`httpx` colapsa causas distintas em `ConnectError`.** Cadeia incompleta,
  certificado expirado, nome que não corresponde, DNS que não resolve e recusa
  de TCP chegam todas como a mesma exceção. Foi preciso reclassificar os 149
  hosts fora do programa para descobrir a composição dos 8.280 casos.
- **O banco atual já carrega a classificação antiga**, de 124.820 recursos e
  141.942 requisições. Repetir a varredura inteira para corrigir rótulo é
  desperdício de três horas e de carga sobre 630 órgãos.
- **A API expõe hoje um booleano** `Recurso.disponivel`, derivado por exclusão de
  uma lista de um elemento. Booleano não expressa "não consegui verificar", que é
  exatamente a distinção que esta mudança existe para fazer.

## Goals / Non-Goals

**Goals:**

- Classe de saúde que afirma só o que a verificação sustenta.
- Reclassificar o que já foi medido sem repetir a rede onde isso for possível.
- Critério de bloqueio explícito, calibrado sobre o catálogo completo.

**Non-Goals:**

- **Não** contornar a cadeia incompleta buscando o intermediário faltante. Isso
  tornaria o verificador mais permissivo que clientes estritos e esconderia um
  defeito real do servidor. A mudança classifica o defeito; não o remedia.
- **Não** tentar burlar o WAF que nos bloqueia — trocar User-Agent, forjar
  `Referer`, distribuir origem. Já verifiquei que não funcionaria no TSE, e a
  postura do verificador é se identificar, não se disfarçar.
- **Não** julgar o órgão publicador. A classe descreve o que observamos.

## Decisions

### A causa da falha vem da cadeia de exceções, não do texto da mensagem

Para separar cadeia incompleta de certificado inválido e de DNS, percorrer
`__cause__`/`__context__` da exceção até achar `ssl.SSLCertVerificationError` ou
`socket.gaierror`, e decidir pelo `verify_code` do erro de certificado — não pela
substring da mensagem.

*Por quê:* mensagem de OpenSSL é texto de biblioteca, muda entre versões e entre
distribuições, e o projeto roda em NixOS no desenvolvimento e Debian na imagem.
`verify_code` é numérico e estável. Casar `"unable to get local issuer"` por
substring funcionaria hoje e quebraria em silêncio na próxima atualização — e a
quebra se manifestaria como reclassificação em massa, não como erro.

*Alternativa considerada:* fazer o handshake TLS em separado, antes do HTTP, para
diagnosticar com controle total. Rejeitada: dobra as conexões por recurso, e a
informação já está na exceção que o `httpx` levanta.

### O reconhecimento de bloqueio é uma passada sobre o agregado por host

Depois de a varredura terminar, agrupar os resultados por host e reclassificar
como `bloqueado` os recursos de host que satisfaça as três condições. A passada
lê status já gravados e não emite requisição.

*Por quê:* além de a evidência ser agregada, isso torna a correção aplicável ao
banco atual. As três horas de varredura não precisam ser repetidas para trocar
5.487 rótulos.

### Volume mínimo de 20 recursos por host

Varredura do limiar sobre o catálogo completo, com as outras duas condições
fixas (zero sucessos, maioria de 403):

| mínimo | hosts | recursos | além dos três grandes |
|---|---|---|---|
| 1 | 11 | 5.511 | `doi.org`, `siorg.planejamento.gov.br`, `painelsipaer.cenipa.fab.mil.br`, … |
| 5 | 5 | 5.503 | `angovbr-my.sharepoint.com`, `mapa.cultura.gov.br` |
| 10 | 4 | 5.498 | `mapa.cultura.gov.br` |
| **20** | **3** | **5.487** | (nenhum) |
| 30 | 2 | 5.463 | (nenhum) |

**Não há joelho, e o motivo é instrutivo:** o limiar quase não move o total —
5.487 contra 5.511, diferença de 0,4% — porque três hosts concentram tudo. O que
o limiar move é *quantos hosts são acusados de bloquear*, de 3 para 11.

Escolhi 20 por causa dos hosts de uma observação só. Com mínimo 1, o `doi.org`
entraria na lista de bloqueadores por causa de um único 403 — o `doi.org` é o
resolvedor global de DOI, e declará-lo bloqueador a partir de uma amostra de um
seria exatamente o tipo de afirmação sem sustentação que esta mudança combate. O
`angovbr-my.sharepoint.com` (9 recursos, 5 com 403) é link pessoal de SharePoint
que pede autenticação: inacessível de verdade, e não bloqueio ao verificador.

*O custo da escolha:* `mapa.cultura.gov.br`, com 11 recursos e 11 negativas,
provavelmente bloqueia e continuará contado como ausência confirmada. Onze
recursos, contra o risco de acusar um host a partir de uma medição. Registrado
como erro conhecido e aceito, não como descuido.

A distância entre 24 (o menor host aceito) e 11 (o maior recusado) é estreita.
O limiar é uma convenção defensável, não uma fronteira natural — e por isso o
diagnóstico precisa listar os hosts reconhecidos, para que a escolha fique
visível a quem lê o número.

### `Recurso.disponivel` vira estado de três valores

Substituir o booleano por `situacao` com os três tratamentos que a spec define:
apresentado sem ressalva, marcado como inacessível, apresentado com ressalva de
não verificado. O mapeamento classe → tratamento vive em um lugar só, e classe
desconhecida cai em "não verificado", nunca em "disponível".

*Por quê:* o booleano derivava por exclusão, e é assim que `dominio_inexistente`
chegaria ao usuário como link bom. Exclusão é o defeito, não o valor da lista.

*Consequência:* muda o formato do evento final do SSE, que o `web/` consome. É
contrato interno nosso, então prefiro trocá-lo limpo a carregar o booleano por
compatibilidade com um consumidor que também é nosso.

## Risks / Trade-offs

**Bloqueio pode mascarar ausência real** → Host inteiramente morto que responda
403 seria chamado de `bloqueado`, e seus recursos nunca sinalizados como
removidos. Mitigado pelo que a classe afirma: `bloqueado` recebe ressalva de não
verificado na resposta, não selo de disponível. O usuário não é informado de que
o link está bom.

**Os `verify_code` do OpenSSL podem variar entre ambientes** → Teste com cadeias
de exceção gravadas como fixture, cobrindo cadeia incompleta, nome divergente e
validade expirada, para que a mudança de ambiente falhe em teste e não em
produção silenciosa.

**A distinção TLS não é recuperável do banco atual** → `motivo_saude` guarda
apenas `ConnectError` para os 8.280 casos. Reclassificar exige revisitar a rede
naquele subconjunto.

**O limiar de 20 deixa 11 recursos classificados errado** → Aceito e registrado
acima.

**A classe `cadeia_incompleta` presume o navegador do usuário** → Ela afirma que
o arquivo é acessível a quem completa a cadeia sozinho, o que é verdade para
navegadores atuais e falso para `curl` e para nós. É uma presunção sobre o
cliente do usuário, declarada como tal na spec.

## Migration Plan

1. **Reconhecimento de bloqueio, sem rede.** Roda sobre o banco atual e corrige
   os 5.487 rótulos a partir dos status gravados.
2. **Domínio sem DNS, quase sem rede.** São 149 hosts com `ConnectError`; uma
   resolução por host, não por recurso, separa os 1.047 recursos de domínio
   morto.
3. **Cadeia e certificado, reverificando só o necessário.** `--somente-falhas`
   sobre o que não está `disponivel` revisita cerca de 26.350 recursos. A 11
   recursos por segundo medidos na varredura completa, são aproximadamente 40
   minutos — contra as 3 horas de refazer tudo.
4. **Publicar catálogo novo.** Os números só chegam a produção por release: a
   imagem em pé serve `catalogo-2026-09-11`, anterior a qualquer verificação.

Reversão: as colunas de saúde são texto e nenhuma migração de esquema ocorre.
Voltar atrás é reverter o código e rodar a varredura antiga; nenhum dado de
catálogo é destruído no caminho.

## Open Questions

- Vale pedir aos três órgãos que liberem o verificador, agora que o User-Agent
  traz contato? É decisão operacional, não técnica: não muda spec, desenho nem
  tarefas, e o resultado só melhoraria a cobertura numa varredura futura.
