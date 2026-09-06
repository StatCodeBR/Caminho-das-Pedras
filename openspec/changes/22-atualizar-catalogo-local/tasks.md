# Tarefas — atualizar catálogo local

## Obtenção

- [ ] Definir formato do manifesto de release com versão, URLs e somas
- [ ] Baixar catálogo, vetores e modelo para diretório temporário
- [ ] Exibir progresso com possibilidade de cancelar
- [ ] Retomar download interrompido quando o servidor permitir

## Integridade

- [ ] Verificar soma de verificação de cada artefato antes de promover
- [ ] Abortar e preservar o catálogo anterior em caso de divergência
- [ ] Validar que o banco abre e que a tabela FTS5 responde

## Promoção atômica

- [ ] Promover por renomeação apenas após todas as verificações
- [ ] Remover o catálogo anterior somente após promoção bem-sucedida
- [ ] Teste: interrupção no meio da atualização preserva o estado anterior

## Atualização

- [ ] Verificar periodicamente a existência de versão nova
- [ ] Avisar sem interromper o uso e aguardar consentimento
- [ ] Baixar sem perguntar apenas quando não houver catálogo algum

## Versão como dado visível

- [ ] Exibir versão e data do catálogo na interface
- [ ] Usar a versão como chave do cache local de respostas
- [ ] Incluir a versão nas respostas produzidas

## Verificação

- [ ] Teste: soma divergente não promove o catálogo
- [ ] Teste: aplicativo abre normalmente sem conexão se já houver catálogo
- [ ] Teste: primeira execução sem rede explica a situação com clareza
- [ ] `openspec validate --strict`
