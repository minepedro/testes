#!/usr/bin/env bash
# Troca a PRODUCAO: demo (mascote-ponte.service, sistema, 8787) -> ponte real (unit --user do hermes, 8787).
# Revisavel. O Pedro roda por SSH:
#     sudo bash /home/hermes/testes/software/bridge/real/trocar_producao.sh            # trocar
#     sudo bash /home/hermes/testes/software/bridge/real/trocar_producao.sh rollback   # voltar para a demo
#     sudo bash ... --seco | rollback --seco                                           # so mostra os comandos
# O nginx nao muda (continua proxy para 127.0.0.1:8787). O firmware nao muda (mesmo token, /api/estado e /api/acao).
set -euo pipefail
U=hermes
H=/home/$U
UID_U=$(id -u $U)
CFG=$H/.config/mascote
MODO="${1:-trocar}"; SECO=0
for a in "$@"; do [ "$a" = "--seco" ] && SECO=1; done
[ "$MODO" = "--seco" ] && MODO=trocar
r() { echo "+ $*"; [ $SECO = 1 ] || "$@"; }
ru() { r sudo -u $U XDG_RUNTIME_DIR=/run/user/$UID_U "$@"; }   # comandos systemctl --user do hermes

if [ $SECO = 0 ] && [ "$(id -u)" != 0 ]; then echo "rode com sudo (ou use --seco)"; exit 1; fi

if [ "$MODO" = trocar ]; then
  # 1) token real do aparelho -> ~/.config/mascote/ponte.env (hermes, 0600). Nao imprime o token.
  r install -d -o $U -g $U -m 700 $CFG
  if [ $SECO = 0 ]; then
    T=$(sed -n 's/^PONTE_TOKEN=//p' /etc/mascote-ponte.env | tr -d '"'"'"' ')
    [ ${#T} -ge 12 ] || { echo "PONTE_TOKEN nao encontrado em /etc/mascote-ponte.env"; exit 1; }
    [ -f $CFG/ponte.env ] && cp -p $CFG/ponte.env $CFG/ponte.env.teste-bak
    umask 077; printf 'PONTE_TOKEN=%s\n' "$T" > $CFG/ponte.env; unset T
  else echo "+ (copia PONTE_TOKEN de /etc/mascote-ponte.env para $CFG/ponte.env)"; fi
  r chown $U:$U $CFG/ponte.env; r chmod 600 $CFG/ponte.env
  # 2) para e desabilita a demo (libera 8787)
  r systemctl stop mascote-ponte.service
  r systemctl disable mascote-ponte.service
  # se algo falhar daqui em diante, volta sozinho para a demo (o aparelho nao fica sem ponte)
  [ $SECO = 1 ] || trap 'echo "FALHOU: voltando para a demo"; bash "$0" rollback' ERR
  # 3) ponte real na 8787 (hook.py le a mesma porta de unit.env)
  if [ $SECO = 0 ]; then echo PORTA=8787 > $CFG/unit.env; chown $U:$U $CFG/unit.env; chmod 600 $CFG/unit.env
  else echo "+ echo PORTA=8787 > $CFG/unit.env"; fi
  ru systemctl --user daemon-reload
  ru systemctl --user restart mascote-ponte-real.service
  r sleep 2
  r curl -fsS http://127.0.0.1:8787/saude
  # confere o que o aparelho faz, sem imprimir o token: sem token -> 401, com token -> 200, HTTPS publico -> 200
  if [ $SECO = 0 ]; then
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787/api/estado)" = 401 ]
    [ "$(sed -n 's/^PONTE_TOKEN=/X-Token: /p' $CFG/ponte.env | curl -s -o /dev/null -w '%{http_code}' -H @- http://127.0.0.1:8787/api/estado)" = 200 ]
    [ "$(curl -s -o /dev/null -w '%{http_code}' https://179.198.122.200/saude)" = 200 ]
    echo "ok: 401 sem token, 200 com o token do aparelho, HTTPS publico ok"
  else echo "+ (confere: 401 sem token, 200 com o token do aparelho, HTTPS publico 200)"; fi
  trap - ERR
  echo; echo "Troca feita. Rollback: sudo bash $0 rollback"
elif [ "$MODO" = rollback ]; then
  # volta a ponte real para a porta de teste e religa a demo na 8787
  if [ $SECO = 0 ]; then echo PORTA=8791 > $CFG/unit.env; chown $U:$U $CFG/unit.env; chmod 600 $CFG/unit.env
  else echo "+ echo PORTA=8791 > $CFG/unit.env"; fi
  ru systemctl --user restart mascote-ponte-real.service
  r systemctl enable mascote-ponte.service
  r systemctl start mascote-ponte.service
  r sleep 2
  r curl -fsS http://127.0.0.1:8787/saude
  echo; echo "Rollback feito: demo na 8787, ponte real na 8791."
else
  echo "uso: $0 [trocar|rollback] [--seco]"; exit 2
fi
