#!/usr/bin/env python3
"""Adaptador NAO DOCUMENTADO para sessoes da NUVEM (claude.ai/code), experimental e desligavel.
Usa a API interna do Claude Code com o OAuth da CLI (~/.claude/.credentials.json); pode quebrar sem aviso.
Testado em 2026-10-11 com CLI 2.1.287 (resultados em README.md).
  nd_cloud.py modo <sid> <modo>                 -> control_request set_permission_mode
  nd_cloud.py pendentes <sid>                   -> lista can_use_tool sem resposta
  nd_cloud.py responder <sid> <request_id> allow|deny|sempre [motivo | json {"answers":{...}}]
  ('sempre' NAO comprovado na nuvem: nao oferecer no mascote)
Nunca imprime token/org. Sem assinatura de dispositivo."""
import json, os, sys, uuid, urllib.request, urllib.error
tok = json.load(open(os.path.expanduser('~/.claude/.credentials.json')))['claudeAiOauth']['accessToken']
org = json.load(open(os.path.expanduser('~/.claude.json')))['oauthAccount']['organizationUuid']
H = {'Authorization': 'Bearer ' + tok, 'anthropic-beta': 'ccr-byoc-2025-07-29', 'anthropic-version': '2023-06-01',
     'x-organization-uuid': org, 'Content-Type': 'application/json'}
BASE = 'https://api.anthropic.com'

def call(method, path, body=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=H, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as f: return f.status, json.loads(f.read() or b'{}')
    except urllib.error.HTTPError as e: return e.code, e.read()[:400].decode()

def eventos(sid):
    ev, cur = [], None
    while True:
        s, b = call('GET', f'/v1/sessions/{sid}/events' + (f'?after_id={cur}' if cur else ''))
        ev += b.get('data', []); cur = b.get('last_id')
        if not b.get('has_more'): return ev

def pendentes(sid):
    ev = eventos(sid)
    feitos = {e['response'].get('request_id') for e in ev if e.get('type') == 'control_response'}
    feitos |= {e.get('request_id') for e in ev if e.get('type') == 'control_cancel_request'}
    return [e for e in ev if e.get('type') == 'control_request' and e['request'].get('subtype') == 'can_use_tool'
            and e['request_id'] not in feitos]

def post_evento(sid, payload):
    payload.setdefault('uuid', str(uuid.uuid4()))
    return call('POST', f"/v1/code/sessions/{sid.replace('session_', 'cse_')}/events", {"events": [{"payload": payload}]})

cmd, sid = sys.argv[1], sys.argv[2]
if cmd == 'modo':
    print(post_evento(sid, {"type": "control_request", "request_id": "mascote-mode-" + uuid.uuid4().hex[:8],
                            "request": {"subtype": "set_permission_mode", "mode": sys.argv[3]}}))
elif cmd == 'pendentes':
    for e in pendentes(sid):
        r = e['request']; print(json.dumps({"request_id": e['request_id'], "tool": r.get('tool_name'),
                                            "tool_use_id": r.get('tool_use_id'), "input": r.get('input')}, ensure_ascii=False)[:400])
elif cmd == 'responder':
    rid, dec = sys.argv[3], sys.argv[4]
    alvo = [e for e in pendentes(sid) if e['request_id'] == rid]
    if not alvo: sys.exit('pedido nao esta pendente (ja respondido?)')
    r = alvo[0]['request']
    extra = json.loads(sys.argv[5]) if dec in ('allow', 'sempre') and len(sys.argv) > 5 else {}
    if dec in ('allow', 'sempre'):
        resp = {"behavior": "allow", "toolUseID": r['tool_use_id'], "tool_name": r['tool_name'],
                "updatedInput": dict(r.get('input', {}), **({"answers": extra["answers"]} if "answers" in extra else {}))}
        if dec == 'sempre':
            regra = {"toolName": r['tool_name']}
            if r['tool_name'] == 'Bash': regra["ruleContent"] = r['input'].get('command', '')
            resp["updatedPermissions"] = [{"type": "addRules", "rules": [regra], "behavior": "allow", "destination": "session"}]
    else:
        resp = {"behavior": "deny", "toolUseID": r['tool_use_id'], "tool_name": r['tool_name'],
                "message": sys.argv[5] if len(sys.argv) > 5 else "Recusado no mascote"}
    print(post_evento(sid, {"type": "control_response", "response": {"subtype": "success", "request_id": rid, "response": resp}}))
