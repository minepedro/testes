#!/usr/bin/env python3
"""Reabre no `tmux -L mascote` as sessoes do mascote que cairam (reboot, servidor tmux morto).

  python3 reabrir_sessoes.py            # reabre (claude --continue --remote-control ... se houver conversa)
  python3 reabrir_sessoes.py --listar   # so mostra o que faria
  python3 reabrir_sessoes.py --rc       # tambem garante a sessao 'mascote-rc' (claude remote-control) em ~/repos/testes-lab
Ignora titulos 'TESTE...', pastas inexistentes e sessoes encerradas de proposito (/exit).
A ponte faz o mesmo sozinha no startup (config reabrir_no_inicio, padrao true).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comum import env_limpo  # noqa: E402
from fonte_vps import TMUX, FonteVPS, comando_reabrir, reabrir_caidas, run_real  # noqa: E402

RC_NOME, RC_DIR = 'mascote-rc', os.path.expanduser('~/repos/testes-lab')
RC_CMD = 'claude remote-control --name mascote-rc --permission-mode auto --spawn worktree'


def garantir_rc():
    vivos = FonteVPS(run=run_real)._tmux_vivos() or set()
    if RC_NOME in vivos or not os.path.isdir(RC_DIR):
        return False
    run_real([*TMUX, 'new-session', '-d', '-s', RC_NOME, '-c', RC_DIR, '-x', '200', '-y', '50', RC_CMD], env=env_limpo())
    for _ in range(30):  # confianca na pasta / "Enable Remote Control? (y/n)"
        time.sleep(1)
        tela = run_real([*TMUX, 'capture-pane', '-p', '-t', RC_NOME]).replace(' ', '')
        if 'Itrustthisfolder' in tela:
            run_real([*TMUX, 'send-keys', '-t', RC_NOME, 'Down']); time.sleep(1)
            run_real([*TMUX, 'send-keys', '-t', RC_NOME, 'Enter'])
        elif '(y/n)' in tela:
            run_real([*TMUX, 'send-keys', '-t', RC_NOME, 'y', 'Enter'])
    return True


def main():
    f = FonteVPS(run=run_real)
    if '--listar' in sys.argv:
        vivos = f._tmux_vivos() or set()
        for sid, c in f.criadas.items():
            print(sid, c.get('tmux'), 'VIVA' if c.get('tmux') in vivos else 'caida',
                  'encerrada' if c.get('encerrada') else '', repr(c.get('titulo')), comando_reabrir(c.get('titulo') or '', c.get('cwd') or '/'))
        return
    if '--rc' in sys.argv:
        print('mascote-rc', 'reaberta' if garantir_rc() else 'ja viva/sem pasta')
    for sid, tm, cmd in reabrir_caidas(f):
        print('reaberta', sid, tm, cmd)
    time.sleep(15)  # deixa _iniciar aceitar a confianca


if __name__ == '__main__':
    main()
