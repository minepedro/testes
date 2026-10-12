"""Fonte VPS da ponte real: sessoes `claude --remote-control` em tmux, alimentadas pelos hooks.

Id da sessao = 'v' + sha1(cwd real)[:10] (uma sessao claude por worktree). Assim a sessao criada
pela ponte tem id antes do primeiro hook, e sessoes abertas a mao em ~/repos/ tambem aparecem.

Criar sessao (POST /api/sessoes origem vps):
  clone sob demanda (repos.garantir_clone) -> worktree ~/repos/<nome>--<slug>
  (nova_branch a partir de origin/<branch>, ou checkout de <branch>) -> tmux 'mascote-<slug>' com
  `claude --remote-control 'TITULO' --permission-mode auto` -> aceita confianca (Down+Enter quando o
  dialogo aparece) -> espera SessionStart -> envia prompt (send-keys -l + Enter, nao documentado).
Sem repo: pasta ~/repos/_sem-repo/<slug>.
Comandos externos via self.run / self.tmux (injetaveis para testes).
"""
import hashlib
import json
import os
import shlex
import subprocess
import threading
import time

from comum import DIR_ESTADO, DIR_REPOS, ascii_tela, env_limpo, slug

TMUX = '/usr/bin/tmux'


def id_de_cwd(cwd):
    return 'v' + hashlib.sha1(os.path.realpath(cwd or '').rstrip('/').encode()).hexdigest()[:10]


def run_real(args, cwd=None, timeout=120, env=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])}: {(p.stderr or p.stdout).strip()[-300:]}")
    return p.stdout


class FonteVPS:
    def __init__(self, repos=None, run=None, dir_repos=DIR_REPOS, dir_estado=DIR_ESTADO):
        self.repos = repos
        self.run = run or run_real
        self.dir_repos = dir_repos
        self.arq_estado = os.path.join(dir_estado, 'sessoes_vps.json')
        self.trava = threading.RLock()
        self.sessoes = {}      # id -> dict
        self.prompts = []      # (ts, id, texto) dos UserPromptSubmit, para confirmar mensagens
        self.criadas = {}      # id -> {titulo, cwd, tmux, repo, branch, criado}
        self._carregar()

    # ---- persistencia minima (sessoes criadas + titulos) ----
    def _carregar(self):
        try:
            with open(self.arq_estado) as f:
                self.criadas = json.load(f)
        except (OSError, ValueError):
            self.criadas = {}
        for sid, c in self.criadas.items():
            self.sessoes[sid] = {'id': sid, 'origem': 'vps', 'titulo': c.get('titulo'), 'cwd': c.get('cwd'),
                                 'repo': c.get('repo'), 'branch': c.get('branch'), 'tmux': c.get('tmux'),
                                 'estado': 'desconectada', 'atualizado': c.get('criado', time.time())}

    def _salvar(self):
        os.makedirs(os.path.dirname(self.arq_estado), mode=0o700, exist_ok=True)
        tmp = self.arq_estado + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(self.criadas, f, ensure_ascii=True, indent=1)
        os.replace(tmp, self.arq_estado)

    # ---- eventos dos hooks ----
    def sessao_de(self, ev):
        cwd = ev.get('cwd') or ''
        sid = id_de_cwd(cwd)
        with self.trava:
            s = self.sessoes.get(sid)
            if not s:
                s = self.sessoes[sid] = {'id': sid, 'origem': 'vps', 'cwd': os.path.realpath(cwd),
                                         'titulo': os.path.basename(os.path.realpath(cwd)) or 'sessao',
                                         'estado': 'parada', 'atualizado': time.time()}
            for k in ('repo', 'branch', 'transcript_path', 'permission_mode'):
                if ev.get(k):
                    s[k] = ev[k]
            if ev.get('session_id'):
                s['claude_session_id'] = ev['session_id']
            return s

    def evento(self, ev):
        s = self.sessao_de(ev)
        e = ev.get('evento')
        with self.trava:
            if e == 'SessionStart':
                s['estado'] = 'parada'
                s['iniciada'] = True
            elif e == 'UserPromptSubmit':
                s['estado'] = 'trabalhando'
                if ev.get('prompt'):
                    s['ultimo_prompt'] = ev['prompt']
                    self.prompts.append((time.time(), s['id'], ev['prompt']))
                    del self.prompts[:-50]
            elif e == 'PostToolUse':
                if s.get('estado') != 'esperando':
                    s['estado'] = 'trabalhando'
            elif e == 'Stop':
                s['estado'] = 'parada'
                if ev.get('last_assistant_message'):
                    s['ultima_resposta'] = ev['last_assistant_message']
            elif e == 'Notification':
                if ev.get('notification_type') in ('permission_prompt', 'elicitation_dialog'):
                    s['estado'] = 'esperando'
                elif ev.get('notification_type') == 'idle_prompt':
                    s['estado'] = 'parada'
            elif e == 'SessionEnd':
                s['estado'] = 'encerrada'
            elif e == 'pedido':
                s['estado'] = 'esperando'
            s['atualizado'] = time.time()
        return s

    def pedido_terminou(self, sid, ainda_pendentes):
        with self.trava:
            s = self.sessoes.get(sid)
            if s and s.get('estado') == 'esperando' and not ainda_pendentes:
                s['estado'] = 'trabalhando'
                s['atualizado'] = time.time()

    def listar(self):
        with self.trava:
            vivos = self._tmux_vivos()
            res = []
            for s in self.sessoes.values():
                s = dict(s)
                if s.get('tmux') and vivos is not None and s['tmux'] not in vivos and s['estado'] != 'encerrada':
                    s['estado'] = 'encerrada'
                res.append(s)
            return res

    def get(self, sid):
        with self.trava:
            return self.sessoes.get(sid)

    def titulos(self):
        with self.trava:
            return {s.get('titulo') for s in self.sessoes.values() if s.get('titulo')}

    # ---- tmux ----
    def _tmux_vivos(self):
        try:
            out = self.run([TMUX, 'list-sessions', '-F', '#{session_name}'], timeout=5)
            return set(out.split())
        except Exception:
            return None

    def _tmux_por_cwd(self, cwd):
        """Sessao tmux cujo painel roda claude nesse cwd (sessoes abertas a mao)."""
        try:
            out = self.run([TMUX, 'list-panes', '-a', '-F', '#{pane_id}|#{pane_current_path}|#{pane_current_command}'], timeout=5)
        except Exception:
            return None
        for linha in out.splitlines():
            pid, path, cmd = (linha.split('|') + ['', '', ''])[:3]
            if cwd and os.path.realpath(path) == os.path.realpath(cwd) and cmd == 'claude':
                return pid
        return None

    def _pane(self, nome):
        try:
            return self.run([TMUX, 'capture-pane', '-p', '-t', nome], timeout=5)
        except Exception:
            return ''

    def _send(self, nome, *teclas, literal=None):
        if literal is not None:
            self.run([TMUX, 'send-keys', '-t', nome, '-l', literal], timeout=5)
        if teclas:
            self.run([TMUX, 'send-keys', '-t', nome, *teclas], timeout=5)

    # ---- criar sessao ----
    def preparar_pasta(self, repo, branch, nova_branch, nome_slug):
        if not repo:
            p = os.path.join(self.dir_repos, '_sem-repo', nome_slug)
            os.makedirs(p, exist_ok=True)
            return p, None
        base = self.repos.garantir_clone(repo)
        wt = f"{base}--{nome_slug}"
        if os.path.exists(wt):
            raise ValueError('worktree ja existe: ' + os.path.basename(wt))
        if nova_branch:
            self.run(['git', '-C', base, 'worktree', 'add', '-b', nova_branch, wt, f'origin/{branch}'])
            return wt, nova_branch
        if branch:
            # branch remota existente: cria local acompanhando a remota (ou usa a local)
            try:
                self.run(['git', '-C', base, 'worktree', 'add', wt, branch])
            except RuntimeError:
                self.run(['git', '-C', base, 'worktree', 'add', '--track', '-b', branch, wt, f'origin/{branch}'])
            return wt, branch
        self.run(['git', '-C', base, 'worktree', 'add', '--detach', wt])
        return wt, None

    def criar(self, repo, branch, nova_branch, titulo, prompt, espera_inicio=90):
        nome_slug = slug(titulo, 24) + '-' + hashlib.sha1(str(time.time()).encode()).hexdigest()[:4]
        pasta, br = self.preparar_pasta(repo, branch, nova_branch, nome_slug)
        sid = id_de_cwd(pasta)
        tmux = 'mascote-' + nome_slug
        titulo_a = ascii_tela(titulo, 80) or nome_slug
        with self.trava:
            self.criadas[sid] = {'titulo': titulo_a, 'cwd': os.path.realpath(pasta), 'tmux': tmux, 'repo': repo,
                                 'branch': br, 'criado': time.time()}
            self._salvar()
            self.sessoes[sid] = {'id': sid, 'origem': 'vps', 'titulo': titulo_a, 'cwd': os.path.realpath(pasta),
                                 'repo': repo, 'branch': br, 'tmux': tmux, 'estado': 'parada',
                                 'atualizado': time.time()}
        env = ' '.join(f'-u {k}' for k in os.environ if k.startswith(('ANTHROPIC_', 'CLAUDE_CODE_USE_')))
        cmd = f"env {env} claude --remote-control {shlex.quote(titulo_a)} --permission-mode auto"
        self.run([TMUX, 'new-session', '-d', '-s', tmux, '-c', pasta, '-x', '200', '-y', '50', cmd],
                 env=env_limpo())
        threading.Thread(target=self._iniciar, args=(sid, tmux, prompt, espera_inicio), daemon=True).start()
        return sid

    def _iniciar(self, sid, tmux, prompt, espera):
        fim = time.time() + espera
        confiou = False
        while time.time() < fim:
            tela = self._pane(tmux).replace(' ', '')
            if not confiou and 'Itrustthisfolder' in tela:
                time.sleep(1)
                self._send(tmux, 'Down')
                time.sleep(1)
                self._send(tmux, 'Enter')
                confiou = True
            s = self.get(sid) or {}
            if s.get('iniciada'):
                break
            time.sleep(1)
        if prompt:
            time.sleep(3)
            self.mensagem(sid, prompt, confirmar=False)

    # ---- mensagem ----
    def mensagem(self, sid, texto, confirmar=True, espera=10):
        s = self.get(sid)
        if s and not s.get('tmux'):
            s['tmux'] = self._tmux_por_cwd(s.get('cwd'))
        if not s or not s.get('tmux'):
            raise LookupError('sessao sem tmux conhecido')
        t0 = time.time()
        self._send(s['tmux'], literal=texto)
        time.sleep(0.3)
        self._send(s['tmux'], 'Enter')
        if not confirmar:
            return True
        while time.time() - t0 < espera:
            with self.trava:
                if any(ts >= t0 - 0.5 and i == sid and p.strip() == texto.strip() for ts, i, p in self.prompts):
                    return True
            time.sleep(0.3)
        return False

    def encerrar(self, sid):
        s = self.get(sid)
        if s and s.get('tmux'):
            try:
                self.run([TMUX, 'kill-session', '-t', s['tmux']], timeout=5)
            except Exception:
                pass
