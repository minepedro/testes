# Decisões

Formato: pergunta, resposta, motivo.

## 1. Como conversa com o mascote?
**Voz + tela touch.** Microfone e alto-falante para conversar, tela touch para navegar nas sessões.

## 2. Onde roda a inteligência?
**ESP32-S3 como terminal + ponte rodando na VPS (nuvem).** O mascote só cuida de tela, touch, mic e alto-falante; a ponte conversa com o Claude, lê as sessões e faz fala/transcrição.
Motivo: já existe servidor ligado 24h, então não precisa de Raspberry Pi (mais caro, esquenta).

## 3. Quais sessões o mascote mostra?
**As duas: Claude Code (cc.remote) e chats do claude.ai.**
- Claude Code: a ponte lê direto na VPS (fonte oficial/estável).
- claude.ai: fonte de dados ainda em aberto. Não há API oficial para conta pessoal; a Compliance API é só Enterprise. Alternativas: wrapper não oficial por cookie (frágil), export manual, extensão de Chrome.
- A fonte dos chats é software (ponte), não muda o hardware.

## 4. Como tratar os chats do claude.ai?
**v1 só Claude Code; claude.ai fica para a v2.** Método da v2 (cookie, export, extensão ou Compliance API) será escolhido depois, sem impacto no hardware.

## 5. Placa pronta ou peças avulsas?
**Peças avulsas, compradas na Santa Ifigênia.** ESP32-S3 (com PSRAM) + tela touch + microfone I2S + amplificador + alto-falante. Carcaça impressa na Bambu A1.

## 6. Qual tela?
**3,5" touch, 480x320.** Maior e mais legível para lista de sessões.
Nota de compra: preferir controlador ST7796 (RGB565, mais rápido) ao ILI9488 (18 bits, mais lento no SPI). Confirmar o tipo de touch (resistivo XPT2046 ou capacitivo) na loja.

## 7. Como acorda o mascote?
**Toque na tela (push-to-talk) na v1; palavra de ativação depois.** O ESP32-S3 suporta as duas, então o hardware não muda.
