#!/usr/bin/env python3
"""Integracao REAL na VPS (ponte na 8791). Uso: python3 integracao_real.py <id_sessao_vps> <passo>
Passos: msg_pedido (mensagem -> pedido Bash -> aprovar via /api/pedidos)
        compat (mensagem -> pedido -> recusar via /api/acao com id de sessao)
        pergunta (mensagem -> AskUserQuestion multipla -> responder via /api/pedidos)
        dedupe (sessao bridge da VPS nao aparece duplicada)
Pre-requisito do pedido: ask rule SO no worktree de lab (.claude/settings.local.json)."""
import json
import sys
import time

from cli import chamar

SID, PASSO = sys.argv[1], sys.argv[2]


def esperar(cond, limite=120, passo=2):
    t = time.time()
    while time.time() - t < limite:
        r = cond()
        if r:
            return r
        time.sleep(passo)
    return None


def pendente():
    st, lst = chamar('GET', '/api/pedidos?pendentes=1')
    return [p for p in lst if p['sessao_id'] == SID and p['estado'] == 'pendente']


def parada():
    st, s = chamar('GET', '/api/sessoes/' + SID)
    return s if s['estado'] == 'parada' else None


def msg(texto):
    esperar(parada, 120)
    st, r = chamar('POST', f'/api/sessoes/{SID}/mensagem', {'texto': texto})
    print('mensagem ->', st, r)
    return st


if PASSO == 'msg_pedido':
    msg('Rode exatamente o comando bash: echo mascote-ponte-aprovar (sem mais nada) e me diga a saida.')
    p = esperar(pendente)
    print('pedido:', json.dumps(p[0] if p else None)[:600])
    st, e = chamar('GET', '/api/estado')
    print('compat ask:', [x['ask'] for x in e['sessoes'] if x['id'] == SID], [x['status'] for x in e['sessoes'] if x['id'] == SID])
    print('resposta ->', *chamar('POST', f"/api/pedidos/{p[0]['id']}/resposta", {'decisao': 'aprovar'}))
    print('repetida ->', *chamar('POST', f"/api/pedidos/{p[0]['id']}/resposta", {'decisao': 'recusar'}))
    s = esperar(parada, 120)
    print('ultima_resposta:', (s or {}).get('ultima_resposta', '')[:300])
elif PASSO == 'compat':
    msg('Rode exatamente o comando bash: echo mascote-ponte-recusar (sem mais nada).')
    p = esperar(pendente)
    print('acao antes do estado ->', *chamar('POST', '/api/acao', {'id': SID, 'acao': 'recusar'}))
    st, e = chamar('GET', '/api/estado')
    print('compat:', [(x['status'], x['ask']) for x in e['sessoes'] if x['id'] == SID])
    print('acao ->', *chamar('POST', '/api/acao', {'id': SID, 'acao': 'recusar'}))
    print('acao atrasada ->', *chamar('POST', '/api/acao', {'id': SID, 'acao': 'aprovar'}))
    s = esperar(parada, 120)
    print('ultima_resposta:', (s or {}).get('ultima_resposta', '')[:300])
elif PASSO == 'pergunta':
    msg('Use a ferramenta AskUserQuestion para me perguntar UMA pergunta de multipla escolha (multiSelect true) '
        '"Quais cores?" com opcoes Azul, Vermelho, Verde. Depois diga exatamente quais escolhi.')
    p = esperar(pendente)
    print('pedido:', json.dumps(p[0] if p else None)[:700])
    q = p[0]['perguntas'][0]
    st, e = chamar('GET', '/api/estado')
    print('compat ask:', [x['ask'] for x in e['sessoes'] if x['id'] == SID])
    print('compat aprovar pergunta ->', *chamar('POST', '/api/acao', {'id': SID, 'acao': 'aprovar'}))
    print('resposta ->', *chamar('POST', f"/api/pedidos/{p[0]['id']}/resposta",
                                 {'decisao': 'aprovar', 'respostas': {q['pergunta']: ['Azul', 'Vermelho']}}))
    s = esperar(parada, 120)
    print('ultima_resposta:', (s or {}).get('ultima_resposta', '')[:300])
elif PASSO == 'dedupe':
    st, lst = chamar('GET', '/api/sessoes')
    print([(x['id'], x['origem'], x['titulo'], x['somente_leitura']) for x in lst if 'PONTE v1' in x['titulo']])
