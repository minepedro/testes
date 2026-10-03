# Lista de compras (BOM) — Santa Ifigênia

Marque com [x] ao comprar. Preencha preço na loja. Comprar 1 reserva dos itens marcados com (R).

## Essenciais

- [ ] **ESP32-S3 DevKitC-1, versão N16R8 (16 MB flash + 8 MB PSRAM)** — qtd 2 (R)
  - Aceitável: N8R8. **Evitar:** ESP32 comum, ESP32-S3 sem PSRAM, ESP32-C3/S2.
  - Conferir na etiqueta do módulo: "ESP32-S3-WROOM-1" com "R8". Ter 2 portas USB-C é normal (uma é UART, outra USB nativa).
  - Preço: ______

- [ ] **Tela 3,5" SPI 480x320 com touch capacitivo** — qtd 1 (+1 reserva se couber) (R)
  - Preferir: controlador **ST7796** + touch capacitivo (FT6336 ou GT911).
  - Aceitável: ILI9488 + touch resistivo (XPT2046). Funciona, mas é mais lento e menos agradável.
  - **Evitar:** versão "shield para Arduino Uno" (barramento paralelo de 8 bits). Precisa ser módulo **SPI** com pinos (SCK, MOSI, CS, DC, RST, LED + pinos do touch).
  - Perguntar: aceita 3,3 V? Tem ficha/datasheet? Pode testar ligada?
  - Preço: ______

- [ ] **Microfone I2S INMP441** — qtd 2 (R)
  - Alternativas: ICS-43434, SPH0645.
  - **Evitar:** microfone analógico (MAX9814, módulo "KY-038"), não é I2S.
  - Preço: ______

- [ ] **Amplificador I2S MAX98357A** — qtd 2 (R) — *opcional na v1: o mascote responde só por texto (decisão 16)*
  - **Evitar:** PAM8403 (é analógico, não recebe I2S).
  - Preço: ______

- [ ] **Alto-falante 4 Ω ou 8 Ω, 3 W, ~40 mm** — qtd 2 (R) — *opcional na v1: o mascote responde só por texto (decisão 16)*
  - Quanto maior o cone, melhor o grave, mas a carcaça cresce. 40 a 50 mm é bom ponto.
  - Preço: ______

- [ ] **Cabo USB-C de dados** (não só de carga) — qtd 2
  - Preço: ______

- [ ] **Fonte 5 V 2 A** (carregador de celular serve se tiver) — qtd 1
  - Preço: ______

## Montagem e protótipo

- [ ] Protoboard 830 pontos — qtd 1
- [ ] Jumpers macho-macho e macho-fêmea 20 cm (kit 40 un.) — qtd 2 kits
- [ ] Barra de pinos (header) macho e fêmea — para soldar nos módulos que vierem sem
- [ ] Capacitor eletrolítico 470 µF 10 V (ou 1000 µF) — qtd 4, reduz ruído no amplificador
- [ ] Botão tátil (push button) — qtd 4, para reset/boot e testes
- [ ] Fio fino 26 a 30 AWG, solda e ferro de solda (se não tiver)

## Carcaça (impressão na Bambu A1)

- [ ] Parafusos M3 (10 a 16 mm) e porcas — kit pequeno
- [ ] Insertos roscados M3 de latão — opcional, melhora a fixação em PLA/PETG
- [ ] Fita dupla-face ou espuma fina para fixar a tela

## Dicas para a loja

1. Peça para a loja **ligar a tela e o ESP32** antes de comprar, se possível.
2. Tire foto da etiqueta do módulo ESP32 e do verso da tela (controlador e pinos).
3. Se não achar ESP32-S3 com PSRAM: não improvise com ESP32 comum. Compre o resto e importe a placa (as demais peças funcionam do mesmo jeito).
4. Guarde a nota fiscal de tudo; telas e ESP32 às vezes vêm com defeito.

## Pendente para depois da compra

- Mapa de pinos (ESP32-S3 com PSRAM octal usa os GPIO 35, 36 e 37 internamente, então eles não podem ser usados nos periféricos)
- Esquema de ligação do I2S (mic e amplificador compartilham o clock)
- Modelo 3D da carcaça
