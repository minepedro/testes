// Extra: botão tátil entre o GPIO 21 e o GND.
// Sem apertar, o pino lê 1 (o resistor interno puxa para 3V3). Apertando, lê 0.
// Abra o Monitor Serial em 115200.

constexpr int PIN_BOTAO = 21;

bool anterior = true;

void setup() {
  Serial.begin(115200);
  delay(1500);
  pinMode(PIN_BOTAO, INPUT_PULLUP);  // pull-up interno: sem botão apertado o pino fica em 1
  Serial.println("Botão pronto. Aperte e solte o botão.");
}

void loop() {
  bool agora = digitalRead(PIN_BOTAO);  // 1 = solto, 0 = apertado
  if (agora != anterior) {
    Serial.println(agora ? "solto  (leitura 1)" : "APERTADO (leitura 0)");
    anterior = agora;
    delay(20);  // espera o ruído do contato passar (debounce)
  }
}
