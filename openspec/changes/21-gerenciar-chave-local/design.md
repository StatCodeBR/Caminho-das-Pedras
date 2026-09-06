# Design — chave local

## Decisão: cofre do sistema, nunca arquivo

Arquivo de configuração em texto puro é acessível a qualquer processo do usuário
e acaba em backup, em sincronização de nuvem e em captura de tela de suporte. O
cofre nativo resolve isso com a garantia que o sistema operacional já oferece.

Consequência: em Linux sem Secret Service disponível não há onde guardar com
segurança. Nesse caso o aplicativo informa a limitação e opera com a chave apenas
na memória da sessão, exigindo que seja informada a cada abertura. É pior em
conveniência e correto em segurança — e o usuário fica sabendo por quê.

## Decisão: a chave não cruza para o WebView

O núcleo Rust lê a chave do cofre e faz a requisição. O frontend recebe apenas
fragmentos de texto. Assim, qualquer conteúdo inesperado renderizado na WebView
não tem como alcançar a credencial.

Isso implica que a configuração de chave é um comando que **escreve** no cofre e
nunca um que lê. A interface pode perguntar se existe chave e exibir os últimos
caracteres para identificação, mas não obtém o valor.

## Decisão: validar na configuração, não no primeiro uso

Uma chave inválida descoberta no meio da primeira pergunta produz erro confuso.
A validação acontece quando o usuário salva, com uma requisição mínima, e o
retorno é traduzido para linguagem comum: chave inválida, sem crédito, sem
conexão.

## Decisão: falha da API nunca derruba o produto

Se a chamada falhar por qualquer motivo, o aplicativo recai no modo de
recuperação já especificado na mudança 20. O usuário continua encontrando dados.
Esse é o mesmo princípio de degradação graciosa da versão servidor, aplicado a
outra causa.

## Riscos aceitos

Custos de uso são do usuário e podem surpreendê-lo. Mitigação: exibir contagem
de chamadas da sessão e um lembrete, na configuração, de que o consumo é cobrado
diretamente pelo provedor.
