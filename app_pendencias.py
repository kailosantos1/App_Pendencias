import os
import re
import sqlite3
import datetime
import asyncio
import requests
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn

app = FastAPI()

# --- CONFIGURAÇÕES DA EVOLUTION API ---
EVOLUTION_URL = os.getenv("EVOLUTION_URL", "http://localhost:8080")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "SUA_INSTANCIA")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "SUA_CHAVE_API_AQUI")

# ID oficial do grupo (O bot SÓ vai responder aqui dentro!)
JID_WHATSAPP = os.getenv("JID_WHATSAPP", "SEU_JID_DO_GRUPO@g.us")

# Caminho do banco de dados SQLite
DB_PATH = "pendencias.db"

# -------------------------------------------------------------
# FUNÇÕES DO BANCO DE DADOS (SQLITE)
# -------------------------------------------------------------
def inicializar_banco():
    """Cria a tabela de pendências se não existir"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pendencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            tarefa TEXT NOT NULL,
            data_alerta TEXT, -- Guardará no formato YYYY-MM-DD HH:MM
            lembrete_enviado INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def calcular_data_hora_lembrete(termo_lembrete):
    """
    Lógica aprimorada de agendamento:
    - Se não especificar o dia -> marca para HOJE.
    - Se não especificar a hora -> marca para as 08:00.
    - Se for para HOJE e as 08:00 já passaram (e nenhuma hora foi especificada), joga para AMANHÃ às 08:00.
    - Suporta 'hoje', 'amanha', dias da semana ('quarta'), dia do mês ('dia 29') e datas ('21/07/2026').
    """
    agora = datetime.datetime.now()
    hoje = datetime.date.today()
    termo_limpo = termo_lembrete.lower().strip()

    # 1. Extração da Data
    data_alvo = hoje # Padrão: HOJE caso não especifique o dia

    # Testa se tem data no formato DD/MM ou DD/MM/AAAA (ex: 21/07/2026)
    match_data_barra = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', termo_limpo)
    
    # Testa se fala "dia 29" ou "dia 5"
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
        # Remove a data do texto para não interferir na busca pela hora
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
        # Verifica dias da semana
        dias_semana = {
            "segunda": 0, "segunda-feira": 0, "seg": 0,
            "terça": 1, "terça-feira": 1, "ter": 1,
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
                    dias_a_somar = 7 # Próxima ocorrência na semana que vem
                data_alvo = hoje + datetime.timedelta(days=dias_a_somar)
                break

    # 2. Extração da Hora (com o texto da data já removido)
    hora_alvo = 8      # Padrão: 08:00
    minuto_alvo = 0
    hora_especificada = False

    # Busca padrões: "as 11:30", "11:30", "11h30", "11h", "11:00", "as 11"
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

    # 3. Regra de Ajuste: Se for HOJE, sem hora especificada e já passou das 08:00, joga para amanhã às 08:00
    if data_alvo == hoje and not hora_especificada:
        if datetime.time(hora_alvo, minuto_alvo) <= agora.time():
            data_alvo = hoje + datetime.timedelta(days=1)

    return datetime.datetime.combine(data_alvo, datetime.time(hora_alvo, minuto_alvo))

def adicionar_pendencia_db(cliente, tarefa, termo_lembrete=None):
    """Salva a tarefa com a data e hora calculadas se houver lembrete"""
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
    """Busca todas as pendências ativas de um cliente"""
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
    """Busca todas as pendências de todos os clientes cadastrados"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT cliente, tarefa FROM pendencias ORDER BY cliente ASC, id ASC")
    linhas = cursor.fetchall()
    conn.close()
    return linhas

def deletar_pendencia_db(cliente, indice_visual):
    """Deleta baseado na numeração sequencial"""
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
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"📡 [ENVIO WHATSAPP] Status: {response.status_code}")
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"❌ [ERRO CRÍTICO ENVIO]: {e}")
        return False

def formatar_lista_resposta(cliente):
    """Busca do banco e monta o painel visual formatado"""
    tarefas = listar_pendencias_db(cliente)
    cliente_maiusculo = cliente.upper()
    
    if not tarefas:
        return f"🎉 Nenhuma pendência em aberto para *{cliente_maiusculo}*!"
        
    resposta = f"📋 *Pendências - {cliente_maiusculo}*:\n\n"
    for idx, item in enumerate(tarefas, start=1):
        resposta += f"{idx}. {item['tarefa']}\n"
        
    resposta += f"\n💡 _Para remover use: del {cliente} <número>_"
    return resposta

def formatar_geral_todos_clientes():
    """Monta o resumão de todos os clientes com dados no banco"""
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
    
    # COMANDO GERAL: "pendencias", "lista", "listar" (Retorna tudo de todo mundo)
    if texto_minusculo in ['pendencias', 'pendencia', 'lista', 'listar', 'todos', 'tudo']:
        resposta = formatar_geral_todos_clientes()
        enviar_whatsapp(jid_remetente, resposta)
        return

    # 1. COMANDO DELETAR: "del cbhidro 1"
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

    # 2. COMANDO ADICIONAR: "cbhidro: mouse"
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

    # 3. COMANDO CONSULTAR INDIVIDUAL: "cbhidro", "pendencias cbhidro"
    for prefixo in ['pendencias ', 'pendencia ', 'lista ', 'listar ']:
        if texto_minusculo.startswith(prefixo):
            texto_minusculo = texto_minusculo.replace(prefixo, '').strip()
            
    if len(texto_minusculo.split()) == 1 and len(texto_minusculo) > 1:
        resposta = formatar_lista_resposta(texto_minusculo)
        enviar_whatsapp(jid_remetente, resposta)
        return

# -------------------------------------------------------------
# ROTINA DE VERIFICAÇÃO CONTINUA (VARREDURA MINUTO A MINUTO)
# -------------------------------------------------------------
def verificar_e_disparar_lembretes():
    """
    Varre o banco procurando lembretes agendados para a data/hora atual (ou anterior)
    que ainda não foram enviados.
    """
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
    
    # Atualiza as tarefas enviadas para não repetir o disparo
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
        # Dorme por 30 segundos antes da próxima checagem
        await asyncio.sleep(30)

# -------------------------------------------------------------
# ENDPOINT DO WEBHOOK (FASTAPI)
# -------------------------------------------------------------
@app.post("/webhook")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    dados = await request.json()
    
    if dados.get("event") == "messages.upsert":
        data = dados.get("data", {})
        key = data.get("key", {})
        jid_remetente = key.get("remoteJid")
        
        if jid_remetente != JID_WHATSAPP:
            return {"status": "ignorado_outro_chat"}
            
        message = data.get("message", {})
        texto_mensagem = ""
        if "conversation" in message:
            texto_mensagem = message["conversation"]
        elif "extendedTextMessage" in message:
            texto_mensagem = message["extendedTextMessage"].get("text", "")
            
        if texto_mensagem:
            print(f"\n📥 [WEBHOOK GRUPO OK] Mensagem processada: {texto_mensagem}")
            background_tasks.add_task(processar_comando_whatsapp, texto_mensagem, jid_remetente)
            
    return {"status": "processado"}

# -------------------------------------------------------------
# STARTUP DO APP
# -------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    inicializar_banco()
    asyncio.create_task(loop_verificacao_horario())
    print("\n🤖 [SISTEMA ATIVO] Servidor pronto com varredura minuto a minuto.\n")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, log_config=None)