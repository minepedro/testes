// Etapa 1: confirma que a placa é N16R8 (PSRAM de 8 MB e flash de 16 MB).
// Abra o Monitor Serial em 115200.

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println();
  Serial.printf("Chip:  %s, %d MHz\n", ESP.getChipModel(), ESP.getCpuFreqMHz());
  Serial.printf("PSRAM: %u bytes (esperado: perto de 8388608)\n", ESP.getPsramSize());
  Serial.printf("Flash: %u bytes (esperado: perto de 16777216)\n", ESP.getFlashChipSize());
}

void loop() {}
