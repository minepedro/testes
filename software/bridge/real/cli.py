#!/usr/bin/env python3
"""Cliente de linha de comando para a ponte real (testes manuais/integracao). Le o token de
~/.config/mascote/ponte.env; nunca imprime o token.
  python3 cli.py GET /api/sessoes
  python3 cli.py POST /api/pedidos/<id>/resposta '{"decisao":"aprovar"}'
Porta: env PORTA (padrao: ~/.config/mascote/unit.env ou 8791)."""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum  # noqa: E402

porta = os.environ.get('PORTA') or comum.ler_env_arquivo(os.path.join(comum.DIR_CONFIG, 'unit.env')).get('PORTA', '8791')


def chamar(metodo, path, corpo=None, timeout=150):
    r = urllib.request.Request(f'http://127.0.0.1:{porta}{path}', method=metodo,
                               data=json.dumps(corpo).encode() if corpo is not None else None,
                               headers={'X-Token': comum.token_aparelho(), 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.status, json.loads(f.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


if __name__ == '__main__':
    corpo = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    st, b = chamar(sys.argv[1], sys.argv[2], corpo)
    print(st, json.dumps(b, indent=1, ensure_ascii=True))
