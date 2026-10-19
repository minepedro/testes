# Caixa Mini Mac

**Onde está:** a caixa inteira está modelada (v1) e conferida no computador. Ainda não imprima: falta o resultado do segundo teste da tela e três medidas (plugue USB-C, J e amplificador), que hoje são chute.

## Arquivos

| Arquivo | O que é |
|---|---|
| `caixas-retro.html` | As ideias de caixa (o Mini Mac foi o escolhido) e o desenho por dentro, com a bandeja. |
| `planta-caixa.html` | A planta da caixa inteira em escala (frente, corte de lado, vista de cima e lateral), com as peças reais dentro. Proposta, ainda não confirmada. |
| `medidas-mini-mac.html` | A página das medidas, com os desenhos em escala. Esta cópia abre com as medidas de `medidas.json`; o que você digitar nela fica só no navegador. |
| `medidas.json` | As medidas em mm, de 19/out/2026. Os nomes dos campos aparecem na página (por exemplo `v_esq` é a medida H, da borda esquerda da placa da tela até o vidro). |
| `gerar_teste_tela.py` | Gera as duas peças de teste da tela: STEP de cada uma e um 3MF com as duas. |
| `teste-tela/` | O croqui cotado (`croqui.html`), os STEP, o 3MF para o Bambu Studio e o PDF de verificação. |
| `verificacao/verificar_teste_tela.py` | Mede os STEP gerados e refaz o PDF de verificação. |
| `gerar_caixa.py` | Gera a caixa inteira: corpo, bandeja, moldura de trás da tela, tecla e tampa do microfone (STEP de cada uma e dois 3MF já deitados na mesa). Usa as medidas da tela de `gerar_teste_tela.py`. |
| `modelo/` | Os STEP e os 3MF da caixa (`caixa-corpo.3mf`, `caixa-bandeja-e-pecas.3mf`), a página para girar a caixa em 3D (`caixa-3d.html`) e o modelo dela (`caixa-3d.gltf.json`). Para abrir a página no computador, sirva a pasta (`python3 -m http.server`); aberta direto do disco o navegador não carrega o modelo. |
| `verificacao/verificar_caixa.py` | Confere a caixa montada medindo os STEP: peças fechadas, nada invadindo nada, a bandeja entrando por trás, a chave de fenda alcançando os parafusos da tela, os parafusos curtos o bastante. Também refaz o modelo 3D da página. |

O mapa dos componentes do ESP32 está em `../mapa-esp32.html`.

## Gerar de novo

```bash
pip install cadquery trimesh manifold3d reportlab --break-system-packages
python3 hardware/caixa/gerar_teste_tela.py hardware/caixa/teste-tela
python3 hardware/caixa/gerar_caixa.py hardware/caixa/modelo
python3 hardware/caixa/verificacao/verificar_caixa.py
# a verificação usa o cadkit e o cadraw do plugin cad-industrial
CADKIT_DIR=<pasta scripts do plugin> python3 hardware/caixa/verificacao/verificar_teste_tela.py
```

As medidas ficam no começo de `gerar_teste_tela.py` (tela) e de `gerar_caixa.py` (o resto). Mudou uma medida, muda lá, gera de novo e roda a verificação.

## Decisões da caixa até agora

- **Formato Mini Macintosh**, uns 11 × 12 × 13 cm (largura × profundidade × altura), em PLA bege e branco. Tem AMS lite.
- **Tela:** presa por uma **moldura de trás** que aperta os 4 cantos da placa vermelha, com **4 parafusos M3 em insertos de calor** nos cantos da moldura da frente, por fora da placa. Os furos da própria tela só recebem pininhos de alinhamento: do furo até o vidro sobram menos de 3 mm, pouco para a cabeça do M3 ou para a parede de um inserto.
- **Botão** tátil 6 × 6 na frente, à direita da grade do microfone (1 clique acorda; segurar fala).
- **LED** WS2812 de 5 mm para status, no GPIO 47 (ainda vai ser comprado e ligado).
- **Microfone** atrás da gradezinha do queixo, ligado à placa por 6 jumpers macho-fêmea.
- **Alto-falante** de 40 mm embaixo da grade do topo.
- **Placa ilhada** 80 × 60 deitada numa bandeja que sai por trás. Os furos dos cantos têm 2,2 mm (o M3 não passa): ela encaixa em pininhos impressos.
- **Cabo USB-C** reto, embutido na lateral direita: o plugue entra inteiro na caixa por um túnel com chanfro e encaixa na porta "USB" do ESP32 (do lado da linha L). A porta COM queimou. Por isso a placa fica deslocada para a esquerda na bandeja.
- **Bandeja** entra por trás em trilhos nas laterais; a tampa de trás faz parte dela e prende com 2 M3 em insertos nos cantos de cima. A chave de fenda alcança os parafusos da tela por trás com tudo montado.
- **Amplificador** desliza por trás em dois trilhos na parede esquerda. **Alto-falante** colado com dupla-face embaixo da grade do topo, centrado por 4 aletas. **Microfone** num copo atrás de uma grade de 19 furos, com anel de EVA de 1 mm e uma tampa.
- **Impressão sem suporte:** o corpo sai com a frente na mesa (a frente fica lisa), a tecla com a face na mesa. Tudo que fica no ar tem rampa de 45°; o que sobra são furos deitados (o maior, o do USB, tem 7 mm de altura), pontes de 1,8 mm nas fendas e um degrau de 1 mm em volta da janela da tela.
- **Sem** sensor de luz e sem fita de cobre.
- **Parafusos:** por enquanto só M3 × 19. Por isso a moldura de trás tem torres de 13 mm, que somem com M3 × 8.

## Pendências

1. No primeiro teste da tela o vidro, os pininhos e a janela ficaram certos; a placa vermelha não entrou do lado esquerdo. Segunda versão: encaixe da placa 1 mm maior de cada lado (98,6 de largura, de −1,3 a 97,3); o bolso do vidro continua 85,0. Imprimir de novo a moldura da frente e conferir.
2. Confirmar o tamanho dos insertos. Supus os de 5,7 mm de comprimento e 4,6 por fora (furo de 4,0).
3. Furos da tela: a 1 mm da borda dá 90,4 × 49,2 entre centros; a primeira medida tinha dado 89,5 × 50. O teste decide.
4. Alto-falante: tem furos ou abas? Amplificador: medir (supus 18 × 19).
4b. Entrada do cabo embutida na lateral (o plugue entra na caixa): medir o plástico do plugue (largura, altura, comprimento) e a posição do USB na placa (medida J). Hoje: plugue 12 × 6,5 × 20 e J 25,1, chutados. O comprimento do plugue move a placa na bandeja, então o corpo e a bandeja esperam essas medidas.
5. Caixa v1 modelada e conferida no computador. Não foi fatiada: conferir tempo, filamento e pontes no Bambu Studio antes de imprimir.
