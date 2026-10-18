// Tipos usados em mascote.ino. Ficam num arquivo a parte porque a Arduino IDE
// cria os prototipos das funcoes no topo do .ino, antes de qualquer tipo declarado nele.
#pragma once
#include <Arduino.h>

struct Sessao {
  String id, title, repo, branch, status, ago, last, reply, askTool, askText;
};
enum Link { CONECTANDO, SEM_WIFI, SEM_PONTE, PONTE_OK };          // estado da conexao com a ponte
enum Estado { REPOUSO, OUVINDO, PENSANDO, RESPONDENDO, TRABALHANDO, ALERTA };
enum Tela { T_MASCOTE, T_LISTA, T_SESSAO, T_MENU, T_CAMARIM };
enum FaseVoz { V_NADA, V_GRAVANDO, V_TRANSCREVENDO, V_CONFIRMAR, V_ENVIANDO };
enum Proposito { PR_NADA, PR_VOZ, PR_MSG, PR_REPOS, PR_BRANCHES, PR_CRIAR, PR_VINCULAR };   // para que serve o pedido de rede
enum Menu { M_FILTRO, M_REPOS, M_BRANCHES };
struct ItemMenu { String rotulo, sub, valor; };
struct Trabalho { uint32_t id = 0; bool post = false, binario = false; String caminho, corpo; const uint8_t *dados = nullptr; size_t n = 0; };

// ---- Camarim (docs/camarim/index.html): camadas, itens, animacoes e particulas ----
enum Camada { CM_CABECA, CM_OLHOS, CM_BIGODE, CM_BOCA, CM_PEITO, CM_MAO, CM_COR, CM_FUNDO, N_CAMADAS };
enum ItemCabeca { CAB_NADA, CAB_CARTOLA, CAB_BONE, CAB_COWBOY, CAB_COROA, CAB_OBRA, CAB_FONE, CAB_NATAL, CAB_FESTA };
enum ItemOlhos { OLH_NADA, OLH_OCULOS, OLH_ESCUROS, OLH_MONOCULO, OLH_TAPAOLHO };
enum ItemBigode { BIG_NADA, BIG_CLASSICO, BIG_GUIDAO };
enum ItemBoca { BOC_NADA, BOC_CIGARRO, BOC_CHARUTO, BOC_CACHIMBO };
enum ItemPeito { PEI_NADA, PEI_BORBOLETA, PEI_GRAVATA, PEI_CACHECOL };
enum ItemMao { MAO_NADA, MAO_CANECA, MAO_CHAVE, MAO_BANDEIRA };
enum ItemCor { COR_LARANJA, COR_AZUL, COR_VERDE, COR_ROXO, COR_DOURADO, COR_ROSA, COR_CINZA };
enum ItemFundo { FUN_LISO, FUN_ESTRELAS, FUN_PORSOL, FUN_GRAMA, FUN_NEVE };
enum Anim { A_NENHUMA, A_COMEMORAR, A_APROVACAO, A_APROVADO, A_RECUSADO, A_TONTO, A_TRABALHANDO, A_OUVINDO,
            A_COCHILO, A_COCEGAS, A_DANCINHA, A_ARRUMAR, N_ANIMS };
struct AnimInfo { const char *nome; float dur; };
// sons do alto-falante (tocarSom)
enum Som : uint8_t { S_CLIQUE, S_GRAVAR, S_ENVIAR, S_PLIM, S_FESTA, S_AVISO, S_APROVADO, S_RECUSADO, S_ERRO, S_COCEGAS };
enum Olhar { O_NORMAL, O_FELIZ, O_FECHADO, O_X, O_RISO, O_PISCA };
enum Emissor { E_SUOR, E_ZZZ, E_NOTA, E_HA, E_NEVE, E_FUMACA, E_VAPOR, E_N };   // ritmo de cada particula
enum TipoParticula : uint8_t { P_LIVRE, P_CONFETE, P_GOTA, P_TEXTO, P_NOTA, P_NEVE, P_FUMACA, P_VAPOR };
struct Particula { TipoParticula tipo = P_LIVRE; uint8_t w = 0, h = 0; uint16_t c = 0; float x = 0, y = 0, vx = 0, vy = 0, vida = 0, max = 1, seed = 0; const char *txt = nullptr; };
// Um quadro do mascote: o que cada animacao ajusta (o objeto s da previa).
struct Quadro {
  float dx = 0, dy = 0; int bodyDy = 0; int rowDx[4] = {0, 0, 0, 0};
  Olhar eye = O_NORMAL; float eyeDx = 0, eyeDy = 0, eyeH = 1; int mouth = 0;
  float armL = 0, armR = 0, legL = 0, legR = 0;
  bool piscar = false, alerta = false, pontos = false, check = false, xis = false, estrelas = false, barras = false, brilho = false, temMaos = false;
  int disco = -1;                        // pista de danca (-1 = sem)
  float maos[2][2] = {{0, 0}, {0, 0}};
  float curl = -1;                       // -1 = usa o enrolado atual do bigode
  int torce[2] = {0, 0};
  int bigode = -1;                       // -1 = o escolhido no Camarim
};
