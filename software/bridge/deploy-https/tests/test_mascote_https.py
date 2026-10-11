"""Testes locais reais (sem root): render, contratos, nginx -t e proxy TLS ponta a ponta.

nginx: usa `nginx` do PATH ou NGINX_BIN (ex.: binario extraido de `apt-get download nginx`).
Sem nginx os testes de integracao sao PULADOS (nunca simulados).
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import mascote_https as m  # noqa: E402

PONTE = os.path.abspath(os.path.join(AQUI, '..', '..', 'ponte.py'))
NGINX = os.environ.get('NGINX_BIN') or shutil.which('nginx')


def escrever(p, c):
    with open(p, 'w') as f:
        f.write(c)


def porta_livre():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Render(unittest.TestCase):
    def test_nginx_preso_ao_ip_publico(self):
        c = m.render_nginx()
        listens = [l.strip() for l in c.splitlines() if l.strip().startswith('listen')]
        self.assertEqual(listens, ['listen 179.198.122.200:80;', 'listen 179.198.122.200:443 ssl;'])
        self.assertNotIn('100.94.88.50', c)
        self.assertNotIn('[::]', c)
        self.assertIn('/etc/letsencrypt/live/179.198.122.200/fullchain.pem', c)
        self.assertIn('proxy_pass http://127.0.0.1:8787', c)

    def test_bootstrap_sem_tls(self):
        c = m.render_nginx(tls=False)
        self.assertNotIn('ssl', c)
        self.assertIn('/.well-known/acme-challenge/', c)

    def test_ip_invalido(self):
        with self.assertRaises(ValueError):
            m.render_nginx(ip='exemplo.com')

    def test_certbot_cmd(self):
        c = m.certbot_cmd()
        for f in ('--preferred-profile', 'shortlived', '--webroot', '--ip-address', '179.198.122.200'):
            self.assertIn(f, c)
        self.assertNotIn('--dry-run', c)
        self.assertIn('--dry-run', m.certbot_cmd(dry_run=True))
        self.assertTrue(m.CERTBOT_SPEC.startswith('certbot>=5.4'))

    def test_dropin_loopback(self):
        d = m.render_dropin()
        self.assertIn('ExecStart=\n', d)
        self.assertIn('--host 127.0.0.1 --porta 8787', d)

    def test_rotate_env(self):
        old = 'PONTE_TOKEN=antigo-token-123\nPONTE_LOG=1\n'
        novo = m.rotate_env(old, 'x' * 43)
        self.assertNotIn('antigo', novo)
        self.assertIn('PONTE_LOG=1', novo)
        self.assertEqual(novo.count('PONTE_TOKEN='), 1)
        self.assertTrue(novo.startswith(m.ACTIVATE_MARK))
        # rerun idempotente: 1 marcador e 1 token
        de_novo = m.rotate_env(novo, 'y' * 43)
        self.assertEqual(de_novo.count(m.ACTIVATE_MARK), 1)
        self.assertEqual(de_novo.count('PONTE_TOKEN='), 1)
        with self.assertRaises(ValueError):
            m.rotate_env(old, 'curto')

    def test_write_file_modo_explicito_com_umask_077(self):
        d = tempfile.mkdtemp()
        velho = os.umask(0o077)
        try:
            p = os.path.join(d, 'sub', 'a.conf')
            m.write_file(p, 'x', 0o644)
            self.assertEqual(os.stat(p).st_mode & 0o777, 0o644)
            self.assertEqual(os.stat(os.path.dirname(p)).st_mode & 0o777, 0o755)
            self.assertFalse(m.write_file(p, 'x', 0o644))  # rerun sem mudanca
        finally:
            os.umask(velho)

    def test_render_cli_e_shell_hook(self):
        d = tempfile.mkdtemp()
        m.main(['render', '--out', d])
        hook = os.path.join(d, 'deploy-hook.sh')
        self.assertEqual(subprocess.run(['sh', '-n', hook]).returncode, 0)
        self.assertEqual(os.stat(hook).st_mode & 0o777, 0o755)

    @unittest.skipUnless(shutil.which('systemd-analyze'), 'sem systemd-analyze')
    def test_units_systemd_validas(self):
        d = tempfile.mkdtemp()
        svc, tmr = m.render_renew_units(venv='/bin')  # ExecStart precisa existir para verify
        svc = svc.replace(f'/bin/bin/certbot renew --cert-name {m.PUBLIC_IP} --quiet --no-random-sleep-on-renew', '/bin/true')
        for n, c in (('mascote-certbot.service', svc), ('mascote-certbot.timer', tmr)):
            with open(os.path.join(d, n), 'w') as f:
                f.write(c)
        r = subprocess.run(['systemd-analyze', 'verify', '--man=no',
                            os.path.join(d, 'mascote-certbot.service'), os.path.join(d, 'mascote-certbot.timer')],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(['systemd-analyze', 'calendar', '*-*-* 00/6:17:00'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(NGINX and shutil.which('openssl') and shutil.which('curl'), 'nginx/openssl/curl ausentes')
class NginxReal(unittest.TestCase):
    """nginx real + CA local + ponte.py real em loopback. Valida cadeia por --cacert (sem -k)."""

    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(prefix='mascote-https-')
        d = cls.d
        ossl = lambda *a: subprocess.run(['openssl', *a], check=True, capture_output=True)
        ossl('req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-days', '1',
             '-subj', '/CN=teste-ca', '-keyout', f'{d}/ca.key', '-out', f'{d}/ca.pem')
        ossl('req', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-subj', '/CN=127.0.0.1',
             '-keyout', f'{d}/privkey.pem', '-out', f'{d}/req.csr')
        escrever(f'{d}/ext', 'subjectAltName=IP:127.0.0.1\n')
        ossl('x509', '-req', '-in', f'{d}/req.csr', '-CA', f'{d}/ca.pem', '-CAkey', f'{d}/ca.key',
             '-CAcreateserial', '-days', '1', '-extfile', f'{d}/ext', '-out', f'{d}/cert.pem')
        shutil.copy(f'{d}/cert.pem', f'{d}/fullchain.pem')
        cls.token = 'token-de-teste-' + os.urandom(8).hex()
        cls.up = porta_livre(); cls.https = porta_livre(); cls.http = porta_livre()
        cls.ponte = subprocess.Popen([sys.executable, PONTE, '--host', '127.0.0.1', '--porta', str(cls.up)],
                                     env=dict(os.environ, PONTE_TOKEN=cls.token),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.makedirs(f'{d}/webroot/.well-known/acme-challenge')
        escrever(f'{d}/webroot/.well-known/acme-challenge/abc', 'desafio-ok')
        escrever(f'{d}/proxy.inc', m.PROXY_INC)
        site = m.render_nginx(ip='127.0.0.1', upstream_port=cls.up, webroot=f'{d}/webroot', cert_dir=d,
                              http_port=cls.http, https_port=cls.https, proxy_inc=f'{d}/proxy.inc')
        escrever(f'{d}/site.conf', site)
        os.makedirs(f'{d}/logs')
        escrever(f'{d}/nginx.conf', f"""pid {d}/nginx.pid; error_log {d}/logs/error.log;
events {{}}
http {{ access_log off; client_body_temp_path {d}/t1; proxy_temp_path {d}/t2; fastcgi_temp_path {d}/t3;
uwsgi_temp_path {d}/t4; scgi_temp_path {d}/t5; include {d}/site.conf; }}
""")
        cls.nginx = [NGINX, '-p', d, '-c', f'{d}/nginx.conf', '-e', f'{d}/logs/error.log']
        r = subprocess.run(cls.nginx + ['-t'], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        subprocess.run(cls.nginx, check=True)
        for _ in range(50):
            try:
                socket.create_connection(('127.0.0.1', cls.https), 0.2).close()
                socket.create_connection(('127.0.0.1', cls.up), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        subprocess.run(cls.nginx + ['-s', 'stop'])
        cls.ponte.terminate(); cls.ponte.wait()

    def base(self):
        return f'https://127.0.0.1:{self.https}'

    def test_upstream_direto_saude_e_401(self):
        self.assertEqual(m.http_get(f'http://127.0.0.1:{self.up}/saude')[0], 200)
        self.assertEqual(m.http_get(f'http://127.0.0.1:{self.up}/api/estado')[0], 401)

    def test_verify_completo_com_cadeia_validada(self):
        falhas = m.verify(token=self.token, require_closed=False, cafile=f'{self.d}/ca.pem', base=self.base())
        self.assertEqual(falhas, [])

    def test_sem_ca_confiavel_curl_recusa(self):
        code, err = m.curl_status(self.base() + '/saude')
        self.assertEqual(code, '000')
        self.assertTrue(err)

    def test_python_tls_valida(self):
        s, b = m.http_get(self.base() + '/api/estado', self.token, cafile=f'{self.d}/ca.pem')
        self.assertEqual(s, 200)
        self.assertIn(b'sessoes', b)

    def test_http_acme_e_redirect(self):
        self.assertEqual(m.http_get(f'http://127.0.0.1:{self.http}/.well-known/acme-challenge/abc'),
                         (200, b'desafio-ok'))
        code, _ = m.curl_status(f'http://127.0.0.1:{self.http}/api/estado')
        self.assertEqual(code, '301')

    def test_deploy_hook_openssl_valida_cert(self):
        hook = m.render_deploy_hook(ip='127.0.0.1').replace(m.live_dir('127.0.0.1'), self.d)
        hook = hook.split('/usr/sbin/nginx')[0]  # so a parte de validacao (sem reload real)
        shutil.copy(f'{self.d}/ca.pem', f'{self.d}/chain.pem')
        r = subprocess.run(['sh', '-c', hook.replace('openssl verify ', f'openssl verify -CAfile {self.d}/ca.pem ')],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class Hardening(unittest.TestCase):
    """Contratos puros da revisao."""

    def test_dropin_environmentfile_explicito(self):
        d = m.render_dropin()
        self.assertIn(f'EnvironmentFile={m.ENV_FILE}\n', d)  # sem '-': ausente = falha, nunca sem token

    def test_renew_restrito_ao_cert_name_ip(self):
        svc, _ = m.render_renew_units()
        self.assertIn(f'renew --cert-name {m.PUBLIC_IP} ', svc)

    def test_hook_san_usa_checkip_exato_sem_grep(self):
        h = m.render_deploy_hook(ip='10.1.2.3')
        self.assertNotIn('grep', h)
        self.assertIn('-checkip 10.1.2.3', h)

    def test_rotate_again_removido(self):
        with self.assertRaises(SystemExit):
            m.main(['activate', '--rotate-again'])


@unittest.skipUnless(shutil.which('openssl'), 'sem openssl')
class HookSanReal(unittest.TestCase):
    """Executa a linha SAN do hook contra certs reais: IP exato passa, prefixo/sufixo falha."""

    def rodar(self, san_ip, alvo):
        d = tempfile.mkdtemp()
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256',
                        '-nodes', '-days', '1', '-subj', '/CN=x', '-addext', f'subjectAltName=IP:{san_ip}',
                        '-keyout', f'{d}/k.pem', '-out', f'{d}/cert.pem'], check=True, capture_output=True)
        linha = [l for l in m.render_deploy_hook(ip=alvo).splitlines() if 'checkip' in l and not l.startswith('#')][0]
        linha = linha.replace(m.live_dir(alvo), d).replace('"$LIVE', f'"{d}')
        return subprocess.run(['sh', '-ec', f'LIVE={d}\n{linha}'], capture_output=True).returncode

    def test_exato(self):
        self.assertEqual(self.rodar('10.1.2.3', '10.1.2.3'), 0)

    def test_prefixo_nao_casa(self):  # grep 'IP Address:10.1.2.3' casaria com 10.1.2.30
        self.assertNotEqual(self.rodar('10.1.2.30', '10.1.2.3'), 0)


class Lifecycle(unittest.TestCase):
    """activate/rollback/prepare com side effects de root mockados (run/chown/verify); arquivos em tmp."""

    def setUp(self):
        from unittest import mock
        self.mock = mock
        self.d = tempfile.mkdtemp()
        self.calls = []
        env = os.path.join(self.d, 'mascote-ponte.env')
        with open(env, 'w') as f:
            f.write('PONTE_TOKEN=antigo-token-xyz\nPONTE_LOG=1\n')
        os.chmod(env, 0o600)
        live = os.path.join(self.d, 'live'); os.makedirs(live)
        escrever(os.path.join(live, 'fullchain.pem'), '')
        self.env, self.live = env, live
        self.v = {'pre': [], 'local': [], 'final': []}
        st = os.path.join(self.d, 'state')
        p = [mock.patch.object(m, 'ENV_FILE', env),
             mock.patch.object(m, 'DROPIN', os.path.join(self.d, 'dropin', '10-loopback.conf')),
             mock.patch.object(m, 'STATE_DIR', st),
             mock.patch.object(m, 'BACKUP_DIR', st + '/backups'),
             mock.patch.object(m, 'ORIG_DIR', st + '/original'),
             mock.patch.object(m, 'POLICY_RC', os.path.join(self.d, 'policy-rc.d')),
             mock.patch.object(m, 'live_dir', lambda ip=None: live),
             mock.patch.object(m, 'ROOT_UID', os.getuid()),
             mock.patch.object(m, 'need_root', lambda: None),
             mock.patch.object(m.os, 'chown', lambda *a: None),
             mock.patch.object(m, 'run', self.fake_run),
             mock.patch.object(m, 'port_listeners', lambda port: ['127.0.0.1:8787']),
             mock.patch.object(m, 'verify', self.fake_verify),
             mock.patch.object(m, 'verify_local', lambda token: self.v['local'])]
        for x in p:
            x.start(); self.addCleanup(x.stop)

    def fake_run(self, cmd, check=True, **kw):
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, '', '')

    def fake_verify(self, token=None, require_closed=True, cafile=None, base=None):
        return self.v['pre'] if token is None else self.v['final']

    def ler(self, p):
        with open(p) as f:
            return f.read()

    def ativar(self):
        m.main(['activate', '--yes'])

    def test_activate_recusa_sem_env_antes_de_side_effects(self):
        os.remove(self.env)
        with self.assertRaises(SystemExit):
            self.ativar()
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(m.DROPIN))
        self.assertFalse(os.path.exists(m.ORIG_DIR))

    def test_https_ruim_aborta_antes_do_token(self):
        self.v['pre'] = ['/saude']
        with self.assertRaises(SystemExit):
            self.ativar()
        self.assertIn('antigo-token-xyz', self.ler(self.env))
        self.assertEqual(self.calls, [])

    def test_sucesso_snapshot_original_0600_e_ufw_depois_do_local(self):
        self.ativar()
        self.assertNotIn('antigo', self.ler(self.env))
        snap = os.path.join(m.ORIG_DIR, 'mascote-ponte.env')
        self.assertEqual(os.stat(snap).st_mode & 0o777, 0o600)
        self.assertIn('antigo-token-xyz', self.ler(snap))
        self.assertTrue(os.path.exists(os.path.join(m.ORIG_DIR, '10-loopback.conf.absent')))
        i_restart = self.calls.index(['systemctl', 'restart', m.SERVICE])
        i_ufw = next(i for i, c in enumerate(self.calls) if c[:2] == ['ufw', 'delete'])
        self.assertLess(i_restart, i_ufw)

    def test_local_falha_rollback_automatico_sem_tocar_ufw(self):
        self.v['local'] = ['bind']
        with self.assertRaises(SystemExit):
            self.ativar()
        self.assertIn('antigo-token-xyz', self.ler(self.env))
        self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)
        self.assertFalse(os.path.exists(m.DROPIN))
        self.assertFalse(any(c[0] == 'ufw' for c in self.calls))
        self.assertEqual(self.calls[-1], ['systemctl', 'restart', m.SERVICE])

    def test_final_falha_rollback_reabre_8787(self):
        self.v['final'] = ['/api/estado']
        with self.assertRaises(SystemExit):
            self.ativar()
        self.assertIn('antigo-token-xyz', self.ler(self.env))
        self.assertFalse(os.path.exists(m.DROPIN))
        self.assertIn(['ufw', 'allow', '8787/tcp'], self.calls)

    def test_snapshot_imutavel_rollback_volta_ao_original(self):
        self.ativar()
        m.main(['rollback-activate'])
        self.assertIn('antigo-token-xyz', self.ler(self.env))
        # segunda ativacao nao sobrescreve o snapshot original
        self.ativar()
        snap = os.path.join(m.ORIG_DIR, 'mascote-ponte.env')
        self.assertIn('antigo-token-xyz', self.ler(snap))
        m.main(['rollback-activate'])
        self.assertIn('antigo-token-xyz', self.ler(self.env))
        self.assertFalse(os.path.exists(m.DROPIN))

    def test_ja_ativado_recusa(self):
        self.ativar()
        n = len(self.calls)
        with self.assertRaises(SystemExit):
            self.ativar()
        self.assertEqual(len(self.calls), n)

    def test_preflight_exige_env_root_sem_ler(self):
        os.remove(self.env)
        with self.mock.patch.object(m.subprocess, 'run',
                                    lambda *a, **k: subprocess.CompletedProcess(a, 0, m.PUBLIC_IP, '')), \
             self.mock.patch.object(m, 'http_get', lambda url, *a, **k: (200 if 'saude' in url else 401, b'')), \
             self.mock.patch.object(m.os.path, 'exists', lambda p: p != self.env):
            probs = m.preflight(strict=False)
        self.assertTrue(any('env' in p for p in probs), probs)

    def test_prepare_aborta_com_policy_rc_preexistente(self):
        with open(m.POLICY_RC, 'w') as f:
            f.write('#!/bin/sh\nexit 0\n')
        with self.mock.patch.object(m, 'preflight', lambda strict=True: []), \
             self.mock.patch.object(m.shutil, 'which', lambda n: None):
            with self.assertRaises(SystemExit):
                m.main(['prepare'])
        self.assertFalse(any(c[0] == 'apt-get' for c in self.calls))
        self.assertEqual(self.ler(m.POLICY_RC), '#!/bin/sh\nexit 0\n')

    def test_rollback_prepare_nao_reexpoe_default(self):
        link = os.path.join(self.d, 'default')
        with self.mock.patch.object(m, 'NGINX_DEFAULT_LINK', link), \
             self.mock.patch.object(m, 'NGINX_LINK', os.path.join(self.d, 'x1')), \
             self.mock.patch.object(m, 'NGINX_SITE', os.path.join(self.d, 'x2')), \
             self.mock.patch.object(m, 'TIMER_UNIT', os.path.join(self.d, 'x3')), \
             self.mock.patch.object(m, 'RENEW_UNIT', os.path.join(self.d, 'x4')), \
             self.mock.patch.object(m, 'DEPLOY_HOOK', os.path.join(self.d, 'x5')):
            os.symlink('/etc/nginx/sites-available/default', link)
            m.backup(link); os.remove(link)
            m.main(['rollback-prepare'])
            self.assertFalse(os.path.lexists(link))


if __name__ == '__main__':
    unittest.main(verbosity=2)
