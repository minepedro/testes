# Firmware: ponte por HTTPS

O `firmware/mascote` fala com a ponte por `http://` (rede local, como antes) ou por
`https://` com o certificado conferido. Este documento cobre só o transporte.

## Como fica a conexão em `https://`

- **Cadeia:** só aceita certificados que levam às raízes da Let's Encrypt, ISRG Root X1 e
  X2 (`firmware/mascote/raizes_letsencrypt.h`). As impressões SHA-256 estão no topo do
  arquivo e foram conferidas contra letsencrypt.org e o repositório de CAs do sistema.
- **Validade:** antes do TLS o ESP32 pega a hora por SNTP (`pool.ntp.org`, `time.google.com`,
  `time.cloudflare.com`). Isso não trava nada: enquanto a hora não chega, a tela mostra
  "sem ponte" e a rede tenta de novo a cada 3 s.
- **Nome:** conectando direto no IP, o core passa o IP para `mbedtls_ssl_set_hostname`.
  O mbedTLS 3.6 só aceita o certificado se o IP aparecer no SAN como **iPAddress**.
  Um certificado só com nome DNS é recusado.
- **Nunca** usa `setInsecure()` nem fixa o certificado pela impressão digital.
- **Falha fechada:** com `PONTE_HTTPS_OBRIGATORIO 1`, uma `PONTE_URL` em `http://` fica
  recusada e nada é enviado, nem mesmo o token.

## Evidência de que IP no SAN é conferido

Valores do core `esp32:esp32` 3.3.12, a versão instalada no teste:

- `libraries/NetworkClientSecure/src/ssl_client.cpp` chama
  `mbedtls_ssl_set_hostname(..., hostname != NULL ? hostname : ip.toString())`.
  `HTTPClient` conecta com `_client->connect(_host.c_str(), ...)`, então o host é o IP da URL.
- O ESP-IDF desse core traz mbedTLS **3.6.6**. A `libmbedx509.a` do ESP32-S3 exporta
  `mbedtls_x509_crt_parse_cn_inet_pton`.
- No mbedTLS 3.6 (`library/x509_crt.c`), `x509_crt_check_san_ip` compara o IP com as
  entradas SAN do tipo iPAddress. Essa função **não existe** no mbedTLS 3.4. Por isso, um
  core antigo (2.x, IDF 4.4) não confere IP no SAN e **não serve** para HTTPS por IP.
  Use **esp32 by Espressif 3.3.12**, a versão efetivamente compilada e inspecionada.
  Não assuma compatibilidade de qualquer versão 3.x: é necessário mbedTLS 3.6 ou posterior.
- Teste de comportamento, com o mesmo mbedTLS 3.6.6 compilado no PC:
  `testes_host/teste_san_ip.sh`. Ele aceita SAN `IP:179.198.122.200`, recusa outro IP e
  recusa certificado só com DNS.

## Gravar

1. Arduino IDE: em Placas, instale **esp32 by Espressif 3.3.12**.
   Instale também LovyanGFX e ArduinoJson.
2. Copie `config.exemplo.h` para `config.h` e preencha. Para HTTPS, use
   `PONTE_URL "https://179.198.122.200"` e `PONTE_HTTPS_OBRIGATORIO 1`.
   O certificado da ponte precisa ser Let's Encrypt **com o IP no SAN** (perfil
   `shortlived`, de cerca de 6 dias). A ponte precisa renovar sozinha.
3. Placa ESP32S3 Dev Module, PSRAM "OPI PSRAM". Grave.

O firmware já gravado continua na demo até você regravar. No novo código, omitir
`PONTE_HTTPS_OBRIGATORIO` equivale a `1`: um `config.h` antigo com HTTP é recusado.
Somente para demo, o opt-in explícito `PONTE_HTTPS_OBRIGATORIO 0` permite HTTP.
Nunca use esse opt-in com sessões reais.

Pela linha de comando (opcional, sem instalar nada no sistema):

    arduino-cli compile -b esp32:esp32:esp32s3:PSRAM=opi firmware/mascote

## Testes no computador

    cd firmware/mascote/testes_host
    g++ -std=c++17 -Wall -Werror -I.. teste_transporte.cpp -o /tmp/t && /tmp/t
    MBEDTLS=/caminho/mbedtls-3.6.6 ./teste_san_ip.sh   # mbedtls compilado com `make lib`

## Limites

- Nada foi testado na placa nem contra a ponte real. Ficaram verificadas a compilação, as
  regras e a conferência do SAN de IP no mbedTLS.
- A latência e a memória durante o handshake ainda precisam ser medidas na placa;
  cada busca pode abrir uma conexão TLS nova.
- SNTP não autentica a fonte de hora. Ele permite verificar a validade do certificado,
  mas não protege o relógio contra manipulação por um atacante da rede.
- Se a Let's Encrypt trocar de raiz (X1 vale até 2035, X2 até 2040), atualize
  `raizes_letsencrypt.h`.
