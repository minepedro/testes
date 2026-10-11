# Prototipo Fase 1: Remote Control + hooks -> ponte de laboratorio

Somente testes. Nao toca na ponte de producao (`software/bridge/ponte.py`, 127.0.0.1:8787).

## Arquivos
- `ponte_lab.py` - servidor HTTP stdlib em 127.0.0.1:8790: `GET /pedidos`, `GET /pedidos/<id>`,
  `POST /pedidos/<id>/decisao` (`{"decisao":"aprovar|recusar|sempre","motivo":..,"answers":{..}}`),
  `POST/GET /eventos`, `GET /sessoes` (estado por sessao). Log em `lab-eventos.jsonl` (ignorado no git).
- `mascote_hook.py` - hook unico para PreToolUse, PermissionRequest, SessionStart, UserPromptSubmit,
  Notification, Stop, SessionEnd.
- `test_hook.py` - testes (classificador de perigosos + hook contra ponte real em porta 8799).
  `python3 test_hook.py` -> 8 testes OK.

## Guardas do hook
- So age se `cwd` estiver sob `/home/hermes/repos/` ou `/home/hermes/mascote-cli-lab/`; senao exit 0 sem saida.
- Ponte nao responde em 2 s -> exit 0 sem saida (fluxo normal).
- Espera ate 300 s (`MASCOTE_ESPERA`); timeout do hook 310 s nos settings.
- Perigosos (decisao 23): PreToolUse devolve `ask` na hora e registra pedido `perigoso=true, so_no_app=true`.
- "Sempre": `updatedPermissions` = addRules com o comando exato (destination session) + sugestoes
  addDirectories. Nunca aplica `setMode` sugerido.

## Instalacao (global, feita em 2026-10-11)
Backup: `~/.claude/settings.json.bak-20261011-192536`. Adicionado a `hooks` (mesclado):
PreToolUse e PermissionRequest (matcher `*`, timeout 310) e SessionStart, UserPromptSubmit,
Notification, Stop, SessionEnd (timeout 10), todos com
`python3 /home/hermes/testes/software/bridge/cli/mascote_hook.py`.
Remover: `cp ~/.claude/settings.json.bak-20261011-192536 ~/.claude/settings.json`.

## Resultados (VPS, Claude Code 2.1.267, assinatura)
1. Remote Control persistente: FUNCIONA em tmux `mascote-rc`
   (`claude remote-control --name mascote-rc --permission-mode auto --spawn worktree` em worktree
   `~/repos/testes-lab`, branch local `lab/mascote-rc`). API interna: `bridge` / `connected`.
   Linger=yes, mas systemd --user nao foi testado (ficou tmux).
   Criar sessao: (a) `claude --remote-control 'MASCOTE INT lab'` interativo em tmux no worktree
   `~/repos/testes-int` (branch `lab/mascote-int`) -> FUNCIONA, aparece na API como bridge/connected.
   E a forma de a ponte escolher repo+branch (worktree + tmux). (b) `--spawn worktree`: documentado,
   cria worktree por sessao, mas a sessao nova e criada pelo app (nao pela ponte); falta checagem visual.
   Obs: diretorio novo exige aceitar a confianca uma vez (`claude` interativo, Down+Enter).
2. PermissionRequest -> ponte: FUNCIONA (aprovar -> executou; recusar -> "Denied by PermissionRequest hook"
   com o motivo). Enquanto o hook espera, o pedido aparece TAMBEM no terminal e no app
   (evento `control_request can_use_tool`); quando a ponte responde, chega `control_cancel_request`
   ao app. Sem resposta em 5 min -> dialogo normal continua (testado). Nao testado: app respondendo
   primeiro enquanto o hook espera. "Sempre": 1a versao (sugestao addDirectories) NAO criou regra;
   versao corrigida (addRules do comando) so coberta por teste unitario - teste real ficou bloqueado.
   Com ask rule de projeto, a ask rule prevalece sobre o allow da sessao (esperado pela doc).
3. AskUserQuestion multiSelect via PreToolUse + updatedInput.answers ("Azul, Vermelho"): FUNCIONA na
   sessao Remote Control real. ExitPlanMode: documentado (PreToolUse allow com input/plan injetado);
   NAO testado real.
4. Perigosos: classificador com testes unitarios OK; caso real (`rm -rf ./lixo-inexistente-teste`)
   nao executado.
5. Mensagem nova para sessao RC: SEM FORMA DOCUMENTADA para programa externo. `tmux send-keys` na
   sessao interativa FUNCIONA (nao documentado) e a mensagem aparece no app como evento `user`.
6. Estado via hooks: FUNCIONA. `/sessoes` mostra repo, branch, estado (trabalhando/parada/esperando/
   encerrada), ultimo prompt e ultima resposta completa (`last_assistant_message` do Stop).
   Notification recebeu `permission_prompt` e `idle_prompt`. Explicacao do pedido: ultimo texto do
   assistente lido do transcript_path (pode atrasar, segundo a doc). Titulo nao vem nos hooks
   (vem do `--name`/API).
