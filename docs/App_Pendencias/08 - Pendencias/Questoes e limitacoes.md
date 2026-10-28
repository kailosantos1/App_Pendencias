# Questões e limitações

## Inconsistências entre README e arquivos presentes

O README descreve um projeto que inclui `sistema.py`, `.env.example`, `iniciar.bat` e possível `pendencias.db` preexistente. Nenhum desses arquivos está entre os seis arquivos versionados deste repositório. O arquivo principal presente é `app_pendencias.py`, com entrada executável própria. Portanto, as instruções de copiar `.env.example`, executar `sistema.py`/`iniciar.bat` e a referência ao banco antigo não foram verificadas contra os arquivos atuais.

O README se intitula “Pendências e Contratos SystemUp” e registra JIDs e práticas de uma instalação específica. Os valores de JID nele descritos não foram copiados para esta documentação; confirme a configuração apropriada para cada ambiente antes de operar.

## Confirmações necessárias

- Quais são os JIDs, URL, instância e credenciais da Evolution de cada ambiente? Não inserir credenciais no vault ou no controle de versão.
- O webhook da Evolution está configurado para `POST /webhook` e para o formato `messages.upsert` esperado pelo código?
- Os operadores ainda precisam de um exemplo de configuração de ambiente, considerando que `.env.example` não está versionado?
- O script [`deletar.py`](../../../deletar.py) é uma ferramenta intencional de manutenção, ou deveria ser removido/reescrito? Ele apaga todas as tarefas do cliente `studio home` em `pendencias.db` quando executado.
- Quais são os requisitos oficiais de versão do Python e o procedimento de deploy/backup? Não há configuração de versão ou deploy no repositório.

## Limitações observadas

- Um único módulo concentra API, comandos, persistência e rotinas.
- Os testes cobrem funções e payloads simulados; não verificam uma instância Evolution real.
- Erros de banco e rede são impressos em stdout; não há métricas, health check, logging estruturado ou observabilidade adicional.
- A interpretação de datas é implementada por regex e regras específicas, sem especificação formal completa para entradas ambíguas.
- O controle de IDs próprios é volátil e local ao processo.
- Não há coordenação entre processos; múltiplas instâncias podem executar tarefas periódicas concorrentes.

São fatos os comportamentos e ausências constatáveis nos arquivos examinados. A intenção dos arquivos ausentes, a configuração de produção, a origem das instruções do README e as decisões futuras requerem confirmação.

Voltar para [[08 - Pendencias/Indice|índice de pendências]] · Ver [[00 - Inicio/Cobertura da analise|cobertura examinada]].
