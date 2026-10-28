# Webhook e Evolution API

## Entrada: `POST /webhook`

Rota FastAPI declarada em [`app_pendencias.py`](../../../app_pendencias.py#L1157). O código espera JSON com `event: "messages.upsert"` e dados de mensagem contendo `data.key.remoteJid`, `data.message` e, quando aplicável, `key.fromMe` e `key.id`.

Tipos de texto extraídos:

- `conversation`
- `extendedTextMessage.text`
- `imageMessage.caption`
- `videoMessage.caption`

O endpoint responde com objetos simples contendo estados como `processando`, `ignorado_outro_chat`, `ignorado_nao_comando`, `sem_texto`, `event_nao_suportado` e erros de JSON/dados. Eventos processáveis são passados para `BackgroundTasks`, portanto a resposta de recebimento não representa confirmação de sucesso do comando ou da resposta externa.

O repositório não contém configuração de webhook da Evolution nem teste de contrato que demonstre o comportamento de uma instância externa real; os testes simulam o payload no `TestClient`.

## Saída: Evolution API

`enviar_whatsapp` constrói a URL `{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}` e envia JSON com `number` (JID do grupo) e `text`. Usa os cabeçalhos `Content-Type: application/json` e `apikey: EVOLUTION_API_KEY`, com timeout de 10 segundos. Somente HTTP 200 ou 201 é considerado sucesso. Em sucesso, tenta guardar o ID retornado em memória.

O destino precisa estar entre os JIDs configurados; caso contrário a chamada HTTP é bloqueada localmente. A integração está em [`app_pendencias.py`](../../../app_pendencias.py#L679); configuração: [[01 - Arquitetura/Configuracao|variáveis de ambiente]].

## Dependências de rede

Não há cliente oficial instalado: o código usa `requests`. A disponibilidade da Evolution API, a validade da chave, o nome da instância, o formato de payload aceito pela versão em uso e a configuração do webhook dependem do ambiente e precisam ser confirmados nele.

Voltar para [[05 - Interfaces e Integracoes/Indice|índice de interfaces]] · Ver [[03 - Fluxos/Recepcao e comandos|fluxo de mensagens]].
