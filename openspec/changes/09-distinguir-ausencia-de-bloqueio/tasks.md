# Tarefas — distinguir ausência de bloqueio

A classe de um recurso deixa de ser decidível só pelo próprio recurso. A
primeira passada grava o que observou naquele endereço; a segunda, com o
agregado por host à vista, decide entre ausência confirmada e bloqueio. As
tarefas seguem essa ordem: primeiro enxergar a causa, depois classificar, depois
afirmar.

## Causa da falha de rede

- [x] Percorrer `__cause__` e `__context__` da exceção até achar
      `ssl.SSLCertVerificationError` ou `socket.gaierror`, sem casar substring
      de mensagem
- [x] Reconhecer cadeia incompleta pelo `verify_code`, separando-a de nome
      divergente e de validade expirada
- [x] Classificar domínio que não resolve como `dominio_inexistente`, sem tentar
      requisição HTTP
- [x] Registrar em `motivo_saude` a causa distinta em cada caso, para que os
      8.280 `ConnectError` de hoje deixem de ser um rótulo único
- [x] Gravar cadeias de exceção como fixture e testar a classificação contra
      elas, para que troca de ambiente falhe em teste

## Classes e classificação

- [x] Acrescentar `bloqueado`, `cadeia_incompleta` e `dominio_inexistente` a
      `CLASSES` e ao glossário, com a definição que cada uma afirma
- [x] Separar a classe provisória, decidida pelo status do recurso, da classe
      final, decidida com o agregado do host — `classificar()` não tem como
      saber que o host nunca respondeu
- [x] Manter a degradação de `HEAD` para `GET` diante de 403 exatamente como
      está: o `www.gov.br` responde 403 a `HEAD` e 206 ao `GET` com `Range`

## Reconhecimento de host que bloqueia

- [x] Agregar o resultado por host: verificados, sucessos e 403
- [x] Reclassificar como `bloqueado` o host com no mínimo 20 recursos, zero
      sucessos e maioria de 403
- [x] Preservar como `indisponivel` os 339 recursos com 403 em host que também
      teve sucesso
- [x] Não reconhecer bloqueador a partir de volume abaixo do mínimo — o `doi.org`
      tem um único 403 no catálogo
- [x] Permitir executar o reconhecimento sobre varredura já gravada, sem emitir
      requisição
- [x] Testar o critério com host de 5.257 negativas, host de 24, host de 11 e
      host misto

## Diagnóstico

- [x] Relatar as sete classes com suas definições
- [x] Listar os hosts reconhecidos como bloqueadores e a contagem de cada um
- [x] Apresentar o total sem verificação possível junto do total de ausência
      confirmada, nunca a ausência sozinha
- [x] Declarar explicitamente quando nenhum host foi reconhecido como bloqueador

## Reverificação seletiva

- [x] Redefinir `--somente-falhas` por exclusão de `disponivel`, em vez de
      enumerar duas classes
- [x] Aceitar restrição da reverificação a uma classe
- [x] Testar que as classes novas entram no reprocessamento

## Sinalização na resposta

- [x] Substituir o booleano `Recurso.disponivel` por estado de três valores
- [x] Mapear classe para tratamento em um lugar único, com classe desconhecida
      caindo em não verificado
- [x] Apresentar `cadeia_incompleta` sem ressalva, e `bloqueado` com ressalva
      que não afirma remoção nem culpa o órgão
- [x] Marcar como inacessível apenas `indisponivel` e `dominio_inexistente`
- [x] Manter o comportamento para catálogo sem a coluna de saúde: sem ressalva e
      sem afirmar verificação
- [x] Ordenar os recursos pelos três tratamentos
- [x] Levar o estado ao evento final do SSE
- [x] Atualizar os testes de roteamento e de recuperação que hoje esperam o
      booleano

## Interface

- [x] Renderizar a ressalva de não verificado, distinta da marca de inacessível
- [x] Conferir o texto da ressalva em português simples, sem jargão

## Migração dos dados já medidos

- [x] Rodar o reconhecimento de bloqueio sobre o banco atual, corrigindo os
      5.487 rótulos sem rede
- [x] Resolver DNS uma vez por host dos 149 com `ConnectError`, separando os
      1.047 recursos de domínio morto
- [x] Reverificar a classe `instavel` — 13.213 recursos, cerca de 20 minutos —
      para obter a distinção de TLS. Estreitado na execução: os 7.273
      `ConnectError` restantes vivem todos ali, e incluir `bloqueado` seriam
      5.487 pedidos a hosts que já nos negam, enquanto `indisponivel` é ausência
      já confirmada
- [x] Registrar a distribuição final das sete classes

## Documentação

- [x] Registrar em `docs/limitacoes-conhecidas.md` que a varredura completa
      rodou. Não há limitação a substituir: a dívida de que a saúde nunca tinha
      rodado estava anotada na conversa, não no arquivo
- [x] Registrar que bloqueio de host é ponto cego permanente deste verificador,
      com os três hosts e os números
- [x] Registrar que o limiar de 20 deixa `mapa.cultura.gov.br` classificado como
      ausência, e por que a escolha foi essa
