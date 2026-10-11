// Copie este arquivo para config.h (na mesma pasta) e preencha.
// O config.h fica fora do git, porque tem a senha do Wi-Fi e o token da ponte.

#define WIFI_NOME   "nome-da-rede-2.4GHz"     // o ESP32 so conecta em 2,4 GHz
#define WIFI_SENHA  "senha-do-wifi"

// Endereco da ponte (software/bridge/ponte.py), com https:// e a porta.
// O certificado precisa ser da Let's Encrypt e ter este IP no SAN (perfil shortlived para IP).
// O firmware confere cadeia, validade (hora via SNTP) e o IP; nunca aceita certificado sem conferir.
#define PONTE_URL   "https://179.198.122.200"
// 1 = so aceita https:// (uma URL http:// fica recusada e o mascote mostra "sem ponte").
// Para usar a ponte na rede local sem TLS, troque a URL para http://... e coloque 0.
#define PONTE_HTTPS_OBRIGATORIO 1
// O mesmo valor de PONTE_TOKEN usado para rodar a ponte
#define PONTE_TOKEN "troque-por-uma-senha-longa"
