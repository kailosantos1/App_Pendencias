# Agendadores

`lifespan` inicializa os dois bancos e cria a tarefa assíncrona `loop_verificacao_horario`. O loop executa `verificar_e_disparar_lembretes` e `verificar_avisos_contratos` em threads de trabalho e aguarda 30 segundos entre ciclos. Ao encerrar o FastAPI, cancela e aguarda a tarefa.

As rotinas de agendamento estão em [`app_pendencias.py`](../../../app_pendencias.py#L99) e [`app_pendencias.py`](../../../app_pendencias.py#L1035). O código não configura um serviço externo de agendamento; a rotina depende do processo permanecer ativo.

- [[03 - Fluxos/Lembretes|Lembretes de tarefas]]
- [[03 - Fluxos/Avisos semanais|Avisos e confirmações de contratos]]
- [[04 - Dados/Modelo SQLite|estado persistido]]

Voltar para [[02 - Modulos/Indice|índice de módulos]].
