# Protótipo da UI (web)

Protótipo da tela do mascote em HTML/JS, na resolução real da tela (480×320).
Serve para fechar o visual e o fluxo antes de o hardware chegar; depois o
desenho vai para LVGL no firmware.

## Como ver

Abra `index.html` no navegador. Não precisa de servidor.

- Segure o dedo (ou o mouse) na tela para falar; solte para ele pensar e responder.
- Toque na faixa de cima para abrir a lista de sessões.
- Os botões abaixo da tela trocam de tela e forçam um estado para inspecionar a animação.
- Zoom 1×, 1,5× e 2× (a tela real tem 480×320 px, 3,5").

## Estados

| Estado      | Entra quando              | O que faz                                                        |
|-------------|---------------------------|------------------------------------------------------------------|
| `idle`      | ligou / terminou de falar | Pisca e olha para os lados. Rodapé "segure para falar".          |
| `listening` | toque e segurar           | Olhos arregalados, barras de áudio, transcrição no rodapé.       |
| `thinking`  | soltou o dedo             | Olha para o lado, três pontos ao lado da cabeça.                 |
| `speaking`  | resposta chegou           | Boca abre e fecha, texto da resposta no rodapé.                  |

Toque curto demais (< 300 ms) volta ao `idle` com a dica "segure o dedo enquanto fala".
Tocar durante `speaking` interrompe e volta a ouvir.

O mascote não muda de lugar em nenhum estado: só olhos, boca e rodapé mudam.

## Sessões

As sessões da tela são exemplos; a ponte vai mandar as reais.

- **Entrar:** toque na faixa de cima da tela do mascote. A faixa mostra
  "N aguardando aprovação" em âmbar quando alguma sessão precisa de você, ou
  "ponte ok · N sessões" em verde.
- **Lista:** cabeçalho de 36 px e uma sessão por linha (58 px): ícone de estado,
  título, `repositório · branch`, tempo e estado. Ordem: aguardando, trabalhando,
  depois o resto por recência. A linha que aguarda tem fundo âmbar. Arraste para rolar.
- **Detalhe:** toque numa linha. Mostra a última atividade e, se a sessão pede
  permissão, o comando exato num quadro âmbar (a tela de aprovar vem depois).
- **Voltar:** seta no canto superior esquerdo (Esc no teclado).

| Estado       | Ícone (16×16)         | Cor     |
|--------------|-----------------------|---------|
| `waiting`    | quadrado com "!"      | âmbar   |
| `working`    | quadrado cheio, pisca | laranja |
| `idle`       | quadrado vazio        | cinza   |
| `done`       | quadrado com ✓        | verde   |

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
  faixas internas. Há ainda uma sombra no chão. Dá para gerar tudo isso offline
  como sprite pré-renderizado, sem custo de CPU no ESP32.
- O sprite fica sempre na mesma posição; cada pose (olhos, boca) é um frame, sem interpolação.
- Paleta de 15 cores, todas representáveis em RGB565.
- Tela do mascote: topo 28 px (ponte, sessões, relógio, tocável numa área de 40 px)
  e rodapé 44 px.
- A ponte na VPS só precisa mandar `{estado, texto}` para o mascote e, para as
  sessões, `{title, repo, branch, status, ago, last, ask?}`; a máquina de estados
  em `update()` e o array `SESSIONS` dentro do `index.html` são o contrato.

## Fora do escopo por enquanto

Tela de aprovar ação (botões Aprovar/Recusar) e conversa completa. Ficam para as próximas iterações.
