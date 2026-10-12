"""Criar sessao na NUVEM: `claude --cloud 'tarefa'` INTERATIVO (pty) dentro do clone na branch.
(`-p` com --cloud sem id da erro.) Baseado em ~/mascote-cli-lab/cloud/drive.py. NAO testado pela
ponte v1 (regra: nao criar sessoes na nuvem nos testes)."""
import os
import pty
import re
import select
import subprocess
import time

from comum import env_limpo


def criar(pasta, branch, prompt, limite=90):
    if branch:
        subprocess.run(['git', '-C', pasta, 'checkout', branch], capture_output=True, timeout=30, check=True)
    env = env_limpo()
    env['TERM'] = 'xterm'
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(pasta)
        os.execvpe('claude', ['claude', '--cloud', prompt], env)
    buf, t0, confiou = b'', time.time(), False
    try:
        while time.time() - t0 < limite:
            r, _, _ = select.select([fd], [], [], 1)
            if r:
                try:
                    buf += os.read(fd, 65536)
                except OSError:
                    break
            txt = re.sub(rb'\x1b\[[0-9;?]*[a-zA-Z]', b'', buf).replace(b' ', b'')
            if not confiou and b'Itrustthisfolder' in txt:
                time.sleep(1); os.write(fd, b'\x1b[B'); time.sleep(1.5); os.write(fd, b'\r'); confiou = True
            m = re.search(rb'session_[0-9A-Za-z]{10,}', txt)
            if m:
                return m.group().decode()
    finally:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    raise RuntimeError('id da sessao nuvem nao apareceu')
