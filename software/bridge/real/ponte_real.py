#!/usr/bin/env python3
"""Ponte REAL do mascote (v1). So stdlib. Substitui a ponte demo (software/bridge/ponte.py).

Rodar:  python3 ponte_real.py --porta 8791          (escuta so 127.0.0.1; nginx faz o HTTPS)
Token do aparelho: env PONTE_TOKEN ou ~/.config/mascote/ponte.env (PONTE_TOKEN=..., 0600).
Token do hook: ~/.config/mascote/hook.token (gerado se faltar), cabecalho X-Hook-Token.
Config: ~/.config/mascote/ponte.json (ver ponte.exemplo.json). Estado: ~/.local/state/mascote/.
Contrato completo da API em README.md.
"""
import argparse
import hmac
import json
import os
import re
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum  # noqa: E402
from comum import (ascii_tela, classificar, detalhe_ferramenta, ha_quanto, perguntas_de,  # noqa: E402
                   respostas_para_answers, resumo_curto, resumo_ferramenta, tipo_pedido)

MAX_CORPO = 64 * 1024
ESTADO_COMPAT = {'esperando': 'waiting', 'trabalhando': 'working', 'parada': 'idle',
                 'encerrada': 'done', 'desconectada': 'done'}
ESTADO_NUVEM = {'running': 'trabalhando', 'requires_action': 'esperando', 'idle': 'parada'}
MAX_SESSOES_COMPAT = 20


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def asciificar(o):
    """Aplica ascii_tela recursivamente (todo JSON servido ao aparelho)."""
    if isinstance(o, str):
        return ascii_tela(o)
    if isinstance(o, list):
        return [asciificar(x) for x in o]
    if isinstance(o, dict):
        return {k: asciificar(v) for k, v in o.items()}
    return o


class Ponte:
    def __init__(self, vps, nuvem=None, repos=None, cfg=None):
        self.vps, self.nuvem, self.repos = vps, nuvem, repos
        self.cfg = cfg or dict(comum.CONFIG_PADRAO)
        self.trava = threading.RLock()
        self.pedidos = {}          # id -> pedido
        self.servido = {}          # sessao_id -> id do pedido mostrado no ultimo /api/estado
        self.nuvem_sessoes = {}    # sid -> dict (origem nuvem ou bridge desconhecida)
        self.nuvem_detalhe = {}    # sid -> (ts, ultima_resposta, ultimo_prompt)
        self.nuvem_erro = None

    # ------------------------------------------------------------------ pedidos
    def _novo_pedido(self, **c):
        pid = uuid.uuid4().hex[:10]
        tool, inp = c.get('ferramenta', ''), c.get('tool_input') or {}
        p = {'id': pid, 'sessao_id': c['sessao_id'], 'origem': c['origem'], 'tipo': tipo_pedido(tool),
             'ferramenta': tool, 'resumo': resumo_ferramenta(tool, inp), 'detalhe': detalhe_ferramenta(tool, inp),
             'explicacao': (c.get('explicacao') or '')[-1500:], 'perguntas': perguntas_de(tool, inp),
             'perigoso': bool(c.get('perigoso')), 'so_no_app': bool(c.get('so_no_app')),
             'motivo_so_no_app': c.get('motivo_so_no_app') or '', 'criado_em': time.time(), 'estado': 'pendente',
             '_input': inp, '_req': c.get('request_id'), '_cloud_sid': c.get('cloud_sid')}
        if p['so_no_app']:
            p['estado'] = 'so_no_app'
        with self.trava:
            self.pedidos[pid] = p
        log('pedido', pid, p['origem'], p['tipo'], tool, p['estado'])
        return p

    def pedido_hook(self, d):
        s = self.vps.evento(dict(d, evento='pedido'))
        perigo = classificar(d.get('ferramenta'), d.get('tool_input'))
        so_app = bool(d.get('so_no_app') or perigo)
        return self._novo_pedido(sessao_id=s['id'], origem='vps', ferramenta=d.get('ferramenta'),
                                 tool_input=d.get('tool_input'), explicacao=d.get('explicacao'),
                                 perigoso=bool(d.get('perigoso') or perigo), so_no_app=so_app,
                                 motivo_so_no_app=d.get('motivo_so_no_app') or (f'Perigoso ({perigo})' if perigo else ''))

    def pedido_hook_ver(self, pid):
        with self.trava:
            p = self.pedidos.get(pid)
            if not p:
                return None
            return {'id': pid, 'estado': p['estado'], 'decisao': p.get('_decisao'), 'motivo': p.get('_motivo'),
                    'answers': p.get('_answers')}

    def pedido_hook_fim(self, pid, estado):
        with self.trava:
            p = self.pedidos.get(pid)
            if not p:
                return
            if p['estado'] == 'pendente' and estado in ('respondido_app', 'expirado'):
                p['estado'] = estado
            p['_finalizado'] = time.time()
            sid = p['sessao_id']
            resta = any(x['sessao_id'] == sid and x['estado'] == 'pendente' for x in self.pedidos.values())
        self.vps.pedido_terminou(sid, resta)

    def listar_pedidos(self, so_pendentes=False, sessao_id=None):
        with self.trava:
            self._limpar()
            lst = [p for p in self.pedidos.values()
                   if (not so_pendentes or p['estado'] in ('pendente', 'so_no_app'))
                   and (not sessao_id or p['sessao_id'] == sessao_id)]
            lst.sort(key=lambda p: p['criado_em'])
            return [{k: v for k, v in p.items() if not k.startswith('_')} for p in lst]

    def _limpar(self):
        """Pedidos so_no_app de VPS somem quando a sessao volta a andar; antigos saem da memoria."""
        agora = time.time()
        for pid in list(self.pedidos):
            p = self.pedidos[pid]
            if p['estado'] == 'so_no_app' and p['origem'] == 'vps':
                s = self.vps.get(p['sessao_id']) or {}
                if s.get('atualizado', 0) > p['criado_em'] + 1 and s.get('estado') in ('trabalhando', 'parada', 'encerrada'):
                    p['estado'] = 'respondido_app'
            if p['estado'] not in ('pendente', 'so_no_app') and agora - p['criado_em'] > 3600:
                del self.pedidos[pid]

    def responder(self, pid, corpo):
        """Resposta do aparelho a UM pedido. Devolve (http, obj)."""
        dec = corpo.get('decisao')
        with self.trava:
            p = self.pedidos.get(pid)
            if not p:
                return 404, {'erro': 'pedido nao existe'}
            if p['estado'] == 'so_no_app' or p['so_no_app']:
                return 403, {'erro': 'so_no_app', 'msg': 'Responda pelo app'}
            if p['estado'] != 'pendente':
                return 409, {'erro': 'ja ' + p['estado']}
            if dec not in ('aprovar', 'recusar', 'sempre'):
                return 400, {'erro': 'decisao invalida'}
            if dec == 'sempre' and p['origem'] == 'nuvem':
                return 403, {'erro': 'sempre nao disponivel na nuvem'}
            if dec == 'sempre' and p['tipo'] != 'permissao':
                return 400, {'erro': 'sempre so vale para permissao'}
            answers = None
            if p['tipo'] == 'pergunta' and dec == 'aprovar':
                try:
                    answers = respostas_para_answers(p['perguntas'], corpo.get('respostas'))
                except ValueError as e:
                    return 400, {'erro': str(e)}
            if p['origem'] == 'vps':
                p.update(estado='respondido_mascote', _decisao=dec, _answers=answers,
                         _motivo=str(corpo.get('motivo') or '')[:500], respondido_em=time.time())
                log('resposta', pid, dec)
                return 200, {'ok': True, 'id': pid, 'estado': p['estado']}
            p['estado'] = 'respondendo'
        # nuvem: fora da trava (rede)
        ok, msg = False, 'desligado'
        if self.cfg.get('nuvem_responder') and self.nuvem:
            try:
                ok, msg = self.nuvem.responder(p['_cloud_sid'], p['_req'], dec != 'recusar', answers, corpo.get('motivo'))
            except Exception as e:  # noqa: BLE001
                ok, msg = False, type(e).__name__
        with self.trava:
            if ok:
                p.update(estado='respondido_mascote', _decisao=dec, respondido_em=time.time())
            elif msg == 'ja respondido':
                p['estado'] = 'respondido_app'
                return 409, {'erro': 'ja respondido_app'}
            else:
                p.update(estado='so_no_app', so_no_app=True, motivo_so_no_app='Falha na nuvem (%s): responda pelo app' % msg)
                log('nuvem responder falhou', pid, msg)
                return 502, {'erro': 'falha nuvem', 'msg': 'Responda pelo app'}
        if p['tipo'] == 'plano' and dec == 'aprovar':
            try:
                self.nuvem.modo(p['_cloud_sid'], 'auto')
            except Exception:  # noqa: BLE001
                pass
        log('resposta nuvem', pid, dec)
        return 200, {'ok': True, 'id': pid, 'estado': 'respondido_mascote'}

    # ------------------------------------------------------------------ sessoes
    def _pend_por_sessao(self):
        d = {}
        for p in self.pedidos.values():
            if p['estado'] in ('pendente', 'so_no_app'):
                d.setdefault(p['sessao_id'], []).append(p)
        return d

    def sessoes(self):
        with self.trava:
            self._limpar()
            pend = self._pend_por_sessao()
            res = []
            for s in self.vps.listar():
                res.append(self._fmt_sessao(s, 'vps', pend.get(s['id'], [])))
            for s in self.nuvem_sessoes.values():
                res.append(self._fmt_sessao(s, s['origem'], pend.get(s['id'], [])))
        res.sort(key=lambda x: (x['estado'] != 'esperando', -x['atualizado_em']))
        return res

    def _fmt_sessao(self, s, origem, pend):
        estado = s.get('estado') or 'parada'
        if pend and estado not in ('encerrada',):
            estado = 'esperando'
        elif estado == 'esperando' and not pend and origem == 'vps':
            estado = 'trabalhando'
        resp = s.get('ultima_resposta') or ''
        return {'id': s['id'], 'origem': origem, 'titulo': s.get('titulo') or '', 'repo': s.get('repo') or None,
                'branch': s.get('branch') or None, 'estado': estado, 'pedidos_pendentes': len(pend),
                'atualizado_em': s.get('atualizado') or 0, 'ha_quanto': ha_quanto(time.time() - (s.get('atualizado') or 0)),
                'ultima_resposta_resumo': resumo_curto(resp, 160), 'somente_leitura': bool(s.get('somente_leitura'))}

    def sessao(self, sid):
        lst = {s['id']: s for s in self.sessoes()}
        if sid not in lst:
            return None
        base = lst[sid]
        if sid.startswith('session_'):
            resp, prompt = self._detalhe_nuvem(sid)
        else:
            s = self.vps.get(sid) or {}
            resp, prompt = s.get('ultima_resposta') or '', s.get('ultimo_prompt') or ''
        base.update(ultima_resposta=(resp or '')[:4000], ultimo_prompt=(prompt or '')[:1000],
                    pedidos=self.listar_pedidos(True, sid))
        return base

    def _detalhe_nuvem(self, sid):
        c = self.nuvem_detalhe.get(sid)
        if c and time.time() - c[0] < 10:
            return c[1], c[2]
        try:
            ev = self.nuvem.eventos(sid)
            c = (time.time(), self.nuvem.ultima_resposta(ev), self.nuvem.ultimo_prompt(ev))
            self.nuvem_detalhe[sid] = c
            with self.trava:
                if sid in self.nuvem_sessoes:
                    self.nuvem_sessoes[sid]['ultima_resposta'] = c[1]
            return c[1], c[2]
        except Exception:  # noqa: BLE001
            return (c[1], c[2]) if c else ('', '')

    # ------------------------------------------------------------------ nuvem
    def atualizar_nuvem(self):
        if not (self.nuvem and self.cfg.get('nuvem_ativa', True)):
            return
        lista = self.nuvem.listar()
        vps = self.vps.listar()
        titulos = {s.get('titulo') for s in vps if s.get('titulo')}
        repobr = {(s.get('repo'), s.get('branch')) for s in vps if s.get('repo')}
        novas = {}
        for n in lista:
            if n['tipo'] == 'bridge':
                # DEDUPE: sessao VPS conhecida pela ponte (hooks/tmux) tem prioridade
                if n['titulo'] in titulos or (n['repo'] and (n['repo'], n['branch']) in repobr):
                    continue
                if self.cfg.get('bridge_desconhecida', 'listar') == 'omitir':
                    continue
                origem, ro = 'vps', True
            else:
                origem, ro = 'nuvem', False
            antigo = self.nuvem_sessoes.get(n['sid'], {})
            novas[n['sid']] = {'id': n['sid'], 'origem': origem, 'somente_leitura': ro, 'titulo': n['titulo'],
                               'repo': n['repo'], 'branch': n['branch'],
                               'estado': ESTADO_NUVEM.get(n['status'], 'parada'), 'atualizado': n['atualizado'],
                               'ultima_resposta': antigo.get('ultima_resposta', ''), '_status': n['status']}
        with self.trava:
            self.nuvem_sessoes = novas
        # pedidos: so sessoes da nuvem (nao bridge) com requires_action
        vivos = set()
        for sid, s in novas.items():
            if s['somente_leitura'] or s['_status'] != 'requires_action':
                continue
            ev = self.nuvem.eventos(sid)
            for e in self.nuvem.pendentes(ev):
                vivos.add(e['request_id'])
                self._pedido_nuvem(sid, e, ev)
        with self.trava:
            for p in self.pedidos.values():
                if p['origem'] == 'nuvem' and p['estado'] in ('pendente', 'so_no_app') and p['_req'] not in vivos:
                    p['estado'] = 'respondido_app'

    def _pedido_nuvem(self, sid, e, ev):
        with self.trava:
            if any(p['_req'] == e['request_id'] for p in self.pedidos.values()):
                return
        r = e.get('request') or {}
        tool, inp = r.get('tool_name', ''), r.get('input') or {}
        perigo = classificar(tool, inp)
        desligado = not self.cfg.get('nuvem_responder', True)
        self._novo_pedido(sessao_id=sid, origem='nuvem', ferramenta=tool, tool_input=inp,
                          explicacao=self.nuvem.ultima_resposta(ev), perigoso=bool(perigo),
                          so_no_app=bool(perigo or desligado),
                          motivo_so_no_app=(f'Perigoso ({perigo})' if perigo else
                                            'Resposta pela nuvem desligada: responda pelo app' if desligado else ''),
                          request_id=e['request_id'], cloud_sid=sid)

    def laco_nuvem(self):
        while True:
            try:
                self.atualizar_nuvem()
                self.nuvem_erro = None
            except Exception as e:  # noqa: BLE001
                if self.nuvem_erro != str(e):
                    log('nuvem: erro', type(e).__name__, str(e)[:200])
                self.nuvem_erro = str(e)
            time.sleep(float(self.cfg.get('nuvem_intervalo', 10)))

    # ------------------------------------------------------------------ compat firmware atual
    def estado_compat(self):
        out = []
        with self.trava:
            pend = self._pend_por_sessao()
        for s in self.sessoes()[:MAX_SESSOES_COMPAT]:
            lst = sorted(pend.get(s['id'], []), key=lambda p: (p['estado'] != 'pendente', p['criado_em']))
            ask = None
            with self.trava:
                if lst:
                    p = lst[0]
                    self.servido[s['id']] = p['id']
                    if p['estado'] == 'so_no_app':
                        txt = 'APROVE PELO APP: ' + p['resumo']
                    elif p['tipo'] == 'pergunta':
                        txt = ' / '.join(q['pergunta'] + ' [' + ', '.join(o['rotulo'] for o in q['opcoes']) + ']'
                                         for q in p['perguntas']) + ' (responda pelo app)'
                    else:
                        txt = p['resumo']
                    ask = {'tool': p['ferramenta'], 'text': resumo_curto(txt, 300)}
                else:
                    self.servido.pop(s['id'], None)
            det = self.vps.get(s['id']) if s['origem'] == 'vps' else None
            reply = (det or {}).get('ultima_resposta') or (self.nuvem_sessoes.get(s['id']) or {}).get('ultima_resposta') or ''
            last = s['ultima_resposta_resumo']
            if ask:
                last = 'Pede: ' + ask['text'][:150]
            elif s['estado'] == 'trabalhando' and det and det.get('ultimo_prompt'):
                last = 'Trabalhando: ' + resumo_curto(det['ultimo_prompt'], 140)
            titulo = s['titulo'] + (' (nuvem)' if s['origem'] == 'nuvem' else '')
            out.append({'id': s['id'], 'title': titulo, 'repo': s['repo'], 'branch': s['branch'],
                        'status': ESTADO_COMPAT.get(s['estado'], 'idle'), 'ago': s['ha_quanto'],
                        'last': last, 'reply': resumo_curto(reply, 1500), 'ask': ask})
        return {'hora': time.strftime('%H:%M'), 'sessoes': out}

    def acao_compat(self, sid, acao):
        if acao not in ('aprovar', 'recusar'):
            return 400, {'ok': False, 'msg': 'acao desconhecida'}
        with self.trava:
            pid = self.servido.get(sid)
            p = self.pedidos.get(pid) if pid else None
            if not p:
                return 409, {'ok': False, 'msg': 'a sessao nao esta pedindo nada'}
            if p['tipo'] == 'pergunta':
                return 409, {'ok': False, 'msg': 'pergunta: responda pelo app'}
        code, obj = self.responder(pid, {'decisao': acao})
        return code, {'ok': code == 200, 'msg': obj.get('erro') or obj.get('msg') or 'ok', 'pedido': pid}

    # ------------------------------------------------------------------ criar / mensagem
    def criar_sessao(self, c):
        origem = c.get('origem')
        titulo = (c.get('titulo') or '').strip()
        repo, branch, nova = c.get('repo') or None, c.get('branch') or None, c.get('nova_branch') or None
        if not titulo:
            return 400, {'erro': 'titulo obrigatorio'}
        for v in (repo, branch, nova):
            if v and not re.fullmatch(r'[A-Za-z0-9._/-]{1,120}', v):
                return 400, {'erro': 'nome invalido'}
        if repo and not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
            return 400, {'erro': 'repo deve ser dono/nome'}
        if nova and not branch:
            return 400, {'erro': 'nova_branch exige branch base'}
        if origem == 'vps':
            try:
                sid = self.vps.criar(repo, branch, nova, titulo, c.get('prompt'))
            except Exception as e:  # noqa: BLE001
                log('criar vps falhou', type(e).__name__, str(e)[:300])
                return 500, {'erro': 'falha ao criar', 'msg': ascii_tela(str(e))[:200]}
            return 202, {'id': sid}
        if origem == 'nuvem':
            if not c.get('prompt') or not repo:
                return 400, {'erro': 'nuvem exige repo e prompt'}
            try:
                import nuvem_criar
                pasta = self.repos.garantir_clone(repo)
                sid = nuvem_criar.criar(pasta, branch, c['prompt'])
            except Exception as e:  # noqa: BLE001
                return 500, {'erro': 'falha ao criar na nuvem', 'msg': ascii_tela(str(e))[:200]}
            return 202, {'id': sid}
        return 400, {'erro': 'origem deve ser vps ou nuvem'}

    def mensagem(self, sid, texto):
        texto = (texto or '').strip()
        if not texto or len(texto) > 8000:
            return 400, {'erro': 'texto vazio ou longo'}
        s = next((x for x in self.sessoes() if x['id'] == sid), None)
        if not s:
            return 404, {'erro': 'sessao nao existe'}
        if s.get('somente_leitura'):
            return 403, {'erro': 'sessao somente leitura'}
        if s['estado'] in ('esperando', 'trabalhando'):
            return 409, {'erro': 'sessao ' + s['estado']}
        if s['origem'] == 'nuvem':
            threading.Thread(target=self._msg_nuvem, args=(sid, texto), daemon=True).start()
            return 202, {'ok': True, 'via': 'claude -p --cloud'}
        if s['estado'] == 'encerrada':
            return 409, {'erro': 'sessao encerrada'}
        try:
            ok = self.vps.mensagem(sid, texto)
        except LookupError as e:
            return 409, {'erro': str(e)}
        if not ok:
            return 504, {'erro': 'sem confirmacao (UserPromptSubmit) em 10 s', 'experimental': True}
        return 202, {'ok': True, 'via': 'tmux send-keys (experimental)'}

    def _msg_nuvem(self, sid, texto):
        try:
            ok, msg = self.nuvem.mensagem(sid, texto)
            log('mensagem nuvem', sid[-6:], 'ok' if ok else 'falhou')
        except Exception as e:  # noqa: BLE001
            log('mensagem nuvem erro', type(e).__name__)


# ====================================================================== HTTP
def criar_handler(ponte, token_aparelho, token_hook):
    class H(BaseHTTPRequestHandler):
        server_version = 'PonteMascote/1'

        def log_message(self, fmt, *a):
            if os.environ.get('PONTE_LOG'):
                super().log_message(fmt, *a)

        def _json(self, code, obj, aparelho=True):
            b = json.dumps(asciificar(obj) if aparelho else obj, ensure_ascii=True).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _ok_token(self, cab, esperado):
            rec = self.headers.get(cab, '')
            if esperado and hmac.compare_digest(rec.encode(), esperado.encode()):
                return True
            self._json(401, {'erro': 'token invalido'})
            return False

        def _corpo(self):
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_CORPO:
                self._json(413, {'erro': 'corpo grande'})
                return None
            try:
                d = json.loads(self.rfile.read(n) or b'{}')
                if not isinstance(d, dict):
                    raise ValueError
                return d
            except ValueError:
                self._json(400, {'erro': 'json invalido'})
                return None

        def _rota(self, metodo):
            path, _, qs = self.path.partition('?')
            path = path.rstrip('/') or '/'
            if path == '/saude':
                b = b'ok'
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Content-Length', '2')
                self.end_headers()
                return self.wfile.write(b)
            partes = path.strip('/').split('/')
            if partes[0] == 'interno':
                if not self._ok_token('X-Hook-Token', token_hook):
                    return
                return self._interno(metodo, partes[1:])
            if partes[0] != 'api':
                return self._json(404, {'erro': 'nao existe'})
            if not self._ok_token('X-Token', token_aparelho):
                return
            return self._api(metodo, partes[1:], qs)

        def _interno(self, metodo, p):
            if metodo == 'POST':
                d = self._corpo()
                if d is None:
                    return
                if p == ['eventos']:
                    ponte.vps.evento(d)
                    return self._json(200, {'ok': True}, False)
                if p == ['pedidos']:
                    return self._json(200, {'id': ponte.pedido_hook(d)['id']}, False)
                if len(p) == 3 and p[0] == 'pedidos' and p[2] == 'fim':
                    ponte.pedido_hook_fim(p[1], d.get('estado'))
                    return self._json(200, {'ok': True}, False)
            if metodo == 'GET' and len(p) == 2 and p[0] == 'pedidos':
                r = ponte.pedido_hook_ver(p[1])
                return self._json(200 if r else 404, r or {'erro': 'nao existe'}, False)
            return self._json(404, {'erro': 'nao existe'})

        def _api(self, metodo, p, qs):
            if metodo == 'GET':
                if p == ['estado']:
                    return self._json(200, ponte.estado_compat())
                if p == ['sessoes']:
                    return self._json(200, ponte.sessoes())
                if len(p) == 2 and p[0] == 'sessoes':
                    s = ponte.sessao(p[1])
                    return self._json(200 if s else 404, s or {'erro': 'sessao nao existe'})
                if p == ['pedidos']:
                    return self._json(200, ponte.listar_pedidos('pendentes=1' in qs))
                if p == ['repos']:
                    return self._json(200, ponte.repos.listar())
                if len(p) == 4 and p[0] == 'repos' and p[3] == 'branches':
                    if not all(re.fullmatch(r'[\w.-]+', x) for x in p[1:3]):
                        return self._json(400, {'erro': 'nome invalido'})
                    return self._json(200, ponte.repos.branches(p[1] + '/' + p[2]))
                return self._json(404, {'erro': 'nao existe'})
            d = self._corpo()
            if d is None:
                return
            if p == ['acao']:
                code, obj = ponte.acao_compat(str(d.get('id', '')), str(d.get('acao', '')))
                log('acao compat', d.get('acao'), d.get('id'), code)
                return self._json(code, obj)
            if len(p) == 3 and p[0] == 'pedidos' and p[2] == 'resposta':
                return self._json(*ponte.responder(p[1], d))
            if p == ['sessoes']:
                return self._json(*ponte.criar_sessao(d))
            if len(p) == 3 and p[0] == 'sessoes' and p[2] == 'mensagem':
                return self._json(*ponte.mensagem(p[1], d.get('texto')))
            return self._json(404, {'erro': 'nao existe'})

        def do_GET(self):
            self._seguro('GET')

        def do_POST(self):
            self._seguro('POST')

        def _seguro(self, m):
            try:
                self._rota(m)
            except Exception as e:  # noqa: BLE001
                log('erro na rota', self.path.split('?')[0], type(e).__name__, str(e)[:200])
                if os.environ.get('PONTE_DEBUG'):
                    traceback.print_exc()
                try:
                    self._json(500, {'erro': 'interno'})
                except Exception:  # noqa: BLE001
                    pass
    return H


def main():
    ap = argparse.ArgumentParser(description='Ponte real do mascote (v1)')
    ap.add_argument('--porta', type=int, default=8787)
    ap.add_argument('--config', default=None)
    a = ap.parse_args()
    token = comum.token_aparelho()
    if len(token) < 12:
        raise SystemExit('Falta PONTE_TOKEN (>=12 caracteres) no ambiente ou em ~/.config/mascote/ponte.env')
    th = comum.token_hook(gerar=True)
    cfg = comum.ler_config(a.config)
    from fonte_nuvem import Nuvem
    from fonte_vps import FonteVPS
    from repos import Repos
    repos = Repos()
    ponte = Ponte(FonteVPS(repos=repos), Nuvem(dias=cfg.get('nuvem_dias', 7)), repos, cfg)
    if cfg.get('nuvem_ativa', True):
        threading.Thread(target=ponte.laco_nuvem, daemon=True).start()
    srv = ThreadingHTTPServer(('127.0.0.1', a.porta), criar_handler(ponte, token, th))
    srv.daemon_threads = True
    log(f'Ponte real v1 em 127.0.0.1:{a.porta} (nuvem_ativa={cfg.get("nuvem_ativa")}, '
        f'nuvem_responder={cfg.get("nuvem_responder")})')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
