# Design — distribuir o catálogo como release

## Decisão: a soma fica no repositório, os bytes ficam na release

É a divisão que dá integridade sem versionar peso. O Git guarda 64 caracteres
que dizem *qual* catálogo esta imagem deve servir; a release guarda os megabytes.

O efeito prático é que a autoridade continua sendo o repositório. Trocar o
catálogo de uma imagem exige um commit, esse commit tem autor e data, e um
`git log` responde à pergunta "quando o catálogo mudou e para qual". Se a soma
morasse junto do artefato, quem publicasse a release poderia trocar os dois ao
mesmo tempo e a verificação não verificaria nada.

## Decisão: gzip, não zstd

Medido sobre o banco atual de 26,7 MB:

| | tamanho | proporção | projeção p/ 155 MB |
|---|---|---|---|
| original | 26,7 MB | 100% | 155 MB |
| gzip -9 | 5,3 MB | 20% | ~31 MB |
| zstd -19 | 3,6 MB | 13% | ~21 MB |

O zstd ganha 10 MB e custa um pacote a mais na imagem: `python:3.12-slim` não o
traz, e o Python não o tem na biblioteca padrão. O gzip está nos dois — dá para
descomprimir com o Python que já está lá, sem instalar nada e sem aumentar a
superfície da imagem.

Dez megabytes de download uma vez por build não valem uma dependência
permanente.

## Decisão: falhar é o comportamento correto

Se o download falhar, ou a soma divergir, o build para. Não existe recurso a
catálogo vazio, nem a "o último que deu certo".

O motivo é que catálogo errado não parece errado. As respostas continuam bem
formadas, os links continuam válidos, as fichas continuam legíveis — só faltam
conjuntos, ou sobram conjuntos velhos. O defeito apareceria semanas depois, para
alguém que procurasse um dado que deveria estar lá, e seria indistinguível de
uma falha de busca. Falhar no build é barulhento e imediato; degradar é
silencioso e caro.

## Decisão: versão fixa, nunca "a mais recente"

O repositório declara a versão da release. Publicar catálogo novo não muda
nenhum build existente.

Com referência móvel, reconstruir a imagem para corrigir uma linha de CSS
traria junto um catálogo diferente, e a imagem deixaria de ser função do commit.
Isso quebra o rastro de qual catálogo respondeu o quê — que foi a razão de pôr o
banco dentro da imagem em vez de num volume, na mudança 09.

O custo é um commit por atualização de catálogo. É exatamente o registro que se
quer.

## Decisão: um escape para desenvolvimento

O build aceita um artefato local no lugar do download. Sem isso, testar uma
mudança no Dockerfile exigiria publicar uma release, e publicar release para
testar build é o tipo de atrito que faz as pessoas pararem de testar.

Nesse caminho a verificação de soma não se aplica: o arquivo é local e o
desenvolvedor sabe o que colocou ali. O padrão continua sendo o publicado, para
que o descuido leve ao caminho seguro.

## Decisão: publicar com `curl`, não com `gh`

O `gh` não está instalado no ambiente de desenvolvimento; o `curl` está. Publicar
por `curl` significa duas chamadas à API do GitHub e um token no ambiente — mais
verboso, e sem dependência nova.

O token precisa de permissão de escrita em releases. Ele nunca entra no
repositório nem em log, pela regra 6 do projeto.

## Riscos aceitos

**O build passa a exigir rede.** Já exigia, para instalar dependências; agora
depende também do GitHub estar de pé. Em troca, o repositório para de crescer e
o limite de 100 MB deixa de existir.

**Os `dados.db` já commitados continuam no histórico.** Reescrever o histórico
de um repositório já publicado é operação de risco desproporcional ao ganho: o
peso já está lá, e o que importa é que ele pare de crescer. Se um dia o clone
ficar pesado demais, aí sim vale um `filter-repo` planejado.

**Quem clonar não terá catálogo.** É consequência desejada: o artefato deixa de
vir de graça e passa a ser um passo explícito, documentado no README. O que se
perde em conveniência se ganha em não haver dúvida sobre qual catálogo se está
usando.
