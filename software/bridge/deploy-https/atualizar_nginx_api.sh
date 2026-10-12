#!/usr/bin/env bash
# Atualiza o site nginx do mascote para a API nova + voz (decisao 26). Revisavel. O Pedro roda por SSH:
#     sudo bash /home/hermes/testes/software/bridge/deploy-https/atualizar_nginx_api.sh
# O que muda: /api/ inteiro passa para a ponte (antes so /api/estado e /api/acao); /api/voz aceita 1 MB e
# espera ate 90 s; demais rotas continuam com corpo pequeno (64 KB). Gerado por mascote_https.render_nginx().
# Seguro: guarda backup, roda nginx -t antes do reload e volta o backup se o teste falhar.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "rode com sudo"; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
SITE=/etc/nginx/sites-available/mascote-https.conf
BAK=/var/lib/mascote-https/backups/mascote-https.conf.$(date +%Y%m%d-%H%M%S)
mkdir -p /var/lib/mascote-https/backups
cp -p "$SITE" "$BAK"; echo "backup: $BAK"
NOVO=$(mktemp)
python3 -c "import sys; sys.path.insert(0, '$AQUI'); import mascote_https as m; sys.stdout.write(m.render_nginx())" > "$NOVO"
diff -u "$SITE" "$NOVO" || true
install -m 644 -o root -g root "$NOVO" "$SITE"; rm -f "$NOVO"
if nginx -t; then
  systemctl reload nginx
  sleep 1
  echo "saude: $(curl -s -o /dev/null -w '%{http_code}' https://179.198.122.200/saude)  (esperado 200)"
  echo "api sem token: $(curl -s -o /dev/null -w '%{http_code}' https://179.198.122.200/api/sessoes)  (esperado 401)"
  echo "voz sem token: $(curl -s -o /dev/null -w '%{http_code}' -X POST --data-binary @/dev/null https://179.198.122.200/api/voz)  (esperado 401)"
  echo "ok. Para voltar: sudo cp -p $BAK $SITE && sudo nginx -t && sudo systemctl reload nginx"
else
  echo "nginx -t FALHOU: restaurando backup"; cp -p "$BAK" "$SITE"; nginx -t && systemctl reload nginx; exit 1
fi
