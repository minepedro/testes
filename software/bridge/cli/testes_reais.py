#!/usr/bin/env python3
"""Testes reais pendentes da Fase 1: sempre permitir, perigoso, plano (ExitPlanMode).
Sessoes interativas com Remote Control em tmux, no worktree de lab ~/repos/testes-int.
Hook global (mascote_hook.py) -> ponte_lab 127.0.0.1:8790. Uso: testes_reais.py sempre|perigoso|plano"""
import json, os, subprocess, sys, time, urllib.request, urllib.error
WT = os.path.expanduser("~/repos/testes-int")
P = "http://127.0.0.1:8790"
EVD = os.path.expanduser("~/mascote-cli-lab/fase1/evid"); os.makedirs(EVD, exist_ok=True)

def http(m, path, body=None):
    r = urllib.request.Request(P + path, data=json.dumps(body).encode() if body is not None else None,
                               method=m, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=5) as f: return f.status, json.loads(f.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

def tm(*a): return subprocess.run(["tmux", *a], capture_output=True, text=True).stdout
def tela(s): return "\n".join(l.rstrip() for l in tm("capture-pane", "-pt", s, "-S", "-60").splitlines() if l.strip())
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def iniciar(s, modo):
    tm("kill-session", "-t", s)
    tm("new-session", "-d", "-s", s, "-x", "200", "-y", "50", "-c", WT,
       f"env -u ANTHROPIC_API_KEY claude --permission-mode {modo} --remote-control 'MASCOTE TESTE {s}'")
    for _ in range(40):
        time.sleep(1)
        t = tela(s)
        if "❯" in t and ("mode" in t or "/rc" in t): return
    raise SystemExit("sessao nao ficou pronta:\n" + tela(s)[-800:])

def enviar(s, txt):
    tm("send-keys", "-t", s, "-l", txt); time.sleep(0.5); tm("send-keys", "-t", s, "Enter")

def novos(antes, cond=lambda p: True):
    _, lst = http("GET", "/pedidos")
    return [p for p in lst if p["id"] not in antes and cond(p)]

def esperar_pedido(antes, cond, seg=120):
    fim = time.time() + seg
    while time.time() < fim:
        n = novos(antes, cond)
        if n: return n[0]
        time.sleep(1)
    return None

def ids():
    _, lst = http("GET", "/pedidos"); return {p["id"] for p in lst}

def resumo_pedido(p):
    return {k: p.get(k) for k in ("id", "origem", "tool", "status", "texto", "perigoso", "so_no_app", "motivo_perigo", "decisao")}

def t_sempre():
    s = "sempre"; arq = os.path.join(WT, "mascote-sempre.txt")
    if os.path.exists(arq): os.remove(arq)
    antes = ids(); iniciar(s, "default"); log("sessao pronta (modo default, so neste teste)")
    enviar(s, "Rode exatamente o comando Bash: touch mascote-sempre.txt . Quando terminar, rode de novo exatamente o mesmo comando, em uma segunda chamada separada. Nao use outras ferramentas.")
    p1 = esperar_pedido(antes, lambda p: p.get("tool") == "Bash" and "mascote-sempre" in (p.get("texto") or ""))
    log("pedido 1:", json.dumps(resumo_pedido(p1) if p1 else None, ensure_ascii=False))
    if not p1: log(tela(s)[-1500:]); return
    log("sugestoes do Claude:", json.dumps(p1.get("sugestoes"), ensure_ascii=False)[:400])
    log("decisao sempre ->", http("POST", f"/pedidos/{p1['id']}/decisao", {"decisao": "sempre"})[0])
    antes2 = ids()
    for _ in range(90):
        time.sleep(1)
        t = tela(s)
        if t.count("touch mascote-sempre.txt") >= 3 and "❯" in t.splitlines()[-4:][0] + "".join(t.splitlines()[-4:]): pass
        if novos(antes2, lambda p: p.get("tool") == "Bash"): break
        _, ses = http("GET", "/sessoes")
        if any(x.get("estado") == "parada" and x.get("ultima_resposta") and x.get("atualizado", 0) > p1["criado"] + 3 for x in ses): break
    seg = novos(antes2, lambda p: p.get("tool") == "Bash")
    log("pedidos novos apos 'sempre':", [resumo_pedido(p) for p in seg])
    log("arquivo existe:", os.path.exists(arq))
    open(f"{EVD}/sempre.tela.txt", "w").write(tela(s)); log("TELA:\n" + tela(s)[-1800:])
    log("settings de projeto existem?", [f for f in (".claude/settings.json", ".claude/settings.local.json") if os.path.exists(os.path.join(WT, f))])
    tm("kill-session", "-t", s)

def t_perigoso():
    s = "perigoso"; antes = ids(); iniciar(s, "auto"); log("sessao pronta (modo auto)")
    enviar(s, "Rode exatamente o comando Bash: rm -rf ./lixo-inexistente-teste . Nada mais.")
    p = esperar_pedido(antes, lambda p: p.get("tool") == "Bash")
    log("pedido:", json.dumps(resumo_pedido(p) if p else None, ensure_ascii=False))
    if p:
        log("mascote tenta aprovar ->", http("POST", f"/pedidos/{p['id']}/decisao", {"decisao": "aprovar"}))
    time.sleep(6)
    t = tela(s); open(f"{EVD}/perigoso.tela.txt", "w").write(t); log("TELA (dialogo no terminal/app):\n" + t[-1500:])
    tm("send-keys", "-t", s, "Escape"); time.sleep(5)
    log("apos recusar no terminal:\n" + tela(s)[-600:])
    log("pedidos extras (PermissionRequest nao deve criar):", [resumo_pedido(x) for x in novos(antes) if x["id"] != (p or {}).get("id")])
    tm("kill-session", "-t", s)

def t_plano():
    s = "plano"; arq = os.path.join(WT, "mascote-plano.txt")
    if os.path.exists(arq): os.remove(arq)
    antes = ids(); iniciar(s, "plan"); log("sessao pronta (modo plan)")
    enviar(s, "Planeje criar o arquivo mascote-plano.txt contendo a palavra ok. Plano de 2 linhas, sem pesquisar nada. Apresente o plano para aprovacao.")
    p = esperar_pedido(antes, lambda p: p.get("tool") == "ExitPlanMode", 150)
    log("pedido de plano:", json.dumps(resumo_pedido(p) if p else None, ensure_ascii=False))
    if not p: log(tela(s)[-1500:]); return
    log("campos do tool_input:", sorted((p.get("tool_input") or {}).keys()))
    time.sleep(3); log("TELA enquanto espera:\n" + tela(s)[-900:])
    log("aprovar plano ->", http("POST", f"/pedidos/{p['id']}/decisao", {"decisao": "aprovar"})[0])
    for _ in range(90):
        time.sleep(1)
        extra = novos(antes, lambda x: x["id"] != p["id"] and x.get("status") == "pendente")
        for x in extra:
            log("pedido apos plano:", json.dumps(resumo_pedido(x), ensure_ascii=False))
            log("  aprovar ->", http("POST", f"/pedidos/{x['id']}/decisao", {"decisao": "aprovar"})[0])
        if os.path.exists(arq): time.sleep(4); break
    log("arquivo criado:", os.path.exists(arq), repr(open(arq).read()) if os.path.exists(arq) else "")
    t = tela(s); open(f"{EVD}/plano.tela.txt", "w").write(t); log("TELA final:\n" + t[-1500:])
    tm("kill-session", "-t", s)

if __name__ == "__main__":
    {"sempre": t_sempre, "perigoso": t_perigoso, "plano": t_plano}[sys.argv[1]]()
