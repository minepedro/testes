from urllib.parse import quote_plus
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, KeepTogether, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("F", D + "DejaVuSansCondensed.ttf"))
pdfmetrics.registerFont(TTFont("FB", D + "DejaVuSansCondensed-Bold.ttf"))
pdfmetrics.registerFont(TTFont("FI", D + "DejaVuSansCondensed-Oblique.ttf"))
pdfmetrics.registerFontFamily("F", normal="F", bold="FB", italic="FI", boldItalic="FB")

NAVY = colors.HexColor("#1f2a44")
ORANGE = colors.HexColor("#d97757")
LIGHT = colors.HexColor("#f6f1ec")
GRAY = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e2d9d0")
LINK = "#1a56db"

s_body = ParagraphStyle("body", fontName="F", fontSize=9, leading=12.2, textColor=colors.HexColor("#222"))
s_small = ParagraphStyle("small", parent=s_body, fontSize=7.8, leading=10.4, textColor=GRAY)
s_h1 = ParagraphStyle("h1", fontName="FB", fontSize=20, leading=24, textColor=NAVY)
s_h2 = ParagraphStyle("h2", fontName="FB", fontSize=13.5, leading=17, textColor=NAVY, spaceBefore=4, spaceAfter=4)
s_lab = ParagraphStyle("lab", parent=s_body, fontName="FB", fontSize=7.6, leading=10, textColor=ORANGE)
s_card_t = ParagraphStyle("ct", fontName="FB", fontSize=10.5, leading=13, textColor=colors.white)
s_card_q = ParagraphStyle("cq", fontName="F", fontSize=8.5, leading=11, textColor=colors.HexColor("#ffd9c9"), alignment=2)
s_cell = ParagraphStyle("cell", parent=s_body, fontSize=8.2, leading=10.8)
s_cellb = ParagraphStyle("cellb", parent=s_cell, fontName="FB")
s_th = ParagraphStyle("th", parent=s_cell, fontName="FB", textColor=colors.white)


def P(t, st=s_body):
    return Paragraph(t, st)


def img_link(q):
    return f"https://www.google.com/search?tbm=isch&q={quote_plus(q)}"


def ml_link(q):
    return "https://lista.mercadolivre.com.br/" + "-".join(q.lower().split())


def links(q):
    return (f'<link href="{img_link(q)}" color="{LINK}"><u>Ver fotos</u></link>'
            f' &nbsp;|&nbsp; <link href="{ml_link(q)}" color="{LINK}"><u>Ver preços (ML)</u></link>')


# ---------------------------------------------------------------- dados
LOJAS_ARDUINO = ("Lojas de Arduino/ESP32: Saravati, NewPort e Mamute (Rua Vitória), "
                 "HPE Robótica (Rua Timbiras), Arduino Santa Efigênia (Rua Aurora)")

COMPONENTES = [
    dict(n="ESP32-S3 DevKitC-1, versão N16R8 (16 MB flash + 8 MB PSRAM)", q=2, lo=80, hi=180,
         why="O cérebro do mascote: Wi-Fi, tela, áudio e touch.",
         marca="Espressif (a placa oficial DevKitC-1)",
         alt="Waveshare (ESP32-S3-DEV-KIT-N16R8, mesmo pinout do DevKitC-1) ou clones genéricos com módulo ESP32-S3-WROOM-1 N16R8. Aceitável: N8R8.",
         onde=LOJAS_ARDUINO + ". Ligue antes: o S3 com PSRAM pode estar em falta.",
         ver="Etiqueta do módulo: ESP32-S3-WROOM-1 com 'R8'. Duas portas USB-C é normal. EVITAR: ESP32 comum, S2, C3, S3 sem PSRAM.",
         busca="ESP32-S3 DevKitC-1 N16R8", bq="esp32-s3 n16r8"),
    dict(n="Tela 3,5 pol SPI 480x320 com touch capacitivo", q=1, lo=90, hi=220,
         why="O rosto e o corpo do mascote, e onde você toca para falar e aprovar.",
         marca="Waveshare (linha 3.5inch Capacitive Touch LCD; confira se o controlador é ST7796)",
         alt="Hosyond (referência MSP3526, que costuma ser ST7796 + touch capacitivo; confirme na embalagem). Mais barata: MSP3520 (costuma ser ILI9488 + touch resistivo), funciona mas é mais lenta.",
         onde=LOJAS_ARDUINO + ". Se tiver só a versão resistiva, leve: dá para começar.",
         ver="Pergunte: SPI ou paralela? Controlador? Touch capacitivo ou resistivo? EVITAR: shield para Arduino Uno (paralela, 8 bits).",
         busca="3.5 inch SPI 480x320 ST7796 capacitive touch display module", bq="tela 3.5 st7796 spi touch"),
    dict(n="Microfone I2S INMP441", q=2, lo=20, hi=50,
         why="Captura sua voz. Sai digital (I2S), sem ruído de conversor analógico.",
         marca="Módulo com chip INMP441 (fabricante do chip: TDK InvenSense)",
         alt="ICS-43434 (também TDK) ou SPH0645 (Knowles, mais comum em breakout da Adafruit, mais caro).",
         onde=LOJAS_ARDUINO + ".",
         ver="EVITAR microfone analógico (MAX9814, módulo KY-038, módulo 'sensor de som'): não é I2S.",
         busca="INMP441 I2S microphone module", bq="inmp441"),
    dict(n="Amplificador I2S MAX98357A", q=2, lo=25, hi=60,
         why="Transforma o áudio digital em som para o alto-falante.",
         marca="Chip MAX98357A (Analog Devices/Maxim). Breakout original: Adafruit (importado, mais caro).",
         alt="Módulos genéricos com MAX98357A, que são a maioria nas lojas daqui.",
         onde=LOJAS_ARDUINO + ".",
         ver="EVITAR PAM8403 (analógico, não recebe I2S). Confira se a serigrafia diz MAX98357.",
         busca="MAX98357A I2S amplifier module", bq="max98357a"),
    dict(n="Alto-falante 4 ohms, 3 W, 40 a 50 mm", q=2, lo=15, hi=45,
         why="A voz do mascote. Cone maior dá mais grave, mas aumenta a carcaça.",
         marca="Sem marca dominante nesse porte. Boas (importadas): Visaton, Dayton Audio.",
         alt="Qualquer alto-falante de 4 ohms e 3 W de fabricante conhecido ou genérico limpo; alto-falante de fone/caixinha desmontada também serve para teste.",
         onde="Lojas de componentes e de som da região; pergunte nas lojas de Arduino também.",
         ver="Confira 4 ohms e potência de 3 W ou mais. Teste: encostar uma pilha de 1,5 V deve fazer 'toc' limpo.",
         busca="alto falante 4 ohm 3W 40mm", bq="alto falante 4 ohm 3w 40mm"),
    dict(n="Cabo USB-C de dados", q=2, lo=20, hi=50,
         why="Programar o ESP32 e alimentar o mascote.",
         marca="Anker, Baseus ou Ugreen",
         alt="Cabo original de celular (Samsung/Apple USB-C) que você já tenha.",
         onde="Lojas de acessórios para celular na Rua Santa Ifigênia (tem em toda esquina).",
         ver="Precisa ser cabo de DADOS, não só carga. Se o computador não reconhece a placa, troque o cabo primeiro.",
         busca="cabo USB-C dados", bq="cabo usb-c dados"),
    dict(n="Fonte USB 5 V 2 A", q=1, lo=40, hi=90,
         why="Alimenta tela, Wi-Fi e áudio com folga.",
         marca="Samsung, Apple, Anker ou Baseus (de procedência)",
         alt="Carregador de celular que você já tenha, desde que seja de 5 V e 2 A ou mais.",
         onde="Lojas de acessórios para celular na Rua Santa Ifigênia.",
         ver="EVITAR fonte sem marca e sem selo: ruído e tensão instável estragam o áudio e a placa.",
         busca="carregador USB 5V 2A", bq="carregador usb 5v 2a"),
]

MONTAGEM = [
    dict(n="Protoboard 830 pontos", q=1, lo=20, hi=40, marca="Genérica (ok)", alt="Qualquer marca",
         onde="Lojas de Arduino ou de componentes", busca="protoboard 830 pontos"),
    dict(n="Kit jumpers 40 un. (macho-macho e macho-fêmea, 20 cm)", q=2, lo=10, hi=25, marca="Genérica (ok)",
         alt="Qualquer marca", onde="Lojas de Arduino ou de componentes", busca="kit jumpers macho femea"),
    dict(n="Barras de pinos macho e fêmea (headers)", q=2, lo=3, hi=10, marca="Genérica", alt="Qualquer marca",
         onde="Lojas de componentes", busca="barra de pinos header 2.54"),
    dict(n="Capacitores: 470 uF 10 V (x4) e 100 nF cerâmico (x10)", q=1, lo=5, hi=15, marca="Nichicon, Panasonic ou Rubycon",
         alt="Samsung, genérico (ok p/ protótipo)", onde="Lojas de componentes (Rua Timbiras)", busca="capacitor eletrolitico 470uF 10V"),
    dict(n="Botões táteis 6x6 mm (x4)", q=1, lo=3, hi=10, marca="Genérico", alt="Qualquer marca",
         onde="Lojas de componentes", busca="botao tatil 6x6"),
    dict(n="Fio fino de silicone 26 a 30 AWG (2 cores)", q=1, lo=10, hi=30, marca="Genérico", alt="Fio de cabo de rede (par trançado) serve",
         onde="Lojas de componentes", busca="fio silicone 28 AWG"),
    dict(n="Parafusos M3 (10 a 16 mm) + insertos de latão M3", q=1, lo=30, hi=80, marca="Genérico", alt="Parafusos de ferragem comum",
         onde="Lojas de ferragens do centro; insertos podem exigir compra online", busca="inserto latao M3 impressao 3D"),
]

FERRAMENTAS = [
    dict(n="Estanho 63/37 ou 60/40, 0,5 a 0,8 mm, com fluxo (rolo 50 a 100 g)", q=1, lo=25, hi=70,
         marca="Best ou Cobix (marcas nacionais)", alt="Kester, Multicore (importadas). Sem chumbo é mais seguro, mas mais difícil de soldar.",
         onde="Lojas de componentes e ferramentas", busca="estanho 63/37 0.8mm"),
    dict(n="Fluxo de solda em pasta ou gel", q=1, lo=15, hi=45, marca="Mechanic", alt="Amtech, Kester",
         onde="Lojas de componentes e ferramentas", busca="fluxo solda pasta"),
    dict(n="Malha dessoldadora + sugador de solda", q=1, lo=15, hi=50, marca="Goot (malha)", alt="Mechanic, genéricas",
         onde="Lojas de componentes e ferramentas", busca="malha dessoldadora sugador solda"),
    dict(n="Suporte para ferro com esponja ou limpador de latão", q=1, lo=15, hi=40, marca="Hikari", alt="Genérico",
         onde="Lojas de componentes e ferramentas", busca="suporte ferro de solda limpador latao"),
    dict(n="Multímetro digital", q=1, lo=80, hi=250, marca="Minipa", alt="Hikari, Uni-T (UT33/UT61)",
         onde="Lojas de componentes e ferramentas (ex.: Victor Eletrônicos; confirme)", busca="multimetro digital minipa"),
    dict(n="Alicate de corte pequeno + alicate de bico fino", q=1, lo=25, hi=90, marca="Tramontina", alt="Hikari, Worker, Goot",
         onde="Lojas de ferramentas e de componentes", busca="alicate corte bico fino eletronica"),
    dict(n="Pinça antiestática (ponta fina)", q=1, lo=10, hi=30, marca="Genérica", alt="Goot, Hikari",
         onde="Lojas de componentes e ferramentas", busca="pinca antiestatica"),
    dict(n="Descascador de fio (wire stripper)", q=1, lo=20, hi=50, marca="Tramontina", alt="Hikari, genérico",
         onde="Lojas de ferramentas e de componentes", busca="descascador de fio automatico"),
    dict(n="Fita Kapton + tubo termo-retrátil (kit)", q=1, lo=15, hi=40, marca="Genéricos", alt="3M (fita)",
         onde="Lojas de componentes e de material elétrico", busca="fita kapton tubo termo retratil kit"),
    dict(n="'Terceira mão' com lupa (garras jacaré)", q=1, lo=30, hi=90, marca="Genérica", alt="Hikari",
         onde="Lojas de componentes e ferramentas", busca="terceira mao solda lupa"),
    dict(n="Tapete de silicone resistente a calor", q=1, lo=20, hi=60, marca="Genérico", alt="Mechanic",
         onde="Lojas de componentes e ferramentas", busca="tapete silicone solda"),
    dict(n="Kit de chaves de precisão + limas pequenas + estilete", q=1, lo=30, hi=90, marca="Tramontina", alt="Hikari, Worker",
         onde="Lojas de ferramentas", busca="kit chaves precisao"),
]

OPCIONAIS = [
    dict(n="Analisador lógico USB 8 canais (24 MHz)", q=1, lo=50, hi=120, marca="Clones compatíveis com Saleae", alt="Saleae (original, bem mais caro)",
         onde="Lojas de componentes; frequentemente só online",
         por="Ajuda a depurar I2S e SPI quando o áudio ou a tela não funciona.", busca="analisador logico usb 8 canais 24mhz"),
    dict(n="Estação de solda com controle de temperatura", q=1, lo=120, hi=400, marca="Hikari", alt="Goot, Hakko (importadas, mais caras)",
         onde="Lojas de componentes e ferramentas",
         por="Vale se o seu ferro for de 30 a 40 W sem controle: esquenta demais e pode estragar os módulos.", busca="estacao de solda controle temperatura hikari"),
    dict(n="Luminária com lupa", q=1, lo=40, hi=150, marca="Genérica", alt="Hikari",
         onde="Lojas de ferramentas e de componentes",
         por="Ajuda muito a soldar pinos finos e conferir solda fria.", busca="luminaria com lupa bancada"),
]


def tot(lst):
    return sum(i["lo"] * i["q"] for i in lst), sum(i["hi"] * i["q"] for i in lst)


tc, tm, tf, to = tot(COMPONENTES), tot(MONTAGEM), tot(FERRAMENTAS), tot(OPCIONAIS)
total_lo, total_hi = tc[0] + tm[0] + tf[0], tc[1] + tm[1] + tf[1]


def brl(v):
    return f"R$ {v:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- páginas
def on_page(c, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, A4[1] - 11 * mm, A4[0], 11 * mm, stroke=0, fill=1)
    c.setFillColor(ORANGE)
    c.rect(0, A4[1] - 11.8 * mm, A4[0], 0.8 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("FB", 9)
    c.drawString(15 * mm, A4[1] - 7.3 * mm, "Mascote Claude  |  Guia de compras, Santa Ifigênia")
    c.setFont("F", 8)
    c.setFillColor(GRAY)
    c.drawRightString(A4[0] - 15 * mm, 8 * mm, f"Página {doc.page}")
    c.drawString(15 * mm, 8 * mm, "Preços são estimativas. Confirme na loja.")
    c.restoreState()


def card(it, idx):
    head = Table([[P(f"{idx}. {it['n']}", s_card_t), P(f"Qtd: {it['q']}", s_card_q)]],
                 colWidths=[148 * mm, 32 * mm])
    head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                              ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                              ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    rows = [
        ["PARA QUE SERVE", it["why"]],
        ["MARCA RECOMENDADA", it["marca"]],
        ["ALTERNATIVAS (MARCAS)", it["alt"]],
        ["ONDE PROCURAR", it["onde"]],
        ["PREÇO ESTIMADO", f"{brl(it['lo'])} a {brl(it['hi'])} cada  |  total previsto: "
                           f"{brl(it['lo'] * it['q'])} a {brl(it['hi'] * it['q'])}"],
        ["CONFERIR NA LOJA", it["ver"]],
        ["FOTOS E PREÇOS ONLINE", (f'<link href="{img_link(it["busca"])}" color="{LINK}"><u>Ver fotos</u></link>'
          f' &nbsp;|&nbsp; <link href="{ml_link(it["bq"])}" color="{LINK}"><u>Ver preços (ML)</u></link>')],
    ]
    body = Table([[P(a, s_lab), P(b, s_cell)] for a, b in rows], colWidths=[38 * mm, 142 * mm])
    body.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                              ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                              ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
    return KeepTogether([head, body, Spacer(1, 7)])


def compact_table(lst, extra_col=None):
    hdr = [P("Item", s_th), P("Marca recomendada", s_th), P("Alternativas", s_th),
           P("Onde", s_th), P("Preço est.", s_th), P("Fotos", s_th)]
    data = [hdr]
    for it in lst:
        data.append([
            P(f"<b>{it['n']}</b> (x{it['q']})", s_cell),
            P(it["marca"], s_cell), P(it["alt"], s_cell), P(it["onde"], s_cell),
            P(f"{brl(it['lo'])} a {brl(it['hi'])}", s_cell),
            P(f'<link href="{img_link(it["busca"])}" color="{LINK}"><u>Ver</u></link>', s_cell),
        ])
    t = Table(data, colWidths=[42 * mm, 30 * mm, 36 * mm, 36 * mm, 24 * mm, 12 * mm], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    for r in range(1, len(data)):
        if r % 2 == 0:
            st.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    t.setStyle(TableStyle(st))
    return t


def stat(label, val, sub):
    t = Table([[P(label, ParagraphStyle("a", parent=s_small, textColor=GRAY))],
               [P(val, ParagraphStyle("b", fontName="FB", fontSize=13, leading=16, textColor=NAVY))],
               [P(sub, s_small)]], colWidths=[57 * mm], rowHeights=[15, 20, 16])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def build(path):
    doc = BaseDocTemplate(path, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                          topMargin=18 * mm, bottomMargin=16 * mm,
                          title="Mascote Claude, guia de compras na Santa Ifigênia", author="Claude")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f", leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    S = []

    # --- capa / resumo
    S += [P("Guia de compras: mascote de mesa", s_h1), Spacer(1, 3),
          P("ESP32-S3 + tela 3,5 pol touch + microfone e alto-falante I2S, alimentado por USB-C. "
            "Tudo o que comprar na Santa Ifigênia, mais as ferramentas que faltam para soldar e montar.", s_body),
          Spacer(1, 9)]
    stats = Table([[stat("COMPONENTES (com reservas)", f"{brl(tc[0])} a {brl(tc[1])}", "ESP32, tela, mic, ampli, alto-falante"),
                    stat("MONTAGEM E CARCAÇA", f"{brl(tm[0])} a {brl(tm[1])}", "protoboard, jumpers, capacitores"),
                    stat("FERRAMENTAS QUE FALTAM", f"{brl(tf[0])} a {brl(tf[1])}", "estanho, fluxo, multímetro, alicates")]],
                  colWidths=[60 * mm, 60 * mm, 60 * mm])
    stats.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    S += [stats, Spacer(1, 7)]
    tt = Table([[P("TOTAL ESTIMADO (sem os opcionais)", ParagraphStyle("t1", fontName="FB", fontSize=9.5, textColor=colors.white)),
                 P(f"{brl(total_lo)} a {brl(total_hi)}", ParagraphStyle("t2", fontName="FB", fontSize=14, leading=17, textColor=colors.white, alignment=2))]],
               colWidths=[90 * mm, 90 * mm])
    tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ORANGE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    S += [tt, Spacer(1, 3),
          P(f"Opcionais (analisador lógico, estação de solda, luminária): mais {brl(to[0])} a {brl(to[1])}.", s_small),
          Spacer(1, 10)]
    S += [P("Como usar este guia", s_h2),
          P("<b>1.</b> Cada item tem a marca recomendada, alternativas (por marca, não por produto), onde procurar, "
            "preço estimado e o que conferir antes de pagar.", s_body), Spacer(1, 2),
          P("<b>2.</b> Toque em <b>Ver fotos</b> para abrir a busca de imagens do item e comparar com o que o vendedor mostrar. "
            "<b>Ver preços (ML)</b> abre a busca no Mercado Livre como referência de preço.", s_body), Spacer(1, 2),
          P("<b>3.</b> Os preços são <b>estimativas minhas</b>, sem cotação em loja (não consegui preços nacionais atualizados). "
            "Use as faixas como orçamento de segurança e cote em 2 ou 3 lojas.", s_body), Spacer(1, 2),
          P("<b>4.</b> Por que não há fotos dentro do PDF: eu não consigo baixar imagens de lojas para embutir aqui. "
            "Os links de fotos resolvem isso na hora, no celular.", s_body), Spacer(1, 10)]
    S += [P("Segurança na bancada", s_h2),
          P("Solde em lugar ventilado, não respire a fumaça do fluxo e lave as mãos depois de usar estanho com chumbo "
            "(63/37 e 60/40). Apoie o ferro no suporte, nunca na mesa, e use óculos de proteção ao cortar fios e terminais.", s_body),
          Spacer(1, 12)]

    # --- onde ir
    S += [P("Onde ir na Santa Ifigênia", s_h2),
          P("Endereços de fontes públicas (guias de lojas e uma lista usada na USP), que podem estar desatualizados. "
            "Confirme endereço, horário e estoque por telefone ou WhatsApp antes de ir.", s_small), Spacer(1, 5)]
    lojas = [[P("Loja", s_th), P("Endereço", s_th), P("O que procurar lá", s_th)],
             [P("NewPort", s_cellb), P("Rua Vitória, 24", s_cell), P("Placas ESP32, telas, módulos", s_cell)],
             [P("Saravati", s_cellb), P("Rua Vitória, 39", s_cell), P("Arduino, Raspberry, componentes", s_cell)],
             [P("Mamute", s_cellb), P("Rua Vitória, 125", s_cell), P("Arduino, módulos, componentes", s_cell)],
             [P("HPE Robótica", s_cellb), P("Rua Timbiras, 239", s_cell), P("Robótica, módulos, componentes", s_cell)],
             [P("Arduino Santa Efigênia", s_cellb), P("Rua Aurora, 28", s_cell), P("Arduino, ESP32, módulos", s_cell)],
             [P("MRD Componentes", s_cellb), P("Rua Timbiras (nº a confirmar)", s_cell), P("Componentes avulsos, capacitores, botões", s_cell)],
             [P("Victor Eletrônicos / Actronic", s_cellb), P("Santa Ifigênia (nº a confirmar)", s_cell), P("Componentes e ferramentas (multímetro, alicates)", s_cell)]]
    lt = Table(lojas, colWidths=[48 * mm, 54 * mm, 78 * mm], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for r in range(2, len(lojas), 2):
        st.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
    lt.setStyle(TableStyle(st))
    S += [lt, Spacer(1, 9),
          P("Roteiro sugerido", s_h2),
          P("<b>1.</b> Rua Vitória: NewPort (24), Saravati (39), Mamute (125). Três lojas de Arduino na mesma rua; "
            "compare o preço de ESP32-S3 e da tela antes de fechar.", s_body), Spacer(1, 2),
          P("<b>2.</b> Rua Timbiras: HPE Robótica (239) e MRD, para capacitores, botões, headers e ferramentas.", s_body), Spacer(1, 2),
          P("<b>3.</b> Rua Aurora: Arduino Santa Efigênia (28), se algo ainda faltar.", s_body), Spacer(1, 2),
          P("<b>4.</b> Rua Santa Ifigênia: cabo USB-C e fonte 5 V em qualquer loja de acessórios de celular.", s_body), Spacer(1, 8),
          P("Horário: muitas lojas fecham cedo aos sábados e não abrem aos domingos. Hoje é sábado, então vale confirmar "
            "o horário de cada uma antes de sair.", s_small),
          PageBreak()]

    # --- componentes
    S += [P("1. Componentes principais", s_h2),
          P(f"Subtotal: {brl(tc[0])} a {brl(tc[1])} (inclui 1 reserva de ESP32, microfone, amplificador, alto-falante e cabo).", s_small),
          Spacer(1, 5)]
    for i, it in enumerate(COMPONENTES, 1):
        S.append(card(it, i))
    S.append(PageBreak())

    # --- montagem
    S += [P("2. Montagem e carcaça", s_h2),
          P(f"Subtotal: {brl(tm[0])} a {brl(tm[1])}. Itens simples, sem marca crítica.", s_small), Spacer(1, 5),
          compact_table(MONTAGEM), Spacer(1, 12)]

    # --- ferramentas
    S += [P("3. Ferramentas que faltam (você já tem ferro de solda e um pouco de estanho)", s_h2),
          P(f"Subtotal: {brl(tf[0])} a {brl(tf[1])}. Marcas comuns no Brasil; as nacionais costumam ser mais fáceis de achar.", s_small),
          Spacer(1, 5), compact_table(FERRAMENTAS), Spacer(1, 14)]

    # --- opcionais
    S += [P("4. Opcionais que ajudam", s_h2),
          P(f"Fora do total. Se comprar os três: {brl(to[0])} a {brl(to[1])}.", s_small), Spacer(1, 5)]
    hdr = [P("Item", s_th), P("Por que vale", s_th), P("Marca recomendada", s_th), P("Alternativas", s_th), P("Preço est.", s_th), P("Fotos", s_th)]
    data = [hdr]
    for it in OPCIONAIS:
        data.append([P(f"<b>{it['n']}</b>", s_cell), P(it["por"], s_cell), P(it["marca"], s_cell), P(it["alt"], s_cell),
                     P(f"{brl(it['lo'])} a {brl(it['hi'])}", s_cell),
                     P(f'<link href="{img_link(it["busca"])}" color="{LINK}"><u>Ver</u></link>', s_cell)])
    ot = Table(data, colWidths=[38 * mm, 47 * mm, 28 * mm, 30 * mm, 24 * mm, 13 * mm], repeatRows=1)
    ot.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("BACKGROUND", (0, 2), (-1, 2), LIGHT)]))
    S += [ot, Spacer(1, 14)]

    # --- checklist
    S += [P("Antes de pagar", s_h2)]
    chk = ["Pedi para ligar e testar a tela e o ESP32 na loja (ou combinei troca em caso de defeito).",
           "Tirei foto da etiqueta do módulo ESP32 (conferir S3 e R8) e do verso da tela (controlador e pinos).",
           "Confirmei que a tela é SPI (não shield Arduino) e se o touch é capacitivo ou resistivo.",
           "Confirmei que o microfone é I2S (INMP441) e o amplificador é MAX98357A, não analógicos.",
           "Pedi nota fiscal de tudo e guardei.",
           "Comprei 1 reserva de ESP32, microfone, amplificador e alto-falante.",
           "Se não achar ESP32-S3 com PSRAM: não improvisar com ESP32 comum. Comprar o resto e importar a placa."]
    ct = Table([[P("[   ]", ParagraphStyle("cb", fontName="F", fontSize=9, textColor=ORANGE)), P(c, s_body)] for c in chk],
               colWidths=[10 * mm, 170 * mm])
    ct.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4)]))
    S += [ct, Spacer(1, 10),
          P("Depois da compra, o próximo passo no repositório é o mapa de pinos, o esquema de ligação I2S e o modelo 3D da carcaça.", s_small)]
    doc.build(S)


if __name__ == "__main__":
    build("/mnt/user-data/outputs/guia-de-compras-mascote.pdf")
    print("ok", tc, tm, tf, to, total_lo, total_hi)
