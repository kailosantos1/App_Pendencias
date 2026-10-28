# Testes

O arquivo [`test_sistema.py`](../../../test_sistema.py) contém uma classe `unittest.TestCase` com testes da API via `fastapi.testclient.TestClient`. O comando documentado e inscrito no README é:

```sh
python -m unittest -v test_sistema.py
```

## Cobertura observada

- Criação, listagem e exclusão isoladas por grupo.
- Ignorar mensagens que não são comandos, outros chats e IDs enviados pelo bot; aceitar comandos manuais do próprio número.
- Marcar lembretes somente quando o envio simulado retorna sucesso.
- Respostas de ajuda em ambos os grupos.
- Horários, repetição e confirmação de avisos de contrato, inclusive reinicialização e atraso.
- Restringir `!ok` ao grupo de Contratos.
- Bloquear tentativas de envio para destinos fora dos grupos configurados.
- Preservar dados existentes e testar uma interpretação de horário.

Os testes criam bancos temporários e substituem o envio por uma função simulada, sem conexão real ao WhatsApp. Isso valida o comportamento interno coberto, mas não valida instância Evolution, webhook externo, deploy ou ambiente de produção. A variável dos dois grupos é preparada no início do módulo de teste antes da importação da aplicação.

Voltar para [[06 - Desenvolvimento/Indice|índice de desenvolvimento]] · Ver [[08 - Pendencias/Questoes e limitacoes|lacunas de cobertura]].
