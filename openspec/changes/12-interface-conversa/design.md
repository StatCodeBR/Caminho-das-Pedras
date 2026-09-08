# Design — interface de conversa

## Decisão: `fetch` com leitura de fluxo, não `EventSource`

`EventSource` é a API nativa para SSE e seria a escolha óbvia, mas ela só faz
`GET` e não envia corpo. A pergunta iria na query string — visível no histórico
do navegador e nos logs de qualquer proxy no caminho, com limite de tamanho e
problemas de codificação em português.

A alternativa é `fetch` com `POST` e leitura incremental do corpo da resposta,
decodificando os eventos no cliente. Custa um analisador de umas vinte linhas e
resolve os três problemas de uma vez.

Consequência: o analisador precisa lidar com fragmento cortado no meio de um
evento, porque o corte do fluxo não respeita a fronteira das mensagens. É a única
parte não trivial do cliente e merece teste próprio.

## Decisão: o navegador não fala direto com a API

A página é servida por um endereço e a API responde em outro. Falar direto
exigiria CORS aberto na API, o que é configuração de segurança feita para
contornar um problema de arquitetura.

O SvelteKit expõe uma rota de servidor que repassa a pergunta à API e devolve o
fluxo ao navegador. A API deixa de precisar de CORS, o endereço interno dela não
vai ao cliente, e em produção só o container do `web` é exposto pelo Traefik.

O repasse precisa transmitir sem acumular — bufferizar aqui desfaria o streaming
que a mudança 09 já entrega.

## Decisão: Tailwind puro, sem shadcn-svelte nesta versão

A tela tem um campo, um botão, um bloco de texto e uma lista de cartões. Instalar
uma biblioteca de componentes para isso acopla a aparência a decisões que não
precisam ser tomadas antes de existir tela funcionando — e shadcn-svelte mudou
bastante, o que transforma cada componente numa consulta à documentação.

Fica registrado como reversível: os componentes podem ser trocados depois, sem
tocar na lógica de fluxo.

## Decisão: uma rota, sem histórico de conversa

A tela responde a uma pergunta por vez e substitui a resposta anterior. Não há
histórico, não há contexto acumulado, não há sessão.

Isso não é simplificação preguiçosa: o sistema recupera por pergunta e responde
ancorado nas fichas daquela recuperação. Uma segunda pergunta não se beneficia da
primeira, e fingir uma conversa criaria a expectativa de que ela se lembra — que
é justamente o tipo de promessa que este projeto não cumpre.

## Decisão: a data exibida diz de que data se trata

O catálogo traz duas datas por conjunto: quando os dados foram atualizados e
quando o registro foi editado. Elas divergem com frequência, e a primeira falta
em cerca de um quinto dos conjuntos da amostra.

A regra é apresentar a data dos dados quando ela existir, identificada como tal;
cair para a data do registro quando não existir, identificada como tal; e dizer
que não foi declarada quando faltarem as duas. Um traço mudo faria o usuário
supor a interpretação mais otimista.

Isso obriga a API a devolver as duas datas separadas, o que a mudança 09 não faz
— daí a alteração na capacidade `resposta-ancorada`.

## Decisão: a origem da resposta em português, não no jargão da API

A API declara `correspondencia_direta`, `redigida_pelo_modelo` e
`modo_reduzido`. Esses nomes servem à telemetria, não ao usuário. A tela traduz:
"encontrado direto no catálogo", "resposta escrita a partir das fichas",
"não consegui redigir, veja os conjuntos encontrados".

Exibir a origem é honestidade sobre como a resposta foi produzida, e só cumpre
esse papel se for compreensível para quem não sabe o que é um modelo de
linguagem.

## Riscos aceitos

**Sem cache, cada pergunta custa o que custar.** A mudança 11 resolve; até lá,
uma pergunta repetida paga de novo. Aceitável enquanto o tráfego é de
demonstração.

**A verificação de acessibilidade é superficial.** Esta versão garante contraste,
foco visível e rótulos nos campos, sem auditoria com leitor de tela. Registrar
como dívida é mais honesto que declarar acessível o que não foi testado.

**Sintaxe do Svelte 5 a confirmar na implementação.** Runes mudaram bastante e a
consulta ao Context7 falhou por falta de credencial durante o planejamento. O
design acima não depende de sintaxe específica, mas a implementação deve
verificar a API antes de escrever componente, conforme a regra do projeto.
