#!/bin/sh
# Renderiza quadros do Camarim no host com o mesmo codigo de desenho do firmware.
# Uso: sh render_camarim.sh [pasta de saida]   (gera .ppm e, com python3, .png)
set -e
AQUI=$(cd "$(dirname "$0")" && pwd)
SAIDA=${1:-$AQUI/quadros}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$SAIDA"
# Arduino.h de mentira: tipos.h so precisa de String e dos inteiros
printf '#pragma once\n#include <cstdint>\n#include <cstddef>\nstruct String {};\n' > "$TMP/Arduino.h"
cp "$AQUI/../tipos.h" "$TMP/"
sed -n '/^\/\/ >>> HOST/,/^\/\/ <<< HOST/p' "$AQUI/../mascote.ino" > "$TMP/camarim_host.inc"
cp "$AQUI/render_camarim.cpp" "$TMP/"
g++ -std=c++17 -O1 -Wall -Wno-unused-function -I"$TMP" -o "$TMP/render" "$TMP/render_camarim.cpp"
"$TMP/render" "$SAIDA"
python3 - "$SAIDA" <<'PY' || true
import sys, os, zlib, struct
d = sys.argv[1]
for n in sorted(os.listdir(d)):
    if not n.endswith('.ppm'): continue
    b = open(os.path.join(d, n), 'rb').read()
    parts = b.split(b'\n', 3); w, h = map(int, parts[1].split()); px = parts[3]
    raw = b''.join(b'\x00' + px[y*w*3:(y+1)*w*3] for y in range(h))
    ch = lambda t, x: struct.pack('>I', len(x)) + t + x + struct.pack('>I', zlib.crc32(t + x) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw, 9)) + ch(b'IEND', b'')
    open(os.path.join(d, n[:-4] + '.png'), 'wb').write(png)
print('png ok')
PY
