# Ponte do mascote

Programa pequeno em Python que fica na VPS, entrega as sessões ao ESP32 e recebe
Aprovar e Recusar. Só usa a biblioteca padrão do Python 3.8+.

**Versão atual: demo.** As sessões são de exemplo (as do protótipo web) e mudam
sozinhas: de 40 em 40 a 80 s uma sessão pede permissão, para testar os botões.
A leitura das sessões reais do claude.ai/code entra no lugar de `FonteDemo`.

## Rodar na VPS (Linux)

```bash
mkdir -p /opt/mascote && cp ponte.py /opt/mascote/
export PONTE_TOKEN='uma-senha-longa-que-voce-inventa'
TZ=America/Sao_Paulo python3 /opt/mascote/ponte.py          # porta 8787
```

Libere a porta no firewall (Ubuntu com ufw: `ufw allow 8787/tcp`; em alguns
provedores também no painel). Teste no navegador: `http://IP-DA-VPS:8787/saude`
deve mostrar `ok`.

Para ficar ligada 24h, use `mascote-ponte.service` (instruções dentro dele).

## API

Todas as rotas `/api` pedem o cabeçalho `X-Token` igual a `PONTE_TOKEN`.

| Rota | O que faz |
|---|---|
| `GET /saude` | `ok` (sem token) |
| `GET /api/estado` | `{"hora": "14:05", "sessoes": [...]}` |
| `POST /api/acao` | `{"id": "s1", "acao": "aprovar"}` ou `"recusar"` |

Cada sessão: `id, title, repo, branch, status` (`waiting`, `working`, `idle`,
`done`), `ago, last, reply, ask` (`{tool, text}` ou `null`). Os textos saem sem
acento, porque a fonte da tela por enquanto só tem ASCII.

## Segurança

A demo usa HTTP simples com um token. Serve para dados de exemplo. Antes de ligar
as sessões reais (que aprovam comandos de verdade), a conexão precisa de HTTPS ou
de uma rede privada (por exemplo Tailscale entre a VPS e a casa).
