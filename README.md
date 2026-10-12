# Mascote Claude

Mascote de mesa com tela que mostra minhas sessões do Claude e permite conversar com ele.

## Status (2026-10-12)
- **Hardware:** protótipo na protoboard funcionando (ESP32-S3 N16R8 + tela 3,5" ILI9488 com touch resistivo). Microfone ainda não ligado.
- **Firmware** (`firmware/mascote/`): Wi-Fi, lista de sessões, tela de cada sessão, Aprovar/Recusar, HTTPS validado (CA + IP). Gravado e funcionando no aparelho.
- **Ponte em produção:** a ponte real (`software/bridge/real/`) roda na VPS como unit `systemd --user` em 127.0.0.1:8787, atrás do nginx em `https://179.198.122.200`. O mascote já mostra as **sessões reais** da VPS (Remote Control) e da nuvem (claude.ai/code). A ponte demo (`software/bridge/ponte.py`) ficou desligada; para voltar a ela: `sudo bash software/bridge/real/trocar_producao.sh rollback`.
- **Comprovado em testes reais** (`software/bridge/cli/README.md`): na VPS, aprovar/recusar, "sempre permitir", perguntas (inclusive várias opções), aprovar plano, perigosos só no app, app e mascote ao mesmo tempo, mensagens (tmux). Na nuvem, por um adaptador **não documentado e experimental**: aprovar/recusar, perguntas e planos (sem "sempre").

## Estrutura
- `docs/decisoes.md` — decisões tomadas (uma por pergunta do grill-me)
- `docs/compras-online.md` — lista de compras com links (Mercado Livre)
- `docs/montagem.md` — mapa de pinos e guia de montagem em etapas, com um teste por etapa
- `hardware/manual-montagem.html` — manual interativo da protoboard (Parte 1): passos curtos, peças ligáveis/desligáveis, multímetro virtual, 3 vistas (física, blocos, símbolos); extras opcionais (capacitores de 100 nF, pull-ups do touch, botão, som) com multímetro de tensão, continuidade e resistência
- `hardware/manual-placa-ilhada.html` — manual interativo da placa ilhada 6×8 cm (Parte 2): soquetes, barramentos, fios do verso, layout ajustável, extras de botão e som. **Não validado com as peças reais**
- `hardware/esquema-ligacoes.html` — esquema visual das ligações (abra no navegador)
- `hardware/manual-montagem-ili9488.html` e `hardware/esquema-ligacoes-ili9488.html` — manual (Parte 1) e esquema para a tela de teste 3,5" ILI9488 com touch resistivo XPT2046 (touch em SPI próprio, GPIO 9, 5, 8, 4)
- `hardware/entendendo-os-componentes.html` — o que é cada peça da lista, com desenhos (capacitor, resistor, botão, protoboard, multímetro)
- `hardware/pcb-placa-base.html` — rascunho da PCB do modelo final (placa-base de 80 × 60 mm onde os módulos encaixam): esquema com rótulos de rede, posição das peças, lista de redes e de peças, regras para o EasyEDA. Serve para as duas telas
- `hardware/solda-passo-a-passo.html` — passo a passo visual para soldar os pinos do ESP32 (desenhos de lado, erros comuns e como consertar)
- `hardware/caixa-desenho.html` — desenhos e recomendações da caixa impressa (vistas, corte, layout interno, impressão)
- `docs/bom.md` — lista de componentes (Santa Ifigênia)
- `docs/guia-de-compras.pdf` — guia ilustrado: marcas, alternativas, onde achar, preço estimado, ferramentas extras
- `hardware/` — esquemáticos, fotos, modelos 3D da carcaça (Bambu A1)
- `firmware/testes/` — programas de teste de cada etapa da montagem e dos extras de botão e som (compilam para ESP32-S3; ainda não testados na placa)
- `firmware/` — código do microcontrolador
- `software/bridge/` — ponte entre as sessões do Claude e o mascote
  - `software/bridge/real/` — **ponte em produção** (API nova + compatível com o firmware atual, hooks, tmux, nuvem experimental, instalação e troca/rollback)
  - `software/bridge/cli/` — protótipo e resultados dos testes da Fase 1 (VPS e nuvem)
  - `software/bridge/deploy-https/` — instalação do HTTPS por IP (nginx + Let's Encrypt)
  - `software/bridge/ponte.py` — ponte demo (sessões de exemplo; desligada)
- `software/ui-proto/` — protótipo web da tela (480x320): mascote animado e push-to-talk

## Próximos passos
1. Usar o mascote com as sessões reais e corrigir bugs que aparecerem.
2. Firmware novo usando a API nova da ponte: perguntas com opções, aprovar plano, aviso "aprove pelo app", criar sessão escolhendo repo/branch, origem vps/nuvem na lista.
3. Ligar o microfone (voz para mensagens e respostas livres).
4. Placa ilhada / PCB e caixa.
