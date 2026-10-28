# Configuração

A aplicação carrega `.env` a partir de `BASE_DIR`. Em execução Python normal, `BASE_DIR` é a pasta de `app_pendencias.py`; em execução congelada, é a pasta do executável. `JID_PENDENCIAS` e `JID_CONTRATOS` são validados durante a importação do módulo: devem identificar dois grupos diferentes e terminar em `@g.us`. Os bancos também precisam ter caminhos diferentes.

> **Não documentar valores secretos:** este vault não contém nem reproduz valores do ambiente. A chave da Evolution deve permanecer fora do controle de versão.

| Variável | Obrigatória | Comportamento confirmado no código |
|---|---:|---|
| `JID_PENDENCIAS` | Sim | JID do primeiro grupo. |
| `JID_CONTRATOS` | Sim | JID do grupo em que avisos de contratos e confirmações são aceitos. |
| `EVOLUTION_API_KEY` | Para autenticação externa | Valor enviado no cabeçalho `apikey`; o código define string vazia se ausente, sem validar isso na inicialização. |
| `EVOLUTION_URL` | Não | Base da API; padrão `http://localhost:8080`. |
| `EVOLUTION_INSTANCE` | Não | Nome da instância; padrão `App_Pendencias`. |
| `DB_PENDENCIAS` | Não | Arquivo do grupo Pendências; padrão efetivo `pendencias.db`. |
| `DB_PATH` | Não | Fallback para o caminho do banco de Pendências se `DB_PENDENCIAS` não estiver definido. |
| `DB_CONTRATOS` | Não | Arquivo do grupo Contratos; padrão `contratos.db`. |
| `PORT` | Não | Porta do Uvicorn; padrão `5000`. |

Os nomes dos bancos são resolvidos relativamente a `BASE_DIR`. Variáveis com caminho absoluto permanecem absolutas ao resolver o caminho. A lógica de fallback `DB_PENDENCIAS` → `DB_PATH` → `pendencias.db` está em [`app_pendencias.py`](../../../app_pendencias.py#L39).

O arquivo `.env.example` mencionado no README não está presente entre os arquivos versionados deste projeto. Consulte [[08 - Pendencias/Questoes e limitacoes|limitações conhecidas]] antes de usar instruções de instalação que dependam dele.

Voltar para [[01 - Arquitetura/Indice|índice de arquitetura]] · Ver também [[06 - Desenvolvimento/Ambiente e comandos|instalação e comandos]].
