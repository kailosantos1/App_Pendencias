import os
import re
import sqlite3
import datetime
import asyncio
import threading
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# --- CARREGAMENTO DAS CONFIGURAÇÕES VIA .ENV ---
EVOLUTION_URL = os.getenv("EVOLUTION_URL", "http://localhost:8080")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "App_Pendencias")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
JID_WHATSAPP = os.getenv("JID_WHATSAPP", "")
DB_PATH = os.getenv("DB_PATH", "pendencias.db")
PORT = int(os.getenv("PORT", 5000))

# Prefixo obrigatório para reconhecer uma mensagem como comando do bot.
# Sem isso, qualquer mensagem sua nesse chat (mesmo conversa solta) seria
# processada como se fosse um comando de pendências.
PREFIXO_COMANDO = "/"

# -------------------------------------------------------------
# LIFESPAN (GERENCIADOR DE INICIALIZAÇÃO DO FASTAPI)
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_banco()
    asyncio.create_task(loop_verificacao_horario())
    print("\n🤖 [SISTEMA ATIVO] Servidor pronto com varredura minuto a minuto.\n")
    yield

app = FastAPI(lifespan=lifespan)

# -------------------------------------------------------------
# CONTROLE DE MENSAGENS ENVIADAS PELO PRÓPRIO BOT
# -------------------------------------------------------------
# Como o número conectado na instância é o mesmo que você usa pra mandar
# comandos, o WhatsApp marca ambos como "fromMe: true". Pra diferenciar
# "resposta automática do bot" de "comando que você digitou", guardamos
# o ID de toda mensagem que o bot manda via API e só ignoramos no webhook
# se o ID bater com um desses.
IDS_BOT_LOCK = threading.Lock()
IDS_ENVIADOS_PELO_BOT = {}

def registrar_id_enviado(msg_id):
    if not msg_id:
        return
    with IDS_BOT_LOCK:
        IDS_ENVIADOS_PELO_BOT[msg_id] = datetime.datetime.now()
        # Limpeza: remove IDs com mais de 10 minutos para não crescer pra sempre
        if len(IDS_ENVIADOS_PELO_BOT) > 300:
            corte = datetime.datetime.now() - datetime.timedelta(minutes=10)
            for k in list(IDS_ENVIADOS_PELO_BOT.keys()):
                if IDS_ENVIADOS_PELO_BOT[k] < corte:
                    del IDS_ENVIADOS_PELO_BOT[k]

def foi_enviado_pelo_bot(msg_id):
    with IDS_BOT_LOCK:
        return msg_id in IDS_ENVIADOS_PELO_BOT

# -------------------------------------------------------------
# FUNÇÕES DO BANCO DE DADOS (SQLITE)
# -------------------------------------------------------------
def inicializar_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pendencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            tarefa TEXT NOT NULL,
            data_alerta TEXT,
            lembrete_enviado INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def calcular_data_hora_lembrete(termo_lembrete):
    agora = datetime.datetime.now()
    hoje = datetime.date.today()
    termo_limpo = termo_lembrete.lower().strip()

    data_alvo = hoje

    match_data_barra = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', termo_limpo)
    match_dia_fixo = re.search(r'\bdia\s+(\d{1,2})\b', termo_limpo)

    if match_data_barra:
        dia = int(match_data_barra.group(1))
        mes = int(match_data_barra.group(2))
        ano = int(match_data_barra.group(3)) if match_data_barra.group(3) else hoje.year
        try:
            d_temp = datetime.date(ano, mes, dia)
            if d_temp < hoje:
                d_temp = datetime.date(ano + 1, mes, dia)
            data_alvo = d_temp
        except ValueError:
            pass
        termo_limpo = termo_limpo.replace(match_data_barra.group(0), '')

    elif match_dia_fixo:
        dia = int(match_dia_fixo.group(1))
        try:
            if dia < hoje.day:
                mes = hoje.month + 1 if hoje.month < 12 else 1
                ano = hoje.year if mes > 1 else hoje.year + 1
            else:
                mes = hoje.month
                ano = hoje.year
            data_alvo = datetime.date(ano, mes, dia)
        except ValueError:
            pass
        termo_limpo = termo_limpo.replace(match_dia_fixo.group(0), '')

    elif "amanha" in termo_limpo or "amanhã" in termo_limpo:
        data_alvo = hoje + datetime.timedelta(days=1)
    elif "hoje" in termo_limpo:
        data_alvo = hoje
    else:
        dias_semana = {
            "segunda": 0, "segunda-feira": 0, "seg": 0,
            "terça": 1, "terca": 1, "terça-feira": 1, "ter": 1,
            "quarta": 2, "quarta-feira": 2, "qua": 2,
            "quinta": 3, "quinta-feira": 3, "qui": 3,
            "sexta": 4, "sexta-feira": 4, "sex": 4,
            "sábado": 5, "sabado": 5, "sab": 5,
            "domingo": 6, "dom": 6
        }
        for nome_dia, numero_dia in dias_semana.items():
            if re.search(r'\b' + re.escape(nome_dia) + r'\b', termo_limpo):
                dia_atual_semana = hoje.weekday()
                dias_a_somar = (numero_dia - dia_atual_semana) % 7
                if dias_a_somar == 0:
                    dias_a_somar = 7
                data_alvo = hoje + datetime.timedelta(days=dias_a_somar)
                break

    hora_alvo = 8
    minuto_alvo = 0
    hora_especificada = False

    match_hora = re.search(r'(?:as\s+|@\s*)?(\d{1,2})(?:[:h](\d{2}))?\s*(?:h|hrs|horas)?\b', termo_limpo)

    if match_hora:
        h_cand = int(match_hora.group(1))
        m_cand = int(match_hora.group(2)) if match_hora.group(2) else 0

        if 0 <= h_cand <= 23 and 0 <= m_cand <= 59:
            texto_encontrado = match_hora.group(0).strip()
            if any(c in texto_encontrado for c in [':', 'h', 'as', '@']) or len(texto_encontrado) >= 2:
                hora_alvo = h_cand
                minuto_alvo = m_cand
                hora_especificada = True

    if data_alvo == hoje and not hora_especificada:
        if datetime.time(hora_alvo, minuto_alvo) <= agora.time():
            data_alvo = hoje + datetime.timedelta(days=1)

    return datetime.datetime.combine(data_alvo, datetime.time(hora_alvo, minuto_alvo))

def adicionar_pendencia_db(cliente, tarefa, termo_lembrete=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    data_alerta = None
    if termo_lembrete:
        data_calculada = calcular_data_hora_lembrete(termo_lembrete)
        data_alerta = data_calculada.strftime("%Y-%m-%d %H:%M")

    cursor.execute(
        "INSERT INTO pendencias (cliente, tarefa, data_alerta) VALUES (?, ?, ?)",
        (cliente.lower(), tarefa, data_alerta)
    )
    conn.commit()
    conn.close()
    return data_alerta

def listar_pendencias_db(cliente):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, tarefa FROM pendencias WHERE cliente = ? ORDER BY id ASC",
        (cliente.lower(),)
    )
    linhas = cursor.fetchall()
    conn.close()
    return [{"id_real": linha[0], "tarefa": linha[1]} for linha in linhas]

def listar_absolutamente_tudo_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT cliente, tarefa FROM pendencias ORDER BY cliente ASC, id ASC")
    linhas = cursor.fetchall()
    conn.close()
    return linhas

def deletar_pendencia_db(cliente, indice_visual):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM pendencias WHERE cliente = ? ORDER BY id ASC",
        (cliente.lower(),)
    )
    linhas = cursor.fetchall()

    if 0 < indice_visual <= len(linhas):
        id_para_deletar = linhas[indice_visual - 1][0]
        cursor.execute("DELETE FROM pendencias WHERE id = ?", (id_para_deletar,))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False

# -------------------------------------------------------------
# FUNÇÕES DE ENVIO E FORMATAÇÃO
# -------------------------------------------------------------
def enviar_whatsapp(jid_destino, texto):
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"

    payload = {
        "number": jid_destino,
        "text": texto
    }
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    print(f"🛫 [TENTANDO ENVIAR] Para: {jid_destino} | URL: {url}")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"📡 [EVOLUTION RESPOSTA] Status: {response.status_code}")
        print(f"📄 [EVOLUTION BODY]: {response.text}")

        sucesso = response.status_code in [200, 201]

        if sucesso:
            try:
                msg_id = response.json().get("key", {}).get("id")
                registrar_id_enviado(msg_id)
                print(f"🔖 [ID REGISTRADO] {msg_id} marcado como mensagem do bot")
            except Exception as e:
                print(f"⚠️ [AVISO] Não consegui capturar o ID da mensagem enviada: {e}")

        return sucesso
    except Exception as e:
        print(f"❌ [ERRO CRÍTICO ENVIO]: {e}")
        return False

def formatar_lista_resposta(cliente):
    tarefas = listar_pendencias_db(cliente)
    cliente_maiusculo = cliente.upper()

    if not tarefas:
        return f"🎉 Nenhuma pendência em aberto para *{cliente_maiusculo}*!"

    resposta = f"📋 *Pendências - {cliente_maiusculo}*:\n\n"
    for idx, item in enumerate(tarefas, start=1):
        resposta += f"{idx}. {item['tarefa']}\n"

    resposta += f"\n💡 _Para remover use: {PREFIXO_COMANDO}del {cliente} <número>_"
    return resposta

def formatar_geral_todos_clientes():
    linhas = listar_absolutamente_tudo_db()

    if not linhas:
        return "🎉 Sensacional! Não há *nenhuma* pendência registrada para nenhum cliente!"

    resposta = "🗂️ *RELAÇÃO GERAL DE PENDÊNCIAS*\n\n"

    dados_agrupados = {}
    for cliente, tarefa in linhas:
        cliente_up = cliente.upper()
        if cliente_up not in dados_agrupados:
            dados_agrupados[cliente_up] = []
        dados_agrupados[cliente_up].append(tarefa)

    for cliente, tarefas in dados_agrupados.items():
        resposta += f"🏢 *{cliente}*:\n"
        for idx, t in enumerate(tarefas, start=1):
            resposta += f"  {idx}. {t}\n"
        resposta += "\n"

    resposta += "💡 _Para ver detalhes ou remover, use os comandos específicos de cada cliente._"
    return resposta

# -------------------------------------------------------------
# MOTOR DE PROCESSAMENTO DE TEXTO (WHATSAPP)
# -------------------------------------------------------------
def processar_comando_whatsapp(mensagem_texto, jid_remetente):
    texto = mensagem_texto.strip()
    texto_minusculo = texto.lower().replace('?', '').strip()

    if texto_minusculo in ['pendencias', 'pendencia', 'lista', 'listar', 'todos', 'tudo']:
        resposta = formatar_geral_todos_clientes()
        enviar_whatsapp(jid_remetente, resposta)
        return

    if texto.lower().startswith(('del ', 'check ')):
        padrao_del = r"^(del|check)\s+(\w+)\s+(\d+)$"
        match = re.match(padrao_del, texto, re.IGNORECASE)

        if match:
            _, cliente, indice_visual = match.groups()
            indice_visual = int(indice_visual)

            sucesso = deletar_pendencia_db(cliente, indice_visual)
            if sucesso:
                resposta = f"✅ Item {indice_visual} removido com sucesso!\n\n"
                resposta += formatar_lista_resposta(cliente)
            else:
                resposta = f"❌ Não achei o item {indice_visual} na lista de *{cliente.upper()}*."

            enviar_whatsapp(jid_remetente, resposta)
            return

    if ":" in texto:
        partes = texto.split(":", 1)
        cliente = partes[0].strip().lower()
        conteudo = partes[1].strip()

        termo_lembrete = None
        match_lembrete = re.search(r"\b(lembrete.*)$", conteudo, re.IGNORECASE)

        if match_lembrete:
            termo_lembrete = match_lembrete.group(1).strip()
            conteudo = conteudo[:match_lembrete.start()].strip()

        if cliente and conteudo:
            data_alerta = adicionar_pendencia_db(cliente, conteudo, termo_lembrete)

            resposta = f"💾 Salvo para *{cliente.upper()}*!\n"
            if data_alerta:
                data_dt = datetime.datetime.strptime(data_alerta, "%Y-%m-%d %H:%M")
                data_formatada = data_dt.strftime("%d/%m/%Y às %H:%M")
                resposta += f"⏰ _Vou te lembrar disso em: {data_formatada}_\n\n"
            else:
                resposta += "\n"

            resposta += formatar_lista_resposta(cliente)
            enviar_whatsapp(jid_remetente, resposta)
            return

    for prefixo in ['pendencias ', 'pendencia ', 'lista ', 'listar ']:
        if texto_minusculo.startswith(prefixo):
            texto_minusculo = texto_minusculo.replace(prefixo, '').strip()

    if len(texto_minusculo.split()) == 1 and len(texto_minusculo) > 1:
        resposta = formatar_lista_resposta(texto_minusculo)
        enviar_whatsapp(jid_remetente, resposta)
        return

# -------------------------------------------------------------
# ROTINA DE VERIFICAÇÃO CONTINUA DE LEMBRETES
# -------------------------------------------------------------
def verificar_e_disparar_lembretes():
    agora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, cliente, tarefa, data_alerta FROM pendencias WHERE data_alerta <= ? AND lembrete_enviado = 0",
        (agora_str,)
    )
    lembretes = cursor.fetchall()

    if not len(lembretes):
        conn.close()
        return

    alertas_por_cliente = {}
    ids_enviados = []

    for id_tarefa, cliente, tarefa, data_alerta in lembretes:
        if cliente not in alertas_por_cliente:
            alertas_por_cliente[cliente] = []
        alertas_por_cliente[cliente].append(tarefa)
        ids_enviados.append(id_tarefa)

    mensagem = "⏰ *LEMBRETE DE PENDÊNCIAS AGENDADAS*\n\nNo horário previsto:\n\n"
    for cliente, tarefas in alertas_por_cliente.items():
        mensagem += f"🏢 *{cliente.upper()}*:\n"
        for t in tarefas:
            mensagem += f"• {t}\n"
        mensagem += "\n"

    enviar_whatsapp(JID_WHATSAPP, mensagem)

    for id_tarefa in ids_enviados:
        cursor.execute("UPDATE pendencias SET lembrete_enviado = 1 WHERE id = ?", (id_tarefa,))

    conn.commit()
    conn.close()

async def loop_verificacao_horario():
    while True:
        try:
            verificar_e_disparar_lembretes()
        except Exception as e:
            print(f"❌ [ERRO VERIFICAÇÃO LEMBRETES]: {e}")
        await asyncio.sleep(30)

# -------------------------------------------------------------
# ENDPOINT DO WEBHOOK (FASTAPI)
# -------------------------------------------------------------
@app.post("/webhook")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    # Log global de entrada para monitorar requisições
    print("\n📩 [WEBHOOK RECEBIDO] Requisição bateu no endpoint /webhook")
    try:
        dados = await request.json()
    except Exception as e:
        print(f"❌ [ERRO JSON]: {e}")
        return {"status": "json_invalido"}

    if dados.get("event") == "messages.upsert":
        data = dados.get("data", {})
        key = data.get("key", {})

        # Primeiro filtro: só continua se a mensagem for do grupo configurado.
        # Qualquer coisa fora desse grupo é descartada aqui, sem olhar fromMe,
        # texto ou qualquer outra coisa.
        jid_remetente = key.get("remoteJid", "").strip()
        if jid_remetente != JID_WHATSAPP.strip():
            return {"status": "ignorado_outro_chat"}

        msg_id = key.get("id")

        if key.get("fromMe") is True:
            # Só ignora se o ID bater com uma mensagem que o PRÓPRIO bot mandou.
            # Caso contrário, é você mesmo digitando um comando do seu celular
            # (mesmo número da instância), então deve ser processado normalmente.
            if foi_enviado_pelo_bot(msg_id):
                print("ℹ️ Mensagem enviada pelo próprio bot - ignorada.")
                return {"status": "ignorado_mensagem_propria"}
            else:
                print("✅ Mensagem sua (mesmo número, digitada manualmente) - processando como comando.")

        print(f"📍 [GRUPO CONFERIDO] Mensagem é do grupo esperado: '{JID_WHATSAPP}'")

        message = data.get("message", {})
        texto_mensagem = ""

        if "conversation" in message and message["conversation"]:
            texto_mensagem = message["conversation"]
        elif "extendedTextMessage" in message and message["extendedTextMessage"]:
            texto_mensagem = message["extendedTextMessage"].get("text", "")
        elif "imageMessage" in message and message["imageMessage"]:
            texto_mensagem = message["imageMessage"].get("caption", "")
        elif "videoMessage" in message and message["videoMessage"]:
            texto_mensagem = message["videoMessage"].get("caption", "")

        texto_mensagem = texto_mensagem.strip()

        if not texto_mensagem:
            return {"status": "sem_texto"}

        if not texto_mensagem.startswith(PREFIXO_COMANDO):
            print("💤 [IGNORADO] Mensagem sem prefixo de comando - tratada como conversa normal.")
            return {"status": "ignorado_nao_comando"}

        # Remove o prefixo antes de repassar para o motor de comandos
        texto_comando = texto_mensagem[len(PREFIXO_COMANDO):].strip()

        if texto_comando:
            print(f"💬 [PROCESSANDO COMANDO]: {texto_comando}")
            background_tasks.add_task(processar_comando_whatsapp, texto_comando, jid_remetente)
            return {"status": "processando"}

    return {"status": "event_nao_suportado"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_config=None)