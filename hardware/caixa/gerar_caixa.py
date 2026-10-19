# -*- coding: utf-8 -*-
"""Caixa Mini Mac do mascote: gera as peças para imprimir e um modelo para ver em 3D.

Peças impressas:
- corpo: frente, topo e laterais numa peça só, com a moldura da tela, o queixo
  (LED, grade do microfone, botão), a grade do alto-falante, a entrada do cabo
  USB-C embutida na lateral direita, os trilhos da bandeja e o berço do
  amplificador; impresso com a frente na mesa;
- bandeja: o fundo com os pininhos da placa ilhada e a tampa de trás, que
  desliza por trás e prende com 2 parafusos M3 em insertos;
- moldura de trás da tela: aperta os cantos da placa vermelha com 4 parafusos
  M3 em insertos (os insertos ficam em cima e embaixo da tela);
- tecla do botão e tampa do microfone.

Medidas em mm. Caixa: x para a direita vista de frente, y para trás, z para
cima, origem na quina de baixo à esquerda da frente. A tela usa as mesmas
medidas e encaixes do teste (gerar_teste_tela.py), em coordenadas (u, v) da
placa vermelha: u para a direita, v para baixo.

Uso: python3 gerar_caixa.py <pasta de saída>
"""
import math
import sys
from pathlib import Path

import cadquery as cq

import gerar_teste_tela as T

# ---------------- caixa ----------------
W, D, H = 110.0, 112.0, 130.0
PAR = 2.4                     # paredes
R_TOPO, R_BASE, R_FRENTE = 6.0, 2.0, 1.2

# ---------------- tela (mesmos encaixes do teste) ----------------
JAN_U = (T.JANELA[0] + T.JANELA[1]) / 2
PCB_X0 = W / 2 - JAN_U        # a janela fica no meio da caixa
PCB_Z1 = 120.0                # topo da placa vermelha
RECUO, BISEL = 3.0, 5.0       # a tela fica 3 mm para dentro, numa moldura chanfrada que começa 5 mm fora da janela
Y_VIDRO = RECUO + T.PELE      # frente do bolso do vidro
Y_APOIO = Y_VIDRO + (T.Z_APOIO - T.PELE)       # onde a placa vermelha apoia
Y_COSTAS = Y_APOIO + (T.Z_TOTAL - T.Z_APOIO)   # costas da moldura da tela (a placa fica 0,2 para fora)
Y_PLACA = Y_APOIO + 1.6
INSERTOS_TELA = [(10.0, -3.6), (86.0, -3.6), (10.0, T.PCB[1] + 3.6), (86.0, T.PCB[1] + 3.6)]   # (u, v): em cima e embaixo
Y_CABECA_TELA = Y_COSTAS - T.INSERTO_L - 0.5 + 0.4 + T.PARAFUSO_L

def tx(u): return PCB_X0 + u
def tz(v): return PCB_Z1 - v

# ---------------- queixo ----------------
Z_QUEIXO = 38.0
LED, MIC, BOTAO = (16.0, Z_QUEIXO), (W / 2, Z_QUEIXO), (W - 16.0, Z_QUEIXO)
LED_D, LED_ABA = 5.1, 6.2     # LED de 5 mm: a ponta fica rente à frente, a aba apoia atrás
MIC_D, MIC_ESP = 14.0, 1.2    # plaquinha redonda do INMP441
EVA = 1.0                     # anel de vedação entre a grade e o microfone

# ---------------- placa ilhada e cabo ----------------
PLACA = (80.0, 60.0)
USB_DENTRO = 8.3              # o USB do ESP32 fica 8,3 para dentro da borda da placa
USB_ACIMA = 13.9              # meio do USB acima da face de cima da placa
FUROS_PLACA = (75.6, 55.8, 2.2)
PLUGUE = (12.0, 6.5, 20.0)    # plástico do plugue: largura, altura, comprimento (suposição até medir)
J_USB = 25.1                  # da borda do lado da linha A até o meio do USB (estimativa até medir)
Z_FUNDO = (1.0, 3.4)          # o fundo da bandeja corre nos trilhos entre estas alturas
ESPACADOR = 5.0               # da face de cima do fundo até a placa
# o plugue entra inteiro: o fim do plástico fica rente à lateral
X_TOMADA = W - PLUGUE[2]                       # face do USB do ESP32
BX1 = X_TOMADA + USB_DENTRO                    # borda da placa do lado da coluna 1 (direita)
BX0 = BX1 - PLACA[0]
BY0 = 44.0                                     # borda do lado da linha V (frente)
BY1 = BY0 + PLACA[1]                           # borda do lado da linha A (trás)
BZ0 = Z_FUNDO[1] + ESPACADOR
BZ1 = BZ0 + 1.6
USB_Y, USB_Z = BY1 - J_USB, BZ1 + USB_ACIMA

# ---------------- alto-falante, amplificador, ventilação, parafusos de trás ----------------
ALTO = (W / 2, 70.0, 40.0, 21.0)               # x, y do centro, diâmetro, profundidade
AMP = (18.0, 19.3)                             # plaquinha do amplificador (suposição: 18 x 19)
AMP_Y, AMP_Z = (52.0, 76.0), 72.0              # trecho dos trilhos e altura da borda de baixo da plaquinha
TRAS_INSERTOS = [(PAR + 4.5, H - PAR - 4.5), (W - PAR - 4.5, H - PAR - 4.5)]   # (x, z)

FOLGA_BANDEJA = 0.3


# ================= utilidades =================
def caixa(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cil(eixo, centro, d, a, b):
    """Cilindro de diâmetro d no eixo 'x', 'y' ou 'z', de a até b, passando por centro (as outras duas coordenadas)."""
    if eixo == 'y':
        return cq.Workplane('XZ').workplane(offset=-a).center(*centro).circle(d / 2).extrude(-(b - a))
    if eixo == 'z':
        return cq.Workplane('XY').workplane(offset=a).center(*centro).circle(d / 2).extrude(b - a)
    return cq.Workplane('YZ').workplane(offset=a).center(*centro).circle(d / 2).extrude(b - a)


def retangulo_arredondado(cx, cz, w, h, r, y, n=6):
    """Pontos de um retângulo de cantos arredondados no plano y (x, y, z)."""
    r = max(min(r, w / 2 - 0.01, h / 2 - 0.01), 0.01)
    pts = []
    for (ax, az, a0) in ((cx + w / 2 - r, cz + h / 2 - r, 0), (cx - w / 2 + r, cz + h / 2 - r, 90),
                         (cx - w / 2 + r, cz - h / 2 + r, 180), (cx + w / 2 - r, cz - h / 2 + r, 270)):
        for i in range(n + 1):
            t = math.radians(a0 + 90 * i / n)
            pts.append(cq.Vector(ax + r * math.cos(t), y, az + r * math.sin(t)))
    return cq.Wire.makePolygon(pts, close=True)


def tronco(cx, cz, w0, h0, r0, y0, w1, h1, r1, y1):
    """Sólido entre dois retângulos arredondados (para chanfros e túneis)."""
    return cq.Workplane().add(cq.Solid.makeLoft([retangulo_arredondado(cx, cz, w0, h0, r0, y0),
                                                 retangulo_arredondado(cx, cz, w1, h1, r1, y1)], True))


def prisma(plano, pts, a, b):
    """Polígono pts desenhado no plano 'XY', 'XZ' ou 'YZ' (coordenadas na ordem do nome) e puxado de a até b no eixo que falta."""
    if plano == 'XZ':
        return cq.Workplane('XZ').workplane(offset=-a).polyline(pts).close().extrude(-(b - a))
    return cq.Workplane(plano).workplane(offset=a).polyline(pts).close().extrude(b - a)


def pilula_x(cy, cz, w, h, x0, x1, extra=0.0):
    """Túnel em forma de pílula ao longo de x (largura w em y, altura h em z)."""
    s = cq.Workplane('YZ').workplane(offset=x0).center(cy, cz).slot2D(w + 2 * extra, h + 2 * extra, 90 if h > w else 0)
    return s.extrude(x1 - x0)


# ================= corpo =================
def batente(x, z):
    """Coluna do inserto de trás encostada no canto de cima, arredondada para dentro, com rampa embaixo para imprimir sem suporte."""
    s = 1 if x < W / 2 else -1
    xp, zt, r = (PAR - 0.1) if s > 0 else (W - PAR + 0.1), H - PAR + 0.1, 4.5
    y0, y1 = D - PAR - 18, D - PAR - 0.2
    perfil = (cq.Workplane('XZ').workplane(offset=-y0).moveTo(xp, zt).lineTo(x + s * r, zt).lineTo(x + s * r, z)
              .threePointArc((x + s * r * math.cos(math.pi / 4), z - r * math.sin(math.pi / 4)), (x, z - r))
              .lineTo(xp, z - r).close().extrude(-(y1 - y0)))
    q = lambda xa, xb, za, y: cq.Wire.makePolygon([cq.Vector(xa, y, za), cq.Vector(xb, y, za), cq.Vector(xb, y, zt), cq.Vector(xa, y, zt)], close=True)
    rampa = cq.Solid.makeLoft([q(xp, x + s * r, z - r, y0 + 0.01), q(xp, xp + s * 0.4, zt - 0.4, y0 - 12)], True)
    return perfil.union(cq.Workplane().add(rampa))


def corpo():
    c = caixa(0, W, 0, D, 0, H)
    c = c.edges('|Y and >Z').fillet(R_TOPO).edges('|Y and <Z').fillet(R_BASE)
    c = c.faces('<Y').edges().fillet(R_FRENTE)
    c = c.cut(caixa(PAR, W - PAR, PAR, D + 1, -1, H - PAR))

    # moldura da tela: um bloco atrás da frente, de onde saem o recuo, a janela, o bolso do vidro e o encaixe da placa
    zb0 = tz(T.PCB[1] + 3.6) - T.INSERTO_FURO / 2 - 2.0
    c = c.union(caixa(PAR - 0.1, W - PAR + 0.1, 0.5, Y_COSTAS, zb0, H - PAR + 0.1))
    jw, jh = T.JANELA[1] - T.JANELA[0], T.JANELA[3] - T.JANELA[2]
    jx, jz = tx(JAN_U), tz((T.JANELA[2] + T.JANELA[3]) / 2)
    c = c.cut(tronco(jx, jz, jw + 2 * (BISEL + 0.5), jh + 2 * (BISEL + 0.5), 5.5, -0.5, jw + 4, jh + 4, 2.0, RECUO))
    c = c.cut(tronco(jx, jz, jw + 2.02, jh + 2.02, 1.5, RECUO - 0.01, jw, jh, 0.5, RECUO + 1.0))
    c = c.cut(tronco(jx, jz, jw, jh, 0.5, RECUO + 0.99, jw, jh, 0.5, Y_VIDRO + 0.2))
    c = c.cut(caixa(tx(T.BOLSO_U[0]), tx(T.BOLSO_U[1]), Y_VIDRO, Y_APOIO + 0.1, tz(T.PCB[1] + T.FOLGA), tz(-T.FOLGA)))
    c = c.cut(caixa(tx(T.ENC_U0), tx(T.ENC_U1), Y_APOIO, Y_COSTAS + 1, tz(T.PCB[1] + T.FOLGA), tz(-T.FOLGA)))
    for u1, u2 in ((T.ENC_U0, T.BOLSO_U[0] + 0.1), (T.BOLSO_U[1] - 0.1, T.ENC_U1)):   # rebaixo das soldas: a placa apoia só nos cantos
        c = c.cut(caixa(tx(u1), tx(u2), Y_APOIO - T.REBAIXO, Y_APOIO + 0.1, tz(T.REB_V[1]), tz(T.REB_V[0])))
    for u, v in T.FUROS:
        c = c.union(cil('y', (tx(u), tz(v)), T.PINO_D, Y_APOIO - 0.1, Y_APOIO + T.PINO_H))
    for u, v in INSERTOS_TELA:
        c = c.cut(cil('y', (tx(u), tz(v)), T.INSERTO_FURO, Y_COSTAS - T.INSERTO_L - 0.5, Y_COSTAS + 1))

    # LED: ponta rente à frente, aba apoiada atrás, dentro de uma luva
    c = c.union(cil('y', LED, LED_ABA + 3.0, PAR - 0.1, 11.0))
    c = c.cut(cil('y', LED, LED_D, -1, 8.6)).cut(cil('y', LED, LED_ABA, 8.6, 12))
    # microfone: grade na frente e copo atrás, com o anel de EVA e a plaquinha
    for i in range(-2, 3):      # 19 furos de 1,4 em colmeia, todos dentro do copo
        for j in range(-2, 3):
            dx, dz = (i + j / 2) * 2.6, j * 2.6 * math.sqrt(3) / 2
            if math.hypot(dx, dz) < 5.3:
                c = c.cut(cil('y', (MIC[0] + dx, MIC[1] + dz), 1.4, -1, PAR + 0.5))
    copo = PAR + EVA + MIC_ESP + 0.2
    c = c.union(cil('y', MIC, MIC_D + 4.4, PAR - 0.1, copo)).cut(cil('y', MIC, MIC_D + 0.6, PAR, copo + 1))
    # botão: furo da tecla, anel decorativo na frente e suporte do botão tátil atrás
    c = c.cut(cil('y', BOTAO, 4.4, -1, PAR + 1)).cut(cil('y', BOTAO, 8.0, -1, 0.6))
    bx, bz = BOTAO
    c = c.union(caixa(bx - 5.0, bx + 5.0, PAR - 0.1, 10.0, bz - 5.0, bz + 5.0))
    c = c.cut(cil('y', BOTAO, 7.6, PAR - 0.2, 3.9))
    c = c.cut(caixa(bx - 3.1, bx + 3.1, 3.8, 8.4, bz - 3.1, bz + 3.1)).cut(caixa(bx - 3.1, bx + 3.1, 8.3, 11, bz - 4.1, bz + 4.1))

    # alto-falante: grade no topo e 4 aletas que centralizam a armação
    ax, ay, ad, ap = ALTO
    for r, n in ((0, 1), (4, 6), (8, 12), (12, 18), (16, 24)):
        for k in range(n):
            a = 2 * math.pi * k / n
            c = c.cut(cil('z', (ax + r * math.cos(a), ay + r * math.sin(a)), 1.6, H - PAR - 1, H + 1))
    rc, zt, zf = ad / 2 + 0.3, H - PAR + 0.1, H - PAR - 3.0      # encosto a 0,3 da armação; aletas de 3 mm
    lado = [(ay - 4, zt), (ay + 4, zt), (ay + 4, zf), (ay - 1, zf)]   # a ponta da frente chanfrada a 45°
    for x0 in (ax - rc - 1.2, ax + rc):
        c = c.union(prisma('YZ', lado, x0, x0 + 1.2))
    c = c.union(prisma('YZ', [(ay - rc - 6, zt), (ay - rc, zt), (ay - rc, zf), (ay - rc - 3, zf)], ax - 0.6, ax + 0.6))
    c = c.union(prisma('YZ', [(ay + rc, zt), (ay + rc + 6, zt), (ay + rc + 6, zf), (ay + rc + 3, zf)], ax - 0.6, ax + 0.6))

    # amplificador: dois trilhos na parede esquerda; a plaquinha entra deslizando por trás
    for zb, lado in ((AMP_Z, -1), (AMP_Z + AMP[1], 1)):
        base = prisma('XY', [(PAR - 0.1, AMP_Y[0] - 4.3), (PAR + 4.2, AMP_Y[0]), (PAR + 4.2, AMP_Y[1]), (PAR - 0.1, AMP_Y[1])],
                      zb - 1.3 if lado < 0 else zb - 1.2, zb + 1.2 if lado < 0 else zb + 1.3)   # ponta da frente a 45°
        fenda = caixa(PAR + 1.8, PAR + 3.8, AMP_Y[0] + 2, AMP_Y[1] + 1, zb - 0.1 if lado < 0 else zb - 1.3, zb + 1.3 if lado < 0 else zb + 0.1)
        c = c.union(base).cut(fenda)

    # entrada do cabo USB-C embutida na lateral direita: chanfro, parede e uma luva curta que guia o plugue
    pw, ph = PLUGUE[0] + 0.6, PLUGUE[1] + 0.6
    ly0, ly1, lx = USB_Y - pw / 2 - 1.6, USB_Y + pw / 2 + 1.6, W - PAR - 7.6
    c = c.union(prisma('XY', [(lx, ly0), (lx, ly1), (W - PAR + 0.1, ly1), (W - PAR + 0.1, ly0 - (W - PAR + 0.1 - lx))],
                       USB_Z - ph / 2 - 1.6, USB_Z + ph / 2 + 1.6))
    c = c.cut(pilula_x(USB_Y, USB_Z, pw, ph, W - PAR - 8, W + 1))
    chanfro = (cq.Workplane('YZ').workplane(offset=W - 1.0).center(USB_Y, USB_Z).slot2D(pw, ph, 0)
               .workplane(offset=1.5).slot2D(pw + 3, ph + 3, 0).loft())
    c = c.cut(chanfro)

    # trilhos da bandeja nas duas laterais (o fundo corre entre eles) e os batentes dos parafusos de trás
    fim = D - PAR - FOLGA_BANDEJA
    for x0, x1 in ((PAR - 0.1, PAR + 1.5), (W - PAR - 1.5, W - PAR + 0.1)):
        c = c.union(caixa(x0, x1, PAR - 0.1, fim, 0, Z_FUNDO[0])).union(caixa(x0, x1, PAR - 0.1, fim, Z_FUNDO[1] + 0.2, Z_FUNDO[1] + 1.6))
    for x, z in TRAS_INSERTOS:
        c = c.union(batente(x, z))
        c = c.cut(cil('y', (x, z), T.INSERTO_FURO, D - PAR - T.INSERTO_L - 0.7, D)).cut(cil('y', (x, z), 2.8, D - PAR - 17.5, D))
    # ventilação nas duas laterais, perto do topo e de trás
    for k in range(5):
        z = 96 + k * 4.5
        for x0, x1 in ((-1, PAR + 1), (W - PAR - 1, W + 1)):
            c = c.cut(caixa(x0, x1, D - 30, D - 8, z, z + 1.6).edges('|X').fillet(0.75))
    return c


# ================= bandeja =================
def bandeja():
    x0, x1 = PAR + FOLGA_BANDEJA, W - PAR - FOLGA_BANDEJA
    b = caixa(x0, x1, PAR + FOLGA_BANDEJA, D, Z_FUNDO[0], Z_FUNDO[1])
    b = b.union(caixa(x0, x1, D - PAR, D, Z_FUNDO[0], H - PAR - FOLGA_BANDEJA))
    # pininhos da placa ilhada em cima de espaçadores
    cx, cy = (BX0 + BX1) / 2, (BY0 + BY1) / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = (cx + sx * FUROS_PLACA[0] / 2, cy + sy * FUROS_PLACA[1] / 2)
            b = b.union(cil('z', p, 5.0, Z_FUNDO[1] - 0.1, BZ0)).union(cil('z', p, FUROS_PLACA[2] - 0.1, BZ0 - 0.1, BZ1 + 1.0))
    # tampa de trás: ventilação e os 2 parafusos
    for k in range(11):
        x = W / 2 + (k - 5) * 5.0
        b = b.cut(caixa(x - 0.9, x + 0.9, D - PAR - 1, D + 1, 92, 118).edges('|Y').fillet(0.85))
    for x, z in TRAS_INSERTOS:
        b = b.cut(cil('y', (x, z), 3.4, D - PAR - 1, D + 1))
    return b


# ================= moldura de trás da tela =================
def moldura_tela():
    y0, y1 = Y_PLACA, Y_PLACA + T.QUADRO_E
    vs, vi = -T.FOLGA, T.PCB[1] + T.FOLGA
    m = caixa(tx(T.ENC_U0), tx(T.ENC_U1), y0, y1, tz(-7.3), tz(vs))           # barra de cima
    m = m.union(caixa(tx(T.ENC_U0), tx(T.ENC_U1), y0, y1, tz(vi + 7.3), tz(vi)))   # barra de baixo
    m = m.union(caixa(tx(T.ENC_U0) - 4.0, tx(T.ENC_U0) + 0.01, y0, y1, tz(vi + 7.3), tz(-7.3)))   # liga as duas por fora da placa, do lado dos pinos
    a, bb = T.CANTO
    for u0, u1 in ((T.ENC_U0, a), (T.PCB[0] - a, T.ENC_U1)):                    # apoios nos cantos, em cima dos furos
        for v0, v1 in ((vs, bb), (T.PCB[1] - bb, vi)):
            m = m.union(caixa(tx(u0), tx(u1), y0, y1, tz(v1), tz(v0)))
    for u, v in INSERTOS_TELA:
        m = m.union(cil('y', (tx(u), tz(v)), T.TORRE_D, y1 - 0.1, Y_CABECA_TELA))
        m = m.cut(cil('y', (tx(u), tz(v)), T.PARAFUSO_FOLGA, y0 - 1, Y_CABECA_TELA + 1))
    return m


# ================= tecla e tampa do microfone =================
def tecla():
    t = cil('y', BOTAO, 4.0, 0.2, PAR + 0.05)
    return t.union(cil('y', BOTAO, 7.0, PAR, PAR + 1.0)).union(cil('y', BOTAO, 3.0, PAR + 0.9, 3.8))


def tampa_mic():
    copo = PAR + EVA + MIC_ESP + 0.2
    t = cil('y', MIC, MIC_D + 4.4 + 2.8, PAR + 0.2, copo + 1.6).cut(cil('y', MIC, MIC_D + 4.4 + 0.2, PAR, copo))
    return t.cut(caixa(MIC[0] - 8, MIC[0] + 8, copo - 1, copo + 3, MIC[1] - 3, MIC[1] + 3))


# ================= peças de referência (não imprimem; só para ver e conferir) =================
def fantasmas():
    f = {}
    f['tela: vidro'] = caixa(tx(T.VIDRO_U[0]), tx(T.VIDRO_U[1]), Y_VIDRO + 0.2, Y_APOIO, tz(T.VIDRO_V[1]), tz(T.VIDRO_V[0]))
    f['tela: placa'] = caixa(tx(0), tx(T.PCB[0]), Y_APOIO, Y_PLACA, tz(T.PCB[1]), tz(0))
    for u, v in T.FUROS:
        f['tela: placa'] = f['tela: placa'].cut(cil('y', (tx(u), tz(v)), T.FURO_D, Y_APOIO - 1, Y_PLACA + 1))
    f['tela: jumpers'] = caixa(tx(1.3), tx(3.9), Y_PLACA, Y_PLACA + 2.5 + 14, tz(45.2), tz(9.6))
    for k in range(14):        # soldas do conector na frente da placa (estimativa: 1,5 de altura, conector no meio da borda)
        f['tela: jumpers'] = f['tela: jumpers'].union(cil('y', (tx(2.6), tz(T.PCB[1] / 2 + (k - 6.5) * 2.54)), 1.8, Y_APOIO - 1.5, Y_APOIO + 0.05))
    f['placa ilhada'] = caixa(BX0, BX1, BY0, BY1, BZ0, BZ1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = ((BX0 + BX1) / 2 + sx * FUROS_PLACA[0] / 2, (BY0 + BY1) / 2 + sy * FUROS_PLACA[1] / 2)
            f['placa ilhada'] = f['placa ilhada'].cut(cil('z', p, FUROS_PLACA[2], BZ0 - 1, BZ1 + 1))
    lin = lambda r: BY1 - (3.33 + (r - 1) * 2.54)
    col = lambda k: BX1 - (6.98 + (k - 1) * 2.54)
    f['ESP32'] = caixa(col(23) - 7.5, X_TOMADA + 0.8, lin(12) - 1.6, lin(2) + 1.6, BZ1, BZ0 - 1 + 19.3)
    f['jumpers da placa'] = caixa(col(21) - 1.3, col(9) + 1.3, lin(17) - 1.3, lin(17) + 1.3, BZ1, BZ0 - 1 + 48.5)
    f['jumpers do mic'] = caixa(col(4) - 1.3, col(1) + 1.3, lin(19) - 1.3, lin(17) + 1.3, BZ1, BZ1 + 8.5 + 14)
    f['jumpers do amp'] = caixa(col(27) - 1.3, col(27) + 1.3, lin(22) - 1.3, lin(18) + 1.3, BZ1, BZ1 + 8.5 + 14)
    f['plugue USB-C'] = pilula_x(USB_Y, USB_Z, PLUGUE[0], PLUGUE[1], X_TOMADA, W).union(cil('x', (USB_Y, USB_Z), 3.5, W, W + 12))
    ax, ay, ad, ap = ALTO
    f['alto-falante'] = cil('z', (ax, ay), ad, H - PAR - 3, H - PAR - 0.05).union(cil('z', (ax, ay), ad * 0.45, H - PAR - ap, H - PAR - 3))
    f['amplificador'] = caixa(PAR + 2.0, PAR + 3.6, AMP_Y[0] + 2.5, AMP_Y[0] + 2.5 + AMP[0], AMP_Z + 0.05, AMP_Z + AMP[1] - 0.05)
    f['microfone'] = cil('y', MIC, MIC_D, PAR + EVA, PAR + EVA + MIC_ESP)
    f['LED'] = cil('y', LED, 5.0, 0.05, 8.6).union(cil('y', LED, 5.8, 8.6, 9.6))
    bx, bz = BOTAO
    f['botão tátil'] = caixa(bx - 3, bx + 3, 5.4, 8.8, bz - 3, bz + 3).union(cil('y', BOTAO, 3.5, 3.85, 5.4))
    return f


PECAS = {'corpo': corpo, 'bandeja': bandeja, 'moldura da tela': moldura_tela, 'tecla': tecla, 'tampa do microfone': tampa_mic}


def malha(shape, tol=0.02):
    import os, tempfile, trimesh
    f = tempfile.mktemp(suffix='.stl')
    cq.exporters.export(shape, f, tolerance=tol, angularTolerance=0.15)
    m = trimesh.load(f, force='mesh')
    os.unlink(f)
    return m


if __name__ == '__main__':
    import numpy as np
    import trimesh
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    saida.mkdir(parents=True, exist_ok=True)
    solidos = {nome: fn() for nome, fn in PECAS.items()}
    for nome, s in solidos.items():
        cq.exporters.export(s, str(saida / ('caixa-' + nome.replace(' ', '-') + '.step')))
    # mesas de impressão: o corpo com a frente na mesa; o resto junto noutra mesa
    giro = trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0])      # (x, y, z) -> (x, -z, y): y vira altura
    giro_inv = trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0])  # (x, y, z) -> (x, z, -y)
    def deitar(m, matriz):
        m = m.copy(); m.apply_transform(matriz); m.apply_translation(-m.bounds[0]); return m
    mc = deitar(malha(solidos['corpo']), giro)
    mb = deitar(malha(solidos['bandeja']), np.eye(4))
    mm = deitar(malha(solidos['moldura da tela']), giro)
    mt = deitar(malha(solidos['tecla']), giro)          # a face da tecla na mesa, lisa como a frente
    mtm = deitar(malha(solidos['tampa do microfone']), giro_inv)
    mm.apply_translation((0, mb.bounds[1][1] + 6, 0))
    mt.apply_translation((mm.bounds[1][0] + 6, mb.bounds[1][1] + 6, 0))
    mtm.apply_translation((mm.bounds[1][0] + 6, mb.bounds[1][1] + 20, 0))
    T.exportar_3mf({'corpo': mc}, saida / 'caixa-corpo.3mf')
    T.exportar_3mf({'bandeja': mb, 'moldura da tela': mm, 'tecla': mt, 'tampa do microfone': mtm}, saida / 'caixa-bandeja-e-pecas.3mf')
    print('ok', ', '.join('%s %s' % (k, np.round(v.bounds[1] - v.bounds[0], 1)) for k, v in
                         (('corpo', mc), ('bandeja', mb), ('moldura', mm), ('tecla', mt), ('tampa', mtm))))
