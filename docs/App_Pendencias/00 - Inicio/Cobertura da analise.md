# Cobertura da análise

## Materiais examinados

- [`app_pendencias.py`](../../../app_pendencias.py): configuração, validação, ciclo de vida, tabelas, operações SQLite, parser de comandos, envio à Evolution, lembretes, avisos programados e rota HTTP.
- [`test_sistema.py`](../../../test_sistema.py): testes de isolamento por grupo, filtros de mensagens, lembretes, confirmações de contrato, preservação do banco e bloqueio de destinos externos.
- [`README.md`](../../../README.md): instruções e comportamento descritos pelo projeto; inconsistências com os arquivos presentes foram registradas em [[08 - Pendencias/Questoes e limitacoes|Pendências]].
- [`requirements.txt`](../../../requirements.txt): dependências declaradas.
- [`deletar.py`](../../../deletar.py): script separado que exclui pendências de um banco fixo.
- [`.gitignore`](../../../.gitignore): exclusões de arquivos gerados, bancos e `.env`.

O repositório contém seis arquivos versionados e não contém pastas de código adicionais, configuração de build, migrações, arquivos de deploy, amostra de ambiente, nem documentação de API independente. Não foram lidos arquivos `.env`, valores de credenciais, dependências instaladas, caches ou arquivos gerados.

## Áreas documentadas

- Arquitetura e responsabilidades: [[01 - Arquitetura/Visao geral|visão geral]].
- Responsabilidades por módulo: [[02 - Modulos/Indice|índice de módulos]].
- Entrada de mensagens, parsing e avisos: [[03 - Fluxos/Indice|índice de fluxos]].
- Modelo e separação dos bancos: [[04 - Dados/Modelo SQLite|modelo SQLite]].
- Contrato HTTP e integração Evolution: [[05 - Interfaces e Integracoes/Webhook e Evolution API|interfaces]].
- Dependências, configuração e testes: [[06 - Desenvolvimento/Indice|desenvolvimento]].
- Inicialização, logs e limites operacionais: [[07 - Operacao/Execucao e operacao|operação]].
- Incertezas e diferenças entre código e README: [[08 - Pendencias/Questoes e limitacoes|pendências]].

## Base de evidência

Os comportamentos descritos como confirmados foram observados nos arquivos listados acima. Referências com linhas apontam para o código correspondente. Recomendações ou limites inferidos estão identificados como tal; detalhes externos de implantação não são presumidos.
