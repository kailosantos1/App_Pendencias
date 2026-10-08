# Pendências e Contratos SystemUp

Um processo, porta 5000 e webhook /webhook. Cada JID usa seu próprio SQLite. JID_PENDENCIAS e JID_CONTRATOS são obrigatórios no .env; não há JIDs padrão no sistema.py nem fallback para JID_WHATSAPP. Se faltar um JID ou forem iguais, o sistema não inicia. A função de envio também bloqueia destinos fora desses dois grupos.

## Instalar no Windows

1. Pare o processo antigo e faça uma cópia de segurança da pasta e do pendencias.db.
2. Extraia este projeto na pasta do sistema original, junto do pendencias.db existente. O banco antigo mantém sua tabela e seus registros; contratos.db será criado separadamente. Nenhum banco de produção foi incluído nesta entrega.
3. Copie .env.example para .env e preencha EVOLUTION_API_KEY com a chave já utilizada. Use os campos novos do exemplo. Se precisar de caminhos diferentes, configure DB_PENDENCIAS e DB_CONTRATOS. Caminhos relativos usam sempre a pasta de sistema.py.
4. No CMD nessa pasta, execute `python -m pip install -r requirements.txt`.
5. Execute `python sistema.py` ou iniciar.bat. Execute somente uma cópia do sistema, sem múltiplos workers, para não duplicar a rotina de lembretes.
6. Mantenha na Evolution o webhook já funcional: http://localhost:5000/webhook. A instância permanece App_Pendencias. Não é necessário distribuidor ou uma segunda porta.

## Comandos em ambos os grupos

- `!ajuda` ou `!comandos` — mostra os comandos disponíveis com exemplos.

- `!studio home: revisar contrato`
- `!studio home: ligar para cliente lembrete amanhã às 14:30`
- `!lista` — lista geral somente do grupo atual.
- `!lista studio home` — lista do cliente no grupo atual.
- `!del studio home 1` — exclui o primeiro item do cliente no grupo atual.
- `!check studio home 1` — mesmo comportamento de del.
- `!cliente` — consulta rápida de um cliente com nome de uma palavra.

Os aliases pendencias, pendencia, listar, todos e tudo continuam disponíveis com `!`. Mensagens começando com `/` e conversas comuns são ignoradas. Comandos manuais do próprio número conectado continuam aceitos. Respostas do bot mantêm a identificação por ID e não iniciam com o prefixo de comando.

Pendências Systemup: 120363428433320020@g.us → pendencias.db.
Contratos SystemUp: 120363413254902958@g.us → contratos.db.

Os lembretes só são marcados como enviados quando a Evolution retorna 200/201; se o envio falhar, são tentados novamente na próxima verificação. Isso confirma aceitação pela API, não leitura pelo destinatário. A interpretação de datas mantém as regras do original e usa o horário local do servidor.

O trecho DELETE enviado no chat não faz parte da inicialização e não foi executado. Para remover studio home em um grupo, use !del studio home N para cada item. Uma limpeza por SQL deve selecionar explicitamente o banco correto.

## Verificação

`python -m unittest -v test_sistema.py`

Os testes usam bancos temporários e envio simulado, sem conectar ao WhatsApp. Após instalar, teste !lista e uma tarefa de teste em cada grupo para confirmar o ambiente real.