# Guia de montagem (v1, na protoboard)

Montagem em etapas. **Cada etapa termina com um teste.** Só passe para a próxima
quando o teste da anterior passar. Se algo falhar, a causa quase sempre está na
etapa que você acabou de fazer.

> O mapa de pinos abaixo é uma **proposta** minha, feita para evitar os pinos
> reservados do ESP32-S3 N16R8. Não foi testado em hardware. Quando as peças
> chegarem, confira os nomes dos pinos na serigrafia do seu módulo de tela antes
> de ligar (a ordem muda de fabricante para fabricante).

## Regras de segurança (valem para todas as etapas)

1. **Desligue o USB antes de mexer em qualquer fio.** Nunca ligue ou desligue jumper com a placa energizada.
2. Tudo trabalha em **3,3 V**. Só ligue algo em 5 V se o módulo disser que aceita.
3. Antes de ligar a tela, meça com o multímetro: pino `3V3` do ESP32 contra `GND` deve dar perto de 3,3 V.
4. Não use estes pinos do ESP32-S3: **0, 3, 45, 46** (boot), **19, 20** (USB), **26 a 37** (memória flash e PSRAM), **43, 44** (porta serial), **38 e 48** (LED da placa, depende da versão).

## Mapa de pinos

### Tela ST7796 (SPI)

| Pino da tela | ESP32-S3 | Observação |
|---|---|---|
| VCC | 3V3 | Confirme no anúncio se aceita 3,3 V |
| GND | GND | |
| CS | GPIO 10 | |
| SCK (CLK) | GPIO 12 | |
| SDI (MOSI) | GPIO 11 | |
| SDO (MISO) | GPIO 13 | Pode ficar sem ligar se a tela não for ler dados |
| DC (RS) | GPIO 14 | |
| RESET | GPIO 21 | |
| LED (backlight) | GPIO 47 | Ou direto no 3V3 se você não quer controlar o brilho |

Os GPIO 10 a 13 são os pinos padrão do SPI rápido do ESP32-S3, por isso foram escolhidos.

### Touch capacitivo (FT6336 ou GT911, I2C)

| Pino do touch | ESP32-S3 | Observação |
|---|---|---|
| SDA | GPIO 8 | Pino padrão de I2C do ESP32-S3 |
| SCL | GPIO 9 | Pino padrão de I2C do ESP32-S3 |
| INT | GPIO 4 | |
| RST | GPIO 5 | |
| VCC / GND | 3V3 / GND | Costuma vir no mesmo conector da tela |

Se a sua tela vier com touch **resistivo** (XPT2046), ele usa o mesmo SPI da tela:
`T_CLK`, `T_DIN` e `T_DO` vão junto com SCK, MOSI e MISO, `T_CS` no **GPIO 1** e `T_IRQ` no **GPIO 2**.

### Microfone INMP441 (I2S)

| Pino do microfone | ESP32-S3 | Observação |
|---|---|---|
| VDD | 3V3 | |
| GND | GND | |
| L/R | GND | Escolhe o canal esquerdo |
| SCK (BCLK) | GPIO 15 | |
| WS | GPIO 16 | |
| SD | GPIO 17 | Dados do microfone para o ESP32 |

### Opcional (só se for ter voz numa versão futura): MAX98357A

| Pino do amplificador | ESP32-S3 | Observação |
|---|---|---|
| VIN | 5V | Dá mais volume que 3,3 V |
| GND | GND | |
| BCLK | GPIO 15 | Compartilha com o microfone |
| LRC | GPIO 16 | Compartilha com o microfone |
| DIN | GPIO 18 | Dados do ESP32 para o amplificador |
| SD, GAIN | sem ligar | |

Capacitor de 470 µF entre `VIN` e `GND` do amplificador, **com a perna do traço (-) no GND**.

## Antes de começar

**Software** (no computador):
1. Instale o [Arduino IDE 2](https://www.arduino.cc/en/software).
2. Em *Gerenciador de placas*, instale **esp32 by Espressif Systems**.
3. Em *Ferramentas*, configure (os nomes podem variar um pouco conforme a versão):
   - Placa: **ESP32S3 Dev Module**
   - Flash Size: **16MB (128Mb)**
   - PSRAM: **OPI PSRAM**
   - USB CDC On Boot: **Disabled** (o Serial sai pela porta UART)
   - Partition Scheme: um esquema de 16 MB
4. O ESP32-S3-DevKitC-1 tem **duas portas USB-C**. Use a marcada **UART** (ou COM) para gravar e ver o Serial.

**Bancada:** protoboard, jumpers (macho-macho e macho-fêmea), multímetro, cabo USB-C **de dados**.
Planeje uns 22 jumpers no total (tela 9, touch 4, microfone 6, mais alimentação).

## Etapa 1: o ESP32-S3 sozinho

Objetivo: provar que a placa é N16R8 de verdade e que você consegue gravar nela.

1. Encaixe o ESP32 na protoboard, com o USB para fora. **Não ligue mais nada.**
2. Conecte o cabo na porta UART e ao computador.
3. Grave este programa:

```cpp
void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.printf("PSRAM: %u bytes\n", ESP.getPsramSize());
  Serial.printf("Flash: %u bytes\n", ESP.getFlashChipSize());
}
void loop() {}
```

**Teste:** o Monitor Serial (115200) mostra PSRAM perto de **8388608** e Flash perto de **16777216**.

| Se aparecer | Causa provável |
|---|---|
| PSRAM: 0 | Opção PSRAM errada nas Ferramentas, ou a placa não tem PSRAM (anúncio enganoso) |
| Não grava | Cabo só de carga, ou porta USB errada. Segure `BOOT`, aperte `RESET` e solte `BOOT` |
| Texto ilegível | Velocidade do monitor diferente de 115200 |

Se vier PSRAM 0 mesmo com a opção certa, você recebeu uma placa sem PSRAM. Peça troca,
é por isso que a lista tem uma placa reserva.

## Etapa 2: a tela (só imagem)

Objetivo: acender a tela e pintar cores.

1. Desligue o USB.
2. Se os pinos da tela vieram soltos na caixa, solde a barra de pinos antes (é a única solda do projeto).
3. Ligue **só os fios da tela** (tabela acima: VCC, GND, CS, SCK, MOSI, MISO, DC, RESET, LED). Deixe o touch para a etapa 3.
4. Antes de ligar o USB, confira com o multímetro que **VCC e GND da tela não estão em curto** (modo continuidade: não pode apitar).
5. Use a biblioteca **LovyanGFX** (ou TFT_eSPI) com o driver **ST7796** e os pinos da tabela.

**Teste:** a tela acende e você consegue pintá-la de vermelho, verde e azul, nessa ordem.

| Se aparecer | Causa provável |
|---|---|
| Tela branca ou preta | `RESET`, `DC` ou `CS` trocados; ou driver errado na biblioteca |
| Cores trocadas (azul vira vermelho) | Ordem RGB/BGR: inverta na configuração do driver |
| Imagem espelhada ou rotacionada | Ajuste a rotação na configuração |
| Imagem com ruído | Fio de SCK ou MOSI frouxo; use jumpers mais curtos |

Com a tela funcionando, o protótipo web que fizemos (480×320) pode ser portado para ela.

## Etapa 3: o touch

1. Desligue o USB e ligue SDA, SCL, INT e RST do touch.
2. Rode um **scanner I2C** (exemplo pronto na própria IDE: *Arquivo > Exemplos > Wire > i2c_scanner*, ajustando SDA=8 e SCL=9).

**Teste:** o scanner acha um endereço (**0x38** para FT6336, **0x5D** ou **0x14** para GT911) e, ao tocar na tela, as coordenadas X e Y mudam.

| Se aparecer | Causa provável |
|---|---|
| Nenhum dispositivo | SDA e SCL trocados, ou `RST` do touch sem ligar |
| Coordenadas invertidas | Normal: ajuste a calibração/rotação no código |

## Etapa 4: o microfone

1. Desligue o USB e ligue o INMP441: VDD, GND, **L/R no GND**, SCK, WS e SD.
2. Leia amostras pelo I2S e imprima o volume no Serial.

**Teste:** o número do volume é baixo no silêncio e **sobe quando você bate palma** perto.

| Se aparecer | Causa provável |
|---|---|
| Sempre zero | `L/R` solto (precisa ir ao GND), ou SD no pino errado |
| Ruído alto e constante | Fios longos; aproxime o microfone do ESP32 |

## Etapa 5: juntar tudo

Com tela, touch e microfone testados separadamente, o próximo passo é gravar o
mascote de verdade (LVGL, com o sprite 18×5 do protótipo) e ligar o touch ao
push-to-talk. Essa parte eu escrevo junto com você quando você chegar aqui.

## Etapa opcional: voz de saída

Fora da v1 (decisão 16). Se decidir ter voz depois, monte o MAX98357A com o
alto-falante e o capacitor, conforme a tabela opcional acima.

## Como vamos fazer juntos

Faça uma etapa por vez e me conte o resultado do teste (o que apareceu no
Serial, foto da tela, etc.). Se falhar, me diga em qual etapa e eu te ajudo a
achar a causa. Eu também escrevo os programas de teste de cada etapa quando você chegar nela.
