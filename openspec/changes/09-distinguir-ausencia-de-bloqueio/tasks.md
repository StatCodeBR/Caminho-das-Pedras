# Tarefas — distinguir ausência de bloqueio

A classe de um recurso deixa de ser decidível só pelo próprio recurso. A
primeira passada grava o que observou naquele endereço; a segunda, com o
agregado por host à vista, decide entre ausência confirmada e bloqueio. As
tarefas seguem essa ordem: primeiro enxergar a causa, depois classificar, depois
afirmar.

## Causa da falha de rede

- [ ] Percorrer `__cause__` e `__context__` da exceção até achar
      `ssl.SSLCertVerificationError` ou `socket.gaierror`, sem casar substring
      de mensagem
- [ ] Reconhecer cadeia incompleta pelo `verify_code`, separando-a de nome
      divergente e de validade expirada
- [ ] Classificar domínio que não resolve como `dominio_inexistente`, sem tentar
      requisição HTTP
- [ ] Registrar em `motivo_saude` a causa distinta em cada caso, para que os
      8.280 `ConnectError` de hoje deixem de ser um rótulo único
- [ ] Gravar cadeias de exceção como fixture e testar a classificação contra
      elas, para que troca de ambiente falhe em teste

## Classes e classificação

- [ ] Acrescentar `bloqueado`, `cadeia_incompleta` e `dominio_inexistente` a
      `CLASSES` e ao glossário, com a definição que cada uma afirma
- [ ] Separar a classe provisória, decidida pelo status do recurso, da classe
      final, decidida com o agregado do host — `classificar()` não tem como
      saber que o host nunca respondeu
- [ ] Manter a degradação de `HEAD` para `GET` diante de 403 exatamente como
      está: o `www.gov.br` responde 403 a `HEAD` e 206 ao `GET` com `Range`

## Reconhecimento de host que bloqueia

- [ ] Agregar o resultado por host: verificados, sucessos e 403
- [ ] Reclassificar como `bloqueado` o host com no mínimo 20 recursos, zero
      sucessos e maioria de 403
- [ ] Preservar como `indisponivel` os 339 recursos com 403 em host que também
      teve sucesso
- [ ] Não reconhecer bloqueador a partir de volume abaixo do mínimo — o `doi.org`
      tem um único 403 no catálogo
- [ ] Permitir executar o reconhecimento sobre varredura já gravada, sem emitir
      requisição
- [ ] Testar o critério com host de 5.257 negativas, host de 24, host de 11 e
      host misto

## Diagnóstico

- [ ] Relatar as sete classes com suas definições
- [ ] Listar os hosts reconhecidos como bloqueadores e a contagem de cada um
- [ ] Apresentar o total sem verificação possível junto do total de ausência
      confirmada, nunca a ausência sozinha
- [ ] Declarar explicitamente quando nenhum host foi reconhecido como bloqueador

## Reverificação seletiva

- [ ] Redefinir `--somente-falhas` por exclusão de `disponivel`, em vez de
      enumerar duas classes
- [ ] Aceitar restrição da reverificação a uma classe
- [ ] Testar que as classes novas entram no reprocessamento

## Sinalização na resposta

- [ ] Substituir o booleano `Recurso.disponivel` por estado de três valores
- [ ] Mapear classe para tratamento em um lugar único, com classe desconhecida
      caindo em não verificado
- [ ] Apresentar `cadeia_incompleta` sem ressalva, e `bloqueado` com ressalva
      que não afirma remoção nem culpa o órgão
- [ ] Marcar como inacessível apenas `indisponivel` e `dominio_inexistente`
- [ ] Manter o comportamento para catálogo sem a coluna de saúde: sem ressalva e
      sem afirmar verificação
- [ ] Ordenar os recursos pelos três tratamentos
- [ ] Levar o estado ao evento final do SSE
- [ ] Atualizar os testes de roteamento e de recuperação que hoje esperam o
      booleano

## Interface

- [ ] Renderizar a ressalva de não verificado, distinta da marca de inacessível
- [ ] Conferir o texto da ressalva em português simples, sem jargão

## Migração dos dados já medidos

- [ ] Rodar o reconhecimento de bloqueio sobre o banco atual, corrigindo os
      5.487 rótulos sem rede
- [ ] Resolver DNS uma vez por host dos 149 com `ConnectError`, separando os
      1.047 recursos de domínio morto
- [ ] Reverificar o subconjunto que não está `disponivel` — cerca de 26.350
      recursos, aproximadamente 40 minutos — para obter a distinção de TLS
- [ ] Registrar a distribuição final das sete classes

## Documentação

- [ ] Substituir em `docs/limitacoes-conhecidas.md` a limitação de que a saúde
      nunca rodou sobre o catálogo completo
- [ ] Registrar que bloqueio de host é ponto cego permanente deste verificador,
      com os três hosts e os números
- [ ] Registrar que o limiar de 20 deixa `mapa.cultura.gov.br` classificado como
      ausência, e por que a escolha foi essa
