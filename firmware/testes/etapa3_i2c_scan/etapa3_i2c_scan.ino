// Etapa 3 (diagnóstico): procura o chip do touch no I2C.
// Esperado: 0x38 (FT6336) ou 0x5D / 0x14 (GT911).

constexpr int PIN_SDA = 8, PIN_SCL = 9, PIN_TP_RST = 5;

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(1500);

  // sem este reset o chip do touch pode não responder
  pinMode(PIN_TP_RST, OUTPUT);
  digitalWrite(PIN_TP_RST, LOW);
  delay(10);
  digitalWrite(PIN_TP_RST, HIGH);
  delay(100);

  Wire.begin(PIN_SDA, PIN_SCL);
  Serial.println("Procurando dispositivos I2C...");
  int achados = 0;
  for (uint8_t endereco = 1; endereco < 127; endereco++) {
    Wire.beginTransmission(endereco);
    if (Wire.endTransmission() == 0) {
      Serial.printf("achei: 0x%02X\n", endereco);
      achados++;
    }
  }
  Serial.printf("%d dispositivo(s) encontrado(s)\n", achados);
}

void loop() {}
