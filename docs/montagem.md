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
5. **Pino 5VIN sem energia (placa genérica "YD", com pinos amarelos):** medido em 10/out, o 3V3 dá 3,3 V, mas o 5VIN dá só 0,5 V com o USB ligado. A ponte de solda **IN-OUT**, na frente das portas USB, vem aberta. Tela, touch e microfone não usam 5 V. Para o amplificador de som: feche a ponte IN-OUT com uma gota de solda (e nunca ligue outra fonte no 5VIN com o USB conectado), ou alimente o VIN do amplificador no 3V3 (volume menor). Não mexa na ponte USB-OTG.
6. Não use estes pinos do ESP32-S3: **0, 3, 45, 46** (boot), **19, 20** (USB), **26 a 37** (memória flash e PSRAM), **43, 44** (porta serial), **38 e 48** (LED da placa, depende da versão).

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
| RESET | GPIO 6 | |
| LED (backlight) | GPIO 7 | Ou direto no 3V3 se você não quer controlar o brilho |

Os GPIO 10 a 13 são os pinos padrão do SPI rápido do ESP32-S3, por isso foram escolhidos. Todos os sinais ficam no conector **esquerdo** da placa, então os jumpers saem de um lado só.

O esquema desenhado, com cada fio colorido, está em `hardware/esquema-ligacoes.html`.

### Touch capacitivo (FT6336 ou GT911, I2C)

| Pino do touch | ESP32-S3 | Observação |
|---|---|---|
| SDA | GPIO 8 | Pino padrão de I2C do ESP32-S3 |
| SCL | GPIO 9 | Pino padrão de I2C do ESP32-S3 |
| INT | GPIO 4 | |
| RST | GPIO 5 | |
| VCC / GND | 3V3 / GND | Costuma vir no mesmo conector da tela |

### Variante de teste: tela ILI9488 com touch resistivo (XPT2046)

Para a tela vermelha de 3,5" com ILI9488 (comprada para testar enquanto a capacitiva não chega).
Os 9 fios da tela são **iguais** aos da ST7796 acima. O touch muda: ele ganha um **SPI só dele**
(SPI3), nos mesmos GPIO que o touch capacitivo usaria. Não divida o SPI da tela com o touch:
o ILI9488 não solta o fio SDO, e isso estraga a leitura do touch.

| Pino da tela | ESP32-S3 | Observação |
|---|---|---|
| T_CLK | GPIO 9 | Relógio do SPI do touch |
| T_CS | GPIO 5 | |
| T_DIN | GPIO 8 | Do ESP32 para o touch |
| T_DO | GPIO 4 | Do touch para o ESP32 |
| T_IRQ | sem ligar | O programa pergunta ao chip se há toque |
| SD_* (4 pinos do outro lado) | sem ligar | Cartão SD, não usado |

O VCC fica no 3V3, como na ST7796. Programa de teste: `firmware/testes/etapa2_3_tela_touch_ili9488`.
Manual e esquema desta variante: `hardware/manual-montagem-ili9488.html` e `hardware/esquema-ligacoes-ili9488.html`.
Placa ilhada com esta tela: `hardware/manual-placa-ilhada-ili9488.html` (a placa é a mesma da ST7796; só mudam os nomes dos 4 fios do touch).
Versão visual, passo a passo, com desenho em cada etapa: `hardware/manual-visual-placa-ilhada-ili9488.html`. Esta é a referência atual: placa de 27 × 22 furos (linhas A a V, colunas 1 a 27), ESP32 já soldado nas linhas B (J3) e L (J1), colunas 2 a 23, USB perto da coluna 2 e microfone redondo em dois soquetes de 3. O manual interativo antigo (`manual-placa-ilhada*.html`) ainda usa o layout de 31 × 23 furos. Como fazer os barramentos: `hardware/barramento-placa-ilhada.html`.
O touch resistivo funciona **apertando** e precisa de calibração (x_min, x_max, y_min, y_max no programa).

### Microfone INMP441 (I2S)

| Pino do microfone | ESP32-S3 | Observação |
|---|---|---|
| VDD | 3V3 | |
| GND | GND | |
| L/R | GND | Escolhe o canal esquerdo |
| SCK (BCLK) | GPIO 15 | |
| WS | GPIO 16 | |
| SD | GPIO 17 | Dados do microfone para o ESP32 |

### Opcional (som: bipes e alertas, sem voz): MAX98357A

| Pino do amplificador | ESP32-S3 | Observação |
|---|---|---|
| VIN | 5V | Dá mais volume que 3,3 V. Na placa YD o pino se chama 5Vin e só entrega 5 V com a ponte IN-OUT fechada (gota de solda nos dois quadradinhos ao lado do LED RGB) |
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
   - Partition Scheme: **16M Flash (3MB APP/9.9MB FATFS)**
4. O ESP32-S3-DevKitC-1 tem **duas portas USB-C**. Use a marcada **UART** (ou COM) para gravar e ver o Serial.
   - **Se a entrada COM parar de dar energia** (aconteceu na placa do Pedro depois de um curto no 5V: o
     diodo dessa entrada abriu), use a entrada marcada **USB** para tudo. Em *Ferramentas*: USB Mode
     **Hardware CDC and JTAG**, USB CDC On Boot **Enabled** (o Serial passa a sair por essa entrada) e
     a porta COM nova que aparece. Se a gravação falhar, segure BOOT, aperte e solte RST, solte BOOT e
     grave de novo. Por essa entrada o 5Vin fica perto de 4,6 V, o que serve para o amplificador.

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

**Resultado (10/out):** passou. Placa genérica "YD" com módulo S3-N16R8: PSRAM 8388608, Flash 16777216,
ESP32-S3 a 240 MHz. Gravada pela porta COM (COM5 no Windows, chip USB CH343), Arduino IDE 2.3.10 com pacote esp32 3.3.12.
3V3 medido: 3,3 V.

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

**Resultado (11/out), tela de teste ILI9488:** passou. Programa `etapa2_3_tela_touch_ili9488` com `USAR_TOUCH 0`
mostrou "Mascote Claude" e "Tela 480x320 ok". Lição: os problemas até aqui foram todos de jumper mal encaixado
(trilho com 0,6 V, GND da tela solto); conferir cada fio com o multímetro em continuidade antes de ligar.

## Etapa 3: o touch

1. Desligue o USB e ligue SDA, SCL, INT e RST do touch.
2. Rode um **scanner I2C** (exemplo pronto na própria IDE: *Arquivo > Exemplos > Wire > i2c_scanner*, ajustando SDA=8 e SCL=9).

**Teste:** o scanner acha um endereço (**0x38** para FT6336, **0x5D** ou **0x14** para GT911) e, ao tocar na tela, as coordenadas X e Y mudam.

| Se aparecer | Causa provável |
|---|---|
| Nenhum dispositivo | SDA e SCL trocados, ou `RST` do touch sem ligar |
| Coordenadas invertidas | Normal: ajuste a calibração/rotação no código |

**Resultado (11/out), touch resistivo XPT2046 da ILI9488:** passou. Com `USAR_TOUCH 1`, T_CLK 9, T_CS 5,
T_DIN 8, T_DO 4 (SPI3) e T_IRQ sem ligar, o ponto amarelo aparece onde se aperta, com a calibração padrão
(x 300 a 3900, y 200 a 3900) e `offset_rotation` 0.

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

## Teste do Camarim (acessórios e animações)

Grave `firmware/mascote` como sempre (placa ESP32S3 Dev Module, PSRAM "OPI PSRAM", porta COM5).
Nada disto foi testado na placa ainda; me conte o que aparecer.

1. Abra o Serial (115200). Logo depois da tela acender deve sair `memoria livre: interna ... B, PSRAM ... B`.
   A interna deve ficar perto de 200 KB ou mais; a PSRAM, perto de 7 MB (os desenhos ficam nela).
2. Na tela inicial, toque no **cabide** no canto superior direito: abre o Camarim
   (mascote à esquerda, coluna com as abas **Animar** e **Visual** à direita, botão **Voltar** embaixo).
3. Aba **Visual**: em "Cabeca", toque na metade direita da linha (`>`) até aparecer "Cartola".
   O chapéu aparece na hora. O Serial mostra `camarim: Cabeca = Cartola`.
4. Desligue e ligue a placa. Abra o Camarim de novo: a cartola continua lá (fica na NVS).
5. Teste "Sortear" no fim da lista e as outras camadas (cor, fundo, bigode...). Arraste a coluna para rolar.
6. Aba **Animar**: toque em cada uma das 11 animações. Tocar de novo na mesma para.
7. Volte para a tela inicial e dê um **toque curto** (rápido) na barriga: ele ri (cócegas).
8. **Segure** a tela e fale: a gravação de voz tem que funcionar como antes (barras sobem, "ouvindo...").
9. Gatilhos automáticos (sem tocar nada): sessão que termina = comemorar; última sessão que termina = dancinha;
   aprovar/recusar = check/X; erro da ponte (ou ponte fora por mais de 1 min) = tonto;
   10 min parado = cochilo (um toque acorda e não abre nada); com o bigode Guidão, a cada 3 a 6 min ele arruma o bigode.

## Etapa opcional: botão físico

Um botão tátil entre o **GPIO 21** e o **GND** (resistor pull-up interno do ESP32; sem apertar lê 1, apertado lê 0).
Teste: `firmware/testes/extra_botao`. Está na Parte 2 do manual interativo (`hardware/manual-placa-ilhada.html`).

## Etapa opcional: som

Sem voz falada (decisão 16), mas com som se você quiser (decisão 18). Monte o MAX98357A com o
alto-falante e o capacitor, conforme a tabela opcional acima.

Na placa ilhada, o amplificador encaixa por jumpers, como a tela: um soquete de 5 em pé na
coluna 27, de R27 a V27 (LRC, BCLK, DIN, GND, VIN, a mesma ordem dos pinos do amplificador), com
fios no verso até L15 (GPIO 16), L16 (GPIO 15), L13 (GPIO 18), B23 (GND do ESP32, pela borda) e L3 (5V). Os fios do 15
e do 16 entram na mesma solda dos fios do microfone. Daí saem 5 jumpers macho-fêmea de 20 cm até o
amplificador (GAIN e SD sem ligar). O capacitor de 470 µF (C4) fica deitado na frente, com a perna
− (faixa clara) em U26 e a + em V26, e uma gota de estanho no verso de U26 a U27 (GND) e de V26 a
V27 (VIN). Passo a passo nos passos 29 a 33 do manual visual
(`hardware/manual-visual-placa-ilhada-ili9488.html`). O mascote toca os sons (bipe ao
gravar e ao enviar a voz, "plim" quando uma sessão termina, festa quando todas terminam, aviso quando
uma sessão pede aprovação, aprovado/recusado, erro, cócegas e um clique nos toques). No `config.h`,
`SOM 0` desliga e `SOM_VOLUME` (0 a 1) ajusta o volume; sem essas linhas vale som ligado e volume 0.4.

## Programas de teste

Ficam em `firmware/testes/`, um por etapa:

| Etapa | Pasta | O que faz |
|---|---|---|
| 1 | `etapa1_psram` | Imprime PSRAM e flash no Serial |
| 2 e 3 | `etapa2_3_tela_touch` | Pinta a tela; com `USAR_TOUCH 1`, desenha um ponto a cada toque |
| 2 e 3 | `etapa2_3_tela_touch_ili9488` | Igual, para a tela de teste ILI9488 com touch resistivo (sem scanner I2C) |
| 3 | `etapa3_i2c_scan` | Procura o chip do touch no I2C |
| 4 | `etapa4_microfone` | Mostra o volume do microfone no Serial |
| extra | `extra_botao` | Mostra no Serial quando o botão é apertado e solto (GPIO 21) |
| extra | `extra_som` | Toca três sons de teste no alto-falante pelo MAX98357A (BCLK 15, LRC 16, DIN 18) |

Os quatro **compilam** para o ESP32-S3 N16R8 (arduino-cli, pacote esp32 3.3.12,
LovyanGFX 1.2.32), inclusive a variante com touch ligado. **Não foram testados na
placa.** Se algum não compilar na sua IDE, ou se comportar diferente do esperado,
me mande a mensagem de erro ou o que apareceu no Serial.

O desenho da protoboard, com cada jumper e as etapas, está em `hardware/esquema-ligacoes.html`.

## Como vamos fazer juntos

Faça uma etapa por vez e me conte o resultado do teste (o que apareceu no
Serial, foto da tela, etc.). Se falhar, me diga em qual etapa e eu te ajudo a
achar a causa. Eu também escrevo os programas de teste de cada etapa quando você chegar nela.
