"""Fonte NUVEM (claude.ai/code) da ponte real. EXPERIMENTAL, API interna NAO documentada.

Reaproveita cli/nuvem_nd.py: OAuth da CLI lido em runtime de ~/.claude/.credentials.json e org de
~/.claude.json (nunca impressos nem gravados). Pode quebrar sem aviso.

- listar(): /v1/sessions (nao arquivadas, atualizadas nos ultimos N dias).
- eventos(sid): TODAS as paginas (has_more / last_id -> after_id).
- pendentes(eventos): control_request can_use_tool sem control_response / control_cancel_request.
- responder(...): POST /v1/code/sessions/<cse_id>/events com control_response.
- modo(sid, 'auto'): control_request set_permission_mode.
- mensagem(sid, texto): `claude -p TEXTO --cloud <sid> --output-format json` (documentado).
O transporte HTTP e injetavel (testes usam fake, sem rede).
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime

from comum import env_limpo

BASE = 'https://api.anthropic.com'


def _cabecalhos():
    cred = json.load(open(os.path.expanduser('~/.claude/.credentials.json')))['claudeAiOauth']['accessToken']
    org = json.load(open(os.path.expanduser('~/.claude.json')))['oauthAccount']['organizationUuid']
    return {'Authorization': 'Bearer ' + cred, 'anthropic-beta': 'ccr-byoc-2025-07-29',
            'anthropic-version': '2023-06-01', 'x-organization-uuid': org, 'Content-Type': 'application/json'}


def http_real(metodo, path, corpo=None):
    """Devolve (status, json|texto). Le o token a cada chamada (renovado pela CLI)."""
    r = urllib.request.Request(BASE + path, data=json.dumps(corpo).encode() if corpo is not None else None,
                               headers=_cabecalhos(), method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=30) as f:
            return f.status, json.loads(f.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode('utf-8', 'replace')


def _ts(s):
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except ValueError:
        return 0.0


class Nuvem:
    def __init__(self, http=None, dias=7):
        self.http = http or http_real
        self.dias = dias

    def listar(self):
        out, cur = [], None
        for _ in range(10):
            st, b = self.http('GET', '/v1/sessions?limit=100' + (f'&after_id={cur}' if cur else ''))
            if st != 200 or not isinstance(b, dict):
                raise IOError(f'listar nuvem: HTTP {st}')
            out += b.get('data', [])
            cur = b.get('last_id')
            if not b.get('has_more') or not cur:
                break
        limite = time.time() - self.dias * 86400
        res = []
        for s in out:
            if s.get('session_status') == 'archived' or s.get('archived') or s.get('status_bucket') == 'archived':
                continue
            upd = _ts(s.get('updated_at'))
            if upd and upd < limite:
                continue
            fontes = ((s.get('session_context') or {}).get('sources') or [])
            url = next((f.get('url') for f in fontes if f.get('url')), '') or ''
            repo = url.split('github.com/')[-1].removesuffix('.git') if 'github.com' in url else ''
            branch = next((f.get('revision') for f in fontes if f.get('revision')), '') or ''
            branch = branch.removeprefix('refs/heads/')
            res.append({'sid': s.get('id'), 'titulo': s.get('title') or '', 'tipo': s.get('environment_kind'),
                        'status': s.get('session_status') or '', 'bucket': s.get('status_bucket') or '',
                        'repo': repo, 'branch': branch, 'atualizado': upd or time.time()})
        return res

    def eventos(self, sid):
        ev, cur = [], None
        for _ in range(200):
            st, b = self.http('GET', f'/v1/sessions/{sid}/events' + (f'?after_id={cur}' if cur else ''))
            if st != 200 or not isinstance(b, dict):
                raise IOError(f'eventos nuvem: HTTP {st}')
            ev += b.get('data', [])
            cur = b.get('last_id')
            if not b.get('has_more') or not cur:
                return ev
        return ev

    @staticmethod
    def pendentes(ev):
        feitos = {(e.get('response') or {}).get('request_id') for e in ev if e.get('type') == 'control_response'}
        feitos |= {e.get('request_id') for e in ev if e.get('type') == 'control_cancel_request'}
        return [e for e in ev if e.get('type') == 'control_request'
                and (e.get('request') or {}).get('subtype') == 'can_use_tool' and e.get('request_id') not in feitos]

    @staticmethod
    def ultima_resposta(ev):
        for e in reversed(ev):
            if e.get('type') == 'assistant':
                txt = [c.get('text', '') for c in (e.get('message') or {}).get('content') or []
                       if isinstance(c, dict) and c.get('type') == 'text']
                if any(t.strip() for t in txt):
                    return '\n'.join(txt)
        return ''

    @staticmethod
    def ultimo_prompt(ev):
        for e in reversed(ev):
            if e.get('type') == 'user':
                c = (e.get('message') or {}).get('content')
                if isinstance(c, str) and c.strip():
                    return c
                if isinstance(c, list):
                    t = [x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text']
                    if any(s.strip() for s in t):
                        return '\n'.join(t)
        return ''

    def _post(self, sid, payload):
        payload.setdefault('uuid', str(uuid.uuid4()))
        return self.http('POST', f"/v1/code/sessions/{sid.replace('session_', 'cse_')}/events",
                         {'events': [{'payload': payload}]})

    def responder(self, sid, request_id, aprovar, answers=None, motivo=None):
        """Responde UM pedido pelo request_id exato, se ainda pendente. Devolve (ok, msg)."""
        alvo = [e for e in self.pendentes(self.eventos(sid)) if e.get('request_id') == request_id]
        if not alvo:
            return False, 'ja respondido'
        r = alvo[0]['request']
        if aprovar:
            inp = dict(r.get('input') or {})
            if answers:
                inp['answers'] = answers
            resp = {'behavior': 'allow', 'toolUseID': r.get('tool_use_id'), 'tool_name': r.get('tool_name'),
                    'updatedInput': inp}
        else:
            resp = {'behavior': 'deny', 'toolUseID': r.get('tool_use_id'), 'tool_name': r.get('tool_name'),
                    'message': motivo or 'Recusado no mascote'}
        st, b = self._post(sid, {'type': 'control_response',
                                 'response': {'subtype': 'success', 'request_id': request_id, 'response': resp}})
        return (200 <= st < 300), f'HTTP {st}'

    def modo(self, sid, modo='auto'):
        st, _ = self._post(sid, {'type': 'control_request', 'request_id': 'mascote-mode-' + uuid.uuid4().hex[:8],
                                 'request': {'subtype': 'set_permission_mode', 'mode': modo}})
        return 200 <= st < 300

    @staticmethod
    def mensagem(sid, texto, timeout=150):
        p = subprocess.run(['claude', '-p', texto, '--cloud', sid, '--output-format', 'json'],
                           capture_output=True, text=True, timeout=timeout, env=env_limpo(),
                           cwd=os.path.expanduser('~'))
        return p.returncode == 0, (p.stdout or p.stderr)[-300:]
