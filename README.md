# Mascote Claude

Mascote de mesa com tela que mostra minhas sessões do Claude e permite conversar com ele.

## Status
Fase 0: definição (grill-me). Lista de compras pronta em `docs/bom.md`; nada comprado ainda.

## Estrutura
- `docs/decisoes.md` — decisões tomadas (uma por pergunta do grill-me)
- `docs/compras-online.md` — lista de compras com links (Mercado Livre)
- `docs/montagem.md` — mapa de pinos e guia de montagem em etapas, com um teste por etapa
- `hardware/esquema-ligacoes.html` — esquema visual das ligações (abra no navegador)
- `docs/bom.md` — lista de componentes (Santa Ifigênia)
- `docs/guia-de-compras.pdf` — guia ilustrado: marcas, alternativas, onde achar, preço estimado, ferramentas extras
- `hardware/` — esquemáticos, fotos, modelos 3D da carcaça (Bambu A1)
- `firmware/` — código do microcontrolador
- `software/bridge/` — ponte entre as sessões do Claude e o mascote
- `software/ui-proto/` — protótipo web da tela (480x320): mascote animado e push-to-talk

## Próximos passos
1. Fechar decisões em `docs/decisoes.md`
2. Fechar BOM em `docs/bom.md`
3. Comprar componentes
4. Prototipar na protoboard
