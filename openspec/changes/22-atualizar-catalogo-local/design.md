# Design — catálogo local

## Decisão: catálogo distribuído à parte do aplicativo

O instalador carrega apenas o programa. Catálogo, vetores e modelo são baixados
na primeira execução para o diretório de dados do aplicativo.

Além do tamanho, isso permite corrigir um problema de dados sem republicar
binário assinado — o que em macOS e Windows envolve notarização e certificado,
processos lentos que não deveriam estar no caminho de uma correção de catálogo.

## Decisão: substituição atômica

O download vai para um diretório temporário. Só depois de verificada a soma de
verificação o novo catálogo é promovido, por renomeação, e o anterior é removido.

Assim, uma queda de energia no meio da atualização deixa o usuário com o catálogo
antigo íntegro, nunca com um banco truncado. Um SQLite parcialmente escrito é
pior que um desatualizado, porque falha de formas confusas.

## Decisão: atualização com consentimento

A verificação de nova versão é automática; a substituição não. O usuário é
avisado e decide quando baixar, porque a operação consome dados móveis e pode ser
inoportuna.

Exceção: quando não há catálogo algum, o download é necessário e acontece sem
pergunta, com indicação clara de progresso.

## Decisão: versão do catálogo é dado de primeira classe

A versão é exibida na interface, registrada junto às respostas e usada como
chave do cache local. Uma pessoa que cita o resultado do aplicativo em um
relatório precisa saber de qual retrato do catálogo aquilo veio.

## Riscos aceitos

O catálogo local envelhece entre atualizações, e o usuário pode não encontrar um
conjunto publicado recentemente. Mitigação: exibir a data do catálogo junto às
respostas e oferecer o link do portal para consulta direta quando a busca não
encontra nada.
