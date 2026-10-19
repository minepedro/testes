# -*- coding: utf-8 -*-
"""Peça de teste da tela ILI9488 3,5" (caixa Mini Mac do mascote).

Duas peças para provar o encaixe e a fixação antes da caixa inteira:

- moldura da frente: janela da parte que acende, bolso do vidro, encaixe da
  placa vermelha, 4 pininhos nos furos da tela e 4 furos para insertos M3
  nos cantos, por fora da placa;
- moldura de trás: um quadro que aperta os cantos da placa vermelha contra a
  frente, preso por 4 parafusos M3 nos insertos.

Os parafusos não passam pelos furos da própria tela: do furo até o vidro sobram
menos de 3 mm, pouco para a cabeça do M3 ou para a parede de um inserto. Os
furos da tela ficam com os pininhos, que alinham a placa.

Medidas em mm. Coordenadas (u, v) vistas de frente, com o mascote em pé e os
pinos da tela à esquerda: u para a direita, v para baixo, origem na quina de
cima à esquerda da placa vermelha. No modelo a frente fica em z = 0 (na mesa
da impressora); quem olha de frente vê x espelhado, por isso x = 48 - u.

Uso: python3 gerar_teste_tela.py <pasta de saída>
"""
import sys
from pathlib import Path

import cadquery as cq

# ---------------- medidas da tela (página "Medidas do Mini Mac") ----------------
PCB = (96.0, 54.8)            # placa vermelha: 0,3 + 54,2 + 0,3 na altura
VIDRO_L = 84.2                # largura do vidro: 6,1 + 84,2 + 5,7 = 96, fecha com a placa
VIDRO_BORDAS = (6.1, 5.7)     # da borda da placa até o vidro: esquerda (pinos), direita
VIDRO_V = (0.3, 54.5)         # o vidro em cima e embaixo
ACENDE = (2.0, 7.0, 2.0, 2.0) # do vidro até a parte que acende: esquerda, direita, cima, baixo
FURO_D = 3.6                  # furos da tela
FURO_BORDA = 1.0              # da borda da placa até a beirada do furo, nos dois sentidos
ESP_TELA = 5.4                # da frente do vidro até as costas da placa

# ---------------- fixação ----------------
INSERTO_FURO, INSERTO_L = 4.0, 5.7   # inserto M3 de calor: furo de 4,0 para um inserto de 5,7 (suposição)
PARAFUSO_L = 19.0                    # os M3 que você tem; com M3 x 8 as torres somem
PARAFUSO_FOLGA = 3.4                 # furo de passagem do M3
TORRE_D = 7.0                        # torre da moldura de trás, onde a cabeça do parafuso apoia
QUADRO_E = 2.4                       # espessura da moldura de trás

# ---------------- escolhas da peça ----------------
FOLGA = 0.3                   # em volta da placa vermelha
PAREDE = 7.0                  # borda da peça em volta do encaixe (cabe o inserto nos cantos)
PELE = 1.6                    # espessura da frente
CHANFRO = 1.0                 # chanfro de 45° em volta da janela
MARGEM_JANELA = 0.5           # a janela mostra 0,5 mm a mais da parte que acende
PINO_D, PINO_H = 2.8, 1.4     # pininhos: 0,4 de folga no furo de 3,6; não passam da placa (1,6)
FOLGA_VIDRO = 0.4             # em volta do vidro, na largura
# o primeiro teste impresso: o vidro entrou perfeito; a placa vermelha não entrou do lado esquerdo (o dos pinos)
ENCAIXE_ESQ = 2.0             # encaixe da placa: 2 mm a mais à esquerda, 1 que faltou e 1 de garantia

c = FURO_BORDA + FURO_D / 2
FUROS = [(c, c), (PCB[0] - c, c), (c, PCB[1] - c), (PCB[0] - c, PCB[1] - c)]
# o vidro fica entre a estimativa pela borda esquerda e a pela direita (hoje as duas batem)
v_esq = (VIDRO_BORDAS[0] + (PCB[0] - VIDRO_BORDAS[1] - VIDRO_L)) / 2
VIDRO_U = (v_esq, v_esq + VIDRO_L)
BOLSO_U = (VIDRO_U[0] - FOLGA_VIDRO, VIDRO_U[1] + FOLGA_VIDRO)
ENC_U0 = -FOLGA - ENCAIXE_ESQ                    # borda esquerda do encaixe da placa
assert BOLSO_U[0] > FUROS[0][0] + PINO_D / 2 and BOLSO_U[1] < FUROS[1][0] - PINO_D / 2, 'o bolso do vidro come os pininhos'
Z_APOIO = PELE + (ESP_TELA - 1.6) + 0.2          # onde a placa vermelha apoia (vidro + tela + 0,2)
Z_PLACA = Z_APOIO + 1.6                          # costas da placa vermelha
Z_TOTAL = Z_PLACA - 0.2                          # a placa fica 0,2 para fora: a moldura de trás aperta nela
JANELA = (VIDRO_U[0] + ACENDE[0] - MARGEM_JANELA, VIDRO_U[1] - ACENDE[1] + MARGEM_JANELA,
          VIDRO_V[0] + ACENDE[2] - MARGEM_JANELA, VIDRO_V[1] - ACENDE[3] + MARGEM_JANELA)
FORA = (-FOLGA - PAREDE, PCB[0] + FOLGA + PAREDE, -FOLGA - PAREDE, PCB[1] + FOLGA + PAREDE)
# insertos nos cantos, por fora do encaixe da placa
d = FOLGA + 3.3
INSERTOS = [(-d, -d), (PCB[0] + d, -d), (-d, PCB[1] + d), (PCB[0] + d, PCB[1] + d)]
Z_FUNDO_INSERTO = Z_TOTAL - INSERTO_L - 0.5
Z_CABECA = Z_FUNDO_INSERTO + 0.4 + PARAFUSO_L    # onde a cabeça apoia para a ponta não bater no fundo
# a moldura de trás aperta os cantos da placa (sobre os furos) sem tocar no meio
CANTO = (5.0, 5.6)            # tamanho do apoio em cada canto, a partir da borda da placa

CX, CY = PCB[0] / 2, PCB[1] / 2
X = lambda u: CX - u
Y = lambda v: CY - v


def bloco(u1, u2, v1, v2, z1, z2):
    xa, xb = sorted((X(u1), X(u2)))
    ya, yb = sorted((Y(v1), Y(v2)))
    return cq.Workplane('XY').box(xb - xa, yb - ya, z2 - z1, centered=False).translate((xa, ya, z1))


def cilindros(pontos, diam, z1, z2):
    return (cq.Workplane('XY').workplane(offset=z1).pushPoints([(X(u), Y(v)) for u, v in pontos])
            .circle(diam / 2).extrude(z2 - z1))


def frente():
    p = bloco(FORA[0], FORA[1], FORA[2], FORA[3], 0, Z_TOTAL).edges('|Z').fillet(3)
    # encaixe da placa vermelha, por trás
    p = p.cut(bloco(ENC_U0, PCB[0] + FOLGA, -FOLGA, PCB[1] + FOLGA, Z_APOIO, Z_TOTAL + 1))
    # bolso do vidro: altura toda do encaixe; sobe 0,1 dentro do encaixe para não deixar face coincidente
    p = p.cut(bloco(BOLSO_U[0], BOLSO_U[1], -FOLGA, PCB[1] + FOLGA, PELE, Z_APOIO + 0.1))
    # janela com chanfro de 45°: começa 0,5 abaixo da frente para o corte atravessar limpo
    jw, jh = JANELA[1] - JANELA[0], JANELA[3] - JANELA[2]
    jx, jy = X((JANELA[0] + JANELA[1]) / 2), Y((JANELA[2] + JANELA[3]) / 2)
    extra = CHANFRO + 0.5
    chanfro = (cq.Workplane('XY').workplane(offset=-0.5).center(jx, jy).rect(jw + 2 * extra, jh + 2 * extra)
               .workplane(offset=CHANFRO + 0.5).rect(jw, jh).loft())
    reto = cq.Workplane('XY').workplane(offset=CHANFRO - 0.01).center(jx, jy).rect(jw, jh).extrude(PELE - CHANFRO + 0.2)
    p = p.cut(chanfro).cut(reto)
    # pininhos: nascem 0,1 dentro do apoio
    p = p.union(cilindros(FUROS, PINO_D, Z_APOIO - 0.1, Z_APOIO + PINO_H))
    # furos dos insertos, por trás
    p = p.cut(cilindros(INSERTOS, INSERTO_FURO, Z_FUNDO_INSERTO, Z_TOTAL + 1))
    # marca do lado dos pinos: um V na borda esquerda
    vm = Y(PCB[1] / 2)
    marca = (cq.Workplane('XY').workplane(offset=-0.1)
             .polyline([(X(FORA[0]) + 0.1, vm - 2), (X(FORA[0] + 1.6), vm), (X(FORA[0]) + 0.1, vm + 2)]).close()
             .extrude(Z_TOTAL + 0.2))
    return p.cut(marca)


def tras():
    """Moldura de trás na posição montada: a face de baixo encosta nas costas da placa."""
    z1, z2 = Z_PLACA, Z_PLACA + QUADRO_E
    q = bloco(FORA[0], FORA[1], FORA[2], FORA[3], z1, z2).edges('|Z').fillet(3)
    vao = bloco(ENC_U0, PCB[0] + FOLGA, -FOLGA, PCB[1] + FOLGA, z1 - 1, z2 + 1)
    for u1, u2 in ((ENC_U0 - 1, CANTO[0]), (PCB[0] - CANTO[0], PCB[0] + FOLGA + 1)):
        for v1, v2 in ((-FOLGA - 1, CANTO[1]), (PCB[1] - CANTO[1], PCB[1] + FOLGA + 1)):
            vao = vao.cut(bloco(u1, u2, v1, v2, z1 - 2, z2 + 2))
    q = q.cut(vao)
    q = q.union(cilindros(INSERTOS, TORRE_D, z2 - 0.1, Z_CABECA))
    return q.cut(cilindros(INSERTOS, PARAFUSO_FOLGA, z1 - 1, Z_CABECA + 1))


def resumo():
    f = lambda n: ('%.2f' % n).rstrip('0').rstrip('.').replace('.', ',')
    return {
        'frente': '%s x %s x %s' % (f(FORA[1] - FORA[0]), f(FORA[3] - FORA[2]), f(Z_TOTAL)),
        'janela': '%s x %s' % (f(JANELA[1] - JANELA[0]), f(JANELA[3] - JANELA[2])),
        'bolso do vidro': '%s de largura, de %s a %s' % (f(BOLSO_U[1] - BOLSO_U[0]), f(BOLSO_U[0]), f(BOLSO_U[1])),
        'encaixe da placa': '%s x %s, de %s a %s' % (f(PCB[0] + FOLGA - ENC_U0), f(PCB[1] + 2 * FOLGA), f(ENC_U0), f(PCB[0] + FOLGA)),
        'furos da tela': 'centros a %s das bordas: %s x %s' % (f(c), f(FUROS[1][0] - FUROS[0][0]), f(FUROS[2][1] - FUROS[0][1])),
        'insertos': 'furo %s, fundo a %s da frente' % (f(INSERTO_FURO), f(Z_FUNDO_INSERTO)),
        'trás': '%s de quadro, torres até %s acima da placa' % (f(QUADRO_E), f(Z_CABECA - Z_PLACA)),
    }


def exportar_3mf(pecas, caminho, cor='#D8CDB2'):
    """3MF com cada peça como um objeto separado na mesa, todas na mesma cor."""
    import zipfile
    NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    objs, itens = [], []
    for i, (nome, m) in enumerate(pecas.items(), start=1):
        vs = ''.join('<vertex x="%.5f" y="%.5f" z="%.5f"/>' % tuple(v) for v in m.vertices)
        ts = ''.join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(t) for t in m.faces)
        objs.append('<object id="%d" type="model" name="%s" pid="100" pindex="0"><mesh><vertices>%s</vertices>'
                    '<triangles>%s</triangles></mesh></object>' % (i, nome, vs, ts))
        itens.append('<item objectid="%d"/>' % i)
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="%s">'
             '<resources><basematerials id="100"><base name="bege" displaycolor="%sFF"/></basematerials>%s</resources>'
             '<build>%s</build></model>' % (NS, cor, ''.join(objs), ''.join(itens)))
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', model)


def malha(shape):
    import os, tempfile, trimesh
    f = tempfile.mktemp(suffix='.stl')
    cq.exporters.export(shape, f, tolerance=0.005, angularTolerance=0.1)
    m = trimesh.load(f, force='mesh')
    os.unlink(f)
    return m


if __name__ == '__main__':
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    saida.mkdir(parents=True, exist_ok=True)
    f, t = frente(), tras()
    cq.exporters.export(f, str(saida / 'teste-tela-frente.step'))
    cq.exporters.export(t, str(saida / 'teste-tela-tras.step'))
    # na mesa: a frente com a face da tela para baixo; a de trás deitada com as torres para cima, ao lado
    mf, mt = malha(f), malha(t)
    mt.apply_translation((0, -(FORA[3] - FORA[2]) - 8, -Z_PLACA))
    exportar_3mf({'moldura da frente': mf, 'moldura de trás': mt}, saida / 'teste-tela.3mf')
    for k, v in resumo().items():
        print('%s: %s' % (k, v))
