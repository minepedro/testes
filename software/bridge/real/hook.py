#!/usr/bin/env python3
"""Hook do Claude Code -> ponte real do mascote. So stdlib. Substitui cli/mascote_hook.py.

settings.json: "command": "python3 /home/hermes/testes/software/bridge/real/hook.py"
Ponte: env MASCOTE_PONTE (padrao http://127.0.0.1:8787). Token interno: ~/.config/mascote/hook.token,
enviado em X-Hook-Token. Sem token ou ponte fora do ar (2 s) -> exit 0 sem saida (fluxo normal).

Eventos:
  PreToolUse        perigoso (Bash/Write/Edit) -> "ask" na hora + registra pedido so_no_app.
                    AskUserQuestion -> espera a ponte (updatedInput.answers).
                    ExitPlanMode -> espera a ponte (padrao MASCOTE_PLANO_VIA=pre; testado real).
  PermissionRequest espera a ponte: aprovar->allow; sempre->allow + addRules(comando exato, session);
                    recusar->deny; plano aprovado -> allow + setMode auto (session).
                    Sem resposta em 300 s -> sem saida (dialogo normal / app).
  Aparelho offline (ponte: dispositivo_online=False ao registrar ou no polling) -> nao espera:
                    sai sem decisao (dialogo normal no terminal/app); pedido vira 'no_app'.
  SessionStart, UserPromptSubmit, Notification, Stop, SessionEnd, PostToolUse -> /interno/eventos.
Guarda: so age com cwd sob ~/repos/ ou ~/mascote-cli-lab/.
Resposta pelo app enquanto espera: detectada por tool_result no transcript (resolvido_fora).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import DIR_CONFIG, DIRS_PERMITIDOS, classificar, ler_env_arquivo, token_hook  # noqa: E402

# URL: env MASCOTE_PONTE; senao a porta da unit --user (~/.config/mascote/unit.env PORTA=); senao 8787
_porta = ler_env_arquivo(os.path.join(DIR_CONFIG, 'unit.env')).get('PORTA') or '8787'
PONTE = os.environ.get('MASCOTE_PONTE', 'http://127.0.0.1:' + _porta).rstrip('/')
ESPERA = float(os.environ.get('MASCOTE_ESPERA', '300'))
PLANO_VIA = os.environ.get('MASCOTE_PLANO_VIA', 'pre')  # 'perm' (PermissionRequest+setMode) ou 'pre'
TOKEN = None


def req(metodo, path, corpo=None, timeout=2.0):
    data = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(PONTE + path, data=data, method=metodo,
                               headers={'Content-Type': 'application/json', 'X-Hook-Token': TOKEN or ''})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b'{}')


def git_info(cwd):
    def g(*a):
        try:
            return subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True, timeout=2).stdout.strip()
        except Exception:
            return ''
    url = g('config', '--get', 'remote.origin.url')
    repo = ''
    if url:
        repo = url.rsplit('github.com', 1)[-1].lstrip(':/')
        repo = repo[:-4] if repo.endswith('.git') else repo
    return repo or os.path.basename(g('rev-parse', '--show-toplevel')), g('branch', '--show-current')


def _linhas(transcript_path, limite):
    try:
        with open(transcript_path, 'rb') as f:
            f.seek(0, 2)
            tam = f.tell()
            f.seek(max(0, tam - limite))
            return f.read().decode('utf-8', 'ignore').splitlines()
    except (OSError, TypeError):
        return []


def ultimo_texto_assistente(transcript_path, n=1500):
    for linha in reversed(_linhas(transcript_path, 400000)):
        try:
            o = json.loads(linha)
        except ValueError:
            continue
        if o.get('type') == 'assistant':
            txt = [c.get('text', '') for c in (o.get('message') or {}).get('content') or []
                   if isinstance(c, dict) and c.get('type') == 'text']
            if any(t.strip() for t in txt):
                return '\n'.join(txt)[-n:]
    return ''


def resolvido_fora(transcript_path, tool, inp, tool_use_id=None):
    """True se ja existe tool_result para o tool_use deste pedido (app/terminal respondeu)."""
    alvo, resultados = tool_use_id, set()
    for linha in _linhas(transcript_path, 600000):
        try:
            o = json.loads(linha)
        except ValueError:
            continue
        for c in (o.get('message') or {}).get('content') or []:
            if not isinstance(c, dict):
                continue
            if c.get('type') == 'tool_use' and not tool_use_id and c.get('name') == tool and c.get('input') == inp:
                alvo = c.get('id')
            elif c.get('type') == 'tool_result':
                resultados.add(c.get('tool_use_id'))
    return bool(alvo) and alvo in resultados


def out(obj):
    sys.stdout.write(json.dumps(obj))
    sys.exit(0)


def fim(pid, estado):
    try:
        req('POST', f'/interno/pedidos/{pid}/fim', {'estado': estado})
    except Exception:
        pass


def esperar(pid, d, online=True):
    """None = fluxo normal. Aparelho offline (ao registrar ou no meio) -> libera na hora ('no_app')."""
    if not online:
        fim(pid, 'no_app')
        return None
    limite = time.time() + ESPERA
    while time.time() < limite:
        if resolvido_fora(d.get('transcript_path'), d.get('tool_name'), d.get('tool_input') or {}, d.get('tool_use_id')):
            fim(pid, 'respondido_app')
            return None
        try:
            p = req('GET', '/interno/pedidos/' + pid)
        except Exception:
            return None  # ponte caiu: fluxo normal
        if p.get('dispositivo_online') is False and p.get('estado') == 'pendente':
            fim(pid, 'no_app')
            return None
        if p.get('estado') == 'respondido_mascote':
            fim(pid, 'usado')
            return p
        if p.get('estado') != 'pendente':
            return None
        time.sleep(1)
    fim(pid, 'expirado')
    return None


def main():
    global TOKEN
    try:
        d = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    cwd = os.path.realpath(d.get('cwd') or os.getcwd()) + '/'
    if not cwd.startswith(DIRS_PERMITIDOS):
        sys.exit(0)
    TOKEN = token_hook()
    if not TOKEN:
        sys.exit(0)
    try:
        with urllib.request.urlopen(PONTE + '/saude', timeout=2) as f:
            f.read()
    except Exception:
        sys.exit(0)

    ev = d.get('hook_event_name')
    tool, inp = d.get('tool_name', ''), d.get('tool_input') or {}
    repo, branch = git_info(d.get('cwd') or os.getcwd())
    base = {'session_id': d.get('session_id'), 'cwd': d.get('cwd'), 'repo': repo, 'branch': branch,
            'transcript_path': d.get('transcript_path'), 'permission_mode': d.get('permission_mode'),
            'tmux': os.environ.get('TMUX_PANE', '')}

    if ev in ('SessionStart', 'UserPromptSubmit', 'Notification', 'Stop', 'SessionEnd', 'PostToolUse'):
        e = dict(base, evento=ev)
        for k in ('source', 'prompt', 'message', 'notification_type', 'last_assistant_message', 'reason', 'tool_name'):
            if d.get(k):
                e[k] = d[k]
        try:
            req('POST', '/interno/eventos', e)
        except Exception:
            pass
        sys.exit(0)

    def novo_pedido(**extra):
        """(id, dispositivo_online)"""
        r = req('POST', '/interno/pedidos', dict(base, ferramenta=tool, tool_input=inp,
                                                    tool_use_id=d.get('tool_use_id'),
                                                    explicacao=ultimo_texto_assistente(d.get('transcript_path')),
                                                    origem_hook=ev, **extra))
        return r['id'], r.get('dispositivo_online', True)

    if ev == 'PreToolUse':
        perigo = classificar(tool, inp)
        if perigo:
            try:
                novo_pedido(perigoso=True, so_no_app=True, motivo_so_no_app='Perigoso (%s)' % perigo)
            except Exception:
                pass
            out({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'ask',
                                        'permissionDecisionReason': 'Perigoso (%s): aprove pelo app' % perigo}})
        alvo = ('AskUserQuestion',) + (('ExitPlanMode',) if PLANO_VIA == 'pre' else ())
        if tool not in alvo:
            sys.exit(0)  # deixa o modo (auto) decidir; se pedir, cai no PermissionRequest
        try:
            pid, online = novo_pedido()
        except Exception:
            sys.exit(0)
        p = esperar(pid, d, online)
        if not p:
            sys.exit(0)  # fluxo normal: o dialogo aparece no terminal/app
        if p['decisao'] == 'recusar':
            out({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                        'permissionDecisionReason': p.get('motivo') or 'Recusado no mascote'}})
        novo = dict(inp, answers=p.get('answers') or {}) if tool == 'AskUserQuestion' else inp
        out({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow', 'updatedInput': novo}})

    if ev == 'PermissionRequest':
        if classificar(tool, inp) or tool == 'AskUserQuestion':
            sys.exit(0)  # perigoso: so no app (PreToolUse ja registrou); pergunta: tratada no PreToolUse
        try:
            pid, online = novo_pedido(sugestoes=d.get('permission_suggestions'))
        except Exception:
            sys.exit(0)
        p = esperar(pid, d, online)
        if not p:
            sys.exit(0)
        if p['decisao'] == 'recusar':
            out({'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': {
                'behavior': 'deny', 'message': p.get('motivo') or 'Recusado no mascote'}}})
        dec = {'behavior': 'allow'}
        if tool == 'ExitPlanMode':
            # volta ao modo automatico (padrao do Pedro) depois do plano aprovado
            dec['updatedPermissions'] = [{'type': 'setMode', 'mode': os.environ.get('MASCOTE_MODO_POS_PLANO', 'auto'),
                                          'destination': 'session'}]
        elif p['decisao'] == 'sempre':
            regra = {'toolName': tool}
            if tool == 'Bash':
                regra['ruleContent'] = inp.get('command', '')
            elif inp.get('file_path'):
                regra['ruleContent'] = inp['file_path']
            dec['updatedPermissions'] = [{'type': 'addRules', 'rules': [regra], 'behavior': 'allow',
                                          'destination': 'session'}] + \
                [s for s in (d.get('permission_suggestions') or []) if s.get('type') == 'addDirectories']
        out({'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': dec}})
    sys.exit(0)


if __name__ == '__main__':
    main()
