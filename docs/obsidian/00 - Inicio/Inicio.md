# Pendências e Contratos SystemUp

Este vault documenta o sistema Python que recebe comandos de grupos do WhatsApp, registra pendências em bancos SQLite separados e envia lembretes e avisos de contrato pela Evolution API.

## Navegação

- [[00 - Inicio/Indice|Mapa do vault]]
- [[01 - Arquitetura/Visao geral|Arquitetura e tecnologias]]
- [[02 - Modulos/Indice|Módulos]]
- [[03 - Fluxos/Indice|Fluxos]]
- [[04 - Dados/Modelo SQLite|Dados e persistência]]
- [[05 - Interfaces e Integracoes/Webhook e Evolution API|Webhook e integração externa]]
- [[06 - Desenvolvimento/Ambiente e comandos|Instalação e comandos]]
- [[06 - Desenvolvimento/Testes|Testes]]
- [[07 - Operacao/Execucao e operacao|Execução e operação]]
- [[08 - Pendencias/Questoes e limitacoes|Dúvidas e limitações]]
- [[00 - Inicio/Cobertura da analise|Cobertura da análise]]

## Em resumo

O ponto de entrada é [`app_pendencias.py`](../../../app_pendencias.py). O processo valida a configuração ao importar o módulo, inicializa os bancos durante o ciclo de vida do FastAPI, recebe eventos em `/webhook` e mantém uma rotina assíncrona que verifica lembretes a cada 30 segundos. Cada grupo permitido está associado a um arquivo SQLite próprio.

As descrições desta documentação distinguem fatos observáveis no código de lacunas que precisam de confirmação. O README versionado contém instruções que mencionam arquivos não presentes neste repositório; veja [[08 - Pendencias/Questoes e limitacoes|limitações e inconsistências]].
