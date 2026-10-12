"""Repositorios do GitHub via gh (decisoes 22 e 25): pessoais + organizacoes, cache 5 min.
Clona sob demanda em ~/repos/<nome>. O runner de comandos e injetavel (testes sem rede)."""
import json
import os
import subprocess
import threading
import time

from comum import DIR_REPOS


def run_real(args, cwd=None, timeout=120):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])}: {(p.stderr or p.stdout).strip()[-300:]}")
    return p.stdout


class Repos:
    CAMPOS = 'nameWithOwner,isPrivate,defaultBranchRef'

    def __init__(self, run=None, dir_repos=DIR_REPOS, ttl=300):
        self.run = run or run_real
        self.dir = dir_repos
        self.ttl = ttl
        self._cache = (0, None)
        self._trava = threading.Lock()

    def pasta(self, nome_completo):
        return os.path.join(self.dir, nome_completo.split('/')[-1])

    def clonado(self, nome_completo):
        return os.path.isdir(os.path.join(self.pasta(nome_completo), '.git'))

    def listar(self):
        with self._trava:
            t, dados = self._cache
            if dados is None or time.time() - t > self.ttl:
                donos = [None] + [o['login'] for o in json.loads(self.run(['gh', 'api', 'user/orgs']) or '[]')]
                dados = []
                for dono in donos:
                    args = ['gh', 'repo', 'list'] + ([dono] if dono else []) + ['--limit', '500', '--json', self.CAMPOS]
                    for r in json.loads(self.run(args) or '[]'):
                        dados.append({'nome': r['nameWithOwner'], 'privado': bool(r.get('isPrivate')),
                                      'branch_padrao': (r.get('defaultBranchRef') or {}).get('name') or ''})
                self._cache = (time.time(), dados)
        return [dict(r, clonado=self.clonado(r['nome'])) for r in dados]

    def branches(self, nome_completo):
        out = self.run(['gh', 'api', '--paginate', f'repos/{nome_completo}/branches?per_page=100', '--jq', '.[].name'])
        return [{'nome': b} for b in out.split() if b]

    def garantir_clone(self, nome_completo):
        """Clona na primeira vez; depois so busca (fetch). Devolve a pasta."""
        p = self.pasta(nome_completo)
        if not self.clonado(nome_completo):
            os.makedirs(self.dir, exist_ok=True)
            self.run(['gh', 'repo', 'clone', nome_completo, p], timeout=300)
        else:
            self.run(['git', '-C', p, 'fetch', '--prune', 'origin'], timeout=120)
        return p
