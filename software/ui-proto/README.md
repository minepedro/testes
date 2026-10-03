# Protótipo da UI (web)

Protótipo da tela do mascote em HTML/JS, na resolução real da tela (480×320).
Serve para fechar o visual e o fluxo antes de o hardware chegar; depois o
desenho vai para LVGL no firmware.

## Como ver

Abra `index.html` no navegador. Não precisa de servidor.

- Segure o dedo (ou o mouse) na tela para falar; solte para ele pensar e responder.
- Os botões abaixo da tela forçam um estado para inspecionar a animação.
- Zoom 1×, 1,5× e 2× (a tela real tem 480×320 px, 3,5").

## Estados

| Estado      | Entra quando              | O que faz                                                        |
|-------------|---------------------------|------------------------------------------------------------------|
| `idle`      | ligou / terminou de falar | Respira (2 px), pisca, olha para os lados. Rodapé "segure para falar". |
| `listening` | toque e segurar           | Olhos arregalados, inclina, anel pulsa, barras de áudio, transcrição. |
| `thinking`  | soltou o dedo             | Olha para cima, três pontos ao lado da cabeça.                   |
| `speaking`  | resposta chegou           | Boca abre e fecha, corpo balança, texto da resposta no rodapé.   |

Toque curto demais (< 300 ms) volta ao `idle` com a dica "segure o dedo enquanto fala".
Tocar durante `speaking` interrompe e volta a ouvir.

## Para o firmware

- Grade de 12 px por célula. Corpo 16×12, olhos 2×3, pés 2×1, boca 2×(0–2).
- Movimento em passos inteiros (sem interpolação): cada pose é um frame de sprite.
- Paleta de 6 cores, todas representáveis em RGB565.
- Faixas de texto: topo 28 px (ponte, sessões, relógio) e rodapé 44 px.
- A ponte na VPS só precisa mandar `{estado, texto}`; a máquina de estados
  em `update()` dentro do `index.html` é o contrato.

## Fora do escopo por enquanto

Lista de sessões, tela de aprovar ação e conversa completa. Ficam para as próximas iterações.
