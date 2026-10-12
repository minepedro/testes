#!/usr/bin/env python3
"""Instalador revisavel: HTTPS por IP (Let's Encrypt, perfil shortlived) para a ponte do mascote.

Modos (rodar como root SOMENTE quando o operador decidir):
  render   --out DIR   gera todos os arquivos para revisao (sem root, nao toca o sistema)
  preflight            checagens somente-leitura (sem root)
  prepare              nginx + certbot (venv) + cert staging(dry-run) -> producao + timer;
                       a ponte continua em 0.0.0.0:8787 com o token ANTIGO (firmware atual segue ok)
  activate             transacional: verifica HTTPS antes, snapshot original imutavel (0600),
                       token novo, ponte so em 127.0.0.1, verifica auth/bind local ANTES do UFW,
                       fecha 8787, verifica tudo; qualquer falha => rollback automatico.
                       Mostra o token UMA vez. Exige /etc/mascote-ponte.env existente.
  rollback-activate    volta env/drop-in/UFW 8787 ao snapshot da PRIMEIRA ativacao
  rollback-prepare     remove o site nginx/regras UFW 80/443/timer (mantem certificados e
                       mantem o site default do nginx DESABILITADO, nunca reexpoe 0.0.0.0:80)
  verify               checa HTTPS com cadeia validada pelo sistema (sem -k)

Nada aqui reinicia a maquina, mexe em SSH ou em outros servicos (tailscale intocado).
O token nunca vai para log, arquivo do repo ou argumento de processo.
"""
import argparse
import datetime
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------- configuracao
PUBLIC_IP = '179.198.122.200'
UPSTREAM_PORT = 8787
SERVICE = 'mascote-ponte'
ENV_FILE = '/etc/mascote-ponte.env'
PONTE_PY = '/opt/mascote/ponte.py'
CERTBOT_VENV = '/opt/certbot-venv'
CERTBOT_SPEC = 'certbot>=5.4,<6'
WEBROOT = '/var/www/mascote-acme'
NGINX_SITE = '/etc/nginx/sites-available/mascote-https.conf'
NGINX_LINK = '/etc/nginx/sites-enabled/mascote-https.conf'
NGINX_DEFAULT_LINK = '/etc/nginx/sites-enabled/default'
DEPLOY_HOOK = '/etc/letsencrypt/renewal-hooks/deploy/mascote-nginx-reload.sh'
TIMER_UNIT = '/etc/systemd/system/mascote-certbot.timer'
RENEW_UNIT = '/etc/systemd/system/mascote-certbot.service'
DROPIN_DIR = f'/etc/systemd/system/{SERVICE}.service.d'
DROPIN = f'{DROPIN_DIR}/10-loopback.conf'
STATE_DIR = '/var/lib/mascote-https'
BACKUP_DIR = f'{STATE_DIR}/backups'
ORIG_DIR = f'{STATE_DIR}/original'  # snapshot da 1a ativacao; nunca sobrescrito
POLICY_RC = '/usr/sbin/policy-rc.d'
ROOT_UID = 0  # dono exigido do env (testes trocam pelo uid local)
LOG_FILE = '/var/log/mascote-https.log'
ACTIVATE_MARK = '# mascote-https: token rotacionado'


def live_dir(ip=PUBLIC_IP):
    return f'/etc/letsencrypt/live/{ip}'


# ---------------------------------------------------------------- renderizacao (puro, testavel)
def render_nginx(ip=PUBLIC_IP, upstream_port=UPSTREAM_PORT, webroot=WEBROOT, tls=True,
                 cert_dir=None, http_port=80, https_port=443,
                 proxy_inc='/etc/nginx/mascote-proxy.inc'):
    """Site nginx preso SOMENTE ao IP publico (nao toca 100.x / fd7a: do tailscale)."""
    ipaddress.IPv4Address(ip)  # valida
    cert_dir = cert_dir or live_dir(ip)
    http = f"""# Gerado por mascote_https.py - nao editar a mao
server {{
    listen {ip}:{http_port};
    server_name {ip};
    location ^~ /.well-known/acme-challenge/ {{
        root {webroot};
        default_type text/plain;
        try_files $uri =404;
    }}
    location / {{ {'return 301 https://$host$request_uri;' if tls else 'return 404;'} }}
}}
"""
    if not tls:
        return http
    return http + f"""
server {{
    listen {ip}:{https_port} ssl;
    server_name {ip};
    ssl_certificate     {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:mascote:1m;
    server_tokens off;
    client_max_body_size 64k;
    add_header Strict-Transport-Security "max-age=86400" always;

    location = /saude   {{ proxy_pass http://127.0.0.1:{upstream_port}; include {proxy_inc}; }}
    location /api/      {{ proxy_pass http://127.0.0.1:{upstream_port}; include {proxy_inc}; }}
    # voz: PCM cru ate 1 MB (~32 s) e transcricao local que pode levar dezenas de segundos
    location = /api/voz {{
        client_max_body_size 1m;
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 5s;
        proxy_read_timeout 90s;
    }}
    location / {{ return 404; }}
}}
"""


PROXY_INC = """# Gerado por mascote_https.py
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
proxy_connect_timeout 5s;
proxy_read_timeout 15s;
"""


def render_deploy_hook(ip=PUBLIC_IP):
    return f"""#!/bin/sh
# Gerado por mascote_https.py. certbot roda isto apos cada renovacao bem-sucedida.
# So recarrega o nginx se o cert novo valida contra a CA do sistema e a config passa no nginx -t.
set -eu
LIVE={live_dir(ip)}
openssl x509 -in "$LIVE/fullchain.pem" -noout -checkend 3600
openssl verify -untrusted "$LIVE/chain.pem" "$LIVE/cert.pem" >/dev/null
# -checkip compara o SAN IP exato (sai 0 mesmo sem match: comparar a saida literal)
[ "$(openssl x509 -in "$LIVE/cert.pem" -noout -checkip {ip})" = "IP {ip} does match certificate" ]
/usr/sbin/nginx -t -q
systemctl reload nginx
logger -t mascote-https "cert renovado e nginx recarregado"
"""


def render_renew_units(venv=CERTBOT_VENV, ip=PUBLIC_IP):
    service = f"""# Gerado por mascote_https.py
[Unit]
Description=Renovacao Let's Encrypt (certbot venv) para HTTPS da ponte do mascote
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={venv}/bin/certbot renew --cert-name {ip} --quiet --no-random-sleep-on-renew
PrivateTmp=yes
"""
    timer = """# Gerado por mascote_https.py. Cert de 6 dias: certbot renova com ~metade da vida (ou via ARI).
[Unit]
Description=Timer da renovacao do cert da ponte do mascote

[Timer]
OnCalendar=*-*-* 00/6:17:00
RandomizedDelaySec=30m
Persistent=true

[Install]
WantedBy=timers.target
"""
    return service, timer


def render_dropin(ponte=PONTE_PY, port=UPSTREAM_PORT):
    return f"""# Gerado por mascote_https.py activate: ponte so em loopback (nginx faz o TLS)
[Service]
EnvironmentFile={ENV_FILE}
ExecStart=
ExecStart=/usr/bin/python3 {ponte} --host 127.0.0.1 --porta {port}
"""


def rotate_env(old_text, new_token):
    """Troca PONTE_TOKEN preservando as outras linhas. Retorna texto novo (nao loga)."""
    if len(new_token) < 32 or any(c in new_token for c in '\n\r"\'$ '):
        raise ValueError('token novo invalido')
    out, done = [], False
    for line in old_text.splitlines():
        if line.startswith(ACTIVATE_MARK):
            continue
        if re.match(r'^\s*(export\s+)?PONTE_TOKEN\s*=', line):
            if not done:
                out.append(f'PONTE_TOKEN={new_token}')
                done = True
            continue
        out.append(line)
    if not done:
        out.append(f'PONTE_TOKEN={new_token}')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return f'{ACTIVATE_MARK} em {stamp}\n' + '\n'.join(out) + '\n'


def certbot_cmd(venv=CERTBOT_VENV, ip=PUBLIC_IP, webroot=WEBROOT, dry_run=False):
    cmd = [f'{venv}/bin/certbot', 'certonly', '--non-interactive', '--agree-tos',
           '--register-unsafely-without-email', '--preferred-profile', 'shortlived',
           '--webroot', '--webroot-path', webroot, '--ip-address', ip,
           '--cert-name', ip, '--keep-until-expiring']
    if dry_run:
        cmd.append('--dry-run')  # usa o servidor staging sem salvar nada
    return cmd


def ufw_allow_https_cmds(ip=PUBLIC_IP):
    return [['ufw', 'allow', 'proto', 'tcp', 'to', ip, 'port', p, 'comment', 'mascote-https']
            for p in ('80', '443')]


# ---------------------------------------------------------------- utilitarios de sistema
def log(msg):
    print(msg, flush=True)
    if os.geteuid() == 0:
        with open(LOG_FILE, 'a') as f:
            os.chmod(LOG_FILE, 0o600)
            f.write(f'{datetime.datetime.now().isoformat(timespec="seconds")} {msg}\n')


def run(cmd, check=True, **kw):
    log('$ ' + ' '.join(cmd))
    return subprocess.run(cmd, check=check, text=True, **kw)


def need_root():
    if os.geteuid() != 0:
        sys.exit('este modo precisa de root (sudo). Use "render" ou "preflight" para revisar sem root.')


def stamp():
    return datetime.datetime.now().strftime('%Y%m%d-%H%M%S')


def backup(path):
    """Copia preservando modo para BACKUP_DIR; retorna destino ou None."""
    if not os.path.lexists(path):
        return None
    os.makedirs(BACKUP_DIR, mode=0o700, exist_ok=True)
    os.chmod(BACKUP_DIR, 0o700)
    dst = os.path.join(BACKUP_DIR, path.strip('/').replace('/', '__') + '.' + stamp())
    if os.path.islink(path):
        os.symlink(os.readlink(path), dst)
    else:
        shutil.copy2(path, dst)
    log(f'backup: {path} -> {dst}')
    return dst


def latest_backup(path):
    if not os.path.isdir(BACKUP_DIR):
        return None
    pref = path.strip('/').replace('/', '__') + '.'
    c = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith(pref))
    return os.path.join(BACKUP_DIR, c[-1]) if c else None


def write_file(path, content, mode, dir_mode=0o755):
    """Escrita atomica com modo explicito (umask 077 ja quebrou isso antes)."""
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d, mode=dir_mode)
        os.chmod(d, dir_mode)
    if os.path.exists(path):
        with open(path) as f:
            if f.read() == content:
                os.chmod(path, mode)
                return False
        backup(path)
    tmp = path + '.tmp-mascote'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    log(f'escrito {path} ({oct(mode)})')
    return True


def http_get(url, token=None, cafile=None, timeout=8):
    """GET com verificacao TLS completa (cadeia + nome/IP). Retorna (status, corpo)."""
    ctx = ssl.create_default_context(cafile=cafile)
    req = urllib.request.Request(url, headers={'X-Token': token} if token else {})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return r.status, r.read(2048)
    except urllib.error.HTTPError as e:
        return e.code, e.read(2048)


def curl_status(url, token=None, cafile=None):
    """Mesmo teste via curl (sem -k). Token vai por stdin/config, nao por argv."""
    cmd = ['curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', '8']
    if cafile:
        cmd += ['--cacert', cafile]
    cfg = f'header = "X-Token: {token}"\n' if token else ''
    cmd += ['-K', '-', url]
    r = subprocess.run(cmd, input=cfg, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip()


def port_listeners(port):
    r = subprocess.run(['ss', '-ltnH'], capture_output=True, text=True)
    return [l.split()[3] for l in r.stdout.splitlines() if l.split()[3].rsplit(':', 1)[-1] == str(port)]


# ---------------------------------------------------------------- modos
def cmd_render(a):
    os.makedirs(a.out, exist_ok=True)
    svc, tmr = render_renew_units()
    files = {
        'nginx-bootstrap.conf': render_nginx(tls=False),
        'nginx-mascote-https.conf': render_nginx(),
        'mascote-proxy.inc': PROXY_INC,
        'deploy-hook.sh': render_deploy_hook(),
        'mascote-certbot.service': svc,
        'mascote-certbot.timer': tmr,
        '10-loopback.conf': render_dropin(),
        'certbot-staging.cmd': ' '.join(certbot_cmd(dry_run=True)) + '\n',
        'certbot-production.cmd': ' '.join(certbot_cmd()) + '\n',
        'ufw.cmd': '\n'.join(' '.join(c) for c in ufw_allow_https_cmds()) + '\n',
    }
    for n, c in files.items():
        p = os.path.join(a.out, n)
        with open(p, 'w') as f:
            f.write(c)
        os.chmod(p, 0o755 if n.endswith('.sh') else 0o644)
    print(f'{len(files)} arquivos em {a.out}')


def preflight(strict=True):
    probs = []
    ips = subprocess.run(['ip', '-4', '-br', 'addr'], capture_output=True, text=True).stdout
    if PUBLIC_IP not in ips:
        probs.append(f'IP {PUBLIC_IP} nao esta em nenhuma interface')
    for port in (80, 443):
        for l in port_listeners(port):
            host = l.rsplit(':', 1)[0].strip('[]')
            if host in ('0.0.0.0', '*', '::', PUBLIC_IP) and not os.path.exists(NGINX_SITE):
                probs.append(f'porta {port} ja ocupada em {l}')
    if not os.path.exists(PONTE_PY):
        probs.append(f'{PONTE_PY} nao existe')
    probs += env_problems()
    try:
        s, b = http_get(f'http://127.0.0.1:{UPSTREAM_PORT}/saude')
        if s != 200:
            probs.append(f'upstream /saude respondeu {s}')
        s, _ = http_get(f'http://127.0.0.1:{UPSTREAM_PORT}/api/estado')
        if s != 401:
            probs.append(f'upstream /api/estado sem token respondeu {s} (esperado 401)')
    except OSError as e:
        probs.append(f'upstream inacessivel: {e}')
    for p in probs:
        print('PROBLEMA:', p)
    if not probs:
        print('preflight ok')
    if probs and strict:
        sys.exit(2)
    return probs


def env_problems():
    """So stat (nunca le o conteudo): escopo e a instalacao demo existente com env root 0600."""
    try:
        st = os.lstat(ENV_FILE)
    except FileNotFoundError:
        return [f'{ENV_FILE} ausente (instalacao sem env nao e suportada)']
    except OSError as e:
        return [f'{ENV_FILE} inacessivel: {e}']
    import stat as _s
    p = []
    if not _s.S_ISREG(st.st_mode):
        p.append(f'{ENV_FILE} nao e arquivo regular')
    if st.st_uid != ROOT_UID or st.st_mode & 0o077:
        p.append(f'{ENV_FILE} deve ser root e 0600 (uid={st.st_uid} modo={oct(st.st_mode & 0o777)})')
    return p


def nginx_test():
    run(['nginx', '-t'])


def cmd_prepare(a):
    need_root()
    os.umask(0o022)
    preflight()
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    # nginx: instalar sem iniciar o site default em 0.0.0.0:80 (policy-rc.d temporario)
    if not shutil.which('nginx'):
        prc = POLICY_RC
        if os.path.lexists(prc):
            # politica do admin: nao sobrescrever nem confiar que bloqueia o start do nginx
            sys.exit(f'{prc} ja existe: nao garanto que o nginx nao inicie o default em 0.0.0.0:80. '
                     'Instale o nginx manualmente (sem iniciar) ou remova a politica, e rode de novo.')
        write_file(prc, '#!/bin/sh\nexit 101\n', 0o755)
        try:
            run(['apt-get', 'update'], env=env)
            run(['apt-get', 'install', '-y', '--no-install-recommends', 'nginx', 'python3-venv'], env=env)
        finally:
            os.remove(prc)
    else:
        run(['apt-get', 'install', '-y', '--no-install-recommends', 'python3-venv'], env=env)
    if os.path.lexists(NGINX_DEFAULT_LINK):
        backup(NGINX_DEFAULT_LINK)
        os.remove(NGINX_DEFAULT_LINK)
        log('site default desabilitado (backup feito)')
    # certbot isolado
    if not os.path.exists(f'{CERTBOT_VENV}/bin/certbot'):
        run(['python3', '-m', 'venv', CERTBOT_VENV])
        os.chmod(CERTBOT_VENV, 0o755)
    run([f'{CERTBOT_VENV}/bin/pip', 'install', '--upgrade', '--quiet', CERTBOT_SPEC])
    ver = subprocess.run([f'{CERTBOT_VENV}/bin/certbot', '--version'], capture_output=True, text=True).stdout
    log(f'certbot: {ver.strip()}')
    m = re.search(r'(\d+)\.(\d+)', ver)
    if not m or (int(m[1]), int(m[2])) < (5, 4):
        sys.exit('certbot < 5.4 (precisa de webroot com --ip-address)')
    # webroot + bootstrap http
    os.makedirs(f'{WEBROOT}/.well-known/acme-challenge', exist_ok=True)
    for d in (WEBROOT, f'{WEBROOT}/.well-known', f'{WEBROOT}/.well-known/acme-challenge'):
        os.chmod(d, 0o755)
    write_file('/etc/nginx/mascote-proxy.inc', PROXY_INC, 0o644)
    have_cert = os.path.exists(f'{live_dir()}/fullchain.pem')
    write_file(NGINX_SITE, render_nginx(tls=have_cert), 0o644)
    if not os.path.lexists(NGINX_LINK):
        os.symlink(NGINX_SITE, NGINX_LINK)
    nginx_test()
    run(['systemctl', 'enable', 'nginx'])
    run(['systemctl', 'reload-or-restart', 'nginx'])
    for c in ufw_allow_https_cmds():
        run(c)
    # staging (dry-run) antes de producao
    run(certbot_cmd(dry_run=True))
    if not a.staging_only:
        run(certbot_cmd())
        write_file(DEPLOY_HOOK, render_deploy_hook(), 0o755)
        run(['openssl', 'verify', '-untrusted', f'{live_dir()}/chain.pem', f'{live_dir()}/cert.pem'])
        write_file(NGINX_SITE, render_nginx(tls=True), 0o644)
        nginx_test()
        run(['systemctl', 'reload', 'nginx'])
        svc, tmr = render_renew_units()
        write_file(RENEW_UNIT, svc, 0o644)
        write_file(TIMER_UNIT, tmr, 0o644)
        run(['systemd-analyze', 'verify', RENEW_UNIT, TIMER_UNIT])
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'enable', '--now', 'mascote-certbot.timer'])
        run([f'{CERTBOT_VENV}/bin/certbot', 'renew', '--dry-run', '--cert-name', PUBLIC_IP])  # so este cert
        if verify(token=None, require_closed=False):
            sys.exit('verificacao HTTPS falhou')
    log('prepare concluido. Ponte ainda em 0.0.0.0:8787 com token antigo (transicao).')


def verify(token=None, require_closed=True, cafile=None, base=None):
    base = base or f'https://{PUBLIC_IP}'
    fails = []
    checks = [('/saude', None, '200'), ('/api/estado', None, '401'),
              ('/api/estado', 'token-errado-123456', '401'), ('/nada', None, '404')]
    if token:
        checks.append(('/api/estado', token, '200'))
    for path, tok, want in checks:
        got, err = curl_status(base + path, tok, cafile)
        ok = got == want
        print(f'{"ok " if ok else "FALHA"} {path} token={"sim" if tok else "nao"} -> {got or err} (esperado {want})')
        if not ok:
            fails.append(path)
    if require_closed:
        pub = [l for l in port_listeners(UPSTREAM_PORT) if not l.startswith('127.0.0.1:')]
        print(f'{"ok " if not pub else "FALHA"} {UPSTREAM_PORT} so em loopback: {port_listeners(UPSTREAM_PORT)}')
        if pub:
            fails.append('bind')
    return fails


def cmd_verify(a):
    sys.exit(1 if verify(require_closed=a.require_closed, cafile=a.cafile, base=a.base) else 0)


def verify_local(token):
    """Apos restart, ANTES do UFW: bind so loopback e auth correta direto no upstream."""
    import time
    for _ in range(20):
        if port_listeners(UPSTREAM_PORT):
            break
        time.sleep(0.5)
    fails = []
    lst = port_listeners(UPSTREAM_PORT)
    if not lst or any(not l.startswith('127.0.0.1:') for l in lst):
        fails.append(f'bind {lst}')
    base = f'http://127.0.0.1:{UPSTREAM_PORT}'
    try:
        for tok, want in ((None, 401), ('token-errado-123456', 401), (token, 200)):
            if http_get(base + '/api/estado', tok)[0] != want:
                fails.append(f'auth esperado {want}')
    except OSError as e:
        fails.append(f'upstream: {e}')
    return fails


def snapshot_original():
    """Uma vez so (1a ativacao): env + drop-in (ou marca de ausencia), root 0700/0600."""
    if os.path.isdir(ORIG_DIR):
        log(f'snapshot original ja existe em {ORIG_DIR} (mantido)')
        return
    tmp = ORIG_DIR + '.tmp'
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    os.mkdir(tmp, 0o700)
    for src in (ENV_FILE, DROPIN):
        dst = os.path.join(tmp, os.path.basename(src))
        if os.path.exists(src):
            shutil.copyfile(src, dst)
            os.chmod(dst, 0o600)
            os.chown(dst, 0, 0)
        else:
            with open(dst + '.absent', 'w'):
                pass
            os.chmod(dst + '.absent', 0o600)
    os.chmod(tmp, 0o700)
    os.replace(tmp, ORIG_DIR)
    log(f'snapshot original em {ORIG_DIR}')


def restore_original():
    if not os.path.isdir(ORIG_DIR):
        sys.exit(f'sem snapshot original em {ORIG_DIR}')
    env_snap = os.path.join(ORIG_DIR, os.path.basename(ENV_FILE))
    if not os.path.exists(env_snap):
        sys.exit('snapshot sem env (inesperado); nada alterado')
    tmp = ENV_FILE + '.tmp-mascote'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f, open(env_snap) as g:
        f.write(g.read())
    os.chmod(tmp, 0o600)
    os.chown(tmp, 0, 0)
    os.replace(tmp, ENV_FILE)
    d_snap = os.path.join(ORIG_DIR, os.path.basename(DROPIN))
    if os.path.exists(d_snap):
        with open(d_snap) as g:
            write_file(DROPIN, g.read(), 0o644)
    elif os.path.exists(DROPIN):
        os.remove(DROPIN)
    log(f'restaurado env/drop-in do snapshot {ORIG_DIR}')
    run(['systemctl', 'daemon-reload'], check=False)
    run(['systemctl', 'restart', SERVICE], check=False)


def cmd_activate(a):
    need_root()
    os.umask(0o022)
    # tudo somente-leitura ate a confirmacao: nenhuma mudanca se algo faltar
    if not os.path.exists(f'{live_dir()}/fullchain.pem'):
        sys.exit('rode prepare antes (sem cert)')
    probs = env_problems()
    if probs:
        sys.exit('; '.join(probs))
    with open(ENV_FILE) as f:
        old = f.read()
    if ACTIVATE_MARK in old:
        sys.exit('ja ativado. Para rodar de novo: rollback-activate e depois activate.')
    if verify(token=None, require_closed=False):
        sys.exit('HTTPS publico nao esta ok; token nao foi tocado')
    if not a.yes:
        print('ATENCAO: o token antigo deixa de valer e a porta 8787 fecha. O ESP precisa do firmware HTTPS novo.')
        if input('digite ATIVAR para continuar: ').strip() != 'ATIVAR':
            sys.exit('cancelado')
    snapshot_original()
    token = secrets.token_urlsafe(32)
    try:
        write_file(ENV_FILE, rotate_env(old, token), 0o600)
        os.chown(ENV_FILE, 0, 0)
        write_file(DROPIN, render_dropin(), 0o644)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'restart', SERVICE])
        fails = verify_local(token)
    except (OSError, subprocess.CalledProcessError) as e:
        fails = [f'erro: {e}']
    if fails:
        print(f'FALHA local {fails}; rollback automatico (UFW intocado). Token NAO mostrado.')
        restore_original()
        sys.exit(1)
    for rule in (['allow', '8787/tcp'], ['allow', '8787']):
        run(['ufw', 'delete'] + rule, check=False)
    fails = verify(token=token)
    if fails:
        print(f'FALHA final {fails}; rollback automatico. Token NAO mostrado.')
        restore_original()
        run(['ufw', 'allow', '8787/tcp'], check=False)
        sys.exit(1)
    log('activate concluido (token nao registrado em log)')
    if sys.stdout.isatty():
        print('\nTOKEN NOVO (copie para o config do firmware; nao sera mostrado de novo):\n' + token + '\n')
    else:
        print(f'stdout nao e terminal: leia o token com  sudo grep ^PONTE_TOKEN= {ENV_FILE}')


def restore(path):
    b = latest_backup(path)
    if b:
        if os.path.lexists(path):
            os.remove(path)
        if os.path.islink(b):
            os.symlink(os.readlink(b), path)
        else:
            shutil.copy2(b, path)
        log(f'restaurado {path} <- {b}')
    return b


def cmd_rollback_activate(a):
    need_root()
    restore_original()
    run(['ufw', 'allow', '8787/tcp'])
    log('rollback-activate ok: env/drop-in originais e 8787 liberada de volta')


def cmd_rollback_prepare(a):
    need_root()
    run(['systemctl', 'disable', '--now', 'mascote-certbot.timer'], check=False)
    for p in (NGINX_LINK, NGINX_SITE, TIMER_UNIT, RENEW_UNIT, DEPLOY_HOOK):
        if os.path.lexists(p):
            backup(p)
            os.remove(p)
    # NAO restaura sites-enabled/default: reexporia 0.0.0.0:80 (wildcard). Fica desabilitado.
    log(f'site default do nginx mantido desabilitado ({NGINX_DEFAULT_LINK}); backup em {BACKUP_DIR}')
    for c in ufw_allow_https_cmds():
        run(['ufw', 'delete'] + c[1:-2], check=False)
    run(['systemctl', 'daemon-reload'])
    run(['nginx', '-t'])
    run(['systemctl', 'reload', 'nginx'])
    log('rollback-prepare ok (certificados e nginx/venv mantidos; remova com apt/rm se quiser)')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='modo', required=True)
    r = sp.add_parser('render'); r.add_argument('--out', required=True); r.set_defaults(f=cmd_render)
    sp.add_parser('preflight').set_defaults(f=lambda a: preflight())
    p = sp.add_parser('prepare'); p.add_argument('--staging-only', action='store_true'); p.set_defaults(f=cmd_prepare)
    c = sp.add_parser('activate'); c.add_argument('--yes', action='store_true'); c.set_defaults(f=cmd_activate)
    sp.add_parser('rollback-activate').set_defaults(f=cmd_rollback_activate)
    sp.add_parser('rollback-prepare').set_defaults(f=cmd_rollback_prepare)
    v = sp.add_parser('verify'); v.add_argument('--cafile'); v.add_argument('--base')
    v.add_argument('--require-closed', action='store_true'); v.set_defaults(f=cmd_verify)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == '__main__':
    main()
