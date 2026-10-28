# Execução e operação

## Inicialização

Ao iniciar o FastAPI, `lifespan` chama `inicializar_banco` para cada caminho em `GRUPOS` e inicia a tarefa periódica. O processo serve HTTP em todas as interfaces (`0.0.0.0`) na porta indicada por `PORT` ou 5000. A rota documentada no código é `/webhook`.

O README sugere manter uma única cópia do sistema ativa para evitar duplicação da rotina. O risco é compatível com o código: cada processo cria sua própria tarefa de verificação, sem coordenação distribuída.

## Observabilidade disponível

O código escreve mensagens em stdout por `print`, inclusive início do sistema, recebimento do webhook, tentativas/respostas Evolution e erros de envio/rotina. Não foram encontrados endpoints de health check, configuração de logging estruturado, métricas ou integração de monitoramento.

## Diagnóstico orientado pelo código

| Sintoma | Verificação baseada no projeto |
|---|---|
| Aplicação falha ao importar | Confira se `JID_PENDENCIAS` e `JID_CONTRATOS` foram definidos como dois JIDs de grupo distintos e se os caminhos SQLite não são iguais. |
| Não processa uma mensagem | Confirme que é um dos grupos configurados, que o evento é `messages.upsert`, que há texto suportado e que a mensagem começa com `!`. |
| Não envia resposta/lembrete | Verifique logs stdout, URL/instância/chave Evolution e se o retorno HTTP é 200 ou 201. O código considera outros status como falha. |
| Lembretes em horário inesperado | Compare relógio/fuso local do servidor; lembretes usam hora local, enquanto avisos de contrato usam `America/Sao_Paulo`. |
| Aviso de contrato não reaparece após confirmação | A confirmação encerra a ocorrência corrente e fica salva no banco de Contratos; novo aviso depende de nova data programada. |

Não há documentação de deploy versionada suficiente para prescrever serviço de sistema, proxy reverso, HTTPS, firewall ou política de backup. Confirme esses pontos para o ambiente concreto.

Voltar para [[07 - Operacao/Indice|índice de operação]] · Ver [[05 - Interfaces e Integracoes/Webhook e Evolution API|interfaces]].
