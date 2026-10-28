# Ambiente e comandos

## Dependências declaradas

[`requirements.txt`](../../../requirements.txt) declara:

- `fastapi` (>=0.115 e <1)
- `uvicorn` (>=0.30 e <1)
- `requests` (>=2.32 e <3)
- `python-dotenv` (>=1 e <2)
- `httpx` (>=0.27 e <1), usado pelo `TestClient` do FastAPI
- `tzdata` (>=2024.1), relacionado à disponibilidade de dados de fuso horário

O código usa Python com `zoneinfo`; o repositório não declara uma versão mínima de Python nem contém configuração de build ou empacotamento.

## Comandos derivados dos arquivos presentes

Estes comandos estão associados aos arquivos e scripts disponíveis no repositório:

```sh
python -m pip install -r requirements.txt
python app_pendencias.py
python -m unittest -v test_sistema.py
```

O primeiro instala as dependências listadas, o segundo inicia a aplicação pelo bloco `__main__` e o terceiro executa a suíte `unittest`. A execução do servidor exige configurar antes os dois JIDs obrigatórios; caso contrário a importação falha com `ValueError`. Configure também a URL e a chave da Evolution para comunicação real.

O aplicativo chama `uvicorn.run(app, host="0.0.0.0", port=PORT)`; `PORT` tem padrão 5000. O README também cita `python sistema.py` e `iniciar.bat`, mas esses arquivos não estão presentes. Consulte [[08 - Pendencias/Questoes e limitacoes|inconsistências documentais]].

Não há script de build, comando de lint, `pyproject.toml`, requirements de desenvolvimento separado nem migrações declaradas.

Voltar para [[06 - Desenvolvimento/Indice|índice de desenvolvimento]] · Ver [[01 - Arquitetura/Configuracao|configuração]].
