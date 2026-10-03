// Etapas 2 e 3: tela ST7796 (SPI) e touch (I2C).
// Etapa 2: deixe USAR_TOUCH em 0 e veja as cores na tela.
// Etapa 3: troque USAR_TOUCH para 1; cada toque desenha um ponto e imprime x e y.
// Biblioteca: LovyanGFX (Gerenciador de Bibliotecas).
// Touch GT911 em vez de FT6336: troque Touch_FT5x06 por Touch_GT911 e i2c_addr por 0x5D.

#define USAR_TOUCH 0

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// Pinos (docs/montagem.md)
constexpr int PIN_SCK = 12, PIN_MOSI = 11, PIN_MISO = 13, PIN_DC = 14;
constexpr int PIN_CS = 10, PIN_RST = 6, PIN_BL = 7;
constexpr int PIN_SDA = 8, PIN_SCL = 9, PIN_TP_INT = 4, PIN_TP_RST = 5;

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ST7796 _panel;
  lgfx::Bus_SPI _bus;
  lgfx::Light_PWM _light;
  lgfx::Touch_FT5x06 _touch;  // o chip FT6336 usa este driver

public:
  LGFX() {
    {
      auto cfg = _bus.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 40000000;
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
      cfg.x_min = 0;
      cfg.x_max = 319;
      cfg.y_min = 0;
      cfg.y_max = 479;
      cfg.pin_int = PIN_TP_INT;
      cfg.bus_shared = false;
      cfg.offset_rotation = 0;
      cfg.i2c_port = 0;
      cfg.i2c_addr = 0x38;     // FT6336
      cfg.pin_sda = PIN_SDA;
      cfg.pin_scl = PIN_SCL;
      cfg.freq = 400000;
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

#if USAR_TOUCH
  // reinicia o chip do touch antes de iniciar a tela
  pinMode(PIN_TP_RST, OUTPUT);
  digitalWrite(PIN_TP_RST, LOW);
  delay(10);
  digitalWrite(PIN_TP_RST, HIGH);
  delay(100);
#endif

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
  tft.print("Toque na tela");
#endif
}

void loop() {
#if USAR_TOUCH
  int32_t x, y;
  if (tft.getTouch(&x, &y)) {
    tft.fillCircle(x, y, 6, TFT_YELLOW);
    Serial.printf("toque: x=%d y=%d\n", (int)x, (int)y);
  }
#endif
}
