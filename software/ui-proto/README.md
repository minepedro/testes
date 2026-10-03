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
| `idle`      | ligou / terminou de falar | Respira (4 px), pisca, olha para os lados. Rodapé "segure para falar". |
| `listening` | toque e segurar           | Olhos arregalados, inclina, anel pulsa, barras de áudio, transcrição. |
| `thinking`  | soltou o dedo             | Olha para o lado, três pontos ao lado da cabeça.                 |
| `speaking`  | resposta chegou           | Boca abre e fecha, corpo balança, texto da resposta no rodapé.   |

Toque curto demais (< 300 ms) volta ao `idle` com a dica "segure o dedo enquanto fala".
Tocar durante `speaking` interrompe e volta a ouvir.

## Para o firmware

- O sprite é o Clawd do terminal do Claude Code, lido em quadrantes:

  ```
   ▐▛███▜▌        ...############...
  ▝▜█████▛▘  ->   ...##.######.##...
    ▘▘ ▝▝         .################.
                  ...############...
                  ....#.#....#.#....
  ```

  18×5 pixels, cada um com **15×30 px** na tela. A proporção 1:2 é a da célula
  do terminal; com pixels quadrados o mascote fica achatado.
  Olhos (fileira 1, colunas 5 e 12) e boca (entre os olhos e a barriga, colunas
  8–9) são buracos no corpo, como no original.
- Sombreamento por vizinhança, sem gradiente: pixel de borda sem vizinho em cima
  ganha luz (`hi`), sem vizinho à esquerda `mid`, sem vizinho embaixo ou à
  direita `lo`; as pernas são mais escuras (`lo`/`deep`). O corpo não tem
  faixas internas. Há ainda uma sombra
  no chão que encolhe quando ele sobe. Dá para gerar tudo isso offline como
  sprite pré-renderizado, sem custo de CPU no ESP32.
- Movimento em passos inteiros (sem interpolação): cada pose é um frame de sprite.
- Paleta de 11 cores, todas representáveis em RGB565.
- Faixas de texto: topo 28 px (ponte, sessões, relógio) e rodapé 44 px.
- A ponte na VPS só precisa mandar `{estado, texto}`; a máquina de estados
  em `update()` dentro do `index.html` é o contrato.

## Fora do escopo por enquanto

Lista de sessões, tela de aprovar ação e conversa completa. Ficam para as próximas iterações.
