// Tipos usados em mascote.ino. Ficam num arquivo a parte porque a Arduino IDE
// cria os prototipos das funcoes no topo do .ino, antes de qualquer tipo declarado nele.
#pragma once
#include <Arduino.h>

struct Sessao {
  String id, title, repo, branch, status, ago, last, reply, askTool, askText;
};
enum Link { CONECTANDO, SEM_WIFI, SEM_PONTE, PONTE_OK };          // estado da conexao com a ponte
enum Estado { REPOUSO, OUVINDO, PENSANDO, RESPONDENDO, TRABALHANDO, ALERTA };
enum Tela { T_MASCOTE, T_LISTA, T_SESSAO, T_MENU };
enum FaseVoz { V_NADA, V_GRAVANDO, V_TRANSCREVENDO, V_CONFIRMAR, V_ENVIANDO };
enum Proposito { PR_NADA, PR_VOZ, PR_MSG, PR_REPOS, PR_BRANCHES, PR_CRIAR };   // para que serve o pedido de rede
enum Menu { M_FILTRO, M_REPOS, M_BRANCHES };
struct ItemMenu { String rotulo, sub, valor; };
struct Trabalho { uint32_t id = 0; bool post = false, binario = false; String caminho, corpo; const uint8_t *dados = nullptr; size_t n = 0; };
