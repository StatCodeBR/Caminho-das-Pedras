# Medir termo comum sem a coluna de tags

## Why

O filtro de termo comum decide o que descartar da pergunta pela fração de fichas
em que a palavra aparece. Esse denominador conta todas as colunas do índice,
inclusive `tags` — e é ali que a indexação escreve os rótulos do nosso próprio
vocabulário controlado de temas.

O resultado é que a estatística passou a medir como *nós rotulamos*, não como as
pessoas falam:

| termo | frequência no corpus | parcela vinda da coluna `tags` |
|---|---:|---:|
| `financas` | 40,2% | 100% |
| `economia` | 40,5% | 99% |
| `administracao` | 24,4% | 99% |
| `publicas` | 41,5% | 97% |
| `publica` | 28,3% | 94% |
| `educacao` | 15,7% | 87% |
| `ciencia` | 16,6% | 81% |
| `tecnologia` | 17,2% | 78% |

`financas` aparece em 8.016 fichas e em 8.010 delas está na coluna `tags`. Não é
a língua portuguesa: é o rótulo "Economia e Finanças" carimbado por classificação
temática. São todas palavras de **assunto** — exatamente o que o cidadão digita —
empurradas acima do limiar de 0,15 por um artefato nosso.

O efeito é perverso na direção contrária ao objetivo do projeto: quanto melhor o
enriquecimento classifica um tema, mais o filtro proíbe que se busque por ele.

Com 505 fichas o defeito estava latente. Com o catálogo completo ele cobra:

```
505 fichas      recall@5 57,1%   recall@10 57,1%   MRR 0,421
19.958 fichas   recall@5 35,7%   recall@10 42,9%   MRR 0,284
```

As categorias que sumiram por completo são as de vocabulário poluído:
`educacao` 0,0% e `trabalho_e_renda` 0,0%.

## What Changes

- `frequencia()` passa a contar apenas as colunas de texto natural — `nome`,
  `perguntas`, `resumo` e `orgao` — ao medir se um termo é comum demais.
- A coluna `tags` **continua indexada, continua pesada no BM25 e continua
  casando consultas**. Muda só o denominador do filtro.
- O limiar permanece em 0,15. A varredura de 0,10 a 0,50 não mostrou joelho:
  subir o corte de 0,15 para 0,50 recupera 7 termos úteis e admite 28 termos de
  ruído, numa reta sem ponto de inflexão. Distribuição sem vão não se conserta
  movendo a linha de corte, e sim removendo o que fechou o vão.

## Capabilities

### Modified Capabilities

- `busca-lexica`: o requisito de descarte de termos comuns passa a especificar
  sobre qual texto a frequência é medida.

## Impact

- `pipeline/busca.py`: `frequencia()`.
- `api/app/recuperacao.py`: porta do mesmo núcleo; precisa da mesma correção,
  sob pena de a busca da produção divergir da avaliada.
- Sem mudança de esquema, sem reindexação, sem recoleta e sem custo de modelo.
