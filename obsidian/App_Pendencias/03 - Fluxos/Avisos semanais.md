# Avisos semanais de contrato

Os avisos só são criados e enviados no grupo identificado por `JID_CONTRATOS`. O agendamento usa `America/Sao_Paulo`. A tabela `AGENDA_CONTRATOS` e a lógica de `gerar_ocorrencias_contratos` estão em [`app_pendencias.py`](../../../app_pendencias.py#L70).

| Cliente | Dias configurados no código | Horário local |
|---|---|---:|
| CNivel | Terça e quinta | 13:30 |
| CBHidro | Quarta | 13:30 |
| Acrel | Quarta | 13:30 |
| Enebras | Quinta | 09:00 |

Quando o processo inicia depois do horário previsto em um dia programado, a ocorrência daquele dia ainda pode ser criada na verificação. Dias anteriores em que o processo ficou desligado não são reconstruídos. Avisos não confirmados continuam sendo tentados; após envio aceito, repetem a cada 10 minutos. A confirmação e o último envio são persistidos no SQLite de Contratos.

Use `!ok cnivel`, `!ok cbhidro`, `!ok acrel` ou `!ok enebras` no grupo Contratos. `!ok` sem cliente confirma quando há somente um cliente pendente; se houver mais, lista as opções. A confirmação encerra os avisos pendentes daquele cliente, não apaga tarefas e não impede nova ocorrência em dia futuro.

A agenda e a lógica estão em [`app_pendencias.py`](../../../app_pendencias.py#L107) e [`app_pendencias.py`](../../../app_pendencias.py#L195). O fuso `America/Sao_Paulo` depende da base de fusos do sistema; `tzdata` é uma dependência declarada.

Voltar para [[03 - Fluxos/Indice|índice de fluxos]] · Ver [[04 - Dados/Modelo SQLite|estado persistido]].
