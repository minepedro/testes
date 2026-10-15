#!/usr/bin/env bash
# Instala a ponte real como servico systemd --user (SEM sudo). Nao toca em /etc nem na demo.
#   bash instalar_usuario.sh [PORTA]      (padrao 8791 = teste)
# - cria ~/.config/mascote (0700), hook.token (0600), ponte.json (se faltar), unit.env (PORTA)
# - ponte.env (PONTE_TOKEN): se faltar, gera um token de TESTE (o aparelho de producao NAO o conhece;
#   trocar_producao.sh copia o token real de /etc/mascote-ponte.env por cima)
# - liga a unit ~/.config/systemd/user/mascote-ponte-real.service (symlink para o repo)
set -euo pipefail
PORTA="${1:-8791}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
CFG="$HOME/.config/mascote"
umask 077
mkdir -p "$CFG" "$HOME/.local/state/mascote" "$HOME/.config/systemd/user"
chmod 700 "$CFG"
[ -s "$CFG/hook.token" ] || python3 -c 'import secrets;print(secrets.token_urlsafe(32))' > "$CFG/hook.token"
if [ ! -s "$CFG/ponte.env" ]; then
  echo "PONTE_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" > "$CFG/ponte.env"
  echo "ponte.env criado com token de TESTE"
fi
[ -f "$CFG/ponte.json" ] || cp "$AQUI/ponte.exemplo.json" "$CFG/ponte.json"
echo "PORTA=$PORTA" > "$CFG/unit.env"
chmod 600 "$CFG"/*
ln -sf "$AQUI/mascote-tmux.service" "$HOME/.config/systemd/user/mascote-tmux.service"
ln -sf "$AQUI/mascote-ponte-real.service" "$HOME/.config/systemd/user/mascote-ponte-real.service"
systemctl --user daemon-reload
systemctl --user enable --now mascote-tmux.service
systemctl --user enable mascote-ponte-real.service
systemctl --user restart mascote-ponte-real.service
sleep 2
curl -fsS "http://127.0.0.1:$PORTA/saude" && echo " <- ponte real ok na porta $PORTA"
