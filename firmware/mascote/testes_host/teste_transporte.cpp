// Teste no computador das regras de transporte (nao precisa da placa):
//   g++ -std=c++17 -Wall -Werror -I.. teste_transporte.cpp -o /tmp/teste_transporte && /tmp/teste_transporte
#include "transporte.h"
#include <cstdio>

static int falhas = 0;
#define CHECA(x) do { if (!(x)) { printf("FALHOU linha %d: %s\n", __LINE__, #x); falhas++; } } while (0)

int main() {
  CHECA(esquemaPonte("https://179.198.122.200:8787") == ESQ_HTTPS);
  CHECA(esquemaPonte("http://192.168.0.10:8787") == ESQ_HTTP);
  CHECA(esquemaPonte("ftp://x") == ESQ_INVALIDO);
  CHECA(esquemaPonte("https://") == ESQ_INVALIDO);
  CHECA(esquemaPonte("") == ESQ_INVALIDO);
  CHECA(esquemaPonte(nullptr) == ESQ_INVALIDO);
  CHECA(esquemaPonte("HTTP://x") == ESQ_INVALIDO);

  // modo seguro: falha fechado para http
  CHECA(!urlPermitida("http://179.198.122.200:8787", true));
  CHECA(urlPermitida("https://179.198.122.200:8787", true));
  CHECA(!urlPermitida("httpx://a", true));
  // modo local (demo atual)
  CHECA(urlPermitida("http://192.168.0.10:8787", false));
  CHECA(urlPermitida("https://179.198.122.200:8787", false));

  // TLS so com relogio sincronizado
  CHECA(!podeAbrirConexao(ESQ_HTTPS, 0));
  CHECA(!podeAbrirConexao(ESQ_HTTPS, RELOGIO_MINIMO - 1));
  CHECA(podeAbrirConexao(ESQ_HTTPS, RELOGIO_MINIMO));
  CHECA(podeAbrirConexao(ESQ_HTTP, 0));
  CHECA(!podeAbrirConexao(ESQ_INVALIDO, 2000000000LL));

  if (falhas) { printf("%d falha(s)\n", falhas); return 1; }
  puts("ok: todas as regras de transporte");
  return 0;
}
