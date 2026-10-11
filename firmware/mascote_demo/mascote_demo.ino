// Mascote na tela (demo, sem Wi-Fi e sem ponte).
// O Clawd do prototipo web (software/ui-proto) no ESP32-S3, com a tela ILI9488 de teste
// e o touch resistivo XPT2046. Mesmo sprite 18x5, mesmas cores e mesmos estados.
//
// Como usar:
//   - Segure a tela (abaixo da faixa de cima): o mascote ouve (olhos arregalados, barras).
//   - Solte: ele pensa (tres pontos) e depois responde com um texto de exemplo (a boca mexe).
//   - Toque na faixa de cima: alterna repouso -> trabalhando -> alerta -> repouso.
// O texto das respostas e fixo; quando a ponte existir, ela manda o estado e o texto.
//
// Biblioteca: LovyanGFX. Placa: ESP32S3 Dev Module, PSRAM "OPI PSRAM" (os desenhos usam a PSRAM).
// Para a tela capacitiva final (ST7796): troque Panel_ILI9488 por Panel_ST7796 e o touch
// pelo bloco Touch_FT5x06 de firmware/testes/etapa2_3_tela_touch.

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// ---- pinos (docs/montagem.md, variante ILI9488) ---------------------------------------
constexpr int PIN_SCK = 12, PIN_MOSI = 11, PIN_MISO = 13, PIN_DC = 14;
constexpr int PIN_CS = 10, PIN_RST = 6, PIN_BL = 7;
constexpr int PIN_T_CLK = 9, PIN_T_CS = 5, PIN_T_DIN = 8, PIN_T_DO = 4;

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ILI9488 _panel;
  lgfx::Bus_SPI _bus;
  lgfx::Light_PWM _light;
  lgfx::Touch_XPT2046 _touch;

public:
  LGFX() {
    {
      auto cfg = _bus.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 27000000;
      cfg.freq_read = 16000000;
      cfg.pin_sclk = PIN_SCK;
      cfg.pin_mosi = PIN_MOSI;
      cfg.pin_miso = PIN_MISO;
      cfg.pin_dc = PIN_DC;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }
    {
      auto cfg = _panel.config();
      cfg.pin_cs = PIN_CS;
      cfg.pin_rst = PIN_RST;
      cfg.pin_busy = -1;
      cfg.panel_width = 320;
      cfg.panel_height = 480;
      cfg.readable = false;
      cfg.invert = false;
      cfg.rgb_order = false;
      cfg.dlen_16bit = false;
      cfg.bus_shared = false;
      _panel.config(cfg);
    }
    {
      auto cfg = _light.config();
      cfg.pin_bl = PIN_BL;
      cfg.freq = 44100;
      cfg.pwm_channel = 7;
      _light.config(cfg);
      _panel.setLight(&_light);
    }
    {
      auto cfg = _touch.config();
      cfg.x_min = 300;  // mesma calibracao que funcionou na etapa 3
      cfg.x_max = 3900;
      cfg.y_min = 200;
      cfg.y_max = 3900;
      cfg.pin_int = -1;
      cfg.bus_shared = false;
      cfg.offset_rotation = 0;
      cfg.spi_host = SPI3_HOST;
      cfg.freq = 1000000;
      cfg.pin_sclk = PIN_T_CLK;
      cfg.pin_mosi = PIN_T_DIN;
      cfg.pin_miso = PIN_T_DO;
      cfg.pin_cs = PIN_T_CS;
      _touch.config(cfg);
      _panel.setTouch(&_touch);
    }
    setPanel(&_panel);
  }
};

LGFX tft;
LGFX_Sprite area(&tft);    // regiao do mascote (desenha fora da tela e envia de uma vez, sem piscar)
LGFX_Sprite rodape(&tft);  // barras de audio e texto de baixo

// ---- geometria (igual ao prototipo web) ------------------------------------------------
constexpr int W = 480, H = 320, PW = 15, PH = 30;
constexpr int BODY_W = 18, BODY_H = 5;
constexpr int EYE_L = 5, EYE_R = 12, EYE_ROW = 1;
constexpr int BODY_X = (W - BODY_W * PW) / 2;  // 105
constexpr int BODY_Y = 68;
constexpr int TOP_BAR = 28, TOP_HIT = 40, FOOT_Y = H - 44;
constexpr int AREA_X = 88, AREA_Y = 26, AREA_W = 316, AREA_H = 216;   // cobre olhos, pontos, "!" e chao
constexpr int FOOT_TOP = AREA_Y + AREA_H, FOOT_H = H - FOOT_TOP;       // barras + 2 linhas de texto

const char *SPRITE[BODY_H] = {
  "...############...",
  "...############...",
  ".################.",
  "...############...",
  "....#.#....#.#....",
};

// paleta da tela (a mesma do prototipo)
uint16_t C_BG, C_FLOOR, C_SHADOW, C_HI, C_MID, C_BODY, C_LO, C_DEEP, C_FG, C_DIM, C_OK, C_WARN, C_WARN_HI;

// ---- estado do mascote -----------------------------------------------------------------
enum Estado { REPOUSO, OUVINDO, PENSANDO, RESPONDENDO, TRABALHANDO, ALERTA };
const char *NOME[] = {"repouso", "ouvindo", "pensando", "respondendo", "trabalhando", "alerta"};

const char *PERGUNTA = "Como estao minhas sessoes?";
const char *RESPOSTAS[] = {
  "Oi, Pedro! Eu ja estou na tela de verdade. Quando a ponte estiver pronta, eu conto aqui o que suas sessoes estao fazendo.",
  "Nenhuma sessao precisa de voce agora. Duas estao trabalhando: mascote-firmware e ponte-vps.",
  "A tela, o touch e o ESP32 estao funcionando. Falta o microfone e a ponte na VPS.",
};
constexpr float TYPE_CPS = 40;  // letras por segundo na resposta

struct {
  Estado estado = REPOUSO;
  float t = 0;                       // segundos no estado atual
  float eyeH = 1, eyeDy = 0;         // altura do olho e deslocamento vertical (em pixels do sprite)
  int eyeDx = 0, mouth = 0;          // olhar para o lado (-1, 0, 1) e boca (0, 1, 2)
  float blinkAt = 3, blinkT = -1;    // piscar
  float glanceAt = 5, glanceUntil = 0; int glanceDx = 0;
  float mouthNext = 0;
  int typed = 0;                     // letras ja escritas no rodape
  const char *texto = "";            // texto do rodape
  float bars[16] = {0}, barsAlvo[16] = {0};
} m;
int respostaAtual = 0;

void desenharTopo();
float rnd() { return (float)esp_random() / 4294967296.0f; }

void entrar(Estado e) {
  m.estado = e; m.t = 0;
  m.eyeH = 1; m.eyeDy = 0; m.eyeDx = 0; m.mouth = 0; m.typed = 0;
  m.blinkT = -1; m.blinkAt = 3 + rnd() * 3; m.glanceAt = 4 + rnd() * 5; m.glanceUntil = 0;
  if (e == OUVINDO) { m.eyeH = 1.5f; m.eyeDy = -0.5f; m.texto = PERGUNTA; }
  if (e == PENSANDO || e == TRABALHANDO) m.eyeDx = 1;
  if (e == RESPONDENDO) { m.texto = RESPOSTAS[respostaAtual]; respostaAtual = (respostaAtual + 1) % 3; }
  if (e == ALERTA) { m.eyeH = 1.5f; m.eyeDy = -0.5f; m.mouth = 1; }
  Serial.printf("estado: %s\n", NOME[e]);
  desenharTopo();
}

void atualizar(float dt) {
  m.t += dt;
  float t = m.t;
  // piscar (menos pensando e alerta, que tem olhar fixo)
  if (m.estado != PENSANDO && m.estado != ALERTA) {
    if (m.blinkT < 0 && t >= m.blinkAt) m.blinkT = 0;
    if (m.blinkT >= 0) { m.blinkT += dt; if (m.blinkT > 0.16f) { m.blinkT = -1; m.blinkAt = t + 3 + rnd() * 3; } }
  } else m.blinkT = -1;

  if (m.estado == REPOUSO) {
    if (t >= m.glanceAt) { m.glanceDx = rnd() < .5f ? -1 : 1; m.glanceUntil = t + .9f + rnd() * .8f; m.glanceAt = t + 4 + rnd() * 5; }
    m.eyeDx = t < m.glanceUntil ? m.glanceDx : 0;
  }
  if (m.estado == OUVINDO) {
    m.typed = max(0, (int)((t - .5f) * 18));
    float env = .35f + .65f * fabsf(sinf(t * 2.3f)) * (t > .5f ? 1 : .2f);
    for (int i = 0; i < 16; i++) {
      if (rnd() < .3f) m.barsAlvo[i] = env * (.3f + rnd() * .7f);
      m.bars[i] += (m.barsAlvo[i] - m.bars[i]) * min(1.0f, dt * 14);
    }
  } else for (int i = 0; i < 16; i++) m.bars[i] *= .8f;

  if (m.estado == PENSANDO && t > 1.6f) entrar(RESPONDENDO);
  if (m.estado == RESPONDENDO) {
    int len = strlen(m.texto);
    m.typed = (int)(t * TYPE_CPS);
    if (m.typed < len) {
      if (t >= m.mouthNext) { const int seq[] = {0, 1, 2, 1}; m.mouth = seq[esp_random() % 4]; m.mouthNext = t + .07f + rnd() * .08f; }
    } else {
      m.mouth = 0;
      if (t > len / TYPE_CPS + 1.2f) { const char *fica = m.texto; entrar(REPOUSO); m.texto = fica; m.typed = strlen(fica); }
    }
  }
}

// ---- desenho -----------------------------------------------------------------------------
bool solido(int x, int y) { return y >= 0 && y < BODY_H && x >= 0 && x < BODY_W && SPRITE[y][x] == '#'; }
void px(int x, int y, int w, int h, uint16_t c) { area.fillRect(x - AREA_X, y - AREA_Y, w, h, c); }

void desenharMascote() {
  area.fillScreen(C_BG);
  // chao: brilho quente e sombra
  int cx = BODY_X + BODY_W * PW / 2, fy = BODY_Y + BODY_H * PH;
  const int fl[3][2] = {{300, 0}, {240, 6}, {180, 12}};
  for (auto &f : fl) px(cx - f[0] / 2, fy + 3 + f[1], f[0], 6, C_FLOOR);
  const int sh[3] = {210, 150, 90};
  for (int i = 0; i < 3; i++) px(cx - sh[i] / 2, fy + 3 + i * 6, sh[i], 6, C_SHADOW);
  // corpo, com luz de cima e da esquerda
  for (int y = 0; y < BODY_H; y++)
    for (int x = 0; x < BODY_W; x++) {
      if (!solido(x, y)) continue;
      int X = BODY_X + x * PW, Y = BODY_Y + y * PH;
      bool perna = y == BODY_H - 1;
      px(X, Y, PW, PH, perna ? C_LO : C_BODY);
      if (!solido(x - 1, y)) px(X, Y, 4, PH, perna ? C_BODY : C_MID);
      if (!solido(x, y - 1)) px(X, Y, PW, 6, C_HI);
      if (!solido(x + 1, y)) px(X + PW - 4, Y, 4, PH, perna ? C_DEEP : C_LO);
      if (!solido(x, y + 1)) px(X, Y + PH - 8, PW, 8, perna ? C_DEEP : C_LO);
    }
  // olhos: buracos no corpo; piscar fecha, arregalar cresce para cima
  if (m.blinkT < 0) {
    for (int ex : {EYE_L, EYE_R}) {
      int x = BODY_X + (ex + m.eyeDx) * PW, y = BODY_Y + (int)((EYE_ROW + m.eyeDy) * PH);
      px(x, y, PW, (int)(m.eyeH * PH), C_BG);
      px(x, y - 4, PW, 4, C_DEEP);
    }
  }
  // boca
  if (m.mouth > 0) {
    int x = BODY_X + 8 * PW, y = BODY_Y + (int)(2.5f * PH), h = m.mouth * PH / 2;
    px(x, y, 2 * PW, h, C_BG);
    px(x, y - 4, 2 * PW, 4, C_DEEP);
  }
  // tres pontos (pensando / trabalhando)
  if (m.estado == PENSANDO || m.estado == TRABALHANDO) {
    int passo = (int)(m.t * 4) % 4, d = 12, x0 = BODY_X + 15 * PW + 10, y0 = BODY_Y - d;
    for (int i = 0; i < 3; i++) px(x0 + i * (d + 8), y0 - i * 10, d, d, i < passo ? C_FG : C_DIM);
  }
  // "!" piscando (alerta)
  if (m.estado == ALERTA) {
    uint16_t c = ((int)(m.t * 3) % 2) ? C_WARN_HI : C_WARN;
    int x = BODY_X + 15 * PW + 14;
    px(x, BODY_Y, 12, 26, c); px(x, BODY_Y + 34, 12, 12, c);
  }
  area.pushSprite(AREA_X, AREA_Y);
}

// quebra o texto em linhas que cabem na largura; devolve quantas linhas
int quebrar(const char *txt, int n, String linhas[], int maxLinhas, int largura) {
  String resto = String(txt).substring(0, n), atual = "";
  int qtd = 0;
  while (resto.length()) {
    int sp = resto.indexOf(' ');
    String palavra = sp < 0 ? resto : resto.substring(0, sp + 1);
    resto = sp < 0 ? "" : resto.substring(sp + 1);
    if (rodape.textWidth((atual + palavra).c_str()) > largura && atual.length()) {
      if (qtd < 32) linhas[qtd++ % 32] = atual;
      atual = "";
    }
    atual += palavra;
  }
  if (atual.length()) linhas[qtd++ % 32] = atual;
  return qtd;
}

void desenharRodape() {
  rodape.fillScreen(C_BG);
  int y0 = FOOT_TOP;
  // barras de audio
  int bw = 6, gap = 4, total = 16 * bw + 15 * gap, bx = (W - total) / 2, base = FOOT_Y - 6;
  for (int i = 0; i < 16; i++) {
    int h = max(2, (int)roundf(m.bars[i] * 14) * 2);
    rodape.fillRect(bx + i * (bw + gap), base - h - y0, bw, h, m.bars[i] > .05f ? C_BODY : C_DIM);
  }
  // texto
  const char *txt = ""; uint16_t cor = C_DIM; int n = 0;
  if (m.estado == REPOUSO && !m.texto[0]) txt = "segure para falar";
  else if (m.estado == ALERTA) { txt = "1 aguardando aprovacao (demo)"; cor = C_WARN; }
  else if (m.estado == TRABALHANDO) txt = "ponte-vps: rodando os testes...";
  else if (m.estado == OUVINDO) { txt = m.typed ? m.texto : "ouvindo..."; cor = m.typed ? C_FG : C_DIM; }
  else if (m.estado == PENSANDO) txt = "";
  else { txt = m.texto; cor = C_FG; }
  n = (m.estado == OUVINDO && m.typed) || m.estado == RESPONDENDO ? min((int)strlen(txt), m.typed) : strlen(txt);
  static String linhas[32];
  int qtd = quebrar(txt, n, linhas, 32, W - 48);
  int ini = m.estado == REPOUSO ? 0 : max(0, qtd - 2);        // repouso: o comeco; escrevendo: as 2 ultimas
  rodape.setTextColor(cor);
  for (int i = 0; i < 2 && ini + i < qtd; i++) {
    String l = linhas[ini + i];
    if (m.estado == REPOUSO && i == 1 && qtd > 2) l = l.substring(0, max(0, (int)l.length() - 3)) + "...";
    rodape.drawString(l.c_str(), W / 2, FOOT_Y + 4 + i * 16 - y0);
  }
  rodape.pushSprite(0, FOOT_TOP);
}

void desenharTopo() {
  tft.fillRect(0, 0, W, TOP_BAR, C_BG);
  tft.fillRect(12, TOP_BAR / 2 - 3, 6, 6, m.estado == ALERTA ? C_WARN : C_OK);
  tft.setFont(&fonts::Font2);
  tft.setTextDatum(middle_left);
  tft.setTextColor(m.estado == ALERTA ? C_WARN : C_DIM, C_BG);
  tft.drawString(m.estado == ALERTA ? "1 aguardando aprovacao" : "demo - sem ponte", 26, TOP_BAR / 2 + 1);
  tft.setTextDatum(middle_right);
  tft.setTextColor(C_DIM, C_BG);
  tft.drawString("toque aqui: estados", W - 12, TOP_BAR / 2 + 1);
}

// ---- programa principal ---------------------------------------------------------------------
uint32_t ultimo = 0;
bool apertado = false;
uint32_t assinaturaMascote = 0, assinaturaRodape = 0;

void setup() {
  Serial.begin(115200);
  delay(300);
  tft.init();
  tft.setRotation(1);
  tft.setBrightness(220);
  C_BG = tft.color565(0x14, 0x12, 0x10);  C_FLOOR = tft.color565(0x1b, 0x16, 0x13); C_SHADOW = tft.color565(0x0b, 0x09, 0x08);
  C_HI = tft.color565(0xf0, 0xa0, 0x7c);  C_MID = tft.color565(0xe5, 0x89, 0x6a);   C_BODY = tft.color565(0xd9, 0x77, 0x57);
  C_LO = tft.color565(0xbf, 0x64, 0x46);  C_DEEP = tft.color565(0x8f, 0x47, 0x31);  C_FG = tft.color565(0xed, 0xe6, 0xdc);
  C_DIM = tft.color565(0x8a, 0x81, 0x78); C_OK = tft.color565(0x6f, 0xbf, 0x73);    C_WARN = tft.color565(0xe6, 0xb4, 0x50);
  C_WARN_HI = tft.color565(0xf6, 0xd2, 0x7e);
  tft.fillScreen(C_BG);

  area.setPsram(true);   area.setColorDepth(16);
  rodape.setPsram(true); rodape.setColorDepth(16);
  if (!area.createSprite(AREA_W, AREA_H) || !rodape.createSprite(W, FOOT_H)) {
    tft.setTextColor(TFT_RED); tft.drawString("Sem memoria: confira PSRAM = OPI PSRAM", 10, 150);
    Serial.println("Falha ao criar os desenhos: PSRAM esta em OPI PSRAM nas Ferramentas?");
    while (true) delay(1000);
  }
  rodape.setFont(&fonts::Font2);
  rodape.setTextDatum(top_center);
  entrar(REPOUSO);
  ultimo = millis();
}

void loop() {
  uint32_t agora = millis();
  float dt = (agora - ultimo) / 1000.0f;
  ultimo = agora;

  // touch: segurar = ouvir; soltar = pensar; tocar no topo = trocar de estado
  int32_t tx, ty;
  static uint32_t ultimoToque = 0;
  bool leu = tft.getTouch(&tx, &ty);
  if (leu) ultimoToque = agora;
  bool toque = leu || (apertado && agora - ultimoToque < 150);   // o resistivo falha por instantes: so solta apos 150 ms
  if (toque && !apertado) {
    if (ty < TOP_HIT) {
      Estado prox = m.estado == REPOUSO ? TRABALHANDO : m.estado == TRABALHANDO ? ALERTA : REPOUSO;
      m.texto = ""; entrar(prox);
    } else { m.texto = ""; entrar(OUVINDO); }
  }
  if (!toque && apertado && m.estado == OUVINDO) { m.typed = strlen(m.texto); entrar(PENSANDO); }
  apertado = toque;

  atualizar(dt);

  // so redesenha o que mudou (a tela ILI9488 e lenta para redesenhar tudo)
  uint32_t a = m.estado;
  a = a * 31u + (m.blinkT >= 0);
  a = a * 31u + (uint32_t)(m.eyeDx + 2);
  a = a * 31u + (uint32_t)(m.eyeH * 10);
  a = a * 31u + (uint32_t)(m.eyeDy * 10 + 20);
  a = a * 31u + (uint32_t)m.mouth;
  if (m.estado == PENSANDO || m.estado == TRABALHANDO) a = a * 31u + (uint32_t)(m.t * 4) % 4;   // pontos
  if (m.estado == ALERTA) a = a * 31u + (uint32_t)(m.t * 3) % 2;                                 // "!" piscando
  if (a != assinaturaMascote) { desenharMascote(); assinaturaMascote = a; }
  uint32_t b = m.estado * 7u + m.typed * 131u + (uint32_t)(uintptr_t)m.texto;
  for (int i = 0; i < 16; i++) b = b * 31u + (uint32_t)(m.bars[i] * 14);
  if (b != assinaturaRodape) { desenharRodape(); assinaturaRodape = b; }

  delay(16);
}
