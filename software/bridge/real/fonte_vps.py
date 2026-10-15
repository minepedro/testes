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
import secrets
import shlex
import subprocess
import threading
import time

from comum import DIR_ESTADO, DIR_REPOS, ascii_tela, env_limpo, slug

# servidor tmux proprio (mascote-tmux.service), nunca o socket padrao
TMUX = ['/usr/bin/tmux', '-L', os.environ.get('MASCOTE_TMUX_SOCKET', 'mascote')]


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
                if self.criadas.get(s['id'], {}).pop('encerrada', None):
                    self._salvar()
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
                # saida deliberada (/exit, logout): nao reabrir sozinho depois
                if ev.get('reason') in ('prompt_input_exit', 'logout') and s['id'] in self.criadas:
                    self.criadas[s['id']]['encerrada'] = True
                    self._salvar()
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

    def do_mascote(self, sid=None, cwd=None):
        """Sessao criada pelo mascote (registrada em criadas), por id ou cwd (decisao 23 revisada)."""
        with self.trava:
            if sid and sid in self.criadas:
                return True
            if cwd:
                c = os.path.realpath(cwd).rstrip('/') + '/'
                for x in self.criadas.values():
                    p = (x.get('cwd') or '').rstrip('/')
                    if p and c.startswith(p + '/'):
                        return True
        return False

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
            out = self.run([*TMUX, 'list-sessions', '-F', '#{session_name}'], timeout=5)
            return set(out.split())
        except Exception:
            return None

    def _tmux_por_cwd(self, cwd):
        """Sessao tmux cujo painel roda claude nesse cwd (sessoes abertas a mao)."""
        try:
            out = self.run([*TMUX, 'list-panes', '-a', '-F', '#{pane_id}|#{pane_current_path}|#{pane_current_command}'], timeout=5)
        except Exception:
            return None
        for linha in out.splitlines():
            pid, path, cmd = (linha.split('|') + ['', '', ''])[:3]
            if cwd and os.path.realpath(path) == os.path.realpath(cwd) and cmd == 'claude':
                return pid
        return None

    def _pane(self, nome):
        try:
            return self.run([*TMUX, 'capture-pane', '-p', '-t', nome], timeout=5)
        except Exception:
            return ''

    def _send(self, nome, *teclas, literal=None):
        if literal is not None:
            self.run([*TMUX, 'send-keys', '-t', nome, '-l', literal], timeout=5)
        if teclas:
            self.run([*TMUX, 'send-keys', '-t', nome, *teclas], timeout=5)

    # ---- criar sessao ----
    def _worktree_novo(self, base, branch_base, nova_branch, nome_slug):
        """Worktree NOVO com branch propria. Nunca faz checkout de <branch> (ela ja esta no clone base).
        Sem nova_branch usa mascote/<slug>. Se pasta/branch ja existir, gera outro slug."""
        existentes = set()
        try:
            existentes = set(self.run(['git', '-C', base, 'branch', '--format=%(refname:short)']).split())
        except Exception:  # noqa: BLE001
            pass
        ref = f'origin/{branch_base}' if branch_base else 'HEAD'
        for i in range(20):
            sl = nome_slug if i == 0 else f'{nome_slug}-{secrets.token_hex(2)}'
            br = nova_branch or f'mascote/{sl}'
            wt = f'{base}--{sl}'
            if os.path.exists(wt) or (br in existentes and not nova_branch):
                continue
            if nova_branch and br in existentes:
                raise ValueError('branch ja existe: ' + br)
            self.run(['git', '-C', base, 'worktree', 'add', '-b', br, wt, ref])
            return wt, br
        raise ValueError('nao achei nome livre para o worktree')

    def preparar_pasta(self, repo, branch, nova_branch, nome_slug):
        if not repo:
            p = os.path.join(self.dir_repos, '_sem-repo', nome_slug)
            os.makedirs(p, exist_ok=True)
            return p, None
        base = self.repos.garantir_clone(repo)
        return self._worktree_novo(base, branch, nova_branch, nome_slug)

    def vincular(self, sid, repo, branch):
        """Sessao sem repo: clona, cria worktree mascote/<slug> e avisa a sessao. Devolve (pasta, branch)."""
        s = self.get(sid)
        nome_slug = slug(s.get('titulo') or 'sessao', 24) + '-' + secrets.token_hex(2)
        base = self.repos.garantir_clone(repo)
        if not branch:
            try:
                branch = self.run(['git', '-C', base, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD']).strip()
                branch = branch.removeprefix('origin/') or None
            except Exception:  # noqa: BLE001
                branch = None
        pasta, br = self._worktree_novo(base, branch, None, nome_slug)
        texto = (f'O repositorio {repo} foi clonado em {pasta} na branch {br}. '
                 'A partir de agora trabalhe nessa pasta (use cd e caminhos absolutos).')
        with self.trava:
            for d in (self.sessoes.get(sid), self.criadas.get(sid)):
                if d is not None:
                    d.update(repo=repo, branch=br, cwd_trabalho=pasta)
            self._salvar()
        ok = self.mensagem(sid, texto)
        return pasta, br, ok

    def criar(self, repo, branch, nova_branch, titulo, prompt, espera_inicio=90):
        nome_slug = slug(titulo, 24) + '-' + secrets.token_hex(2)
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
        self.run([*TMUX, 'new-session', '-d', '-s', tmux, '-c', pasta, '-x', '200', '-y', '50', cmd],
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
        with self.trava:
            if sid in self.criadas:
                self.criadas[sid]['encerrada'] = True
                self._salvar()
        if s and s.get('tmux'):
            try:
                self.run([*TMUX, 'kill-session', '-t', s['tmux']], timeout=5)
            except Exception:
                pass


# ---- reabertura (apos reboot / queda do servidor tmux) ----
def tem_conversa(cwd, dir_projetos=os.path.expanduser('~/.claude/projects')):
    """True se o claude tem transcript salvo para esse cwd (entao --continue retoma a conversa)."""
    d = os.path.join(dir_projetos, os.path.realpath(cwd).replace('/', '-').replace('.', '-').replace('_', '-'))
    try:
        return any(n.endswith('.jsonl') for n in os.listdir(d))
    except OSError:
        return False


def comando_reabrir(titulo, cwd):
    cont = '--continue ' if tem_conversa(cwd) else ''
    return f"claude {cont}--remote-control {shlex.quote(titulo)} --permission-mode auto"


def reabrir_caidas(fonte, prefixos_ignorar=('TESTE',), aceitar=True, dormir=time.sleep):
    """Reabre no `tmux -L mascote` as sessoes salvas cuja tmux morreu. Devolve [(sid, tmux, comando)].

    Ignora: titulo com prefixo de teste, pasta inexistente, marcada 'encerrada' (saida deliberada).
    """
    vivos = fonte._tmux_vivos()
    if vivos is None:  # servidor tmux fora: nao adianta (mascote-tmux.service cuida)
        return []
    feitas = []
    with fonte.trava:
        itens = list(fonte.criadas.items())
    for sid, c in itens:
        tmux, cwd, tit = c.get('tmux'), c.get('cwd'), c.get('titulo') or ''
        if not tmux or tmux in vivos or c.get('encerrada') or tit.upper().startswith(prefixos_ignorar):
            continue
        if not cwd or not os.path.isdir(cwd):
            continue
        cmd = comando_reabrir(tit, cwd)
        fonte.run([*TMUX, 'new-session', '-d', '-s', tmux, '-c', cwd, '-x', '200', '-y', '50', cmd], env=env_limpo())
        if aceitar:
            threading.Thread(target=fonte._iniciar, args=(sid, tmux, None, 60), daemon=True).start()
        feitas.append((sid, tmux, cmd))
    return feitas
