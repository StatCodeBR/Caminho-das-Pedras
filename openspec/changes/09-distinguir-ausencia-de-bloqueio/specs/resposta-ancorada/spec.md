## MODIFIED Requirements

### Requirement: Sinalização de recursos indisponíveis

A API SHALL incluir recursos com link indisponível na resposta, marcados como
tal, em vez de omiti-los, e SHALL sempre oferecer o link da página do conjunto
no portal.

A marcação SHALL derivar das sete classes de saúde, e SHALL afirmar ao usuário
apenas o que a verificação sustenta. A API NÃO SHALL tratar como disponível toda
classe que não seja `indisponivel`: derivar a marcação por exclusão faz com que
classe nova chegue ao usuário como link verificado sem que ninguém decida isso.

Cada classe SHALL cair em um de três tratamentos:

- **apresentado sem ressalva** — `disponivel` e `cadeia_incompleta`. O segundo
  falha apenas em cliente que não completa a cadeia de certificação sozinho;
  quem abre o link no navegador baixa o arquivo, e alertar seria descrever a
  nossa ferramenta, não o link.
- **marcado como inacessível** — `indisponivel` e `dominio_inexistente`. Nos
  dois há evidência: o host respondeu e negou o endereço, ou o domínio não
  existe mais.
- **apresentado com ressalva de não verificado** — `bloqueado`, `instavel` e
  `nao_verificado`. A ressalva SHALL dizer que o link não pôde ser conferido, e
  NÃO SHALL afirmar que o arquivo foi removido.

A ressalva de não verificado NÃO SHALL ser redigida como defeito do órgão
publicador: em `bloqueado` a informação que temos é sobre o nosso acesso, não
sobre o arquivo.

#### Scenario: conjunto com recurso removido

- **WHEN** um conjunto recuperado tem recursos classificados como `indisponivel`
      ou `dominio_inexistente`
- **THEN** esses recursos aparecem marcados como indisponíveis
- **AND** o link para a página do conjunto no dados.gov.br é apresentado

#### Scenario: recurso em host que recusa o verificador

- **WHEN** um conjunto recuperado tem recursos classificados como `bloqueado`
- **THEN** esses recursos NÃO aparecem marcados como indisponíveis
- **AND** aparecem com a ressalva de que o link não pôde ser verificado
- **AND** a resposta NÃO afirma que o arquivo foi removido

#### Scenario: recurso cujo servidor não envia a cadeia de certificação

- **WHEN** um recurso está classificado como `cadeia_incompleta`
- **THEN** ele é apresentado sem ressalva, como disponível
- **AND** NÃO é marcado como indisponível nem como não verificado

#### Scenario: classe de saúde desconhecida pela API

- **WHEN** um recurso traz classe de saúde que a API não reconhece
- **THEN** ele é apresentado com a ressalva de não verificado
- **AND** NÃO é apresentado como disponível

#### Scenario: catálogo sem verificação de saúde

- **WHEN** o banco não traz a coluna de classe de saúde, ou o recurso não tem
      classe registrada
- **THEN** o recurso é apresentado sem ressalva
- **AND** a resposta NÃO afirma que o link foi verificado

#### Scenario: preferência por recursos disponíveis

- **WHEN** um conjunto possui recursos em classes diferentes
- **THEN** os apresentados sem ressalva vêm primeiro
- **AND** em seguida os de ressalva de não verificado
- **AND** por último os marcados como inacessíveis
