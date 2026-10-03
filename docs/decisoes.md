# Decisões

Formato: pergunta, resposta, motivo.

## 1. Como conversa com o mascote?
**Voz + tela touch.** Microfone e alto-falante para conversar, tela touch para navegar nas sessões.

## 2. Onde roda a inteligência?
**ESP32-S3 como terminal + ponte rodando na VPS (nuvem).** O mascote só cuida de tela, touch, mic e alto-falante; a ponte conversa com o Claude, lê as sessões e faz fala/transcrição.
Motivo: já existe servidor ligado 24h, então não precisa de Raspberry Pi (mais caro, esquenta).
