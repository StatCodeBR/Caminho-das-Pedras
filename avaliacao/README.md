# Conjunto de avaliação

Perguntas curadas à mão, escritas como o cidadão as faria, com os conjuntos do
catálogo que as respondem. É o que mede se a recuperação melhorou ou piorou.

## Não abra o `perguntas.csv` em planilha

**Edite em editor de texto. Nunca em LibreOffice, Excel ou Google Sheets.**

A planilha reescreve os slugs em silêncio, e já corrompeu os mesmos três campos
três vezes. Os estragos observados:

| o que a planilha faz | exemplo |
|---|---|
| maiúscula na primeira letra | `hospitais-e-leitos` → `Hospitais-e-leitos` |
| hífen duplo vira travessão | `lista-de-espera--cirrgica-` → `lista-de-espera—cirrgica-` |
| cola fragmento de URL | `violencia_ses2` → `conjuntos-dados/violencia_ses2` |

Nenhum desses slugs resolve depois. O portal **distingue maiúsculas de
minúsculas** e **preserva espaço duplo como hífen duplo** — a grafia precisa vir
da API, não do bom senso. Está detalhado na limitação 5 de
[`docs/limitacoes-conhecidas.md`](../docs/limitacoes-conhecidas.md).

Pior: a corrupção é silenciosa. Um slug que não resolve mede recall baixo por
erro de digitação, não por falha da busca, e o número parece uma regressão real.
Na última vez foram 11 anotações quebradas de uma só edição.

Os arquivos `.ods` e `.bak` deste diretório são resquício desse fluxo e **não são
fonte de verdade**. O `perguntas.csv` é.

## Antes de confiar numa medição

```
cd pipeline
uv run python -c "
import sys; sys.path.insert(0,'.')
import avalia, busca
con = busca.abrir_banco('dados/dados.db')
print(avalia.anotacoes_ausentes(con, avalia.ler_perguntas(avalia.ARQUIVO_PERGUNTAS)))"
```

Lista vazia é o esperado. Qualquer slug ali significa que o número da avaliação
está medindo anotação quebrada. O `avalia.py` também reporta isso no relatório.

## Arquivos

- `perguntas.csv` — o conjunto de avaliação. Fonte de verdade.
- `historico.jsonl` — uma linha por execução de `avalia.py`, para comparar entre
  mudanças. `--sem-registrar` roda sem acrescentar linha.

## Colunas

`conjuntos_aceitaveis` aceita vários slugs separados por `;`. O valor `nenhum`
marca pergunta **sem resposta no catálogo**: a recuperação acerta quando não
devolve nada. Essa anotação envelhece — conjunto que não existia pode passar a
existir —, então revise-a quando o catálogo crescer.
