"""Testes unitarios da ponte real (sem rede real: fakes para tmux/gh/nuvem).
Rodar:  cd software/bridge/real && python3 -m unittest -v"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix='mascote-teste-')
os.environ['MASCOTE_CONFIG_DIR'] = os.path.join(TMP, 'cfg')
os.environ['MASCOTE_STATE_DIR'] = os.path.join(TMP, 'estado')
sys.path.insert(0, AQUI)

import comum  # noqa: E402
import ponte_real  # noqa: E402
from fonte_nuvem import Nuvem  # noqa: E402
from fonte_vps import FonteVPS, id_de_cwd  # noqa: E402

TOKEN = 'token-aparelho-de-teste-123'
HOOKTOK = 'token-hook-de-teste-456'
CWD = '/home/hermes/repos/projeto-x'


def run_fake(args, **kw):
    return ''


class NuvemFake(Nuvem):
    """Simula a API interna: uma sessao nuvem com pedido pendente e uma bridge."""
    def __init__(self):
        super().__init__(http=self.http)
        self.posts = []
        self.falhar = False
        self.ev = [
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Vou rodar os testes \u2014 ok?'}]}},
            {'type': 'control_request', 'request_id': 'r1', 'request': {'subtype': 'can_use_tool', 'tool_name': 'Bash',
             'tool_use_id': 'tu1', 'input': {'command': 'npm test'}}},
            {'type': 'control_request', 'request_id': 'r2', 'request': {'subtype': 'can_use_tool', 'tool_name': 'Bash',
             'tool_use_id': 'tu2', 'input': {'command': 'sudo apt install x'}}},
        ]

    def http(self, metodo, path, corpo=None):
        if metodo == 'GET' and path.startswith('/v1/sessions?'):
            agora = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            return 200, {'data': [
                {'id': 'session_N1', 'title': 'Tarefa nuvem', 'environment_kind': 'anthropic_cloud',
                 'session_status': 'requires_action', 'updated_at': agora,
                 'session_context': {'sources': [{'url': 'https://github.com/minepedro/testes', 'revision': 'main'}]}},
                {'id': 'session_B1', 'title': 'Sessao VPS conhecida', 'environment_kind': 'bridge',
                 'session_status': 'idle', 'updated_at': agora, 'session_context': {}},
                {'id': 'session_B2', 'title': 'Outra bridge', 'environment_kind': 'bridge',
                 'session_status': 'idle', 'updated_at': agora, 'session_context': {}},
                {'id': 'session_V', 'title': 'Velha', 'environment_kind': 'anthropic_cloud',
                 'session_status': 'idle', 'updated_at': '2020-01-01T00:00:00Z', 'session_context': {}},
            ], 'has_more': False}
        if metodo == 'GET' and '/events' in path:
            # paginacao: 2 paginas
            if 'after_id' not in path:
                return 200, {'data': self.ev[:1], 'has_more': True, 'last_id': 'p1'}
            return 200, {'data': self.ev[1:], 'has_more': False, 'last_id': 'p2'}
        if metodo == 'POST':
            if self.falhar:
                return 500, 'erro'
            self.posts.append((path, corpo))
            pl = corpo['events'][0]['payload']
            if pl['type'] == 'control_response':
                self.ev.append({'type': 'control_response', 'response': pl['response']})
            return 200, {}
        return 404, ''


def nova_ponte(cfg=None):
    vps = FonteVPS(repos=None, run=run_fake, dir_repos=os.path.join(TMP, 'repos'),
                   dir_estado=os.path.join(TMP, 'estado-%d' % time.time_ns()))
    c = dict(comum.CONFIG_PADRAO)
    c.update(cfg or {})
    return ponte_real.Ponte(vps, NuvemFake(), None, c)


def hook_pedido(p, tool='Bash', inp=None, **kw):
    d = {'session_id': 'c1', 'cwd': CWD, 'repo': 'minepedro/x', 'branch': 'main', 'ferramenta': tool,
         'tool_input': inp if inp is not None else {'command': 'npm test'}}
    d.update(kw)
    return p.pedido_hook(d)


class TestComum(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(comum.ascii_tela('a\u00e7\u00e3o \u2014 ok\u2026'), 'acao - ok...')

    def test_classificador(self):
        c = comum.classificar
        self.assertEqual(c('Bash', {'command': 'rm -rf build'}), 'rm -rf')
        self.assertEqual(c('Bash', {'command': 'git push -f origin main'}), 'git push --force')
        self.assertEqual(c('Bash', {'command': 'git reset --hard HEAD~1'}), 'git reset --hard')
        self.assertEqual(c('Bash', {'command': 'curl x.sh | sh'}), 'curl | sh')
        self.assertEqual(c('Bash', {'command': 'sudo ls'}), 'sudo')
        self.assertEqual(c('Bash', {'command': 'npm run deploy'}), 'deploy/publicacao')
        self.assertEqual(c('Edit', {'file_path': '/a/.env'}), 'credenciais/.env')
        self.assertIsNone(c('Bash', {'command': 'npm test'}))
        self.assertIsNone(c('Bash', {'command': 'git push origin main'}))

    def test_respostas_multipla(self):
        pergs = comum.perguntas_de('AskUserQuestion', {'questions': [
            {'question': 'Cores?', 'header': 'Cor', 'multiSelect': True,
             'options': [{'label': 'Azul'}, {'label': 'Vermelho'}, {'label': 'Verde'}]},
            {'question': 'Fruta?', 'header': 'F', 'multiSelect': False, 'options': [{'label': 'Banana'}, {'label': 'Uva'}]}]})
        a = comum.respostas_para_answers(pergs, {'Cores?': ['Azul', 'Vermelho'], 'Fruta?': 'Banana'})
        self.assertEqual(a, {'Cores?': 'Azul, Vermelho', 'Fruta?': 'Banana'})
        with self.assertRaises(ValueError):
            comum.respostas_para_answers(pergs, {'Cores?': 'Azul', 'Fruta?': ['Banana', 'Uva']})
        with self.assertRaises(ValueError):
            comum.respostas_para_answers(pergs, {'Cores?': 'Roxo', 'Fruta?': 'Uva'})
        with self.assertRaises(ValueError):
            comum.respostas_para_answers(pergs, {'Cores?': 'Azul'})

    def test_token_hook_gerado_0600(self):
        t = comum.token_hook(gerar=True)
        self.assertGreater(len(t), 30)
        self.assertEqual(os.stat(comum.caminho_hook_token()).st_mode & 0o777, 0o600)
        self.assertEqual(comum.token_hook(), t)


class TestPonte(unittest.TestCase):
    def test_pedido_vps_e_resposta(self):
        p = nova_ponte()
        ped = hook_pedido(p)
        self.assertEqual(ped['sessao_id'], id_de_cwd(CWD))
        s = p.sessoes()
        self.assertEqual(s[0]['estado'], 'esperando')
        self.assertEqual(s[0]['pedidos_pendentes'], 1)
        self.assertEqual(p.responder(ped['id'], {'decisao': 'talvez'})[0], 400)
        self.assertEqual(p.responder(ped['id'], {'decisao': 'aprovar'})[0], 200)
        self.assertEqual(p.pedido_hook_ver(ped['id'])['decisao'], 'aprovar')
        self.assertEqual(p.responder(ped['id'], {'decisao': 'recusar'})[0], 409)
        self.assertEqual(p.responder('naoexiste', {'decisao': 'aprovar'})[0], 404)

    def test_so_no_app_403(self):
        p = nova_ponte()
        ped = hook_pedido(p, inp={'command': 'rm -rf /tmp/x'}, perigoso=True, so_no_app=True)
        self.assertEqual(ped['estado'], 'so_no_app')
        self.assertEqual(p.responder(ped['id'], {'decisao': 'aprovar'})[0], 403)
        # mesmo se o hook nao marcou, o classificador da ponte marca
        ped2 = hook_pedido(p, inp={'command': 'git push --force'})
        self.assertTrue(ped2['so_no_app'])

    def test_pergunta(self):
        p = nova_ponte()
        ped = hook_pedido(p, tool='AskUserQuestion', inp={'questions': [
            {'question': 'Cores?', 'header': 'Cor', 'multiSelect': True, 'options': [{'label': 'Azul'}, {'label': 'Vermelho'}]}]})
        self.assertEqual(ped['tipo'], 'pergunta')
        self.assertEqual(p.responder(ped['id'], {'decisao': 'sempre'})[0], 400)
        self.assertEqual(p.responder(ped['id'], {'decisao': 'aprovar', 'respostas': {'Cores?': ['Roxo']}})[0], 400)
        self.assertEqual(p.responder(ped['id'], {'decisao': 'aprovar', 'respostas': {'Cores?': ['Azul', 'Vermelho']}})[0], 200)
        self.assertEqual(p.pedido_hook_ver(ped['id'])['answers'], {'Cores?': 'Azul, Vermelho'})

    def test_resposta_pelo_app(self):
        p = nova_ponte()
        ped = hook_pedido(p)
        p.pedido_hook_fim(ped['id'], 'respondido_app')
        self.assertEqual(p.responder(ped['id'], {'decisao': 'aprovar'})[0], 409)
        self.assertEqual(p.listar_pedidos(True), [])

    def test_compat_estado_e_toque_atrasado(self):
        p = nova_ponte({'nuvem_ativa': False})
        a = hook_pedido(p, inp={'command': 'npm test'})
        e = p.estado_compat()
        s = e['sessoes'][0]
        self.assertEqual(set(s), {'id', 'title', 'repo', 'branch', 'status', 'ago', 'last', 'reply', 'ask'})
        self.assertEqual(s['status'], 'waiting')
        self.assertEqual(s['ask'], {'tool': 'Bash', 'text': 'npm test'})
        # o pedido A some (respondido pelo app) e chega B ANTES de novo /api/estado
        p.pedido_hook_fim(a['id'], 'respondido_app')
        b = hook_pedido(p, inp={'command': 'npm run build'})
        code, obj = p.acao_compat(s['id'], 'aprovar')
        self.assertEqual(code, 409)                     # toque atrasado nao aprova B
        self.assertEqual(p.pedidos[b['id']]['estado'], 'pendente')
        p.estado_compat()                               # agora o aparelho ve B
        self.assertEqual(p.acao_compat(s['id'], 'aprovar')[0], 200)
        self.assertEqual(p.pedidos[b['id']]['estado'], 'respondido_mascote')
        self.assertEqual(p.acao_compat(s['id'], 'aprovar')[0], 409)
        self.assertEqual(p.acao_compat('sessao-x', 'aprovar')[0], 409)

    def test_compat_so_no_app_e_pergunta(self):
        p = nova_ponte({'nuvem_ativa': False})
        hook_pedido(p, inp={'command': 'sudo reboot'})
        s = p.estado_compat()['sessoes'][0]
        self.assertTrue(s['ask']['text'].startswith('APROVE PELO APP: '))
        self.assertEqual(p.acao_compat(s['id'], 'aprovar')[0], 403)
        p2 = nova_ponte({'nuvem_ativa': False})
        hook_pedido(p2, tool='AskUserQuestion', inp={'questions': [{'question': 'Fruta?', 'options': [{'label': 'Banana'}]}]})
        s2 = p2.estado_compat()['sessoes'][0]
        self.assertIn('Fruta? [Banana]', s2['ask']['text'])
        self.assertEqual(p2.acao_compat(s2['id'], 'aprovar')[0], 409)

    def test_nuvem_dedupe_pedidos_e_resposta(self):
        p = nova_ponte()
        p.vps.criadas['x'] = {}
        p.vps.sessoes['vx'] = {'id': 'vx', 'origem': 'vps', 'titulo': 'Sessao VPS conhecida', 'estado': 'parada',
                               'atualizado': time.time()}
        p.atualizar_nuvem()
        ids = {s['id']: s for s in p.sessoes()}
        self.assertNotIn('session_B1', ids)          # dedupe: bridge conhecida
        self.assertTrue(ids['session_B2']['somente_leitura'])
        self.assertEqual(ids['session_B2']['origem'], 'vps')
        self.assertNotIn('session_V', ids)           # > 7 dias
        n = ids['session_N1']
        self.assertEqual((n['origem'], n['estado'], n['pedidos_pendentes']), ('nuvem', 'esperando', 2))
        peds = {x['resumo']: x for x in p.listar_pedidos(True)}
        self.assertTrue(peds['sudo apt install x']['so_no_app'])
        nid = peds['npm test']['id']
        self.assertEqual(p.responder(nid, {'decisao': 'sempre'})[0], 403)
        self.assertEqual(p.responder(nid, {'decisao': 'aprovar'})[0], 200)
        post = p.nuvem.posts[-1][1]['events'][0]['payload']['response']
        self.assertEqual(post['request_id'], 'r1')
        self.assertEqual(post['response']['toolUseID'], 'tu1')
        p.atualizar_nuvem()                          # nao recria pedido ja respondido
        self.assertEqual([x['resumo'] for x in p.listar_pedidos(True)], ['sudo apt install x'])

    def test_nuvem_falha_vira_so_no_app(self):
        p = nova_ponte()
        p.atualizar_nuvem()
        nid = [x for x in p.listar_pedidos(True) if x['resumo'] == 'npm test'][0]['id']
        p.nuvem.falhar = True
        self.assertEqual(p.responder(nid, {'decisao': 'aprovar'})[0], 502)
        self.assertEqual(p.pedidos[nid]['estado'], 'so_no_app')
        self.assertIn('responda pelo app', p.pedidos[nid]['motivo_so_no_app'])

    def test_nuvem_responder_desligado(self):
        p = nova_ponte({'nuvem_responder': False})
        p.atualizar_nuvem()
        self.assertTrue(all(x['so_no_app'] for x in p.listar_pedidos(True)))

    def test_estados_por_hook(self):
        p = nova_ponte({'nuvem_ativa': False})
        base = {'cwd': CWD, 'session_id': 'c1'}
        p.vps.evento(dict(base, evento='SessionStart'))
        p.vps.evento(dict(base, evento='UserPromptSubmit', prompt='faca x'))
        self.assertEqual(p.sessoes()[0]['estado'], 'trabalhando')
        p.vps.evento(dict(base, evento='Stop', last_assistant_message='Feito: \u00e9 isso.'))
        s = p.sessao(id_de_cwd(CWD))
        self.assertEqual((s['estado'], s['ultimo_prompt']), ('parada', 'faca x'))
        self.assertEqual(p.mensagem(s['id'], 'oi')[0], 409)  # sem tmux conhecido
        p.vps.evento(dict(base, evento='SessionEnd'))
        self.assertEqual(p.sessoes()[0]['estado'], 'encerrada')

    def test_criar_validacao(self):
        p = nova_ponte()
        self.assertEqual(p.criar_sessao({'origem': 'vps'})[0], 400)
        self.assertEqual(p.criar_sessao({'origem': 'vps', 'titulo': 'x', 'repo': 'a b'})[0], 400)
        self.assertEqual(p.criar_sessao({'origem': 'nuvem', 'titulo': 'x', 'repo': 'a/b'})[0], 400)
        self.assertEqual(p.criar_sessao({'origem': 'marte', 'titulo': 'x'})[0], 400)


class TestHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = nova_ponte({'nuvem_ativa': False})
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), ponte_real.criar_handler(cls.p, TOKEN, HOOKTOK))
        cls.url = 'http://127.0.0.1:%d' % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def chamar(self, metodo, path, corpo=None, cab=None, cru=None):
        data = cru if cru is not None else (json.dumps(corpo).encode() if corpo is not None else None)
        r = urllib.request.Request(self.url + path, data=data, method=metodo, headers=cab or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as f:
                b = f.read()
                return f.status, (json.loads(b) if b != b'ok' else 'ok'), b
        except urllib.error.HTTPError as e:
            b = e.read()
            return e.code, json.loads(b or b'{}'), b

    def test_tokens(self):
        self.assertEqual(self.chamar('GET', '/saude')[0], 200)
        self.assertEqual(self.chamar('GET', '/api/estado')[0], 401)
        self.assertEqual(self.chamar('GET', '/api/estado', cab={'X-Token': 'errado'})[0], 401)
        self.assertEqual(self.chamar('GET', '/api/estado', cab={'X-Token': TOKEN})[0], 200)
        # token do aparelho nao abre rota interna e vice-versa
        self.assertEqual(self.chamar('POST', '/interno/eventos', {}, {'X-Token': TOKEN})[0], 401)
        self.assertEqual(self.chamar('GET', '/api/sessoes', cab={'X-Hook-Token': HOOKTOK})[0], 401)

    def test_voz(self):
        class Fake:
            def transcrever(self, pcm):
                return 'rode os testes' if pcm else ''
        h = {'X-Token': TOKEN, 'Content-Type': 'application/octet-stream'}
        antigo = self.p.stt
        try:
            self.p.stt = None
            self.assertEqual(self.chamar('POST', '/api/voz', cab=h, cru=b'\0' * 100)[0], 503)
            self.p.stt = Fake()
            st, r, _ = self.chamar('POST', '/api/voz', cab=h, cru=b'\0' * 32000)
            self.assertEqual((st, r['texto'], r['segundos']), (200, 'rode os testes', 1.0))
            self.assertEqual(self.chamar('POST', '/api/voz', cab={'Content-Type': 'application/octet-stream'},
                                         cru=b'\0' * 10)[0], 401)
            try:   # a ponte responde 413 sem ler o corpo; o cliente pode ver a conexao fechada antes
                self.assertEqual(self.chamar('POST', '/api/voz', cab=h, cru=b'\0' * (ponte_real.MAX_VOZ + 2))[0], 413)
            except (ConnectionError, urllib.error.URLError):
                pass
        finally:
            self.p.stt = antigo

    def test_stt_sem_biblioteca(self):
        import stt
        t = stt.Transcritor()
        self.assertEqual(t.transcrever(b'\0' * 100), '')          # curto demais: nem carrega o modelo
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            with self.assertRaises(stt.SemTranscritor):
                t.transcrever(b'\0' * 32000)

    def test_corpo_grande(self):
        c = self.chamar('POST', '/api/acao', cab={'X-Token': TOKEN}, cru=b'{"a":"' + b'x' * 70000 + b'"}')
        self.assertEqual(c[0], 413)

    def test_fluxo_http_ascii(self):
        h = {'X-Hook-Token': HOOKTOK}
        st, r, _ = self.chamar('POST', '/interno/pedidos', {
            'cwd': '/home/hermes/repos/http-y', 'ferramenta': 'Bash', 'explicacao': 'Explica\u00e7\u00e3o',
            'tool_input': {'command': 'echo ol\u00e1'}}, h)
        self.assertEqual(st, 200)
        st, lst, cru = self.chamar('GET', '/api/pedidos?pendentes=1', cab={'X-Token': TOKEN})
        cru.decode('ascii')
        alvo = [x for x in lst if x['id'] == r['id']][0]
        for k in ('id', 'sessao_id', 'origem', 'tipo', 'ferramenta', 'resumo', 'detalhe', 'explicacao', 'perguntas',
                  'perigoso', 'so_no_app', 'motivo_so_no_app', 'criado_em', 'estado'):
            self.assertIn(k, alvo)
        self.assertEqual(alvo['resumo'], 'echo ola')
        st, ses, _ = self.chamar('GET', '/api/sessoes', cab={'X-Token': TOKEN})
        for k in ('id', 'origem', 'titulo', 'repo', 'branch', 'estado', 'pedidos_pendentes', 'atualizado_em',
                  'ha_quanto', 'ultima_resposta_resumo'):
            self.assertIn(k, ses[0])
        st, det, _ = self.chamar('GET', '/api/sessoes/' + alvo['sessao_id'], cab={'X-Token': TOKEN})
        self.assertEqual(len(det['pedidos']), 1)
        st, _, _ = self.chamar('POST', '/api/pedidos/%s/resposta' % r['id'], {'decisao': 'recusar', 'motivo': 'nao'},
                               {'X-Token': TOKEN})
        self.assertEqual(st, 200)
        st, v, _ = self.chamar('GET', '/interno/pedidos/' + r['id'], cab=h)
        self.assertEqual((v['estado'], v['decisao'], v['motivo']), ('respondido_mascote', 'recusar', 'nao'))
        self.assertEqual(self.chamar('POST', '/api/pedidos/%s/resposta' % r['id'], {'decisao': 'aprovar'},
                                     {'X-Token': TOKEN})[0], 409)


class TestHook(unittest.TestCase):
    """hook.py de verdade (subprocesso) contra a ponte HTTP em porta livre."""
    @classmethod
    def setUpClass(cls):
        cls.p = nova_ponte({'nuvem_ativa': False})
        th = comum.token_hook(gerar=True)
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), ponte_real.criar_handler(cls.p, TOKEN, th))
        cls.url = 'http://127.0.0.1:%d' % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.cwd = os.path.join(os.path.expanduser('~'), 'mascote-cli-lab', 'teste-unit-hook')
        os.makedirs(cls.cwd, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.cwd, ignore_errors=True)

    def hook(self, d, espera='20', url=None):
        env = dict(os.environ, MASCOTE_PONTE=url or self.url, MASCOTE_ESPERA=espera)
        d = dict({'cwd': self.cwd, 'session_id': 'h1', 'transcript_path': '/nao/existe'}, **d)
        return subprocess.Popen([sys.executable, os.path.join(AQUI, 'hook.py')], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, env=env), json.dumps(d)

    def rodar(self, d, responder=None, **kw):
        pr, entrada = self.hook(d, **kw)
        pr.stdin.write(entrada)
        pr.stdin.close()
        if responder:
            for _ in range(50):
                pend = [x for x in self.p.listar_pedidos(True) if x['estado'] == 'pendente']
                if pend:
                    self.assertEqual(self.p.responder(pend[-1]['id'], responder)[0], 200)
                    break
                time.sleep(0.1)
        out = pr.stdout.read()
        pr.wait(30)
        return json.loads(out) if out.strip() else None

    def test_fora_do_dir_nao_age(self):
        self.assertIsNone(self.rodar({'cwd': '/tmp', 'hook_event_name': 'PermissionRequest', 'tool_name': 'Bash',
                                      'tool_input': {'command': 'ls'}}))

    def test_ponte_fora_do_ar(self):
        t = time.time()
        self.assertIsNone(self.rodar({'hook_event_name': 'PermissionRequest', 'tool_name': 'Bash',
                                      'tool_input': {'command': 'ls'}}, url='http://127.0.0.1:9'))
        self.assertLess(time.time() - t, 5)

    def test_perigoso_ask(self):
        o = self.rodar({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'rm -rf x'}})
        self.assertEqual(o['hookSpecificOutput']['permissionDecision'], 'ask')
        self.assertTrue(any(x['so_no_app'] for x in self.p.listar_pedidos(True)))
        self.assertIsNone(self.rodar({'hook_event_name': 'PermissionRequest', 'tool_name': 'Bash',
                                      'tool_input': {'command': 'rm -rf x'}}))

    def test_permissao_sempre(self):
        o = self.rodar({'hook_event_name': 'PermissionRequest', 'tool_name': 'Bash', 'tool_input': {'command': 'make'}},
                       {'decisao': 'sempre'})
        d = o['hookSpecificOutput']['decision']
        self.assertEqual(d['behavior'], 'allow')
        self.assertEqual(d['updatedPermissions'][0]['rules'], [{'toolName': 'Bash', 'ruleContent': 'make'}])

    def test_recusar(self):
        o = self.rodar({'hook_event_name': 'PermissionRequest', 'tool_name': 'Bash', 'tool_input': {'command': 'make'}},
                       {'decisao': 'recusar', 'motivo': 'agora nao'})
        self.assertEqual(o['hookSpecificOutput']['decision'], {'behavior': 'deny', 'message': 'agora nao'})

    def test_plano_setmode_auto(self):
        o = self.rodar({'hook_event_name': 'PermissionRequest', 'tool_name': 'ExitPlanMode', 'tool_input': {'plan': 'p'}},
                       {'decisao': 'aprovar'})
        self.assertEqual(o['hookSpecificOutput']['decision']['updatedPermissions'],
                         [{'type': 'setMode', 'mode': 'auto', 'destination': 'session'}])

    def test_pergunta_multipla(self):
        inp = {'questions': [{'question': 'Cores?', 'multiSelect': True, 'options': [{'label': 'Azul'}, {'label': 'Vermelho'}]}]}
        o = self.rodar({'hook_event_name': 'PreToolUse', 'tool_name': 'AskUserQuestion', 'tool_input': inp},
                       {'decisao': 'aprovar', 'respostas': {'Cores?': ['Azul', 'Vermelho']}})
        self.assertEqual(o['hookSpecificOutput']['updatedInput']['answers'], {'Cores?': 'Azul, Vermelho'})

    def test_timeout_vai_pro_app(self):
        self.assertIsNone(self.rodar({'hook_event_name': 'PermissionRequest', 'tool_name': 'Bash',
                                      'tool_input': {'command': 'make t'}}, espera='1'))
        self.assertTrue(any(x['estado'] == 'expirado' for x in self.p.listar_pedidos()))


if __name__ == '__main__':
    unittest.main()
