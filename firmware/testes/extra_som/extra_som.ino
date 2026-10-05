// Extra: toca bipes no alto-falante pelo amplificador MAX98357A (I2S).
// Precisa do núcleo esp32 (Espressif) versão 3.0 ou mais nova.
// O som é gerado aqui mesmo, sem arquivos: uma onda senoidal na frequência pedida.
// Se o microfone estiver montado, ele divide os fios BCLK e WS: use este programa
// com o microfone desligado do I2S (o teste do microfone fica para depois).

#include <ESP_I2S.h>
#include <math.h>

constexpr int PIN_BCLK = 15, PIN_WS = 16, PIN_DIN = 18;
constexpr int TAXA = 16000;      // amostras por segundo
constexpr float VOLUME = 0.25f;  // 0 a 1. Comece baixo: o alto-falante é pequeno

I2SClass i2s;

// toca um tom de 'hz' durante 'ms' milissegundos (hz = 0 faz silêncio)
void tom(float hz, int ms) {
  int total = TAXA * ms / 1000;
  for (int n = 0; n < total; n++) {
    float fade = 1.0f;                        // sobe e desce suave, para não estalar
    if (n < 160) fade = n / 160.0f;
    if (total - n < 160) fade = (total - n) / 160.0f;
    int16_t s = hz > 0 ? (int16_t)(sinf(2.0f * PI * hz * n / TAXA) * 32000.0f * VOLUME * fade) : 0;
    int16_t par[2] = {s, s};                  // esquerdo e direito iguais
    i2s.write((uint8_t *)par, sizeof(par));
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  i2s.setPins(PIN_BCLK, PIN_WS, PIN_DIN, -1);  // só saída (-1 = sem entrada)
  if (!i2s.begin(I2S_MODE_STD, TAXA, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO)) {
    Serial.println("Falha ao iniciar o I2S. Confira BCLK (15), LRC (16) e DIN (18).");
    while (true) delay(1000);
  }
  Serial.println("Som pronto.");
}

void loop() {
  Serial.println("bipe de toque");    tom(1200, 60);  tom(0, 600);
  Serial.println("aviso de aprovação"); tom(880, 120); tom(0, 60); tom(1320, 180); tom(0, 800);
  Serial.println("erro");             tom(300, 400);  tom(0, 1200);
}
