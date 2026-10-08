// Etapas 2 e 3 (tela de teste): ILI9488 (SPI) e touch resistivo XPT2046 (SPI separado).
// Etapa 2: deixe USAR_TOUCH em 0 e veja as cores na tela.
// Etapa 3: troque USAR_TOUCH para 1; cada toque desenha um ponto e imprime x e y (cru e na tela).
// Biblioteca: LovyanGFX (Gerenciador de Bibliotecas).
// O touch usa um segundo barramento SPI (SPI3) com fios próprios. Assim ele não divide
// o MISO com a tela: o ILI9488 não solta o fio SDO e atrapalharia a leitura do touch.

#define USAR_TOUCH 0

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// Pinos da tela (docs/montagem.md, variante ILI9488): os mesmos da ST7796
constexpr int PIN_SCK = 12, PIN_MOSI = 11, PIN_MISO = 13, PIN_DC = 14;
constexpr int PIN_CS = 10, PIN_RST = 6, PIN_BL = 7;
// Pinos do touch XPT2046: os GPIO que o touch capacitivo usaria (4, 5, 8, 9)
constexpr int PIN_T_CLK = 9, PIN_T_CS = 5, PIN_T_DIN = 8, PIN_T_DO = 4;
constexpr int PIN_T_IRQ = -1;  // T_IRQ fica sem ligar; a biblioteca pergunta ao chip se há toque

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
      cfg.freq_write = 27000000;  // o ILI9488 é mais lento; se aparecer ruído, baixe para 20000000
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
      cfg.panel_width = 320;   // a tela é 320x480 "em pé"; setRotation(1) deixa 480x320
      cfg.panel_height = 480;
      cfg.offset_x = 0;
      cfg.offset_y = 0;
      cfg.offset_rotation = 0;
      cfg.readable = false;
      cfg.invert = false;      // se as cores saírem invertidas (preto vira branco), troque para true
      cfg.rgb_order = false;   // se vermelho e azul saírem trocados, troque para true
      cfg.dlen_16bit = false;
      cfg.bus_shared = false;
      _panel.config(cfg);
    }
    {
      auto cfg = _light.config();
      cfg.pin_bl = PIN_BL;
      cfg.invert = false;
      cfg.freq = 44100;
      cfg.pwm_channel = 7;
      _light.config(cfg);
      _panel.setLight(&_light);
    }
#if USAR_TOUCH
    {
      auto cfg = _touch.config();
      // valores crus típicos do XPT2046; refine com o que o Serial mostrar nos cantos
      cfg.x_min = 300;
      cfg.x_max = 3900;
      cfg.y_min = 200;
      cfg.y_max = 3900;
      cfg.pin_int = PIN_T_IRQ;
      cfg.bus_shared = false;
      cfg.offset_rotation = 0;  // se o ponto sair espelhado ou de lado, tente 1 a 7
      cfg.spi_host = SPI3_HOST;
      cfg.freq = 1000000;
      cfg.pin_sclk = PIN_T_CLK;
      cfg.pin_mosi = PIN_T_DIN;
      cfg.pin_miso = PIN_T_DO;
      cfg.pin_cs = PIN_T_CS;
      _touch.config(cfg);
      _panel.setTouch(&_touch);
    }
#endif
    setPanel(&_panel);
  }
};

LGFX tft;

void setup() {
  Serial.begin(115200);
  delay(1000);

  tft.init();
  tft.setRotation(1);       // paisagem, 480x320
  tft.setBrightness(200);

  // 1) as três cores, nesta ordem: vermelho, verde, azul
  const uint32_t cores[] = {TFT_RED, TFT_GREEN, TFT_BLUE};
  for (uint32_t c : cores) {
    tft.fillScreen(c);
    delay(800);
  }

  // 2) moldura e texto
  tft.fillScreen(TFT_BLACK);
  tft.drawRect(0, 0, tft.width(), tft.height(), TFT_WHITE);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(3);
  tft.setCursor(24, 24);
  tft.print("Mascote Claude");
  tft.setTextSize(2);
  tft.setCursor(24, 80);
  tft.printf("Tela %dx%d ok", tft.width(), tft.height());
#if USAR_TOUCH
  tft.setCursor(24, 112);
  tft.print("Aperte a tela (touch resistivo)");
#endif
}

void loop() {
#if USAR_TOUCH
  int32_t x, y;
  if (tft.getTouch(&x, &y)) {
    tft.fillCircle(x, y, 6, TFT_YELLOW);
    lgfx::touch_point_t cru;
    tft.getTouchRaw(&cru, 1);
    Serial.printf("toque: x=%d y=%d  (cru: %d, %d)\n", (int)x, (int)y, cru.x, cru.y);
    delay(20);
  }
#endif
}
