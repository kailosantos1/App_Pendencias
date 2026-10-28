# Persistência de pendências

As funções SQLite de [`app_pendencias.py`](../../../app_pendencias.py#L347) inicializam as tabelas e executam inserção, listagem e exclusão. A inicialização cria tabelas caso ainda não existam; não apaga registros já existentes.

As funções `adicionar_pendencia_db`, `listar_pendencias_db`, `listar_absolutamente_tudo_db` e `deletar_pendencia_db` recebem o caminho do banco como parâmetro. O fluxo seleciona esse caminho pela associação do JID ao grupo, evitando compartilhar as listas entre os dois grupos.

O número usado em `!del`/`!check` é uma posição visual da lista ordenada por `id`, não o ID interno do banco. Cada exclusão apaga apenas a linha correspondente àquela posição e cliente no banco selecionado.

Modelo detalhado: [[04 - Dados/Modelo SQLite|tabelas e relações]]. Fluxo: [[03 - Fluxos/Recepcao e comandos|processamento de comandos]].

Voltar para [[02 - Modulos/Indice|índice de módulos]].
