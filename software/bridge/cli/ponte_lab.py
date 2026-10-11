#!/usr/bin/env python3
"""Prototipo de laboratorio da ponte (Fase 1). So stdlib. Porta 127.0.0.1:8790.

Rotas:
  GET  /saude                      -> {"ok": true}
  POST /pedidos                    -> cria pedido (usado pelo hook); devolve {"id": ...}
  GET  /pedidos                    -> lista pedidos (pendentes primeiro)
  GET  /pedidos/<id>               -> um pedido (o hook faz polling aqui)
  POST /pedidos/<id>/decisao       -> {"decisao": "aprovar"|"recusar"|"sempre",
                                       "motivo": "...", "answers": {...}}
  POST /eventos                    -> registra evento de sessao (hooks de estado)
  GET  /eventos                    -> ultimos eventos
  GET  /sessoes                    -> estado agregado por session_id
Nao toca na ponte de producao (8787). Estado so em memoria + log jsonl opcional.
"""
import json, os, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORTA = int(os.environ.get("PONTE_LAB_PORTA", "8790"))
LOG = os.environ.get("PONTE_LAB_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab-eventos.jsonl"))
lock = threading.Lock()
PEDIDOS, EVENTOS, SESSOES = {}, [], {}


def ascii_txt(s, n=4000):
    """Texto que vai para a tela do mascote: ASCII, cortado."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s[:n]


def registrar(obj):
    try:
        with open(LOG, "a") as f:
            f.write(json.dumps(obj, ensure_ascii=True) + "\n")
    except OSError:
        pass


def atualizar_sessao(ev):
    sid = ev.get("session_id")
    if not sid:
        return
    s = SESSOES.setdefault(sid, {"session_id": sid, "estado": "parada"})
    for k in ("titulo", "repo", "branch", "cwd", "transcript_path", "permission_mode"):
        if ev.get(k):
            s[k] = ev[k]
    e = ev.get("evento")
    if e in ("SessionStart",):
        s["estado"] = "parada"
    elif e in ("UserPromptSubmit", "PostToolUse"):
        s["estado"] = "trabalhando"
        if ev.get("prompt"):
            s["ultimo_prompt"] = ascii_txt(ev["prompt"], 500)
    elif e == "Stop":
        s["estado"] = "parada"
        s["ultima_resposta"] = ascii_txt(ev.get("last_assistant_message"))
    elif e == "Notification":
        if ev.get("notification_type") in ("permission_prompt", "elicitation_dialog", "agent_needs_input"):
            s["estado"] = "esperando"
        s["ultima_notificacao"] = ascii_txt(ev.get("message"), 300)
    elif e == "pedido":
        s["estado"] = "esperando"
    elif e == "SessionEnd":
        s["estado"] = "encerrada"
    s["atualizado"] = time.time()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=True).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/")
        with lock:
            if p == "/saude":
                return self._json(200, {"ok": True})
            if p == "/pedidos":
                lst = sorted(PEDIDOS.values(), key=lambda x: (x["status"] != "pendente", x["criado"]))
                return self._json(200, lst)
            if p.startswith("/pedidos/"):
                pid = p.split("/")[2]
                if pid in PEDIDOS:
                    return self._json(200, PEDIDOS[pid])
                return self._json(404, {"erro": "nao existe"})
            if p == "/eventos":
                return self._json(200, EVENTOS[-200:])
            if p == "/sessoes":
                return self._json(200, list(SESSOES.values()))
        self._json(404, {"erro": "rota"})

    def do_POST(self):
        p = self.path.split("?")[0].rstrip("/")
        d = self._body()
        with lock:
            if p == "/pedidos":
                pid = uuid.uuid4().hex[:8]
                d.update(id=pid, status="pendente", criado=time.time())
                if d.get("perigoso"):
                    d["status"] = "so_no_app"
                d["texto"] = ascii_txt(d.get("texto"), 1500)
                PEDIDOS[pid] = d
                registrar({"tipo": "pedido", **d})
                atualizar_sessao({"evento": "pedido", "session_id": d.get("session_id")})
                return self._json(200, {"id": pid})
            parts = p.split("/")
            if len(parts) == 4 and parts[1] == "pedidos" and parts[3] == "decisao":
                pd = PEDIDOS.get(parts[2])
                if not pd:
                    return self._json(404, {"erro": "nao existe"})
                if pd["status"] != "pendente":
                    return self._json(409, {"erro": "status " + pd["status"]})
                dec = d.get("decisao")
                if dec not in ("aprovar", "recusar", "sempre"):
                    return self._json(400, {"erro": "decisao invalida"})
                pd.update(status="decidido", decisao=dec, motivo=d.get("motivo", ""),
                          answers=d.get("answers"), decidido=time.time())
                registrar({"tipo": "decisao", **pd})
                return self._json(200, pd)
            if len(parts) == 4 and parts[1] == "pedidos" and parts[3] == "fim":
                # o hook avisa que desistiu (timeout -> app) ou que ja usou a decisao
                pd = PEDIDOS.get(parts[2])
                if pd and pd["status"] == "pendente":
                    pd["status"] = d.get("status", "expirado")
                return self._json(200, pd or {})
            if p == "/eventos":
                d["recebido"] = time.time()
                EVENTOS.append(d)
                del EVENTOS[:-1000]
                atualizar_sessao(d)
                registrar({"tipo": "evento", **d})
                return self._json(200, {"ok": True})
        self._json(404, {"erro": "rota"})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORTA), H)
    print("ponte_lab em 127.0.0.1:%d" % PORTA, flush=True)
    srv.serve_forever()
