# Gerenciar a chave de API do usuário

## Por que

Na versão desktop a credencial pertence ao usuário, e isso inverte as
responsabilidades: não somos donos da chave, somos depositários dela. Um
aplicativo que guarda credencial alheia de forma descuidada é pior que um que
não a guarda.

Duas regras organizam tudo. A chave vive no cofre de credenciais do sistema
operacional, não em arquivo de configuração. E a chave nunca atravessa a
fronteira para o WebView — todas as chamadas à API partem do núcleo Rust.

A segunda regra tem motivo prático além do princípio: a API da Anthropic não é
desenhada para ser chamada diretamente de navegador, e contornar isso seria
tratar um sinal de alerta como obstáculo.

## O que muda

- Módulo `chave.rs` usando o cofre do sistema via crate keyring.
- Validação da chave contra a API no momento da configuração, com retorno
  compreensível para quem não é técnico.
- Todas as chamadas à Anthropic partindo do núcleo Rust.
- Remoção da chave pelo usuário, com efeito imediato.

## Fora de escopo

- Qualquer forma de proxy, repasse ou armazenamento remoto da chave.
- Suporte a outros provedores de modelo, que fica para depois.

## Impacto

- Introduz dependência do cofre nativo: Keychain no macOS, Credential Manager no
  Windows, Secret Service no Linux.
- Em ambientes Linux sem Secret Service disponível, é preciso degradar de forma
  explícita e honesta, sem gravar a chave em disco às escondidas.
