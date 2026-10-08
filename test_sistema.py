import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import sistema as s

class SistemaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.grupos = {jid: str(Path(self.temp.name) / f'{i}.db') for i, jid in enumerate(s.GRUPOS)}
        self.patch = patch.object(s, 'GRUPOS', self.grupos)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        for db in self.grupos.values():
            s.inicializar_banco(db)
        self.envio = patch.object(s, 'enviar_whatsapp', return_value=True).start()
        self.addCleanup(patch.stopall)
        self.client = TestClient(s.app)
        self.jids = list(self.grupos)

    def webhook(self, jid, texto, from_me=False, msg_id='manual'):
        return self.client.post('/webhook', json={'event':'messages.upsert','data':{'key':{'remoteJid':jid,'fromMe':from_me,'id':msg_id},'message':{'conversation':texto}}}).json()

    def test_isolamento_criacao_lista_exclusao(self):
        for jid, tarefa in zip(self.jids, ['pendencia original', 'contrato novo']):
            self.assertEqual(self.webhook(jid, '!studio home: '+tarefa)['status'], 'processando')
        self.webhook(self.jids[0], '!lista studio home')
        self.assertIn('pendencia original', self.envio.call_args.args[1])
        self.assertNotIn('contrato novo', self.envio.call_args.args[1])
        self.webhook(self.jids[0], '!del studio home 1')
        self.assertEqual(s.listar_pendencias_db('studio home',self.grupos[self.jids[0]]), [])
        self.assertEqual(len(s.listar_pendencias_db('studio home',self.grupos[self.jids[1]])),1)

    def test_filtros_e_comando_proprio(self):
        for texto in ['/lista', 'conversa normal']:
            self.assertEqual(self.webhook(self.jids[0],texto)['status'], 'ignorado_nao_comando')
        self.assertEqual(self.webhook('outro@g.us','!lista')['status'], 'ignorado_outro_chat')
        self.assertEqual(self.webhook(self.jids[0],'!lista',True)['status'], 'processando')
        s.registrar_id_enviado('bot')
        self.assertEqual(self.webhook(self.jids[0],'!lista',True,'bot')['status'],'ignorado_mensagem_propria')

    def test_lembretes_falha_e_sucesso_por_grupo(self):
        for jid in self.jids:
            with sqlite3.connect(self.grupos[jid]) as conn:
                conn.execute("INSERT INTO pendencias(cliente,tarefa,data_alerta) VALUES ('cliente', ?, '2000-01-01 08:00')",(jid,))
        self.envio.side_effect = lambda jid,texto: jid == self.jids[1]
        s.verificar_e_disparar_lembretes()
        for jid, esperado in zip(self.jids,[0,1]):
            with sqlite3.connect(self.grupos[jid]) as conn:
                self.assertEqual(conn.execute('SELECT lembrete_enviado FROM pendencias').fetchone()[0],esperado)
        self.assertEqual([c.args[0] for c in self.envio.call_args_list],self.jids)

    def test_preserva_banco_existente_e_horario(self):
        db=self.grupos[self.jids[0]]
        s.adicionar_pendencia_db('cliente','antiga',None,db)
        s.inicializar_banco(db)
        self.assertEqual(len(s.listar_pendencias_db('cliente',db)),1)
        data=s.calcular_data_hora_lembrete('lembrete amanhã às 14:30')
        self.assertEqual((data.hour,data.minute),(14,30))

if __name__ == '__main__':
    unittest.main()