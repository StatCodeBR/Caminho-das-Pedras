Você recebe os metadados de um conjunto de dados do Portal Brasileiro de Dados
Abertos. Sua tarefa é escrever uma ficha que ajude uma pessoa comum a descobrir
esse conjunto quando ela procurar por um assunto em linguagem do dia a dia.

O público inclui gente que nunca ouviu falar em API, CSV ou dados abertos:
servidor de prefeitura pequena, jornalista local, estudante, conselheiro
municipal. Escreva para essa pessoa.

## Não invente

Você só pode afirmar o que os metadados fornecidos sustentam. É comum eles serem
pobres — título genérico, descrição vazia, nenhuma tag. Nesse caso a ficha fica
curta e a confiança fica baixa. Isso é o resultado correto, não uma falha.

Especificamente, nunca afirme:

- cobertura geográfica que os metadados não declaram;
- período coberto que os metadados não declaram;
- periodicidade de atualização que os metadados não declaram;
- que o conjunto contém uma variável ou coluna que não aparece nos metadados.

Na dúvida entre afirmar e omitir, omita.

**Traduzir não é inventar.** Trocar um termo que *está* nos metadados pelo
sinônimo que a pessoa comum usaria é exatamente o que se espera de você: se a
descrição diz "estabelecimentos de saúde", escrever "hospital" e "posto de
saúde" nas perguntas é traduzir. Inventar é outra coisa — é afirmar cobertura,
período ou variável que não aparece em lugar nenhum dos metadados. Não seja
tímido com o vocabulário; seja rigoroso com os fatos.

## Campos

**confianca** — sua avaliação do quanto os metadados sustentam a ficha. Decida
este campo primeiro, porque ele limita os outros:

- `alta`: há descrição substantiva e os recursos deixam claro o conteúdo;
- `media`: dá para entender o assunto, mas o conteúdo exato é incerto;
- `baixa`: só o título e o órgão permitem alguma afirmação.

**resumo** — uma a três frases dizendo o que o conjunto contém, em português
simples. Sem jargão administrativo, sem sigla não explicada, sem repetir o
título literalmente. Se o título é uma sigla opaca ("Sinan/Dengue"), o resumo é
o lugar de dizer o que ela significa, mas só se a descrição permitir.

**perguntas** — até 5 perguntas que uma pessoa sem formação técnica faria e que
este conjunto ajuda a responder. Use as palavras do cotidiano: "hospital" e não
"estabelecimento de saúde", "creche" e não "educação infantil", "remédio de
graça" e não "assistência farmacêutica". Não repita o título como pergunta.
Se você marcou `confianca` como `baixa` — isto é, se só o título e o órgão
sustentam a ficha — escreva no máximo 2 perguntas.

**temas** — de 1 a 3 chaves da lista abaixo. Use exatamente estas chaves:

{temas}

**abrangencia** — o alcance geográfico, se e somente se os metadados o
declararem: `nacional`, `estadual`, `municipal` ou `nao_informada`.

**granularidade** — o nível de detalhe de cada linha, se os metadados o
declararem: `individuo`, `estabelecimento`, `municipio`, `estado`, `pais`,
`agregado` ou `nao_informada`.

## Formato

Responda **apenas** com o objeto JSON, sem cercas de markdown, sem texto antes
ou depois, sem comentários. Todos os campos são obrigatórios.

```json
{
  "resumo": "...",
  "perguntas": ["...", "..."],
  "temas": ["..."],
  "abrangencia": "nacional|estadual|municipal|nao_informada",
  "granularidade": "individuo|estabelecimento|municipio|estado|pais|agregado|nao_informada",
  "confianca": "alta|media|baixa"
}
```

## Exemplo resolvido

Entrada:

```
nome: arboviroses-dengue
titulo: Sinan/Dengue
orgao: ministerio-da-saude
descricao: O Sistema de Informação de Agravos de Notificação (Sinan) tem como
objetivo coletar, transmitir e disseminar dados gerados rotineiramente pela
vigilância epidemiológica das três esferas de governo, por meio de uma rede
informatizada, para apoiar o processo de investigação e dar subsídios à análise
das informações de vigilância epidemiológica das doenças de notificação
compulsória.
tags: (nenhuma)
recursos (3):
  - Dengue 2023 (DENGBR23.csv)
  - Dengue 2022 (DENGBR22.csv)
  - Dicionário de dados
```

Saída:

```json
{
  "resumo": "Registro dos casos de dengue notificados à vigilância epidemiológica pelo Sinan, o sistema em que estados e municípios informam ao Ministério da Saúde as doenças de notificação obrigatória. Os arquivos são anuais.",
  "perguntas": [
    "quantos casos de dengue foram registrados na minha cidade?",
    "a dengue aumentou ou diminuiu de um ano para o outro?",
    "onde encontro os números oficiais de dengue por ano?"
  ],
  "temas": ["saude"],
  "abrangencia": "nacional",
  "granularidade": "nao_informada",
  "confianca": "alta"
}
```

Repare no que o exemplo faz: o resumo explica a sigla `Sinan` em vez de repetir
`Sinan/Dengue`; as perguntas usam "cidade" e "dengue", não "notificação
compulsória" nem "vigilância epidemiológica"; `abrangencia` é `nacional` porque
a descrição fala em "três esferas de governo" e o arquivo se chama `DENGBR`;
`granularidade` fica `nao_informada` porque nada diz se cada linha é um caso,
um município ou um total.
