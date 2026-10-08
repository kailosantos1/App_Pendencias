import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import os
with patch.dict(os.environ, {"JID_PENDENCIAS": "teste-pendencias@g.us", "JID_CONTRATOS": "teste-contratos@g.us"}):
    import app_pendencias as s

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
        self.config_env = patch.dict(os.environ, {"JID_CONTRATOS": self.jids[1]})
        self.config_env.start()
        self.addCleanup(self.config_env.stop)

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

    def test_ajuda_e_comandos_nos_dois_grupos(self):
        respostas = []
        for jid in self.jids:
            for comando in ['!ajuda', '!comandos']:
                self.assertEqual(self.webhook(jid, comando)['status'], 'processando')
                destino, resposta = self.envio.call_args.args
                self.assertEqual(destino, jid)
                self.assertIn('!del studio home 1', resposta)
                self.assertIn('!lista', resposta)
                respostas.append(resposta)
            self.assertEqual(s.listar_absolutamente_tudo_db(self.grupos[jid]), [])
        self.assertEqual(len(set(respostas)), 1)

    def horario(self, dia, hora, minuto):
        return s.datetime.datetime(2026, 10, dia, hora, minuto, tzinfo=s.FUSO_CONTRATOS)

    def test_terca_repeticao_confirmacao_e_proximo_ciclo(self):
        s.verificar_avisos_contratos(self.horario(6, 13, 29))
        self.envio.assert_not_called()
        s.verificar_avisos_contratos(self.horario(6, 13, 30))
        self.assertEqual(self.envio.call_count, 1)
        self.assertEqual(self.envio.call_args.args[0], self.jids[1])
        s.verificar_avisos_contratos(self.horario(6, 13, 39))
        self.assertEqual(self.envio.call_count, 1)
        s.verificar_avisos_contratos(self.horario(6, 13, 40))
        self.assertEqual(self.envio.call_count, 2)
        self.assertIn('confirmado', s.confirmar_contrato(self.jids[1], agora=self.horario(6,13,41)))
        s.verificar_avisos_contratos(self.horario(6, 14, 0))
        self.assertEqual(self.envio.call_count, 2)
        s.verificar_avisos_contratos(self.horario(8, 13, 30))
        self.assertEqual(self.envio.call_count, 4)  # CNivel e Enebras na quinta.

    def test_quarta_confirmacao_separada(self):
        agora=self.horario(7,13,30)
        s.verificar_avisos_contratos(agora)
        self.assertEqual(self.envio.call_count,2)
        resposta=s.confirmar_contrato(self.jids[1], agora=agora)
        self.assertIn('!ok acrel',resposta)
        self.assertIn('!ok cbhidro',resposta)
        self.assertIn('confirmado',s.confirmar_contrato(self.jids[1],'acrel',agora))
        self.envio.reset_mock()
        s.verificar_avisos_contratos(self.horario(7,13,40))
        self.assertEqual(self.envio.call_count,1)
        self.assertIn('CBHidro',self.envio.call_args.args[1])

    def test_enebras_manha_falha_reinicio_e_atraso(self):
        s.verificar_avisos_contratos(self.horario(8,8,59))
        self.envio.assert_not_called()
        self.envio.return_value=False
        s.verificar_avisos_contratos(self.horario(8,9,0))
        self.assertIn('Enebras',self.envio.call_args.args[1])
        with sqlite3.connect(self.grupos[self.jids[1]]) as conn:
            self.assertIsNone(conn.execute('SELECT ultimo_envio FROM avisos_contratos').fetchone()[0])
        self.envio.return_value=True
        s.verificar_avisos_contratos(self.horario(8,9,1))
        self.assertEqual(self.envio.call_count,2)
        s.inicializar_banco(self.grupos[self.jids[1]])
        s.verificar_avisos_contratos(self.horario(8,9,2))
        self.assertEqual(self.envio.call_count,2)
        s.verificar_avisos_contratos(self.horario(9,9,1))
        self.assertIn('08/10/2026',self.envio.call_args.args[1])
        self.assertNotIn('Hoje é',self.envio.call_args.args[1])

    def test_ok_pelo_webhook_e_isolamento(self):
        agora=self.horario(6,13,30)
        s.verificar_avisos_contratos(agora)
        with patch.object(s,'agora_contratos',return_value=agora):
            self.webhook(self.jids[0],'!ok cnivel')
            self.assertIn('somente no grupo Contratos',self.envio.call_args.args[1])
            self.webhook(self.jids[1],'!ok cnivel')
            self.assertIn('confirmado',self.envio.call_args.args[1])
        self.envio.reset_mock()
        s.verificar_avisos_contratos(self.horario(6,14,0))
        self.envio.assert_not_called()

    def test_bloqueia_envio_fora_dos_grupos(self):
        # Recupera a função original sem realizar chamadas externas.
        patch.stopall()
        with patch.object(s.requests, 'post') as post:
            self.assertFalse(s.enviar_whatsapp('pessoa@s.whatsapp.net', 'teste'))
            post.assert_not_called()

    def test_preserva_banco_existente_e_horario(self):
        db=self.grupos[self.jids[0]]
        s.adicionar_pendencia_db('cliente','antiga',None,db)
        s.inicializar_banco(db)
        self.assertEqual(len(s.listar_pendencias_db('cliente',db)),1)
        data=s.calcular_data_hora_lembrete('lembrete amanhã às 14:30')
        self.assertEqual((data.hour,data.minute),(14,30))

if __name__ == '__main__':
    unittest.main()