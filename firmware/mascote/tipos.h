// Tipos usados em mascote.ino. Ficam num arquivo a parte porque a Arduino IDE
// cria os prototipos das funcoes no topo do .ino, antes de qualquer tipo declarado nele.
#pragma once
#include <Arduino.h>

struct Sessao {
  String id, title, repo, branch, status, ago, last, reply, askTool, askText;
};
enum Link { CONECTANDO, SEM_WIFI, SEM_PONTE, PONTE_OK };          // estado da conexao com a ponte
enum Estado { REPOUSO, OUVINDO, PENSANDO, RESPONDENDO, TRABALHANDO, ALERTA };
enum Tela { T_MASCOTE, T_LISTA, T_SESSAO };
