# Ponte REAL do mascote (v1)

Substitui a ponte demo (`../ponte.py`). So stdlib (Python 3.12), escuta **so 127.0.0.1**
(o nginx da producao faz HTTPS -> 127.0.0.1:8787). Contrato do firmware atual mantido
(`GET /api/estado`, `POST /api/acao`); API nova para o firmware futuro.

## Arquivos
| arquivo | o que faz |
|---|---|
| `ponte_real.py` | servidor HTTP + regras (pedidos, compat, dedupe, nuvem) |
| `fonte_vps.py` | sessoes `claude --remote-control` em tmux, estado vindo dos hooks, criar sessao, mensagem |
| `fonte_nuvem.py` | adaptador NAO documentado da nuvem (de `../cli/nuvem_nd.py`), transporte injetavel |
| `nuvem_criar.py` | `claude --cloud 'tarefa'` em pty (nao testado pela v1) |
| `repos.py` | `gh`: repos pessoais + orgs (cache 5 min), branches, clone sob demanda em `~/repos/<nome>` |
| `hook.py` | hook do Claude Code (substitui `../cli/mascote_hook.py`) |
| `comum.py` | ascii_tela, classificador de perigosos (decisao 23), tokens, config |
| `cli.py` | cliente de teste (`python3 cli.py GET /api/sessoes`) |
| `test_ponte.py` | 26 testes unitarios (fakes, sem rede): `python3 -m unittest -v` |
| `integracao_real.py` | roteiro da integracao real (precisa de sessao VPS criada pela ponte) |
| `mascote-ponte-real.service`, `instalar_usuario.sh` | unit systemd --user (sem sudo) |
| `trocar_producao.sh` | troca demo -> real (sudo, revisavel), `rollback`, `--seco` |
| `ponte.exemplo.json` | config (copiada para `~/.config/mascote/ponte.json`) |

## Arquivos fora do repo (nunca commitar)
- `~/.config/mascote/ponte.env` `PONTE_TOKEN=...` (0600) token do aparelho (ou env `PONTE_TOKEN`).
- `~/.config/mascote/hook.token` (0600) token interno hook->ponte (gerado se faltar), cabecalho `X-Hook-Token`.
- `~/.config/mascote/unit.env` `PORTA=8791|8787` - porta da unit E do hook (o hook le daqui; env `MASCOTE_PONTE` sobrepoe).
- `~/.config/mascote/ponte.json` config: `nuvem_ativa`, `nuvem_responder` (EXPERIMENTAL, padrao true),
  `nuvem_intervalo` (10 s), `nuvem_dias` (7), `bridge_desconhecida` (`listar`|`omitir`).
- `~/.local/state/mascote/sessoes_vps.json` sessoes criadas pela ponte (titulo, cwd, tmux). Pedidos so em memoria.

## Estado em producao (2026-10-12)
Troca feita por `sudo bash trocar_producao.sh` (conferiu 401 sem token, 200 com o token do aparelho e
HTTPS publico). `mascote-ponte.service` (demo) desabilitado; `mascote-ponte-real` (--user) em 127.0.0.1:8787;
`~/.config/mascote/unit.env` = `PORTA=8787`. Pedro confirmou no aparelho: sessoes reais da VPS e da nuvem
aparecem. Rollback (volta a demo): `sudo bash trocar_producao.sh rollback`.

## Operar
```
bash instalar_usuario.sh 8791              # instala/reinicia unit --user na 8791 (teste)
systemctl --user status mascote-ponte-real; journalctl --user -u mascote-ponte-real -f
python3 -m unittest -v                     # testes unitarios
sudo bash trocar_producao.sh --seco        # mostra o que a troca faria
sudo bash trocar_producao.sh               # PRODUCAO: demo -> real na 8787 (copia token de /etc)
sudo bash trocar_producao.sh rollback      # volta: demo na 8787, real na 8791
```
Hook global: `~/.claude/settings.json` chama `python3 /home/hermes/testes/software/bridge/real/hook.py`
em PreToolUse/PermissionRequest (timeout 310) e SessionStart/UserPromptSubmit/Notification/Stop/SessionEnd (10).
So age com cwd sob `~/repos/` ou `~/mascote-cli-lab/`; ponte fora do ar em 2 s -> fluxo normal.

## API (todas com `X-Token`; respostas JSON ASCII; corpo max 64 KB; `/saude` sem token)
- `GET /api/sessoes` -> `[{id, origem:vps|nuvem, titulo, repo, branch, estado:trabalhando|parada|esperando|encerrada|desconectada, pedidos_pendentes, atualizado_em, ha_quanto, ultima_resposta_resumo, somente_leitura}]`
- `GET /api/sessoes/{id}` -> + `ultima_resposta` (<=4000), `ultimo_prompt`, `pedidos`
- `GET /api/repos` -> `[{nome, privado, branch_padrao, clonado}]`; `GET /api/repos/{dono}/{nome}/branches` -> `[{nome}]`
- `POST /api/sessoes {origem, repo|null, branch, nova_branch|null, titulo, prompt|null}` -> 202 `{id}`
  VPS: clone -> worktree `~/repos/<nome>--<slug>` -> tmux `mascote-<slug>` com
  `claude --remote-control 'TITULO' --permission-mode auto` -> aceita confianca -> prompt por send-keys.
  Id VPS = `v` + sha1(cwd)[:10]. Nuvem: exige repo e prompt.
- `GET /api/pedidos[?pendentes=1]` -> `[{id, sessao_id, origem, tipo:permissao|pergunta|plano, ferramenta, resumo, detalhe, explicacao, perguntas:[{pergunta, cabecalho, multipla, opcoes:[{rotulo, descricao}]}], perigoso, so_no_app, motivo_so_no_app, criado_em, estado}]`
- `POST /api/pedidos/{id}/resposta {decisao:aprovar|recusar|sempre, respostas:{pergunta: rotulo|[r1,r2]}, motivo}`
  -> 200 | 400 | 403 (so_no_app; `sempre` na nuvem) | 404 | 409 (ja respondido/expirado) | 502 (nuvem falhou -> pedido vira so_no_app)
- `POST /api/sessoes/{id}/mensagem {texto}` -> 202 | 409 (esperando/trabalhando/encerrada/sem tmux) | 403 (somente leitura) | 504 (sem `UserPromptSubmit` em 10 s)
- Compat firmware: `GET /api/estado` -> `{hora, sessoes:[{id,title,repo,branch,status,ago,last,reply,ask}]}` (max 20);
  `POST /api/acao {id: <sessao>, acao}`: vale so para o pedido servido no ultimo `/api/estado` daquela sessao e ainda
  pendente (senao 409). so_no_app -> `ask.text` "APROVE PELO APP: ..." e acao 403. Pergunta -> acao 409.

## Voz (decisao 26)
- `POST /api/voz` corpo cru PCM s16le mono 16 kHz (`Content-Type: application/octet-stream`, max 1 MB ~ 32 s)
  -> `{texto, segundos}` | 503 (transcricao desligada ou faster-whisper ausente) | 413. So transcreve: o aparelho
  mostra o texto e so depois envia (`/api/sessoes/{id}/mensagem` ou `POST /api/sessoes`).
- `stt.py`: faster-whisper local (modelo `small`, `pt`, int8 na CPU; carrega na 1a fala). Config `stt_ativo`,
  `stt_modelo`, `stt_idioma`, `stt_threads`. Instalar num venv e apontar o ExecStart da unit para ele:
  ```
  python3 -m venv ~/.local/share/mascote/venv
  ~/.local/share/mascote/venv/bin/pip install faster-whisper
  # unit: ExecStart=%h/.local/share/mascote/venv/bin/python3 .../ponte_real.py --porta ${PORTA}
  ```
  O modelo `small` usa ~1 GB de RAM; com pouca RAM use `base`. O nginx precisa aceitar 1 MB (`client_max_body_size 1m`, o padrao).

## Regras
- Perigosos (comum.PERIGOS) e falhas da nuvem: `so_no_app`. `sempre` so na VPS (addRules comando exato, session).
- Plano na VPS: hook trata ExitPlanMode no **PreToolUse** (padrao `MASCOTE_PLANO_VIA=pre`): aprovado -> sessao sai do
  plano em modo auto (testado real). A variante `perm` (PermissionRequest + setMode auto) NAO funciona: o
  PermissionRequest nao dispara para ExitPlanMode na CLI 2.1.287; o dialogo "Ready to code?" fica no terminal.
- Nuvem: plano aprovado -> `set_permission_mode auto`.
- Dedupe: sessao `bridge` da API da nuvem com titulo ou (repo, branch) de sessao VPS conhecida e omitida; outras
  bridge aparecem como `origem vps`, `somente_leitura: true` (config `bridge_desconhecida: omitir` esconde).
- Pedido VPS so_no_app some quando a sessao volta a andar (hook de estado posterior).
