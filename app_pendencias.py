import os
import sys
import re
import sqlite3
import datetime
import asyncio
import threading
from pathlib import Path
from zoneinfo import ZoneInfo
from contextlib import suppress
import requests
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from dotenv import load_dotenv



# Carrega variáveis do arquivo .env

BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)

load_dotenv(BASE_DIR / ".env")



# --- CARREGAMENTO DAS CONFIGURAÇÕES VIA .ENV ---

EVOLUTION_URL = os.getenv("EVOLUTION_URL", "http://localhost:8080")

EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "App_Pendencias")

EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")

def caminho_banco(nome):

    return str((BASE_DIR / nome).resolve())



GRUPOS = {

    os.getenv("JID_PENDENCIAS", "").strip(): caminho_banco(os.getenv("DB_PENDENCIAS", os.getenv("DB_PATH", "pendencias.db"))),

    os.getenv("JID_CONTRATOS", "").strip(): caminho_banco(os.getenv("DB_CONTRATOS", "contratos.db")),

}

if len(GRUPOS) != 2 or any(not jid.endswith("@g.us") for jid in GRUPOS):

    raise ValueError("Configure JID_PENDENCIAS e JID_CONTRATOS no .env com dois JIDs de grupos distintos.")

if len(set(os.path.normcase(p) for p in GRUPOS.values())) != 2:

    raise ValueError("Cada grupo precisa de um banco distinto.")



PORT = int(os.getenv("PORT", 5000))



# Prefixo obrigatório para reconhecer uma mensagem como comando do bot.

# Sem isso, qualquer mensagem sua nesse chat (mesmo conversa solta) seria

# processada como se fosse um comando de pendências.

PREFIXO_COMANDO = "!"



# Agenda semanal de contratos, com confirmações persistidas no SQLite.

AGENDA_CONTRATOS = {

    "cnivel": {"nome": "CNivel", "dias": (1, 3), "hora": (13, 30)},

    "cbhidro": {"nome": "CBHidro", "dias": (2,), "hora": (13, 30)},

    "enebras": {"nome": "Enebras", "dias": (3,), "hora": (9, 0)},

    "acrel": {"nome": "Acrel", "dias": (2,), "hora": (13, 30)},

}

CONTRATOS_LOCK = threading.RLock()

FUSO_CONTRATOS = ZoneInfo("America/Sao_Paulo")





def agora_contratos():

    return datetime.datetime.now(FUSO_CONTRATOS)





def gerar_ocorrencias_contratos(conn, agora):

    data = agora.date().isoformat()

    for cliente, config in AGENDA_CONTRATOS.items():

        if agora.weekday() in config["dias"] and (agora.hour, agora.minute) >= config["hora"]:

            conn.execute(

                "INSERT OR IGNORE INTO avisos_contratos (cliente, data_contrato) VALUES (?, ?)",

                (cliente, data),

            )

    conn.commit()





def verificar_avisos_contratos(agora=None):

    agora = agora or agora_contratos()

    jid = os.getenv("JID_CONTRATOS", "").strip()

    db_path = GRUPOS.get(jid)

    if db_path is None:

        return

    with CONTRATOS_LOCK, sqlite3.connect(db_path, timeout=30) as conn:

        gerar_ocorrencias_contratos(conn, agora)

        linhas = conn.execute(

            "SELECT cliente, MIN(data_contrato), MAX(ultimo_envio) FROM avisos_contratos "

            "WHERE confirmado = 0 GROUP BY cliente ORDER BY cliente"

        ).fetchall()

        for cliente, data_contrato, ultimo_envio in linhas:

            if ultimo_envio and agora.timestamp() - ultimo_envio < 600:

                continue

            nome = AGENDA_CONTRATOS[cliente]["nome"]

            if data_contrato == agora.date().isoformat():

                inicio = f"Hoje é dia de contrato na {nome}"

            else:

                data_formatada = datetime.date.fromisoformat(data_contrato).strftime("%d/%m/%Y")

                inicio = f"O contrato na {nome} do dia {data_formatada} ainda está pendente"

            mensagem = (

                f"{inicio}, por favor me diga quando alguém for para não ficar pendente o contrato.\n\n"

                f"✅ Para confirmar, envie !ok {cliente}."

            )

            if enviar_whatsapp(jid, mensagem):

                conn.execute(

                    "UPDATE avisos_contratos SET ultimo_envio = ? WHERE cliente = ? AND confirmado = 0",

                    (agora.timestamp(), cliente),

                )

                conn.commit()





def confirmar_contrato(jid, cliente="", agora=None):

    if jid != os.getenv("JID_CONTRATOS", "").strip():

        return "Os avisos de contrato são confirmados somente no grupo Contratos."

    agora = agora or agora_contratos()

    with CONTRATOS_LOCK, sqlite3.connect(GRUPOS[jid], timeout=30) as conn:

        gerar_ocorrencias_contratos(conn, agora)

        pendentes = [r[0] for r in conn.execute(

            "SELECT DISTINCT cliente FROM avisos_contratos WHERE confirmado = 0 ORDER BY cliente"

        )]

        cliente = cliente.strip().lower()

        if not cliente:

            if not pendentes:

                return "✅ Não há avisos de contrato pendentes."

            if len(pendentes) > 1:

                opcoes = "\n".join(f"• !ok {c}" for c in pendentes)

                return "Há mais de um cliente pendente. Confirme pelo nome:\n" + opcoes

            cliente = pendentes[0]

        if cliente not in AGENDA_CONTRATOS:

            return "Cliente desconhecido. Use !ok cnivel, !ok cbhidro, !ok enebras ou !ok acrel."

        if cliente not in pendentes:

            return f"Não há aviso ativo de contrato para {AGENDA_CONTRATOS[cliente]['nome']}."

        conn.execute(

            "UPDATE avisos_contratos SET confirmado = 1, confirmado_em = ? WHERE cliente = ? AND confirmado = 0",

            (agora.isoformat(), cliente),

        )

        return f"✅ Contrato de {AGENDA_CONTRATOS[cliente]['nome']} confirmado! Os avisos foram encerrados."





# -------------------------------------------------------------

# LIFESPAN (GERENCIADOR DE INICIALIZAÇÃO DO FASTAPI)

# -------------------------------------------------------------

@asynccontextmanager

async def lifespan(app: FastAPI):

    for db_path in GRUPOS.values():

        inicializar_banco(db_path)

    rotina = asyncio.create_task(loop_verificacao_horario())

    print("\n🤖 [SISTEMA ATIVO] Servidor pronto com varredura minuto a minuto.\n")

    try:

        yield

    finally:

        rotina.cancel()

        with suppress(asyncio.CancelledError):

            await rotina



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

def inicializar_banco(db_path):

    conn = sqlite3.connect(db_path, timeout=30)

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

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS avisos_contratos (

            cliente TEXT NOT NULL,

            data_contrato TEXT NOT NULL,

            confirmado INTEGER NOT NULL DEFAULT 0,

            ultimo_envio REAL,

            confirmado_em TEXT,

            PRIMARY KEY (cliente, data_contrato)

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



def adicionar_pendencia_db(cliente, tarefa, termo_lembrete, db_path):

    conn = sqlite3.connect(db_path, timeout=30)

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



def listar_pendencias_db(cliente, db_path):

    conn = sqlite3.connect(db_path, timeout=30)

    cursor = conn.cursor()

    cursor.execute(

        "SELECT id, tarefa FROM pendencias WHERE cliente = ? ORDER BY id ASC",

        (cliente.lower(),)

    )

    linhas = cursor.fetchall()

    conn.close()

    return [{"id_real": linha[0], "tarefa": linha[1]} for linha in linhas]



def listar_absolutamente_tudo_db(db_path):

    conn = sqlite3.connect(db_path, timeout=30)

    cursor = conn.cursor()

    cursor.execute("SELECT cliente, tarefa FROM pendencias ORDER BY cliente ASC, id ASC")

    linhas = cursor.fetchall()

    conn.close()

    return linhas



def deletar_pendencia_db(cliente, indice_visual, db_path):

    conn = sqlite3.connect(db_path, timeout=30)

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

    if jid_destino not in GRUPOS:

        print("Envio bloqueado: destino não está nos grupos configurados.")

        return False

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



def formatar_lista_resposta(cliente, db_path):

    tarefas = listar_pendencias_db(cliente, db_path)

    cliente_maiusculo = cliente.upper()



    if not tarefas:

        return f"🎉 Nenhuma pendência em aberto para *{cliente_maiusculo}*!"



    resposta = f"📋 *Pendências - {cliente_maiusculo}*:\n\n"

    for idx, item in enumerate(tarefas, start=1):

        resposta += f"{idx}. {item['tarefa']}\n"



    resposta += f"\n💡 _Para remover use: {PREFIXO_COMANDO}del {cliente} <número>_"

    return resposta



def formatar_geral_todos_clientes(db_path):

    linhas = listar_absolutamente_tudo_db(db_path)



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

    db_path = GRUPOS.get(jid_remetente)

    if db_path is None:

        return

    texto = mensagem_texto.strip()

    texto_minusculo = texto.lower().replace('?', '').strip()



    if texto_minusculo == 'ok' or texto_minusculo.startswith('ok '):

        cliente = texto_minusculo[2:].strip()

        enviar_whatsapp(jid_remetente, confirmar_contrato(jid_remetente, cliente))

        return



    if texto_minusculo in ['ajuda', 'comandos']:

        resposta = (

            "📖 *COMANDOS DISPONÍVEIS*\n\n"

            "• !ajuda ou !comandos — mostra esta ajuda.\n"

            "• !ok <cliente> — confirma contrato e encerra os avisos desse cliente.\n"

            "  Exemplo: !ok cnivel; !ok sozinho confirma se houver só um cliente pendente.\n"

            "• !lista — lista todas as pendências deste grupo.\n"

            "• !lista <cliente> — lista as pendências de um cliente.\n"

            "  Exemplo: !lista studio home\n"

            "• !<cliente> — consulta rápida para nomes de uma palavra.\n"

            "  Exemplo: !acme\n"

            "• !<cliente>: <tarefa> — adiciona uma pendência.\n"

            "  Exemplo: !studio home: revisar contrato\n"

            "• !<cliente>: <tarefa> lembrete <data/hora> — adiciona com lembrete.\n"

            "  Exemplo: !studio home: ligar lembrete amanhã às 14:30\n"

            "• !del <cliente> <número> ou !check <cliente> <número> — remove o item da lista.\n"

            "  Exemplo: !del studio home 1\n\n"

            "Aliases da lista geral: !pendencias, !pendencia, !listar, !todos e !tudo.\n"

            "Consulta por cliente: !pendencias <cliente>, !pendencia <cliente> ou !listar <cliente>.\n\n"

            "Cada comando consulta ou altera somente os dados deste grupo."

        )

        enviar_whatsapp(jid_remetente, resposta)

        return



    if texto_minusculo in ['pendencias', 'pendencia', 'lista', 'listar', 'todos', 'tudo']:

        resposta = formatar_geral_todos_clientes(db_path)

        enviar_whatsapp(jid_remetente, resposta)

        return



    if texto.lower().startswith(('del ', 'check ')):

        padrao_del = r"^(del|check)\s+(.+?)\s+(\d+)$"

        match = re.match(padrao_del, texto, re.IGNORECASE)



        if match:

            _, cliente, indice_visual = match.groups()

            indice_visual = int(indice_visual)



            sucesso = deletar_pendencia_db(cliente, indice_visual, db_path)

            if sucesso:

                resposta = f"✅ Item {indice_visual} removido com sucesso!\n\n"

                resposta += formatar_lista_resposta(cliente, db_path)

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

            data_alerta = adicionar_pendencia_db(cliente, conteudo, termo_lembrete, db_path)



            resposta = f"💾 Salvo para *{cliente.upper()}*!\n"

            if data_alerta:

                data_dt = datetime.datetime.strptime(data_alerta, "%Y-%m-%d %H:%M")

                data_formatada = data_dt.strftime("%d/%m/%Y às %H:%M")

                resposta += f"⏰ _Vou te lembrar disso em: {data_formatada}_\n\n"

            else:

                resposta += "\n"



            resposta += formatar_lista_resposta(cliente, db_path)

            enviar_whatsapp(jid_remetente, resposta)

            return



    consulta_explicita = False

    for prefixo in ['pendencias ', 'pendencia ', 'lista ', 'listar ']:

        if texto_minusculo.startswith(prefixo):

            texto_minusculo = texto_minusculo[len(prefixo):].strip()

            consulta_explicita = True

            break



    if texto_minusculo and (consulta_explicita or len(texto_minusculo.split()) == 1):

        resposta = formatar_lista_resposta(texto_minusculo, db_path)

        enviar_whatsapp(jid_remetente, resposta)

        return



# -------------------------------------------------------------

# ROTINA DE VERIFICAÇÃO CONTINUA DE LEMBRETES

# -------------------------------------------------------------

def verificar_e_disparar_lembretes_grupo(jid_destino, db_path):

    agora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")



    conn = sqlite3.connect(db_path, timeout=30)

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



    if not enviar_whatsapp(jid_destino, mensagem):

        conn.close()

        return



    for id_tarefa in ids_enviados:

        cursor.execute("UPDATE pendencias SET lembrete_enviado = 1 WHERE id = ?", (id_tarefa,))



    conn.commit()

    conn.close()



def verificar_e_disparar_lembretes():

    for jid, db_path in GRUPOS.items():

        try:

            verificar_e_disparar_lembretes_grupo(jid, db_path)

        except Exception as erro:

            print(f"Erro nos lembretes do grupo {jid}: {erro}")





async def loop_verificacao_horario():

    while True:

        try:

            await asyncio.to_thread(verificar_e_disparar_lembretes)

            await asyncio.to_thread(verificar_avisos_contratos)

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



    if not isinstance(dados, dict):

        return {"status": "json_invalido"}



    if dados.get("event") == "messages.upsert":

        data = dados.get("data", {})

        if not isinstance(data, dict):

            return {"status": "dados_invalidos"}

        key = data.get("key", {})

        if not isinstance(key, dict):

            return {"status": "dados_invalidos"}



        # Primeiro filtro: só continua se a mensagem for do grupo configurado.

        # Qualquer coisa fora desse grupo é descartada aqui, sem olhar fromMe,

        # texto ou qualquer outra coisa.

        jid_remetente = str(key.get("remoteJid") or "").strip()

        if jid_remetente not in GRUPOS:

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



        print(f"📍 [GRUPO CONFERIDO] Mensagem é do grupo esperado: '{jid_remetente}'")



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



        if not isinstance(texto_mensagem, str):

            return {"status": "sem_texto"}

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