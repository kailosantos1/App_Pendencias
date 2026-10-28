# Entrada e comandos

## Entrada HTTP

O endpoint `POST /webhook` é definido pela função `receber_webhook` em [`app_pendencias.py`](../../../app_pendencias.py#L1157). Para eventos `messages.upsert`, verifica o grupo, inspeciona se a mensagem veio do próprio número e extrai texto de `conversation`, `extendedTextMessage`, `imageMessage.caption` ou `videoMessage.caption`. Mensagens sem `!` são ignoradas; comandos são repassados a `BackgroundTasks`.

IDs de mensagens enviadas pelo bot ficam em memória em `IDS_ENVIADOS_PELO_BOT`. Eles são usados para filtrar mensagens próprias e a limpeza de IDs antigos ocorre quando o conjunto supera 300 elementos. Essa memória não é persistida entre reinicializações.

## Comandos

O webhook remove o primeiro `!` antes de chamar `processar_comando_whatsapp`; por isso, o processador compara palavras sem o prefixo.

| Forma digitada no grupo | Efeito |
|---|---|
| `!ajuda`, `!comandos` | Mostra a lista de comandos. |
| `!lista` | Lista todas as pendências deste grupo. Aliases: `!pendencias`, `!pendencia`, `!listar`, `!todos`, `!tudo`. |
| `!lista <cliente>` | Lista as pendências do cliente neste grupo. Também aceita `!pendencias <cliente>`, `!pendencia <cliente>` e `!listar <cliente>`. |
| `!<cliente>` | Consulta rápida para nome de cliente de uma palavra. |
| `!<cliente>: <tarefa>` | Cria uma pendência. O cliente é normalizado para minúsculas no banco. |
| `!<cliente>: <tarefa> lembrete <data/hora>` | Cria pendência com lembrete, extraindo a parte que começa por `lembrete`. |
| `!del <cliente> <número>` ou `!check <cliente> <número>` | Exclui o item pela posição atual na lista do cliente. |
| `!ok <cliente>` | Confirma avisos de contrato no grupo Contratos. |
| `!ok` | Confirma se existir apenas um cliente pendente; se houver vários, apresenta opções. |

O parser e os textos de ajuda estão em [`app_pendencias.py`](../../../app_pendencias.py#L833). A interpretação de datas é baseada em regras textuais simples e horário local do servidor; não equivale a um interpretador geral de linguagem natural. Ver [[03 - Fluxos/Recepcao e comandos|fluxo de comandos]] e [[03 - Fluxos/Lembretes|lembretes]].

Voltar para [[02 - Modulos/Indice|índice de módulos]].
