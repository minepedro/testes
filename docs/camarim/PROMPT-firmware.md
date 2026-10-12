# Prompt: levar o Camarim para o firmware do mascote

Cole o texto abaixo numa sessão do Claude Code com o repositório `minepedro/testes`.

---

Repositório `minepedro/testes`, branch `main`. Leia antes: `CLAUDE.md` (se existir), `docs/decisoes.md` (decisões 1 a 27), `firmware/mascote/mascote.ino`, `firmware/mascote/tipos.h` e `docs/camarim/index.html`.

## Objetivo
Levar para o firmware (`firmware/mascote/`) o que está na prévia `docs/camarim/index.html`:
1. **Os acessórios**, um por camada:
   - Cabeça, Olhos, Bigode, Boca, Peito, Mão
   - Cor do corpo (7 paletas de 5 tons)
   - Fundo (liso, estrelas, pôr do sol, grama, neve)
2. **As 11 animações:** comemorar, pedir aprovação, aprovado, recusado, tonto, trabalhando, ouvindo, cochilo, cócegas, dancinha, arrumar o bigode.
3. **Uma tela "Camarim" no próprio aparelho**, onde o Pedro escolhe o visual e toca as animações quando quiser.

## A prévia é a especificação
A prévia é um canvas de 480×320 desenhado só com retângulos, do mesmo jeito que `desenharMascote()` usa `px()`/`fillRect`. Porte as funções de desenho 1 para 1, com as mesmas cores e formas:
- `CABECA`, `OLHOS`, `BIGODE`, `BOCA`, `PEITO`, `MAO`
- `fundo`, `chao`, `neveNoCorpo`, `olhos`, `boca`, `efeitos`, `particulas`
- os passos de cada animação em `PASSO`

Há um cuidado com as coordenadas. Na prévia o corpo está em `BX=105, BY=96`, e no firmware `BODY_X=105, BODY_Y=68`. Todas as coordenadas da prévia são absolutas com `BY=96`. Converta para coordenadas relativas ao corpo (`x - 105 + BODY_X`, `y - 96 + BODY_Y`), para não ficar tudo 28 px mais alto ou mais baixo.

Os olhos, a boca e os acessórios acompanham os deslocamentos do corpo:
- deslocamentos: `dx`, `dy`, `bodyDy` e `rowDx` (inclinação por linha);
- braços e pernas: `armL`, `armR`, `legL`, `legR`.

Veja como a prévia aplica isso com `em(rosto, ...)`, `em(cab, ...)` e `em(peito, ...)`.

## Espaço na tela
Hoje o sprite `area` vai de `AREA_X=88, AREA_Y=48` com `316×194`. Os chapéus sobem até cerca de 60 px acima da cabeça, e a bandeira e a caneca passam do lado direito. Faça a área de desenho crescer (para cima até logo abaixo do cabeçalho e para os lados) e/ou abaixe o corpo quando houver chapéu. O rodapé (barras, texto, botões Aprovar/Recusar e a confirmação de voz) deve continuar igual e no mesmo lugar.

Os sprites ficam na PSRAM (`setPsram(true)`). Confira a memória livre no Serial depois da mudança.

## Animações ligadas a eventos reais
Crie um sistema de animação por cima do `Estado` atual. Uma animação tem início e duração; enquanto toca, ela ajusta o quadro, e ao terminar volta ao estado normal. Gatilhos:
- **comemorar:** uma sessão passou de `working`/`waiting` para `done`.
- **dancinha:** a última sessão em `working`/`waiting` terminou (todas concluídas). Tem prioridade sobre comemorar.
- **pedir aprovação:** é o `ALERTA` atual, agora com aceno e o pé batendo depois de 2 s.
- **aprovado / recusado:** logo depois da resposta 200 de `/api/acao`.
- **tonto:** uma ação ou envio falhou (resposta de erro da ponte) ou a ponte ficou fora por mais de 1 min.
- **trabalhando:** é o `TRABALHANDO` atual, com gota de suor.
- **ouvindo:** é o `OUVINDO` atual, com a cabeça inclinada.
- **cochilo:** 10 min sem toque e sem mudança nas sessões. Qualquer toque acorda, e esse toque **não** abre nada.
- **cócegas:** toque curto (menos de 250 ms) no corpo, na tela inicial. Segurar continua sendo a gravação de voz (decisão 26); não quebre isso.
- **arrumar o bigode:** sozinho, a cada 3 a 6 min em repouso, só se o bigode escolhido for o guidão.

## Tela Camarim
- **Como abrir:** um botão pequeno (ícone de cabide, desenhado em pixels) no canto superior direito da tela inicial. Hoje tocar no topo (`TOP_HIT`) abre a lista; o canto direito passa a abrir o Camarim. Crie `T_CAMARIM` em `tipos.h` (os tipos ficam lá por causa dos protótipos automáticos do Arduino).
- **Layout em 480×320:**
  - à esquerda, o mascote ao vivo (pode empurrar o sprite `area` para x ≈ 0 nessa tela);
  - à direita, uma coluna de cerca de 160 px com duas abas, "Animar" e "Visual", e uma lista rolável, como no menu genérico (`T_MENU`, linha de 48 px);
  - um botão "Voltar".
- **Animar:** um botão por animação. Tocar toca a animação; tocar de novo para.
- **Visual:** uma linha por camada mostrando `Camada: item`, com setas `<` `>` (alvos de pelo menos 44 px) que trocam o item ao vivo. No final, um "Sortear".
- **Textos:** a fonte da tela só tem ASCII, então escreva sem acento ("Cocegas", "Coracao").
- **Memória da escolha:** a escolha fica na NVS com `Preferences` (namespace `mascote`, uma chave por camada) e é carregada no `setup()`.

## Desempenho
- **Taxa de quadros:** em repouso, mantenha o redesenho só quando o estado muda (o hash de hoje). Com animação, partícula (fumaça, vapor, neve, confete, notas, Zzz) ou fundo animado, redesenhe a no máximo cerca de 25 quadros/s.
- **Partículas:** um vetor fixo de cerca de 64 posições, sem `new`/`String` dentro do laço de desenho.
- **Áudio:** a tarefa de áudio (núcleo 1) e a de rede não podem travar; o desenho continua no `loop()`.

## Não mexer
- O `config.h` não pode ser lido, mostrado nem commitado.
- Não altere a ponte nem os fluxos de voz, aprovação, filtro ou sessão nova, a não ser para encaixar os gatilhos.
- Comandos perigosos continuam só pelo app (decisão 23).
- Comandos de voz para o camarim ("coloca a cartola", "dança") ficam para depois, porque hoje a fala na tela inicial vira sessão nova (decisão 26).

## Como entregar
1. Compile com o arduino-cli:
   - core `esp32:esp32@3.3.12`
   - FQBN `esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,CDCOnBoot=default`
   - bibliotecas LovyanGFX e ArduinoJson iguais às de hoje

   O build tem que passar sem avisos novos.
2. Rode os testes de `firmware/mascote/testes_host` que existirem.
3. Atualize `docs/montagem.md` com o teste do Camarim, passo a passo. Na decisão 27 de `docs/decisoes.md`, acrescente uma linha dizendo que o firmware foi feito.
4. Faça commit e push na `main`.
5. Gere um .zip com `mascote.ino`, `tipos.h`, `transporte.h`, `raizes_letsencrypt.h` e `config.exemplo.h`, **sem o config.h**, para o Pedro trocar os arquivos em `Downloads\mascote\mascote` e gravar pelo Arduino IDE (porta COM5).
6. Diga claramente que nada foi testado na placa, e dê ao Pedro um roteiro curto de teste:
   - abrir o Camarim;
   - trocar o chapéu e conferir se continua depois de desligar;
   - tocar cada animação;
   - dar um toque curto no corpo (cócegas);
   - conferir que segurar para falar ainda funciona.
