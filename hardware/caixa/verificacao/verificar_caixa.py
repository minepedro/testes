# -*- coding: utf-8 -*-
"""Confere a caixa Mini Mac montada, medindo os arquivos gerados, e faz o modelo 3D para ver no navegador.

- cada peça impressa fechada e numa casca só;
- nenhuma peça invade outra, nem as peças de verdade (tela, placa, ESP32, jumpers,
  plugue, alto-falante, amplificador, microfone, LED, botão);
- a bandeja entra por trás sem bater em nada com a placa montada em cima;
- os parafusos não passam do fundo dos furos.

Uso: python3 verificar_caixa.py [pasta do modelo]   (padrão: ../modelo)
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import numpy as np
import trimesh
import cadquery as cq

import gerar_caixa as C

pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI.parent / 'modelo'
r = lambda t: tuple(round(float(x), 2) for x in t)

pecas = {nome: C.malha(cq.importers.importStep(str(pasta / ('caixa-' + nome.replace(' ', '-') + '.step'))))
         for nome in C.PECAS}
fant = {nome: C.malha(s.val() if hasattr(s, 'val') else s) for nome, s in C.fantasmas().items()}

print('== peças impressas')
for nome, m in pecas.items():
    print('%-20s fechada %s, cascas %d, %5.1f cm3, caixa %s' % (nome, m.is_watertight, len(m.split(only_watertight=False)), m.volume / 1000, r(m.bounds[1] - m.bounds[0])))

def comum(a, b):
    i = trimesh.boolean.intersection([a, b], engine='manifold')
    return i.volume if len(i.faces) else 0.0

print('== colisões na montagem (mm3; tem que dar 0)')
nomes = list(pecas)
ruins = []
for i, a in enumerate(nomes):
    for b in nomes[i + 1:]:
        v = comum(pecas[a], pecas[b])
        if v > 0.01:
            ruins.append((a, b, v))
for a, ma in pecas.items():
    for b, mb in fant.items():
        v = comum(ma, mb)
        if v > 0.01:
            ruins.append((a, b, v))
print('nenhuma' if not ruins else '\n'.join('%s x %s: %.2f' % t for t in ruins))

print('== a bandeja entrando por trás com a placa montada')
bateu = []
for nome in ('placa ilhada', 'ESP32', 'jumpers da placa', 'jumpers do mic', 'jumpers do amp'):
    b0, b1 = fant[nome].bounds
    rastro = trimesh.creation.box(extents=(b1[0] - b0[0], C.D + 30 - b0[1], b1[2] - b0[2]))
    rastro.apply_translation(((b0[0] + b1[0]) / 2, (b0[1] + C.D + 30) / 2, (b0[2] + b1[2]) / 2))
    v = comum(pecas['corpo'], rastro)
    if v > 0.01:
        bateu.append((nome, v))
print('passa livre' if not bateu else '\n'.join('%s bate no corpo: %.2f mm3' % t for t in bateu))

print('== folgas')
print('jumpers da tela vão até y = %.1f; a placa ilhada começa em y = %.1f' % (fant['tela: jumpers'].bounds[1][1], C.BY0))
print('alto-falante de z = %.1f a %.1f; jumpers mais altos em %.1f' % (fant['alto-falante'].bounds[0][2], fant['alto-falante'].bounds[1][2], fant['jumpers da placa'].bounds[1][2]))
print('plugue USB-C: de x = %.1f (USB do ESP32) a %.1f (lateral), meio em y = %.1f, z = %.1f' % (C.X_TOMADA, C.W, C.USB_Y, C.USB_Z))
print('parafusos da tela: ponta em y = %.1f, fundo do furo em y = %.1f' % (C.Y_CABECA_TELA - C.T.PARAFUSO_L, C.Y_COSTAS - C.T.INSERTO_L - 0.5))
print('parafusos de trás: ponta em y = %.1f, fundo do furo em y = %.1f' % (C.D - C.T.PARAFUSO_L, C.D - C.PAR - 17.5))

print('== a chave de fenda alcança os parafusos da tela por trás (haste de 6 mm, com o alto-falante e o amplificador no lugar)')
for u, v in C.INSERTOS_TELA:
    haste = trimesh.creation.cylinder(radius=3.0, segment=[(C.tx(u), C.Y_CABECA_TELA + 0.1, C.tz(v)), (C.tx(u), C.D + 20, C.tz(v))])
    bate = sum(comum(haste, m) for m in (pecas['corpo'], fant['alto-falante'], fant['amplificador']))
    print('  parafuso em x = %5.1f, z = %5.1f: %s' % (C.tx(u), C.tz(v), 'livre' if bate < 0.01 else 'bate (%.1f mm3)' % bate))

# ---------------- modelo 3D para o navegador ----------------
cores = {'corpo': '#D8CDB2', 'bandeja': '#CDBFA0', 'moldura da tela': '#BDB193', 'tecla': '#F3F0E8', 'tampa do microfone': '#E7E1D2',
         'tela: vidro': '#1B1F26', 'tela: placa': '#B3322B', 'tela: jumpers': '#E8B52F', 'placa ilhada': '#2F6A46', 'ESP32': '#2A2F38',
         'jumpers da placa': '#3D9B5B', 'jumpers do mic': '#3B7DD8', 'jumpers do amp': '#D9453B', 'plugue USB-C': '#202226',
         'alto-falante': '#8D96A3', 'amplificador': '#5B2E87', 'microfone': '#25518F', 'LED': '#5FD17A', 'botão tátil': '#33363C'}
cena = trimesh.Scene()
leves = {nome: C.malha(fn(), tol=0.08) for nome, fn in C.PECAS.items()}
for nome, m in list(leves.items()) + list(fant.items()):
    hx = cores[nome]
    mat = trimesh.visual.material.PBRMaterial(name=nome, baseColorFactor=[int(hx[i:i + 2], 16) for i in (1, 3, 5)] + [255],
                                              metallicFactor=0.0, roughnessFactor=0.85)
    m = m.copy()
    m.visual = trimesh.visual.TextureVisuals(material=mat)
    cena.add_geometry(m, node_name=nome, geom_name=nome)
# glTF em texto com o binário embutido: a página publicada só serve .json, não .glb
import base64, json, struct
glb = cena.export(file_type='glb')
n = struct.unpack_from('<I', glb, 12)[0]
gltf = json.loads(glb[20:20 + n])
binario = glb[20 + n + 8:]
gltf['buffers'] = [{'byteLength': len(binario), 'uri': 'data:application/octet-stream;base64,' + base64.b64encode(binario).decode()}]
saida = pasta / 'caixa-3d.gltf.json'
saida.write_text(json.dumps(gltf, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print('modelo 3D: %s (%d KB, %d triângulos)' % (saida.name, saida.stat().st_size // 1024, sum(len(g.faces) for g in cena.geometry.values())))
