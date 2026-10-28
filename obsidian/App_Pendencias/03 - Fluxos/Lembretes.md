# Lembretes de tarefas

Ao criar uma tarefa com um trecho iniciado por `lembrete`, o processador chama `calcular_data_hora_lembrete` e grava a data/hora em `pendencias.data_alerta`. A interpretação tenta reconhecer datas numéricas `d/m` ou `d/m/aaaa`, `dia N`, `hoje`, `amanhã`, dias da semana e horários. O padrão de horário é 08:00. Para tarefa com lembrete de hoje sem horário informado e horário padrão já passado, a data é deslocada para amanhã.

O cálculo usa `datetime.now()` e `date.today()` do servidor, sem aplicar `FUSO_CONTRATOS`. Portanto, o fuso dos lembretes depende do relógio e fuso local da máquina. A função e os formatos reconhecidos estão em [`app_pendencias.py`](../../../app_pendencias.py#L397).

## Disparo

1. A rotina periódica consulta cada banco por registros vencidos (`data_alerta <= agora`) que ainda não foram marcados como enviados.
2. Agrupa as tarefas por cliente e envia uma mensagem consolidada ao grupo associado ao banco.
3. Marca `lembrete_enviado = 1` somente se `enviar_whatsapp` indicar sucesso (HTTP 200 ou 201).
4. Em falha, os itens permanecem pendentes para nova tentativa na próxima verificação.

O endpoint externo aceitar o envio não prova que o destinatário leu a mensagem. O envio usa timeout de 10 segundos; erros são registrados no log e tratados como falha de envio.

Detalhes técnicos: [`app_pendencias.py`](../../../app_pendencias.py#L1035), [[04 - Dados/Modelo SQLite|persistência]] e [[07 - Operacao/Execucao e operacao|operação]].

Voltar para [[03 - Fluxos/Indice|índice de fluxos]].
