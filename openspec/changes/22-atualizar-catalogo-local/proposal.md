# Obter e atualizar o catálogo local

## Por que

O aplicativo precisa do `dados.db`, dos vetores e do modelo ONNX para funcionar.
Embutir tudo no instalador seria simples e errado: o pacote passaria de cem
megabytes, e qualquer atualização do catálogo exigiria publicar versão nova do
programa, com nova assinatura e novo download completo.

Separar catálogo de aplicativo desacopla dois ciclos que têm ritmos diferentes.
O catálogo muda quando o portal muda, com frequência mensal. O aplicativo muda
quando o código muda. Um não deve arrastar o outro.

Isso também resolve, na versão desktop, o mesmo problema de versionamento já
tratado na mudança 11: o cache de respostas é chaveado pela versão do catálogo, e
aqui essa versão passa a ser um artefato explícito e verificável.

## O que muda

- Download do catálogo na primeira execução, a partir de uma release publicada.
- Verificação de integridade por soma de verificação antes de ativar.
- Substituição atômica, de modo que uma atualização interrompida nunca deixe o
  aplicativo sem catálogo utilizável.
- Verificação periódica de catálogo novo, com atualização sob consentimento.

## Fora de escopo

- Execução do pipeline no dispositivo do usuário, que permanece responsabilidade
  do mantenedor.
- Atualização automática do próprio aplicativo.

## Impacto

- Introduz dependência de um endereço de distribuição estável para as releases.
- Primeira execução exige conexão; execuções seguintes, não.
