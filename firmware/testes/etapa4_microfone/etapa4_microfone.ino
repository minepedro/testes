// Etapa 4: lê o microfone INMP441 pelo I2S e mostra o volume no Serial.
// Precisa do núcleo esp32 (Espressif) versão 3.0 ou mais nova.
// Esperado: o número e a barra sobem quando você bate palma perto.

#include <ESP_I2S.h>

constexpr int PIN_BCLK = 15, PIN_WS = 16, PIN_MIC_DATA = 17;

I2SClass i2s;

void setup() {
  Serial.begin(115200);
  delay(1500);

  i2s.setPins(PIN_BCLK, PIN_WS, -1, PIN_MIC_DATA);  // sem saída de áudio (-1)
  // o INMP441 manda 24 bits dentro de uma palavra de 32; L/R no GND = canal esquerdo
  if (!i2s.begin(I2S_MODE_STD, 16000, I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO, I2S_STD_SLOT_LEFT)) {
    Serial.println("Falha ao iniciar o I2S. Confira os fios SCK, WS e SD.");
    while (true) delay(1000);
  }
  Serial.println("Microfone pronto. Bata palma perto dele.");
}

void loop() {
  int32_t amostras[256];
  size_t n = i2s.readBytes((char *)amostras, sizeof(amostras)) / sizeof(int32_t);
  if (n == 0) return;

  // volume = desvio médio em relação à média (tira o nível contínuo do microfone)
  int64_t soma = 0;
  for (size_t i = 0; i < n; i++) soma += amostras[i] >> 14;
  int32_t media = soma / (int64_t)n;
  int64_t desvio = 0;
  for (size_t i = 0; i < n; i++) desvio += abs((amostras[i] >> 14) - media);
  int32_t volume = desvio / (int64_t)n;

  int barra = constrain(volume / 100, 0, 60);
  Serial.printf("%6d ", (int)volume);
  for (int i = 0; i < barra; i++) Serial.print('#');
  Serial.println();
}
