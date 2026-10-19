# -*- coding: utf-8 -*-
"""Peça de teste da tela ILI9488 3,5" (caixa Mini Mac do mascote).

Uma moldura pequena para provar o encaixe antes da caixa inteira: janela da
parte que acende, bolso do vidro, encaixe da placa vermelha e 4 pininhos nos
furos da tela. Impressa com a frente para baixo, sem suporte.

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
FUROS = [(3.25, 2.4), (92.75, 2.4), (3.25, 52.4), (92.75, 52.4)]   # 89,5 x 50 no meio da placa (suposição)
ESP_TELA = 5.4                # da frente do vidro até as costas da placa

# ---------------- escolhas da peça ----------------
FOLGA = 0.3                   # em volta da placa vermelha
PAREDE = 5.0                  # borda da peça em volta do encaixe
PELE = 1.6                    # espessura da frente
CHANFRO = 1.0                 # chanfro de 45° em volta da janela
MARGEM_JANELA = 0.5           # a janela mostra 0,5 mm a mais da parte que acende
PINO_D, PINO_H = 3.0, 1.4     # pininhos: 0,3 de folga no furo de 3,6; não passam da placa (1,6)

FOLGA_VIDRO = 0.4            # em volta do vidro, na largura

# o vidro fica entre a estimativa pela borda esquerda e a pela direita (hoje as duas batem)
v_esq = (VIDRO_BORDAS[0] + (PCB[0] - VIDRO_BORDAS[1] - VIDRO_L)) / 2
VIDRO_U = (v_esq, v_esq + VIDRO_L)
BOLSO_U = (VIDRO_U[0] - FOLGA_VIDRO, VIDRO_U[1] + FOLGA_VIDRO)
assert BOLSO_U[0] > FUROS[0][0] + PINO_D / 2 and BOLSO_U[1] < FUROS[1][0] - PINO_D / 2, 'o bolso do vidro come os pininhos'
Z_APOIO = PELE + (ESP_TELA - 1.6) + 0.2          # onde a placa vermelha apoia (vidro + tela + 0,2)
Z_TOTAL = Z_APOIO + 1.6 + 0.2                    # a placa fica 0,2 abaixo das costas da peça
JANELA = (VIDRO_U[0] + ACENDE[0] - MARGEM_JANELA, VIDRO_U[1] - ACENDE[1] + MARGEM_JANELA,
          VIDRO_V[0] + ACENDE[2] - MARGEM_JANELA, VIDRO_V[1] - ACENDE[3] + MARGEM_JANELA)
FORA = (-FOLGA - PAREDE, PCB[0] + FOLGA + PAREDE, -FOLGA - PAREDE, PCB[1] + FOLGA + PAREDE)

CX, CY = PCB[0] / 2, PCB[1] / 2
X = lambda u: CX - u
Y = lambda v: CY - v


def bloco(u1, u2, v1, v2, z1, z2):
    xa, xb = sorted((X(u1), X(u2)))
    ya, yb = sorted((Y(v1), Y(v2)))
    return cq.Workplane('XY').box(xb - xa, yb - ya, z2 - z1, centered=False).translate((xa, ya, z1))


def peca():
    p = bloco(FORA[0], FORA[1], FORA[2], FORA[3], 0, Z_TOTAL).edges('|Z').fillet(3)
    # encaixe da placa vermelha, por trás
    p = p.cut(bloco(-FOLGA, PCB[0] + FOLGA, -FOLGA, PCB[1] + FOLGA, Z_APOIO, Z_TOTAL + 1))
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
    pinos = (cq.Workplane('XY').workplane(offset=Z_APOIO - 0.1).pushPoints([(X(u), Y(v)) for u, v in FUROS])
             .circle(PINO_D / 2).extrude(PINO_H + 0.1))
    p = p.union(pinos)
    # marca do lado dos pinos: um V na borda esquerda
    vm = Y(PCB[1] / 2)
    marca = (cq.Workplane('XY').workplane(offset=-0.1)
             .polyline([(X(FORA[0]) + 0.1, vm - 2), (X(FORA[0] + 1.6), vm), (X(FORA[0]) + 0.1, vm + 2)]).close()
             .extrude(Z_TOTAL + 0.2))
    return p.cut(marca)


def resumo():
    f = lambda n: ('%.2f' % n).rstrip('0').rstrip('.').replace('.', ',')
    return {
        'peça': '%s x %s x %s' % (f(FORA[1] - FORA[0]), f(FORA[3] - FORA[2]), f(Z_TOTAL)),
        'janela': '%s x %s' % (f(JANELA[1] - JANELA[0]), f(JANELA[3] - JANELA[2])),
        'bolso do vidro': '%s de largura, de %s a %s' % (f(BOLSO_U[1] - BOLSO_U[0]), f(BOLSO_U[0]), f(BOLSO_U[1])),
        'vidro estimado': 'de %s a %s' % (f(VIDRO_U[0]), f(VIDRO_U[1])),
        'apoio da placa': 'z = %s' % f(Z_APOIO),
    }


if __name__ == '__main__':
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    saida.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(peca(), str(saida / 'teste-tela.step'))
    for k, v in resumo().items():
        print('%s: %s' % (k, v))
