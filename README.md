# Mascote Claude

Mascote de mesa com tela que mostra minhas sessões do Claude e permite conversar com ele.

## Status
Fase 0: definição (grill-me). Lista de compras pronta em `docs/bom.md`; nada comprado ainda.

## Estrutura
- `docs/decisoes.md` — decisões tomadas (uma por pergunta do grill-me)
- `docs/compras-online.md` — lista de compras com links (Mercado Livre)
- `docs/montagem.md` — mapa de pinos e guia de montagem em etapas, com um teste por etapa
- `hardware/manual-montagem.html` — manual interativo da protoboard (Parte 1): passos curtos, peças ligáveis/desligáveis, multímetro virtual, 3 vistas (física, blocos, símbolos)
- `hardware/manual-placa-ilhada.html` — manual interativo da placa ilhada 6×8 cm (Parte 2): soquetes, barramentos, fios do verso, layout ajustável, extras de botão e som. **Não validado com as peças reais**
- `hardware/esquema-ligacoes.html` — esquema visual das ligações (abra no navegador)
- `hardware/entendendo-os-componentes.html` — o que é cada peça da lista, com desenhos (capacitor, resistor, botão, protoboard, multímetro)
- `hardware/caixa-desenho.html` — desenhos e recomendações da caixa impressa (vistas, corte, layout interno, impressão)
- `docs/bom.md` — lista de componentes (Santa Ifigênia)
- `docs/guia-de-compras.pdf` — guia ilustrado: marcas, alternativas, onde achar, preço estimado, ferramentas extras
- `hardware/` — esquemáticos, fotos, modelos 3D da carcaça (Bambu A1)
- `firmware/testes/` — programas de teste de cada etapa da montagem e dos extras de botão e som (compilam para ESP32-S3; ainda não testados na placa)
- `firmware/` — código do microcontrolador
- `software/bridge/` — ponte entre as sessões do Claude e o mascote
- `software/ui-proto/` — protótipo web da tela (480x320): mascote animado e push-to-talk

## Próximos passos
1. Fechar decisões em `docs/decisoes.md`
2. Fechar BOM em `docs/bom.md`
3. Comprar componentes
4. Prototipar na protoboard
