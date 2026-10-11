// Copie este arquivo para config.h (na mesma pasta) e preencha.
// O config.h fica fora do git, porque tem a senha do Wi-Fi e o token da ponte.

#define WIFI_NOME   "nome-da-rede-2.4GHz"     // o ESP32 so conecta em 2,4 GHz
#define WIFI_SENHA  "senha-do-wifi"

// Endereco da ponte (software/bridge/ponte.py), com http:// e a porta
#define PONTE_URL   "http://192.168.0.10:8787"
// O mesmo valor de PONTE_TOKEN usado para rodar a ponte
#define PONTE_TOKEN "troque-por-uma-senha-longa"
