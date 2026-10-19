# -*- coding: utf-8 -*-
"""Confere as peças de teste da tela, medindo os arquivos gerados, e desenha o PDF.

Usa o cadkit e o cadraw do plugin cad-industrial (skill modelagem-cad). Aponte
a pasta deles em CADKIT_DIR se estiverem em outro lugar.

Uso: python3 verificar_teste_tela.py [pasta com os STEP]   (padrão: ../teste-tela)
"""
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get('CADKIT_DIR', str(Path.home() / '.claude/plugins/cad-industrial/skills/modelagem-cad/scripts')))
sys.path.insert(0, str(AQUI.parent))

import cadquery as cq
import trimesh
from reportlab.lib.colors import HexColor

import cadkit as ck
import cadraw as cr
import gerar_teste_tela as g

pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI.parent / 'teste-tela'
mf = g.malha(cq.importers.importStep(str(pasta / 'teste-tela-frente.step')))
mt = g.malha(cq.importers.importStep(str(pasta / 'teste-tela-tras.step')))
X, Y = g.X, g.Y
r = lambda t: tuple(round(float(x), 2) for x in t)

# ---------------- medidas tiradas dos arquivos ----------------
for nome, m in (('frente', mf), ('trás', mt)):
    c = ck.check(m)
    print(nome, 'fechado', c['watertight'], 'orientação', c['winding'], 'cascas', len(c['cascas']),
          'volume %.1f cm3' % (c['volume'] / 1000), 'caixa', r(m.bounds[1] - m.bounds[0]))
cont = lambda m, z: [r((d['w'], d['h'])) for d in ck.contours(m, z)]
print('frente z=1,3 (janela)', cont(mf, 1.3))
print('frente z=3,5 (bolso do vidro)', cont(mf, 3.5))
print('frente z=4,6 (rebaixo das soldas)', cont(mf, 4.6))
print('frente z=6,3 (encaixe, pininhos, insertos)', cont(mf, 6.3))
print('rebaixo: fundo no meio da faixa esquerda z =', [r(p) for p in ck.probe(mf, X((g.ENC_U0 + g.BOLSO_U[0]) / 2), Y(g.PCB[1] / 2))],
      '; no canto z =', [r(p) for p in ck.probe(mf, X((g.ENC_U0 + g.BOLSO_U[0]) / 2), Y(g.APOIO_V / 2 + 1.5))])
print('trás z=8,4 (quadro)', cont(mt, 8.4))
for u, v in g.INSERTOS:
    print('inserto', r((u, v)), 'frente z', [r(p) for p in ck.probe(mf, X(u), Y(v))])
import numpy as np
sec = mf.section(plane_origin=[0, 0, 6.3], plane_normal=[0, 0, 1])
pts = np.vstack([e.discrete(sec.vertices) for e in sec.entities])[:, :2]
ix, iy = X(g.INSERTOS[0][0]), Y(g.INSERTOS[0][1])
dist = np.hypot(pts[:, 0] - ix, pts[:, 1] - iy)
u, v = g.CX - pts[:, 0], g.CY - pts[:, 1]
encaixe = (u > g.ENC_U0 - 0.05) & (v > -g.FOLGA - 0.05) & (u < g.ENC_U1 + 0.05) & (v < g.PCB[1] + g.FOLGA + 0.05) & (dist > g.INSERTO_FURO / 2 + 0.05)
fora = (u < g.FORA[0] + 0.05) | (v < g.FORA[2] + 0.05)
print('parede do furo do inserto (canto de cima à esquerda), z=6,3: até o encaixe da placa %.2f mm; até a borda de fora %.2f mm'
      % (dist[encaixe].min() - g.INSERTO_FURO / 2, dist[fora].min() - g.INSERTO_FURO / 2))
inter = trimesh.boolean.intersection([mf, mt], engine='manifold')
print('volume em comum na montagem: %.4f mm3' % (inter.volume if len(inter.faces) else 0.0))
print('ponta do parafuso z = %.2f; fundo do furo do inserto z = %.2f' % (g.Z_CABECA - g.PARAFUSO_L, g.Z_FUNDO_INSERTO))

# ---------------- PDF ----------------
d = cr.Folha(str(pasta / 'teste-tela-verificacao.pdf'))
d.cabecalho('Peça de teste da tela: verificação', 'Medido nos arquivos gerados. Vista por trás, como sai da impressora: os pinos da tela ficam à direita aqui.')
jan = (-57, 57, -36.5, 36.5); e = 2.15
f1 = d.corte(ck.section(mf, 2, 1.3), 46, 345, e, jan)
d.titulo_bloco(46, 510, 'FRENTE, A 1,3 mm: JANELA E INSERTOS')
a = f1(X(g.JANELA[1]), Y(g.JANELA[3]) - 5); b = f1(X(g.JANELA[0]), Y(g.JANELA[3]) - 5)
d.cota_h(a[0], b[0], a[1], '76,2', d.AZUL)
d.balao(1, 46 + 14, 334, *f1(X(g.INSERTOS[3][0]), Y(g.INSERTOS[3][1])), cor=d.LARANJA)
f2 = d.corte(ck.section(mf, 2, 4.6), 310, 345, e, jan)
d.titulo_bloco(310, 510, 'FRENTE, A 4,6 mm: VIDRO E REBAIXO DAS SOLDAS')
xr = X(g.FORA[0]) + 2.5
a = f2(xr, Y(g.REB_V[0])); b = f2(xr, Y(g.REB_V[1]))
d.cota_v(a[1], b[1], a[0], '40,8', d.LARANJA)
d.balao(2, 310 + 250, 334, *f2(X((g.ENC_U0 + g.BOLSO_U[0]) / 2), Y(g.PCB[1] / 2 + 8)), cor=d.LARANJA)
f3 = d.corte(ck.section(mt, 2, 8.4), 46, 150, e, jan)
d.titulo_bloco(46, 315, 'MOLDURA DE TRÁS, A 1,2 mm DA PLACA')
d.balao(3, 46 + 120, 140, *f3(X(g.FUROS[0][0]), Y(g.FUROS[0][1])), cor=d.AZUL)
y = Y(g.INSERTOS[0][1]); jan2 = (X(g.INSERTOS[0][0]) - 6, X(g.INSERTOS[0][0]) + 14, -0.5, 21)
f4 = d.corte(ck.section(mf, 1, y), 310, 70, 7.6, jan2)
d.corte(ck.section(mt, 1, y), 310, 70, 7.6, jan2, preenche=HexColor('#fde8c8'))
d.titulo_bloco(310, 240, 'MONTADO, PELO INSERTO DE CIMA (FRENTE EMBAIXO)')
d.balao(4, 310 + 140, 200, *f4(X(g.INSERTOS[0][0]), 14), cor=d.LARANJA)
f = lambda n: ('%.2f' % n).rstrip('0').rstrip('.').replace('.', ',')
d.notas(620, 490, 190, [
    (d.LARANJA, '1 e 4. Insertos e parafusos', 'Furo de 4,0 por 6,2 nos 4 cantos, por fora da placa, com 0,8 de frente embaixo. O M3 de 19 entra pela torre da moldura de trás: a cabeça apoia a 13 mm da placa e a ponta para 0,4 antes do fundo.'),
    (d.LARANJA, '2. Rebaixo das soldas', 'A placa apoia só nos 4 cantos (%s em cima e embaixo). O meio das duas faixas fica %s mais fundo: as soldas do conector não encostam.' % (f(g.APOIO_V), f(g.REBAIXO))),
    (d.VERDE, 'Pininhos', 'Quatro de 2,8 nos furos da tela, 90,4 x 49,2 entre centros. Alinham a placa; não seguram.'),
    (d.AZUL, 'Encaixe e vidro', 'Encaixe da placa de %s a %s (%s x 55,4), com %s de folga de cada lado. Bolso do vidro com %s, como nos testes em que o vidro entrou perfeito.' % (f(g.ENC_U0), f(g.ENC_U1), f(g.ENC_U1 - g.ENC_U0), f(g.FOLGA_LADO), f(g.BOLSO_U[1] - g.BOLSO_U[0]))),
    (d.AZUL, '3. Moldura de trás', 'Aperta só os 4 cantos da placa, em cima dos furos; o meio fica livre para os componentes e o conector. Fica 0,2 acima da frente: o parafuso puxa e prende a placa.'),
    (d.CINZA, 'Sólidos', 'Os dois fechados, uma casca cada. Montados, não se invadem.'),
])
d.rodape('Gerado por hardware/caixa/gerar_teste_tela.py. Imprimir sem suporte: a frente com a face da tela na mesa; a de trás com as torres para cima.')
d.salvar()
print('PDF:', pasta / 'teste-tela-verificacao.pdf')
