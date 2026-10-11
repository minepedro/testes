#!/usr/bin/env python3
"""Ponte do mascote: entrega as sessoes do Claude Code ao ESP32 e recebe as acoes.

Versao 0 (demo): as sessoes sao de exemplo e mudam sozinhas (uma pede permissao de
tempos em tempos), para testar o caminho inteiro: Wi-Fi, ponte, lista, Aprovar e Recusar.
A fonte real (sessoes do claude.ai/code) entra depois no lugar de FonteDemo, com os
mesmos metodos listar() e agir().

So usa a biblioteca padrao do Python 3.8+. Para rodar:

    PONTE_TOKEN=uma-senha-longa python3 ponte.py            # porta 8787
    PONTE_TOKEN=uma-senha-longa python3 ponte.py --porta 9000

API (todas pedem o cabecalho X-Token com o mesmo valor de PONTE_TOKEN):
    GET  /api/estado   -> {"hora": "14:05", "sessoes": [ {...}, ... ]}
    POST /api/acao     <- {"id": "s1", "acao": "aprovar" | "recusar"}
    GET  /saude        -> "ok" (sem token; para testar no navegador)

Cada sessao: id, title, repo, branch, status (waiting | working | idle | done),
ago, last, reply e ask ({tool, text} ou null). Os textos vao sem acento, porque a
fonte da tela por enquanto so tem ASCII.
"""
import argparse
import hmac
import json
import os
import random
import threading
import time
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def ascii_tela(texto):
    """Tira acentos e troca simbolos que a fonte da tela nao tem."""
    if texto is None:
        return None
    texto = texto.replace('·', '-').replace('…', '...').replace('—', '-').replace('–', '-')
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')


def ha_quanto(segundos):
    if segundos < 60:
        return 'agora'
    if segundos < 3600:
        return f'{int(segundos // 60)} min'
    if segundos < 86400:
        return f'{int(segundos // 3600)} h'
    return f'{int(segundos // 86400)} d'


class FonteDemo:
    """Sessoes de exemplo (as mesmas do prototipo web), que mudam com o tempo."""

    PEDIDOS = [
        ('Bash', 'git push origin main'),
        ('Edit', 'software/bridge/ponte.py'),
        ('Bash', 'rm -rf node_modules && npm ci'),
        ('Bash', 'npm run deploy'),
    ]

    def __init__(self):
        agora = time.time()
        self.trava = threading.Lock()
        self.sessoes = [
            dict(id='s1', title='Corrigir build do site', repo='lookvision-site', branch='fix/build', status='waiting',
                 desde=agora - 240, last='O build quebrava no passo de lint. Corrigi 3 erros e o build passou local.',
                 reply='O build quebrava por tres erros de lint. Corrigi os tres e o build passou aqui. Para publicar preciso rodar npm run deploy e espero a sua aprovacao.',
                 ask=dict(tool='Bash', text='npm run deploy')),
            dict(id='s2', title='UI do mascote', repo='testes', branch='main', status='working', desde=agora - 20,
                 last='Editando firmware/mascote: lista de sessoes e botoes Aprovar e Recusar.',
                 reply='Estou fazendo a lista de sessoes do mascote. Ja tenho a tela de cada sessao e os botoes. Falta ligar a ponte de verdade.', ask=None),
            dict(id='s3', title='Ponte das sessoes', repo='mascote-claude', branch='bridge', status='idle', desde=agora - 3600,
                 last='Esqueleto da ponte pronto. Falta ler as sessoes do claude.ai/code.',
                 reply='O esqueleto da ponte esta pronto. Ainda nao le as sessoes reais; o proximo passo e a autenticacao.', ask=None),
            dict(id='s4', title='Guia de compras', repo='testes', branch='main', status='done', desde=agora - 86400,
                 last='PDF gerado com marcas, lojas e precos estimados.',
                 reply='O guia de compras em PDF esta pronto, em docs/guia-de-compras.pdf.', ask=None),
            dict(id='s5', title='Revisar PR 214', repo='api-pagamentos', branch='main', status='done', desde=agora - 2 * 86400,
                 last='Revisao enviada com 2 comentarios bloqueantes.',
                 reply='Revisei o PR 214 e deixei 2 comentarios bloqueantes: validar o valor antes de gravar e cobrir o estorno parcial.', ask=None),
            dict(id='s6', title='Duvida sobre Tailwind', repo=None, branch=None, status='done', desde=agora - 3 * 86400,
                 last='Expliquei a diferenca entre utilitarios e componentes.',
                 reply='Use utilitarios primeiro e extraia um componente quando o padrao se repetir tres vezes.', ask=None),
        ]
        self.proximo_pedido = agora + 45

    def _simular(self):
        """De tempos em tempos uma sessao trabalhando ou parada pede permissao."""
        agora = time.time()
        if agora < self.proximo_pedido:
            return
        self.proximo_pedido = agora + random.uniform(40, 80)
        livres = [s for s in self.sessoes if s['status'] in ('working', 'idle')]
        if not livres or any(s['status'] == 'waiting' for s in self.sessoes):
            return
        s = random.choice(livres)
        tool, text = random.choice(self.PEDIDOS)
        s.update(status='waiting', desde=agora, ask=dict(tool=tool, text=text),
                 last=f'Quer rodar {text} e espera a sua aprovacao.')

    def listar(self):
        with self.trava:
            self._simular()
            agora = time.time()
            return [dict(id=s['id'], title=s['title'], repo=s['repo'], branch=s['branch'], status=s['status'],
                         ago=ha_quanto(agora - s['desde']), last=s['last'], reply=s['reply'], ask=s['ask'])
                    for s in self.sessoes]

    def agir(self, sid, acao):
        with self.trava:
            s = next((x for x in self.sessoes if x['id'] == sid), None)
            if s is None:
                return False, 'sessao nao encontrada'
            if s['status'] != 'waiting' or not s['ask']:
                return False, 'a sessao nao esta pedindo nada'
            pedido = s['ask']['text']
            if acao == 'aprovar':
                s.update(status='working', ask=None, desde=time.time(), last=f'Aprovado pelo mascote: {pedido}. Rodando...')
            elif acao == 'recusar':
                s.update(status='idle', ask=None, desde=time.time(), last=f'Recusado pelo mascote: {pedido}.')
            else:
                return False, 'acao desconhecida'
            return True, 'ok'


def criar_handler(fonte, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'PonteMascote/0'

        def _responder(self, codigo, corpo, tipo='application/json'):
            dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=True).encode()
            self.send_response(codigo)
            self.send_header('Content-Type', tipo)
            self.send_header('Content-Length', str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def _autorizado(self):
            recebido = self.headers.get('X-Token', '')
            if hmac.compare_digest(recebido.encode(), token.encode()):
                return True
            self._responder(401, {'erro': 'token invalido'})
            return False

        def do_GET(self):
            if self.path == '/saude':
                return self._responder(200, b'ok', 'text/plain')
            if self.path != '/api/estado':
                return self._responder(404, {'erro': 'nao existe'})
            if not self._autorizado():
                return
            sessoes = fonte.listar()
            for s in sessoes:
                for k in ('title', 'repo', 'branch', 'last', 'reply', 'ago'):
                    s[k] = ascii_tela(s[k])
                if s['ask']:
                    s['ask'] = {k: ascii_tela(v) for k, v in s['ask'].items()}
            self._responder(200, {'hora': time.strftime('%H:%M'), 'sessoes': sessoes})

        def do_POST(self):
            if self.path != '/api/acao':
                return self._responder(404, {'erro': 'nao existe'})
            if not self._autorizado():
                return
            try:
                tamanho = min(int(self.headers.get('Content-Length', 0)), 4096)
                pedido = json.loads(self.rfile.read(tamanho) or b'{}')
                ok, msg = fonte.agir(str(pedido.get('id', '')), str(pedido.get('acao', '')))
            except (ValueError, json.JSONDecodeError):
                return self._responder(400, {'erro': 'json invalido'})
            print(f'acao: {pedido.get("acao")} em {pedido.get("id")} -> {msg}', flush=True)
            self._responder(200 if ok else 409, {'ok': ok, 'msg': msg})

        def log_message(self, fmt, *args):
            if os.environ.get('PONTE_LOG'):
                super().log_message(fmt, *args)

    return Handler


def main():
    ap = argparse.ArgumentParser(description='Ponte do mascote (demo)')
    ap.add_argument('--porta', type=int, default=8787)
    ap.add_argument('--host', default='0.0.0.0')
    args = ap.parse_args()
    token = os.environ.get('PONTE_TOKEN', '')
    if len(token) < 12:
        raise SystemExit('Defina PONTE_TOKEN com pelo menos 12 caracteres (o mesmo valor vai no config.h do mascote).')
    servidor = ThreadingHTTPServer((args.host, args.porta), criar_handler(FonteDemo(), token))
    print(f'Ponte do mascote (demo) ouvindo em {args.host}:{args.porta}. Teste: http://<ip>:{args.porta}/saude', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
