\# 🤖 Bot Gerenciador de Pendências (WhatsApp + Evolution API)



Sistema em Python utilizando \*\*FastAPI\*\* e \*\*SQLite\*\* para gerenciamento de tarefas e lembretes automáticos diretamente via grupos do WhatsApp, integrado à \*\*Evolution API\*\*.



\---



\## 🚀 Funcionalidades



\- 📝 \*\*Adição de Pendências:\*\* Registre tarefas atribuídas a clientes diretamente pelo chat.

\- ⏰ \*\*Lembretes Automáticos:\*\* Reconhece horários e datas no texto (ex: `hoje`, `amanhã`, `dia 20`, `as 14:00`) e dispara alertas no horário agendado.

\- 📊 \*\*Consultas:\*\* Visualize pendências específicas por cliente ou a relação geral de todas as tarefas.

\- ✅ \*\*Remoção de Tarefas:\*\* Conclua ou remova itens facilmente por comandos numéricos.

\- 🛡️ \*\*Filtro de Segurança:\*\* Responde apenas no grupo de WhatsApp autorizado.



\---



\## 🛠️ Tecnologias Utilizadas



\- \*\*Python 3.10+\*\*

\- \*\*FastAPI\*\* (Backend e Webhook)

\- \*\*Uvicorn\*\* (Servidor ASGI)

\- \*\*SQLite3\*\* (Banco de dados relacional leve)

\- \*\*Evolution API\*\* (Integração com WhatsApp)



\---



\## 📦 Como Configurar e Rodar o Projeto



\### 1. Pré-requisitos



\- Python instalado na sua máquina.

\- Uma instância funcional da \[Evolution API](https://github.com/EvolutionAPI/evolution-api).



\### 2. Instalação



Clone o repositório e instale as dependências:



```bash

git clone \[https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)

cd seu-repositorio

pip install -r requirements.txt

