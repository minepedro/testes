#!/usr/bin/env bash
# Prova que o mbedTLS usado pelo core ESP32 confere SAN iPAddress ao conectar por IP:
# aceita certificado com IP:179.198.122.200 e recusa IP diferente ou so DNS.
# Uso: MBEDTLS=/caminho/mbedtls-3.6.6 ./teste_san_ip.sh   (fonte compilada com `make lib`)
set -euo pipefail
: "${MBEDTLS:?defina MBEDTLS com a pasta do mbedtls compilado}"
aqui=$(cd "$(dirname "$0")" && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
cd "$t"
cc -I"$MBEDTLS/include" "$aqui/verifica_san_ip.c" -L"$MBEDTLS/library" -lmbedx509 -lmbedcrypto -o v
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout ca.key -out ca.pem -days 2 \
  -subj /CN=CA-teste -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign 2>/dev/null
folha() { # nome san
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout "$1.key" -out "$1.csr" -subj /CN=ignorado 2>/dev/null
  openssl x509 -req -in "$1.csr" -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 -out "$1.pem" \
    -extfile <(printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "$2") 2>/dev/null
}
folha ip  IP:179.198.122.200
folha dns DNS:exemplo.org
falhas=0
espera() { local r=0; ./v ca.pem "$2.pem" "$3" || r=1; [ "$r" = "$1" ] || { echo "FALHOU: $*"; falhas=1; }; }
espera 0 ip  179.198.122.200   # SAN IP correto: aceita
espera 1 ip  179.198.122.201   # outro IP: recusa
espera 1 dns 179.198.122.200   # certificado sem SAN IP: recusa
[ $falhas = 0 ] && echo "ok: SAN iPAddress conferido pelo mbedTLS" || exit 1
