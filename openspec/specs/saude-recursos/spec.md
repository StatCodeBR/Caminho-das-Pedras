# Saúde dos recursos

## Purpose

Saber quais links do catálogo realmente abrem, para que a resposta ao usuário
nunca aponte para um arquivo removido. O portal registra o endereço declarado
pelo órgão publicador e não o verifica; sem essa etapa, o sistema herdaria links
mortos e os apresentaria como se fossem bons.

A verificação também alimenta o diagnóstico de qualidade do catálogo: distinguir
link ausente de link malformado, e servidor fora do ar de arquivo apagado, é o
que permite cobrar do órgão certo — ou apenas esperar.

## Requirements

### Requirement: Verificação HTTP com degradação para GET

O verificador SHALL tentar `HEAD` e, quando o servidor recusar o método,
SHALL repetir com `GET` limitado por cabeçalho `Range`, sem ler o corpo da
resposta. Recusa de método inclui 405 e 501, mas também **403**.

O 403 está nessa lista por evidência, não por precaução: o `www.gov.br` — o
host com mais recursos no catálogo — responde 403 a `HEAD` e 206 ao mesmo
endereço via `GET` com `Range`, com qualquer User-Agent e também sem nenhum
(verificado em 2026-09-07). Tratar esse 403 como acesso negado marcaria como
link morto centenas de arquivos intactos. **Não remova o 403 desta lista sem
antes reverificar esse comportamento.**

#### Scenario: servidor que aceita HEAD

- **WHEN** a URL responde 200 a um HEAD
- **THEN** o status registrado é 200
- **AND** nenhuma requisição adicional é feita

#### Scenario: servidor que rejeita HEAD

- **WHEN** a URL responde 405, 501 ou 403 a um HEAD
- **THEN** uma requisição GET com Range de poucos bytes é feita
- **AND** o status dessa segunda requisição é o registrado

#### Scenario: recusa de método não é arquivo removido

- **WHEN** o HEAD responde 403 e o GET com Range responde 206
- **THEN** a classe é `disponivel`
- **AND** o recurso NÃO é marcado como indisponível

#### Scenario: redirecionamento

- **WHEN** a URL responde 302 para outro endereço
- **THEN** o redirecionamento é seguido até o limite de 5 saltos
- **AND** o status final é o registrado

### Requirement: Classificação estável do estado

O verificador SHALL classificar cada recurso em `disponivel`, `indisponivel`,
`bloqueado`, `cadeia_incompleta`, `dominio_inexistente`, `instavel` ou
`nao_verificado`.

Cada classe SHALL afirmar apenas o que a verificação sustenta, e o conjunto
SHALL separar **"o arquivo não está lá"** de **"não consegui verificar"**:

- `disponivel` — respondeu com sucesso;
- `indisponivel` — **ausência confirmada**: o host demonstrou responder e negou
  este endereço;
- `bloqueado` — o host recusa este cliente; nada é afirmado sobre o arquivo;
- `cadeia_incompleta` — o servidor não envia a cadeia de certificação; o arquivo
  é presumido acessível a cliente que completa a cadeia sozinho;
- `dominio_inexistente` — o domínio não resolve em DNS;
- `instavel` — estado de um instante: tempo esgotado, 5xx, 429 ou falha de
  leitura;
- `nao_verificado` — não havia o que verificar.

`indisponivel` SHALL exigir que o host tenha demonstrado responder, e NÃO SHALL
ser atribuída a recurso cujo host recusou toda a verificação. `instavel` NÃO
SHALL absorver falha de certificação nem de resolução de nome, que são estados
persistentes e não instantâneos.

#### Scenario: recurso disponível

- **WHEN** o status final está entre 200 e 299
- **THEN** a classe é `disponivel`

#### Scenario: ausência confirmada

- **WHEN** o status final é 404 ou 410
- **AND** o host respondeu com sucesso a algum outro recurso da varredura
- **THEN** a classe é `indisponivel`

#### Scenario: negativa de acesso a um arquivo, em host que responde

- **WHEN** o status final é 403 depois da degradação para GET
- **AND** o host respondeu com sucesso a algum outro recurso da varredura
- **THEN** a classe é `indisponivel`
- **AND** a negativa é atribuída ao arquivo, não ao host

#### Scenario: servidor lento ou intermitente

- **WHEN** a requisição excede 10 segundos ou retorna 5xx
- **THEN** a classe é `instavel`
- **AND** o recurso NÃO é tratado como removido

#### Scenario: cadeia de certificação incompleta

- **WHEN** a conexão TLS falha porque o servidor não enviou o certificado
      intermediário que assinou a folha
- **THEN** a classe é `cadeia_incompleta`
- **AND** o motivo registrado distingue esse caso de certificado inválido
- **AND** o recurso NÃO é tratado como removido nem como instável

#### Scenario: certificado inválido

- **WHEN** a conexão TLS falha por nome que não corresponde ao certificado, ou
      por validade expirada
- **THEN** a classe é `instavel` e o motivo nomeia a falha de certificado
- **AND** o recurso NÃO é classificado como `cadeia_incompleta`

#### Scenario: domínio que não resolve

- **WHEN** o nome do host não resolve em DNS
- **THEN** a classe é `dominio_inexistente`
- **AND** nenhuma requisição HTTP é tentada

#### Scenario: recurso sem URL

- **WHEN** o recurso não possui URL
- **THEN** a classe é `nao_verificado`
- **AND** nenhuma requisição de rede é feita

#### Scenario: link que não é uma URL

- **WHEN** o campo de link contém texto que não é endereço — frase, caminho com
      barra invertida, ou prefixo `URL:` esquecido no valor
- **THEN** a classe é `nao_verificado` e o motivo é registrado
- **AND** nenhuma requisição de rede é feita
- **AND** o valor original NÃO é corrigido por inferência

### Requirement: Registro do momento da checagem

O verificador SHALL gravar `checado_em` em UTC e `latencia_ms` para cada
recurso verificado, e SHALL gravar o motivo quando a classe não vier de um
status HTTP, para que o diagnóstico de qualidade do catálogo possa distinguir
link ausente de link malformado e de tempo esgotado.

#### Scenario: carimbo sempre em UTC

- **WHEN** um recurso é verificado
- **THEN** `checado_em` está em UTC ISO 8601
- **AND** independe do fuso da máquina que executou o pipeline

### Requirement: Contenção de carga por host

O verificador SHALL limitar a 2 requisições simultâneas por host e a 20 no
total, e SHALL identificar-se por User-Agent com nome do projeto e contato.

#### Scenario: muitos recursos do mesmo órgão

- **WHEN** 500 recursos pertencem ao mesmo domínio
- **THEN** no máximo 2 requisições simultâneas atingem esse domínio
- **AND** outros domínios continuam sendo verificados em paralelo

#### Scenario: identificação do agente

- **WHEN** qualquer requisição é emitida
- **THEN** o cabeçalho User-Agent identifica o projeto e um endereço de contato

### Requirement: Reverificação seletiva

O verificador SHALL aceitar `--idade-maxima DIAS` e verificar apenas recursos
cuja última checagem seja mais antiga que o limite, e SHALL aceitar
`--somente-falhas` para reprocessar apenas os que não estão `disponivel`.

Com sete classes, `--somente-falhas` SHALL definir falha por exclusão —
qualquer classe diferente de `disponivel` — em vez de enumerar duas. Enumerar
deixaria as classes novas fora do reprocessamento sem que ninguém percebesse.

`--somente-falhas` SHALL aceitar a restrição a uma classe, para que reverificar
um host que voltou a responder não obrigue a reprocessar o catálogo inteiro.

#### Scenario: execução incremental

- **WHEN** executado com `--idade-maxima 7`
- **THEN** recursos checados há menos de 7 dias são ignorados
- **AND** o log informa quantos foram pulados

#### Scenario: reprocessar apenas falhas

- **WHEN** executado com `--somente-falhas`
- **THEN** apenas recursos cuja classe não é `disponivel` são checados
- **AND** isso inclui as classes `bloqueado`, `cadeia_incompleta` e
      `dominio_inexistente`

#### Scenario: reprocessar uma classe só

- **WHEN** executado restringindo a reverificação à classe `bloqueado`
- **THEN** apenas recursos dessa classe são checados
- **AND** as demais classes permanecem intocadas no banco

### Requirement: Reconhecimento de host que bloqueia o verificador

O verificador SHALL reconhecer, **depois** de concluir a varredura, os hosts que
recusaram toda a verificação, e SHALL reclassificar seus recursos como
`bloqueado`.

O reconhecimento SHALL ser uma passada sobre o resultado agregado por host, e
NÃO SHALL ser decidido recurso por recurso: a evidência de bloqueio é a ausência
de qualquer sucesso no host inteiro, que nenhuma requisição isolada revela.

O critério SHALL exigir as três condições ao mesmo tempo: volume mínimo de
recursos verificados no host, **zero** respostas de sucesso, e maioria absoluta
de 403. As três juntas separam recusa de host de negativa por arquivo.

Esta requisição NÃO altera a degradação de `HEAD` para `GET` diante de 403: a
reclassificação só considera o status final, depois da segunda tentativa.

#### Scenario: host que recusa toda a verificação

- **WHEN** um host tem volume suficiente de recursos verificados, nenhum deles
      respondeu com sucesso, e a maioria respondeu 403
- **THEN** todos os recursos desse host recebem a classe `bloqueado`
- **AND** o motivo registrado nomeia a recusa do host
- **AND** nenhum deles é contado como ausência confirmada

#### Scenario: host que responde e nega arquivos específicos

- **WHEN** um host respondeu com sucesso a parte dos recursos e 403 a outros
- **THEN** os recursos com 403 permanecem `indisponivel`
- **AND** o host NÃO é reconhecido como bloqueador

#### Scenario: poucos recursos não bastam como evidência

- **WHEN** um host tem menos recursos verificados que o volume mínimo, todos com
      403
- **THEN** o host NÃO é reconhecido como bloqueador
- **AND** a classe permanece a que o status determinou

#### Scenario: reclassificação sem repetir a rede

- **WHEN** o reconhecimento é executado sobre uma varredura já gravada
- **THEN** as classes são corrigidas a partir dos status armazenados
- **AND** nenhuma requisição HTTP nova é emitida

### Requirement: Diagnóstico que declara o próprio ponto cego

O diagnóstico impresso ao fim da varredura SHALL relatar as sete classes com
suas definições, e SHALL listar os hosts reconhecidos como bloqueadores com a
contagem de recursos de cada um.

O total de ausência confirmada NÃO SHALL ser apresentado sozinho quando houver
host bloqueado: o diagnóstico SHALL declarar quantos recursos ficaram sem
verificação possível, para que a proporção de links mortos não seja lida como se
fosse medida quando parte dela é cegueira do verificador.

#### Scenario: varredura com host bloqueado

- **WHEN** a varredura termina e ao menos um host foi reconhecido como bloqueador
- **THEN** o diagnóstico lista esses hosts e quantos recursos cada um tem
- **AND** informa o total de recursos sem verificação possível junto do total de
      ausência confirmada

#### Scenario: varredura sem host bloqueado

- **WHEN** nenhum host é reconhecido como bloqueador
- **THEN** o diagnóstico informa isso explicitamente
- **AND** a ausência confirmada é apresentada como medida completa
