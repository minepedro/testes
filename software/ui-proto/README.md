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
| `working`   | abriu uma sessão rodando  | Olha para o lado, três pontos piscando. Rodapé: última atividade. |
| `alert`     | sessão pediu permissão    | Olhos arregalados, boca pequena, "!" âmbar. Aparecem os botões.  |

Toque curto demais (< 300 ms) volta ao `idle` com a dica "segure o dedo enquanto fala".
Tocar durante `speaking` interrompe e volta a ouvir.

O mascote não muda de lugar em nenhum estado: só olhos, boca e rodapé mudam.

## Sessões

As sessões da tela são exemplos; a ponte vai mandar as reais. Use "simular
pedido de permissão" na bancada para ver a reação do mascote.

- **Entrar:** toque na faixa de cima da tela do mascote. A faixa mostra
  "N aguardando aprovação" em âmbar (o mascote fica em `alert`) ou
  "ponte ok · N sessões" em verde.
- **Lista:** uma sessão por linha (58 px): ícone de estado, título,
  `repositório · branch`, tempo e estado. Ordem: aguardando, trabalhando, depois
  o resto. Arraste para rolar.
- **Filtro por repo:** botão "repo" no cabeçalho. Abre a lista de repositórios
  com a contagem de sessões de cada um, mais "Avulsas (sem repositório)".
- **Abrir a sessão:** toque numa linha. O mascote abre *dentro* da sessão: o
  cabeçalho mostra título e branch, segurar a tela fala com aquela sessão e o
  rodapé mostra a última atividade. Na mesma posição de sempre.
- **Aprovar:** se a sessão pede permissão, o mascote reage (`alert`) e abaixo
  dele aparecem o comando exato e os botões Recusar e Aprovar (40 px). Se outra
  sessão pedir enquanto você está numa, um selo "!1" aparece no cabeçalho.
- **Nova sessão:** botão "+" da lista. Escolha repositório e branch (padrão,
  outra existente ou "nova branch automática"), ou "Sessão avulsa". Ao criar, a
  sessão abre no mascote para você dizer o que fazer.

| Estado    | Ícone (16×16)         | Cor     |
|-----------|-----------------------|---------|
| `waiting` | quadrado com "!"      | âmbar   |
| `working` | quadrado cheio, pisca | laranja |
| `idle`    | quadrado vazio        | cinza   |
| `done`    | quadrado com ✓        | verde   |

## Conexão com o Claude Code (verificado em 2026-10-03)

Legenda: **testado** = rodei nesta sessão; **documentado** = está na doc oficial
(code.claude.com/docs); **a validar** = plausível, ainda sem teste.

**Listar e acompanhar sessões** (testado, nesta sessão, pelas ferramentas
`claude-code-remote`). Cada sessão traz `title`, `session_status`,
`status_bucket` (WORKING / BLOCKED / COMPLETED), `session_context.sources[].git_repository`
(`url` e `revision`, que dão repo e branch), `post_turn_summary`
(`status_category`, `recent_action`, `needs_action`) e `updated_at`. É tudo o que
a lista precisa. *A validar:* a ponte na VPS chamar essa API sozinha (credencial).

| Campo da UI | Origem |
|---|---|
| `repo`, `branch` | `session_context.sources[0].git_repository` (`url`, `revision`) |
| `status` `working` | `status_bucket` = WORKING |
| `status` `waiting` | `status_bucket` = BLOCKED e `status_category` = `need_input` |
| `status` `done` / `idle` | `status_bucket` = COMPLETED / sessão parada |
| `last` | `post_turn_summary.recent_action` ou `task_summary` |
| `ago` | `updated_at` |

**Mandar uma instrução** (documentado): `claude -p "mensagem" --cloud <session-id>`
enfileira a mensagem numa sessão em nuvem e sai sem esperar resposta
(`--output-format json` devolve `{ok, session_id, url}`). A resposta se lê
acompanhando a sessão. Exige `claude auth login` com conta Anthropic.

**Criar sessão** (documentado): `claude --cloud "tarefa"` cria uma sessão em nuvem
para o repositório *do diretório atual*, na branch atual (precisa estar no
GitHub). Para escolher repo e branch pela tela, a ponte roda o comando dentro de
um checkout na branch escolhida. As ferramentas `claude-code-remote` desta sessão
também aceitam `source_url`, `source_revision`, `outcome_branch` e permitem
criar sem repositório (*a validar*, não criei sessão para testar).

**Aprovar permissões** (o ponto delicado):
- Sessões que **a própria ponte inicia** pelo Agent SDK: documentado e viável. O
  callback `canUseTool` é assíncrono e "pode ficar pendente indefinidamente",
  então dá para esperar o toque no botão do mascote e responder
  `{behavior: "allow"}` ou `{behavior: "deny", message}`. Há também o hook
  `PermissionRequest` (resposta em `hookSpecificOutput.decision.behavior`,
  `timeout` padrão de 600 s para hooks `command`/`http`) e o `Notification` com o
  filtro `permission_prompt`, para sessões locais no terminal da VPS.
- Sessões **já abertas no claude.ai/code ou no app**: não encontrei API
  documentada para aprovar um pedido de permissão de fora. O fluxo de eventos
  tem `control_request` / `control_response`, mas só vi os de inicialização
  (a sessão testada roda em modo `auto`, sem pedidos). *A validar* com uma
  sessão que peça permissão de verdade.
- `status_category = need_input` cobre também **perguntas** do Claude, não só
  permissões. Para esses casos o certo é mostrar `needs_action` e responder por
  voz, em vez de Aprovar/Recusar.

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
- Paleta de 18 cores, todas representáveis em RGB565.
- Tela do mascote: topo 28 px (ponte, sessões, relógio, tocável numa área de 40 px)
  e rodapé 44 px.
- A ponte na VPS só precisa mandar `{estado, texto}` para o mascote e, para as
  sessões, `{title, repo, branch, status, ago, last, ask?}` (`ask` = `{tool, text}`);
  a máquina de estados em `update()` e o array `SESSIONS` dentro do `index.html`
  são o contrato.

## Fora do escopo por enquanto

Conversa completa por voz, resposta a perguntas do Claude (`need_input` que não é permissão) e a conexão real com a ponte. Ficam para as próximas iterações.
