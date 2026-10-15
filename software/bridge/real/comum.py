"""Funcoes comuns da ponte real do mascote (so stdlib).

- ascii_tela / corta: textos que vao para a tela (fonte so ASCII).
- ha_quanto: "agora", "5 min", "2 h", "3 d".
- classificar: comandos perigosos (decisao 23). Mesma lista do prototipo cli/mascote_hook.py.
- caminhos e leitura de tokens/config (nunca imprime tokens).
"""
import json
import os
import re
import secrets
import time
import unicodedata

HOME = os.path.expanduser('~')
DIR_CONFIG = os.environ.get('MASCOTE_CONFIG_DIR', os.path.join(HOME, '.config', 'mascote'))
DIR_ESTADO = os.environ.get('MASCOTE_STATE_DIR', os.path.join(HOME, '.local', 'state', 'mascote'))
DIR_REPOS = os.environ.get('MASCOTE_REPOS_DIR', os.path.join(HOME, 'repos'))
DIRS_PERMITIDOS = (os.path.join(HOME, 'repos') + '/', os.path.join(HOME, 'mascote-cli-lab') + '/')

CONFIG_PADRAO = {
    'reabrir_no_inicio': True,  # no startup, reabre sessoes salvas sem tmux vivo (reabrir_sessoes.py)
    'dispositivo_timeout': 15,  # s sem /api/* do aparelho -> offline (hook nao espera)
    'nuvem_ativa': True,        # listar sessoes da nuvem (API interna)
    'nuvem_responder': True,    # EXPERIMENTAL: responder pedidos da nuvem pela API interna
    'nuvem_intervalo': 10,      # segundos entre leituras da nuvem
    'nuvem_dias': 7,            # so sessoes atualizadas nos ultimos N dias
    'bridge_desconhecida': 'listar',  # 'listar' (origem vps, somente leitura) ou 'omitir'
    'espera_hook': 300,
}


def ascii_tela(texto, n=None):
    """Tira acentos e troca simbolos que a fonte da tela nao tem (igual a ponte demo)."""
    if texto is None:
        return None
    texto = str(texto)
    for a, b in (('\u00b7', '-'), ('\u2026', '...'), ('\u2014', '-'), ('\u2013', '-'), ('\u2018', "'"),
                 ('\u2019', "'"), ('\u201c', '"'), ('\u201d', '"'), ('\u2022', '-'), ('\u2192', '->')):
        texto = texto.replace(a, b)
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    return texto[:n] if n else texto


def resumo_curto(texto, n=160):
    t = re.sub(r'\s+', ' ', ascii_tela(texto) or '').strip()
    return t if len(t) <= n else t[:n - 3].rstrip() + '...'


def ha_quanto(segundos):
    if segundos < 60:
        return 'agora'
    if segundos < 3600:
        return f'{int(segundos // 60)} min'
    if segundos < 86400:
        return f'{int(segundos // 3600)} h'
    return f'{int(segundos // 86400)} d'


def slug(texto, n=32):
    s = re.sub(r'[^a-z0-9]+', '-', (ascii_tela(texto) or '').lower()).strip('-')
    return (s[:n].strip('-') or 'sessao')


# ---- perigosos (decisao 23) ----
PERIGOS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r\s+-f|-f\s+-r|--recursive\s+--force|--force\s+--recursive)\b", "rm -rf"),
    (r"\bgit\s+push\b[^;&|]*(\s--force(-with-lease)?\b|\s-f\b|\s\+\S)", "git push --force"),
    (r"\bgit\s+reset\b[^;&|]*--hard\b", "git reset --hard"),
    (r"\bgit\s+push\b[^;&|]*(\s--delete\b|\s-d\b|\s:\S)", "apagar branch remota"),
    (r"\bgh\s+api\b[^;&|]*-X\s*DELETE[^;&|]*refs/heads", "apagar branch remota"),
    (r"\b(deploy|vercel|netlify|fly\s+deploy|firebase\s+deploy|kubectl\s+apply|terraform\s+apply|npm\s+publish|twine\s+upload|gh\s+release\s+create)\b", "deploy/publicacao"),
    (r"(^|[;&|(]\s*|\s)sudo\b", "sudo"),
    (r"\b(curl|wget)\b[^;&]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "curl | sh"),
    (r"(^|[\s/'\"])\.env(\.[\w.-]+)?\b|credentials|\.netrc|id_rsa|id_ed25519|\.pem\b|secrets?\.", "credenciais/.env"),
]
ARQ_SENSIVEL = re.compile(r"(^|/)(\.env(\..*)?|\.netrc|credentials(\.json)?|id_rsa|id_ed25519|.*\.pem|secrets?\..*)$")


def classificar(tool, inp):
    """Motivo (str) se o pedido e perigoso (so pelo app), senao None."""
    inp = inp or {}
    if tool == 'Bash':
        cmd = inp.get('command', '') or ''
        for pad, nome in PERIGOS:
            if re.search(pad, cmd):
                return nome
    elif tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        if ARQ_SENSIVEL.search(inp.get('file_path', '') or inp.get('notebook_path', '') or ''):
            return 'credenciais/.env'
    return None


def tipo_pedido(tool):
    return {'AskUserQuestion': 'pergunta', 'ExitPlanMode': 'plano'}.get(tool, 'permissao')


def resumo_ferramenta(tool, inp):
    inp = inp or {}
    if tool == 'Bash':
        return inp.get('command', '')
    if tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Read'):
        return f"{tool} {inp.get('file_path') or inp.get('notebook_path') or ''}".strip()
    if tool == 'AskUserQuestion':
        return ' | '.join(q.get('question', '') for q in inp.get('questions', []))
    if tool == 'ExitPlanMode':
        return 'Aprovar plano: ' + (inp.get('plan') or '').strip().splitlines()[0][:200] if inp.get('plan') else 'Aprovar plano'
    if tool == 'WebFetch':
        return 'WebFetch ' + inp.get('url', '')
    return tool + ' ' + json.dumps(inp, ensure_ascii=True)[:300]


def detalhe_ferramenta(tool, inp):
    inp = inp or {}
    if tool == 'Bash':
        return ((inp.get('description') or '') + '\n' + inp.get('command', '')).strip()
    if tool == 'ExitPlanMode':
        return inp.get('plan') or ''
    if tool in ('Write',):
        return f"{inp.get('file_path', '')}\n{(inp.get('content') or '')[:1500]}"
    if tool in ('Edit',):
        return f"{inp.get('file_path', '')}\n- {(inp.get('old_string') or '')[:700]}\n+ {(inp.get('new_string') or '')[:700]}"
    return json.dumps(inp, ensure_ascii=True)[:2000]


def perguntas_de(tool, inp):
    if tool != 'AskUserQuestion':
        return []
    out = []
    for q in (inp or {}).get('questions', []):
        out.append({'pergunta': q.get('question', ''), 'cabecalho': q.get('header', ''),
                    'multipla': bool(q.get('multiSelect')),
                    'opcoes': [{'rotulo': o.get('label', ''), 'descricao': o.get('description', '')}
                               for o in q.get('options', [])]})
    return out


def respostas_para_answers(perguntas, respostas):
    """{pergunta: 'rotulo' | ['r1','r2']} -> answers do AskUserQuestion ({pergunta: 'r1, r2'}).
    Valida: toda pergunta respondida, rotulos existentes, lista so em multipla. Levanta ValueError."""
    if not isinstance(respostas, dict):
        raise ValueError('respostas deve ser objeto')
    answers = {}
    for q in perguntas:
        p = q['pergunta']
        if p not in respostas:
            raise ValueError('falta resposta: ' + ascii_tela(p, 80))
        r = respostas[p]
        lst = r if isinstance(r, list) else [r]
        if not lst or not all(isinstance(x, str) and x for x in lst):
            raise ValueError('resposta vazia')
        if len(lst) > 1 and not q['multipla']:
            raise ValueError('pergunta aceita uma opcao')
        rotulos = {o['rotulo'] for o in q['opcoes']}
        for x in lst:
            if rotulos and x not in rotulos:
                raise ValueError('opcao inexistente: ' + ascii_tela(x, 60))
        answers[p] = ', '.join(lst)
    return answers


# ---- arquivos de config/token ----
def ler_env_arquivo(caminho):
    d = {}
    try:
        with open(caminho) as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith('#') and '=' in linha:
                    k, v = linha.split('=', 1)
                    d[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return d


def token_aparelho():
    t = os.environ.get('PONTE_TOKEN') or ler_env_arquivo(os.path.join(DIR_CONFIG, 'ponte.env')).get('PONTE_TOKEN', '')
    return t.strip()


def caminho_hook_token():
    return os.path.join(DIR_CONFIG, 'hook.token')


def token_hook(gerar=False):
    c = caminho_hook_token()
    try:
        with open(c) as f:
            t = f.read().strip()
        if t:
            return t
    except OSError:
        pass
    if not gerar:
        return ''
    os.makedirs(DIR_CONFIG, mode=0o700, exist_ok=True)
    t = secrets.token_urlsafe(32)
    fd = os.open(c, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(t + '\n')
    return t


def ler_config(caminho=None):
    cfg = dict(CONFIG_PADRAO)
    caminho = caminho or os.path.join(DIR_CONFIG, 'ponte.json')
    try:
        with open(caminho) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def env_limpo():
    """Ambiente para processos filhos: sem ANTHROPIC_* (forca o login da assinatura)."""
    return {k: v for k, v in os.environ.items()
            if not re.match(r'(ANTHROPIC_|CLAUDE_CODE_USE_|OPENAI_)', k) and k not in ('PONTE_TOKEN',)}


def agora():
    return time.time()
