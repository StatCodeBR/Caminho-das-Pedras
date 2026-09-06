# Coletar o catálogo do Portal Brasileiro de Dados Abertos

## Por que

O produto responde à pergunta "onde encontro este dado público?". Para isso
precisa conhecer o catálogo inteiro do dados.gov.br — cerca de 19 mil conjuntos
de dados e mais de 91 mil recursos.

O catálogo é acessível pela API pública do portal, que exige uma chave obtida
via conta gov.br. Fazer essa coleta a cada execução do pipeline seria lento,
frágil e abusivo com a infraestrutura da CGU. Precisamos de uma coleta única,
retomável, cujo resultado bruto fique em disco e sirva de insumo estável para
todas as etapas seguintes.

Esta é a primeira camada do sistema. Nada mais funciona sem ela.

## O que muda

- Novo projeto Python `pipeline/`, isolado do projeto `api/` porque carrega
  dependências pesadas que não devem chegar à imagem de produção.
- Novo comando `coleta.py` que percorre a API e grava JSONL bruto.
- Nenhuma transformação, validação de negócio ou enriquecimento nesta etapa.

## Fora de escopo

- Normalização para banco relacional (mudança 02).
- Verificação de saúde dos links dos recursos (mudança 03).
- Qualquer chamada a modelo de linguagem (mudança 04).

## Impacto

- Cria o diretório `pipeline/bruto/`, não versionado.
- Passa a exigir a variável de ambiente `DADOS_GOV_API_KEY`.
- Tempo estimado da coleta completa: dezenas de minutos, executada raramente.
