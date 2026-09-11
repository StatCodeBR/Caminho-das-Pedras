# Desenho — medir termo comum sem a coluna de tags

## O problema em uma frase

A frequência documental é uma boa medida de "esta palavra não discrimina" apenas
enquanto o texto medido for escrito por quem publica os dados. Assim que o
próprio sistema escreve dentro do texto medido, a estatística passa a refletir as
decisões do sistema.

## Como o vão fechou

Nas 505 fichas a distribuição separava limpo, e o limiar de 0,15 caía num vazio:

```
de 99%  da 58%  dados 51%  qual 46%  sobre 43%  quantos 26%  onde 19%
————————————————————— vão —————————————————————
minha 8,8%  cidade 5%  gastos 3%  dengue 1,2%  aeroportos 0,8%
```

Nas 19.958 essas mesmas doze palavras quase não se moveram — `de` foi a 98,6%,
`onde` a 25,9%, `minha` a 9,0%. O que mudou foi o que apareceu **entre** elas:

```
19,7 foram      19,3 nacional    18,5 encontro   18,3 estao
17,6 quantos    17,2 tecnologia  16,8 instituto  16,6 ciencia
16,1 mais       15,8 pessoas     15,7 educacao   15,4 estado
15,3 foi        15,1 ipea  ——— 0,15 ———  14,8 esta   14,7 pela
14,1 quantas    14,0 inovacao    14,0 credito    13,4 financeira
```

Palavra de função e palavra de assunto ficaram intercaladas. `quantos` (17,6%)
encosta em `tecnologia` (17,2%); `ipea` (15,1%) encosta em `foi` (15,3%). A linha
de corte erra nos dois sentidos ao mesmo tempo.

## Três causas, uma tratável

A quebra da frequência por coluna do índice separa as fontes:

1. **Vocabulário controlado injetado (`tags`).** `economia` 99% via tags,
   `financas` 100%, `publicas` 97%, `administracao` 99%, `inclusao` 99%,
   `emprego` 100%. São os rótulos de tema que a indexação escreve. Autoinfligido,
   e é o que esta mudança corrige.

2. **Cacoetes do modelo (`perguntas`, `resumo`).** `longo` está em 25,5% das
   fichas, 4.377 delas com a palavra na coluna `perguntas`: é "ao longo do tempo",
   escrito milhares de vezes pelo mesmo modelo com o mesmo prompt. Um corpus de
   19.455 documentos de autoria única tem tiques que a estatística lê como
   gramática.

3. **Concentração real do catálogo (`orgao`, `resumo`).** `banco` 22,9% e
   `central` 21,5%, quase tudo em nome de órgão: o BCB publica mesmo um quinto do
   acervo. Esta é a única das três em que "termo comum" descreve o catálogo, e
   não um artefato — aqui o filtro está certo em agir.

Tratamos (1). (2) e (3) ficam registradas como limitação conhecida: (2) só se
resolve variando o prompt ou o modelo, e (3) é verdade sobre o mundo.

## Por que não recalibrar o limiar

Varredura nas 14 perguntas da avaliação:

| limiar | ruído mantido | termos úteis mantidos |
|---:|---:|---:|
| 0,10 | 12 | 43 |
| 0,15 | 20 | 43 |
| 0,20 | 24 | 46 |
| 0,30 | 39 | 47 |
| 0,40 | 41 | 49 |
| 0,50 | 48 | 50 |

Sete termos úteis comprados por vinte e oito de ruído, sem joelho. Uma
distribuição com corte natural mostraria um ponto onde a utilidade sobe rápido e
o ruído sobe devagar; esta é uma reta. Mover a linha só troca um erro por outro,
e por isso o limiar fica onde está.

## Por que o denominador, e não a coluna

Três saídas foram consideradas:

**Parar de indexar os rótulos de tema.** Resolveria a estatística e destruiria a
busca por tema — que é justamente o que o enriquecimento produziu de mais útil.
Quem digita "economia" precisa alcançar as fichas de economia.

**Dar peso zero a `tags` no BM25.** Não resolve: o peso afeta ordenação, não
frequência. E ainda perderia o casamento por tag.

**Medir a frequência só nas colunas de texto natural.** A coluna segue indexada,
buscável e pesada; apenas deixa de votar em quem é palavra banal. É a única que
separa as duas funções que a coluna acumulava — ser recuperável e ser evidência
estatística — sem sacrificar nenhuma.

Pelos números por coluna, `economia` cai de 40,5% para cerca de 3% e `financas`
para menos de 1%, devolvendo o vão na região que a injeção havia preenchido.

## Nota sobre `orgao`

`orgao` fica **dentro** do denominador, embora também seja texto derivado de
slug. A diferença é de autoria: o nome do órgão vem do portal, não de decisão
nossa, e a concentração do BCB é fato do catálogo. Um usuário que busca "banco
central" e recebe pouco está diante de um limite real da recuperação léxica —
não de um artefato de rotulagem.

## Risco

`api/app/recuperacao.py` é porta do núcleo de `busca.py`, com a duplicação já
registrada como dívida. Corrigir só um lado faz a produção divergir do que a
avaliação mede — que é a pior falha possível aqui, porque some sem alarme. Os
dois mudam juntos, e um teste fixa o comportamento em cada um.
