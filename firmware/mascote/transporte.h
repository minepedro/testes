// Regras do transporte com a ponte, sem dependencia de Arduino para poderem ser
// testadas no computador (firmware/mascote/testes_host/).
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum EsquemaPonte { ESQ_INVALIDO, ESQ_HTTP, ESQ_HTTPS };

// Le o esquema do inicio da URL (minusculas, como no config.exemplo.h).
inline EsquemaPonte esquemaPonte(const char *url) {
  if (!url) return ESQ_INVALIDO;
  if (strncmp(url, "https://", 8) == 0 && url[8] != '\0') return ESQ_HTTPS;
  if (strncmp(url, "http://", 7) == 0 && url[7] != '\0') return ESQ_HTTP;
  return ESQ_INVALIDO;
}

// Em modo seguro (PONTE_HTTPS_OBRIGATORIO = 1) so https:// e aceito: falha fechado.
// Em modo demo/rede local (0) aceita http:// e https://.
inline bool urlPermitida(const char *url, bool httpsObrigatorio) {
  EsquemaPonte e = esquemaPonte(url);
  if (e == ESQ_HTTPS) return true;
  if (e == ESQ_HTTP) return !httpsObrigatorio;
  return false;
}

// Relogio valido para checar validade do certificado: depois de 2024-01-01 (epoch 1704067200).
// Sem SNTP o ESP32 comeca em 1970 e todo certificado pareceria "ainda nao valido".
constexpr int64_t RELOGIO_MINIMO = 1704067200LL;
inline bool relogioValido(int64_t epoch) { return epoch >= RELOGIO_MINIMO; }

// Pode tentar TLS agora? Exige relogio sincronizado. Nao bloqueia: quem chama tenta de novo.
inline bool podeAbrirConexao(EsquemaPonte e, int64_t epoch) {
  if (e == ESQ_HTTP) return true;
  if (e == ESQ_HTTPS) return relogioValido(epoch);
  return false;
}
