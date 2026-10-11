/* Confere, com o mesmo mbedTLS do core ESP32 (3.6.x), como o nome e conferido quando a
 * ponte e acessada por IP literal. O ssl_client.cpp do core chama mbedtls_ssl_set_hostname
 * com o host da URL; na verificacao isso vira o "cn" de mbedtls_x509_crt_verify.
 * Uso: verifica_san_ip ca.pem folha.pem nome  -> imprime flags e sai 0 se aceito. */
#include <stdio.h>
#include "mbedtls/x509_crt.h"

int main(int argc, char **argv) {
  if (argc != 4) return 2;
  mbedtls_x509_crt ca, folha;
  mbedtls_x509_crt_init(&ca); mbedtls_x509_crt_init(&folha);
  if (mbedtls_x509_crt_parse_file(&ca, argv[1]) || mbedtls_x509_crt_parse_file(&folha, argv[2])) return 3;
  uint32_t flags = 0;
  int r = mbedtls_x509_crt_verify(&folha, &ca, NULL, argv[3], &flags, NULL, NULL);
  printf("nome=%s ret=%d flags=0x%x%s\n", argv[3], r, flags,
         (flags & MBEDTLS_X509_BADCERT_CN_MISMATCH) ? " (CN_MISMATCH)" : "");
  return r == 0 ? 0 : 1;
}
