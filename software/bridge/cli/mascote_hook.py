#!/usr/bin/env python3
"""Hook do Claude Code -> ponte de laboratorio (127.0.0.1:8790). So stdlib.

Uso em settings.json: "command": "python3 /home/hermes/testes/software/bridge/cli/mascote_hook.py"
Eventos tratados:
  PreToolUse        Bash/Write/Edit: classifica perigoso -> "ask" na hora + avisa ponte.
                    AskUserQuestion / ExitPlanMode: espera a ponte (answers / aprovar plano).
  PermissionRequest espera a ponte: aprovar->allow, sempre->allow+updatedPermissions,
                    recusar->deny com motivo; sem resposta -> sem saida (dialogo normal / app).
  SessionStart, UserPromptSubmit, Notification, Stop, PostToolUse, SessionEnd -> /eventos.
Guardas: so age com cwd sob DIRS_PERMITIDOS; ponte fora do ar (2 s) -> exit 0 sem saida.
"""
import json, os, re, subprocess, sys, time, urllib.request

PONTE = os.environ.get("MASCOTE_PONTE", "http://127.0.0.1:8790")
ESPERA = float(os.environ.get("MASCOTE_ESPERA", "300"))  # 5 min
DIRS_PERMITIDOS = ("/home/hermes/repos/", "/home/hermes/mascote-cli-lab/")

# ---- classificador de perigosos (decisao 23) ----
PERIGOS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r\s+-f|-f\s+-r|--recursive\s+--force|--force\s+--recursive)\b", "rm -rf"),
    (r"\bgit\s+push\b[^;&|]*(\s--force(-with-lease)?\b|\s-f\b|\s\+\S)", "git push --force"),
    (r"\bgit\s+reset\b[^;&|]*--hard\b", "git reset --hard"),
    (r"\bgit\s+push\b[^;&|]*(\s--delete\b|\s-d\b|\s:\S)", "apagar branch remota"),
    (r"\bgh\s+api\b[^;&|]*-X\s*DELETE[^;&|]*refs/heads", "apagar branch remota"),
    (r"\b(deploy|vercel|netlify|fly\s+deploy|firebase\s+deploy|kubectl\s+apply|terraform\s+apply|npm\s+publish|twine\s+upload|gh\s+release\s+create)\b", "deploy/publicacao"),
    (r"(^|[;&|(]\s*|\s)sudo\b", "sudo"),
    (r"\b(curl|wget)\b[^;&]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "curl | sh"),
    (r"(^|[\s/'\"])\.env(\.[\w.-]+)?\b|credentials|\.netrc|id_rsa|id_ed25519|\.pem\b|secrets?\.", "credenciais/.env"),
]
ARQ_SENSIVEL = re.compile(r"(^|/)(\.env(\..*)?|\.netrc|credentials(\.json)?|id_rsa|id_ed25519|.*\.pem|secrets?\..*)$")


def classificar(tool, inp):
    """Devolve motivo (str) se perigoso, senao None."""
    if tool == "Bash":
        cmd = inp.get("command", "")
        for pad, nome in PERIGOS:
            if re.search(pad, cmd):
                return nome
    elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if ARQ_SENSIVEL.search(inp.get("file_path", "") or inp.get("notebook_path", "")):
            return "credenciais/.env"
    return None


# ---- comunicacao com a ponte ----
def req(metodo, path, corpo=None, timeout=2.0):
    data = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(PONTE + path, data=data, method=metodo,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return json.loads(f.read() or b"{}")


def git_info(cwd):
    def g(*a):
        try:
            return subprocess.run(["git", "-C", cwd, *a], capture_output=True, text=True, timeout=2).stdout.strip()
        except Exception:
            return ""
    top = g("rev-parse", "--show-toplevel")
    url = g("config", "--get", "remote.origin.url")
    repo = re.sub(r"(\.git)?$", "", url.rsplit(":", 1)[-1].split("github.com/")[-1]) if url else os.path.basename(top)
    return repo, g("branch", "--show-current")


def ultimo_texto_assistente(transcript_path, n=1500):
    """Texto do assistente que antecede o pedido (explicacao), lido do transcript."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2); tam = f.tell(); f.seek(max(0, tam - 400000))
            linhas = f.read().decode("utf-8", "ignore").splitlines()
        for l in reversed(linhas):
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if o.get("type") == "assistant":
                txt = [c.get("text", "") for c in o.get("message", {}).get("content", []) if c.get("type") == "text"]
                if any(t.strip() for t in txt):
                    return "\n".join(txt)[-n:]
    except OSError:
        pass
    return ""


def resumo(tool, inp):
    if tool == "Bash":
        return (inp.get("description", "") + ": " if inp.get("description") else "") + inp.get("command", "")
    if tool in ("Write", "Edit", "MultiEdit"):
        return tool + " " + inp.get("file_path", "")
    if tool == "AskUserQuestion":
        return " | ".join(q.get("question", "") for q in inp.get("questions", []))
    if tool == "ExitPlanMode":
        return (inp.get("plan") or "")[:1200]
    return tool + " " + json.dumps(inp)[:300]


def out(obj):
    sys.stdout.write(json.dumps(obj))
    sys.exit(0)


def esperar(pid):
    fim = time.time() + ESPERA
    while time.time() < fim:
        try:
            p = req("GET", "/pedidos/" + pid)
        except Exception:
            return None  # ponte caiu: segue fluxo normal
        if p.get("status") == "decidido":
            try:
                req("POST", "/pedidos/%s/fim" % pid, {"status": "usado"})
            except Exception:
                pass
            return p
        if p.get("status") not in ("pendente",):
            return None
        time.sleep(1)
    try:
        req("POST", "/pedidos/%s/fim" % pid, {"status": "expirado_foi_pro_app"})
    except Exception:
        pass
    return None


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    cwd = os.path.realpath(d.get("cwd") or os.getcwd()) + "/"
    if not cwd.startswith(DIRS_PERMITIDOS):
        sys.exit(0)
    try:
        req("GET", "/saude")
    except Exception:
        sys.exit(0)  # ponte fora do ar -> fluxo normal

    ev = d.get("hook_event_name")
    tool, inp = d.get("tool_name", ""), d.get("tool_input") or {}
    sid = d.get("session_id")
    repo, branch = git_info(d.get("cwd") or os.getcwd())
    base = {"session_id": sid, "cwd": d.get("cwd"), "repo": repo, "branch": branch,
            "transcript_path": d.get("transcript_path"), "permission_mode": d.get("permission_mode")}

    if ev in ("SessionStart", "UserPromptSubmit", "Notification", "Stop", "SessionEnd", "PostToolUse"):
        e = dict(base, evento=ev)
        for k in ("source", "prompt", "message", "notification_type", "last_assistant_message", "reason", "tool_name"):
            if d.get(k):
                e[k] = d[k]
        try:
            req("POST", "/eventos", e)
        except Exception:
            pass
        sys.exit(0)

    if ev == "PreToolUse":
        perigo = classificar(tool, inp)
        if perigo:
            try:
                req("POST", "/pedidos", dict(base, tool=tool, tool_input=inp, texto=resumo(tool, inp),
                                             explicacao=ultimo_texto_assistente(d.get("transcript_path", "")),
                                             perigoso=True, so_no_app=True, motivo_perigo=perigo, origem=ev))
            except Exception:
                pass
            out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                        "permissionDecisionReason": "Perigoso (%s): aprove pelo app" % perigo}})
        if tool not in ("AskUserQuestion", "ExitPlanMode"):
            sys.exit(0)  # ferramentas comuns: deixa o modo (auto) decidir; se pedir, cai no PermissionRequest
        pid = req("POST", "/pedidos", dict(base, tool=tool, tool_input=inp, texto=resumo(tool, inp),
                                           explicacao=ultimo_texto_assistente(d.get("transcript_path", "")),
                                           origem=ev))["id"]
        p = esperar(pid)
        if not p:
            out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}})
        if p["decisao"] == "recusar":
            out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                        "permissionDecisionReason": p.get("motivo") or "Recusado no mascote"}})
        if tool == "AskUserQuestion":
            novo = dict(inp, answers=p.get("answers") or {})
            out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                        "updatedInput": novo}})
        # ExitPlanMode aprovado
        out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                    "updatedInput": inp}})

    if ev == "PermissionRequest":
        if classificar(tool, inp):
            sys.exit(0)  # perigoso: so no app (PreToolUse ja avisou)
        pid = req("POST", "/pedidos", dict(base, tool=tool, tool_input=inp, texto=resumo(tool, inp),
                                           explicacao=ultimo_texto_assistente(d.get("transcript_path", "")),
                                           sugestoes=d.get("permission_suggestions"), origem=ev))["id"]
        p = esperar(pid)
        if not p:
            sys.exit(0)  # sem resposta: dialogo normal (terminal/app)
        if p["decisao"] == "recusar":
            out({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {
                "behavior": "deny", "message": p.get("motivo") or "Recusado no mascote"}}})
        dec = {"behavior": "allow"}
        if p["decisao"] == "sempre":
            sug = d.get("permission_suggestions") or []
            regra = {"toolName": tool}
            if tool == "Bash":
                regra["ruleContent"] = inp.get("command", "")
            elif inp.get("file_path"):
                regra["ruleContent"] = inp["file_path"]
            # regra propria (comando exato) + sugestoes de diretorio; nunca setMode (nao muda o modo do Pedro)
            dec["updatedPermissions"] = [{"type": "addRules", "rules": [regra], "behavior": "allow",
                                          "destination": "session"}] + \
                [s for s in sug if s.get("type") == "addDirectories"]
        out({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": dec}})
    sys.exit(0)


if __name__ == "__main__":
    main()
