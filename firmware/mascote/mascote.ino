// Mascote do Claude: o Clawd na tela, a lista de sessoes e os botoes Aprovar e Recusar.
// Conversa por Wi-Fi com a ponte (software/bridge/ponte.py), que entrega as sessoes.
//
// Telas:
//   - Mascote: o Clawd no meio. Faixa de cima: estado da ponte; toque nela para abrir a lista.
//     Segure abaixo dela e fale: ao soltar, a ponte transcreve (Whisper na VPS), o texto aparece
//     e "Nova sessao" cria uma sessao com essa tarefa (escolhendo repositorio e branch).
//   - Sessoes: uma por linha, quem precisa de voce primeiro. Arraste para rolar, toque para abrir.
//     "repo" filtra por repositorio; "+" cria sessao sem tarefa.
//   - Sessao: o mascote reage ao estado dela. Se pede permissao, aparecem Recusar e Aprovar.
//     Segure e fale: o texto vira mensagem para a sessao (Enviar ou Descartar).
//     A seta do canto de cima volta.
// Microfone INMP441 (I2S): SCK 15, WS 16, SD 17, L/R no GND.
//
// Antes de gravar: copie config.exemplo.h para config.h e preencha Wi-Fi e ponte.
// Transporte: PONTE_URL com https:// usa TLS validado (raizes Let's Encrypt, relogio por SNTP).
// Com PONTE_HTTPS_OBRIGATORIO 1, uma URL http:// e recusada (falha fechado). Ver docs/firmware-https.md.
// Bibliotecas: LovyanGFX e ArduinoJson (Gerenciador de Bibliotecas).
// Placa: ESP32S3 Dev Module, PSRAM "OPI PSRAM". Tela de teste ILI9488 + touch XPT2046.
// Para a tela capacitiva final (ST7796): troque Panel_ILI9488 por Panel_ST7796 e o touch
// pelo bloco Touch_FT5x06 de firmware/testes/etapa2_3_tela_touch.

#include <WiFi.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <time.h>
#include <ArduinoJson.h>
#include <ESP_I2S.h>
#include <vector>
#include <Preferences.h>
#include "config.h"
#include "tipos.h"
#include "transporte.h"
#include "raizes_letsencrypt.h"

// Seguro por padrao; HTTP exige opt-in explicito e so pode ser usado com a demo.
#ifndef PONTE_HTTPS_OBRIGATORIO
#define PONTE_HTTPS_OBRIGATORIO 1
#endif

#define LGFX_USE_V1
#include <LovyanGFX.hpp>

// ---- pinos (docs/montagem.md, variante ILI9488) ---------------------------------------
constexpr int PIN_SCK = 12, PIN_MOSI = 11, PIN_MISO = 13, PIN_DC = 14;
constexpr int PIN_CS = 10, PIN_RST = 6, PIN_BL = 7;
constexpr int PIN_T_CLK = 9, PIN_T_CS = 5, PIN_T_DIN = 8, PIN_T_DO = 4;

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ILI9488 _panel;
  lgfx::Bus_SPI _bus;
  lgfx::Light_PWM _light;
  lgfx::Touch_XPT2046 _touch;

public:
  LGFX() {
    {
      auto cfg = _bus.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 27000000;
      cfg.freq_read = 16000000;
      cfg.pin_sclk = PIN_SCK;
      cfg.pin_mosi = PIN_MOSI;
      cfg.pin_miso = PIN_MISO;
      cfg.pin_dc = PIN_DC;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }
    {
      auto cfg = _panel.config();
      cfg.pin_cs = PIN_CS;
      cfg.pin_rst = PIN_RST;
      cfg.pin_busy = -1;
      cfg.panel_width = 320;
      cfg.panel_height = 480;
      cfg.readable = false;
      cfg.invert = false;
      cfg.rgb_order = false;
      cfg.dlen_16bit = false;
      cfg.bus_shared = false;
      _panel.config(cfg);
    }
    {
      auto cfg = _light.config();
      cfg.pin_bl = PIN_BL;
      cfg.freq = 44100;
      cfg.pwm_channel = 7;
      _light.config(cfg);
      _panel.setLight(&_light);
    }
    {
      auto cfg = _touch.config();
      cfg.x_min = 300;
      cfg.x_max = 3900;
      cfg.y_min = 200;
      cfg.y_max = 3900;
      cfg.pin_int = -1;
      cfg.bus_shared = false;
      cfg.offset_rotation = 0;
      cfg.spi_host = SPI3_HOST;
      cfg.freq = 1000000;
      cfg.pin_sclk = PIN_T_CLK;
      cfg.pin_mosi = PIN_T_DIN;
      cfg.pin_miso = PIN_T_DO;
      cfg.pin_cs = PIN_T_CS;
      _touch.config(cfg);
      _panel.setTouch(&_touch);
    }
    setPanel(&_panel);
  }
};

LGFX tft;
LGFX_Sprite area(&tft);    // regiao do mascote
LGFX_Sprite rodape(&tft);  // barras, texto de baixo e botoes de aprovacao
LGFX_Sprite lista(&tft);   // linhas da lista de sessoes
LGFX_Sprite coluna(&tft);  // coluna da direita do Camarim (abas e lista)
Preferences prefs;         // escolha do Camarim (NVS, namespace "mascote")

// ---- geometria (igual ao prototipo web) ------------------------------------------------
constexpr int W = 480, H = 320, PW = 15, PH = 30;
constexpr int BODY_W = 18, BODY_H = 5;
constexpr int EYE_L = 5, EYE_R = 12, EYE_ROW = 1;
constexpr int BODY_X = (W - BODY_W * PW) / 2;  // 105
constexpr int BODY_Y = 68;
constexpr int TOP_BAR = 28, TOP_HIT = 40, FOOT_Y = H - 44;
constexpr int HDR = 36, HDR_S = 46, RH = 58;
constexpr int BTN_Y = 272, BTN_H = 40, BTN_W = (W - 32 - 12) / 2;
constexpr int AREA_X = 0, AREA_Y = TOP_BAR, AREA_W = W, AREA_H = 242 - TOP_BAR;  // cena inteira: do cabecalho ao rodape (chapeus e bandeira cabem)
constexpr int FOOT_TOP = AREA_Y + AREA_H, FOOT_H = H - FOOT_TOP;

const char *SPRITE[BODY_H] = {
  "...############...",
  "...############...",
  ".################.",
  "...############...",
  "....#.#....#.#....",
};

uint16_t C_BG, C_FLOOR, C_SHADOW, C_HI, C_MID, C_BODY, C_LO, C_DEEP, C_FG, C_DIM, C_OK, C_BAD,
         C_WARN, C_WARN_HI, C_WARN_BG, C_PANEL, C_LINE;

// ---- dados da ponte (escritos pela tarefa de rede, lidos pela tela) ----------------------

SemaphoreHandle_t trava;
std::vector<Sessao> redeSessoes;  // protegido por trava
String redeHora;
Link redeLink = CONECTANDO;
uint32_t redeVersao = 0;
String acaoId, acaoTipo;          // acao pendente (aprovar/recusar), enviada pela tarefa de rede
int acaoCod = 0;                  // resposta de /api/acao (0 = nada novo); 1 no bit 16 = aprovar
Trabalho trabPedido;              // pedido avulso da tela (voz, mensagem, repos, criar); id 0 = nada
uint32_t trabFeitoId = 0;         // resultado do ultimo pedido avulso
int trabCod = 0;
String trabResp;

// copia local usada pela tela
std::vector<Sessao> sessoes;
String hora;
Link conexao = CONECTANDO;
uint32_t versaoVista = 0;

int ordem(const String &st) { return st == "waiting" ? 0 : st == "working" ? 1 : st == "idle" ? 2 : 3; }

// ---- transporte (http:// local ou https:// validado) -------------------------------------
const EsquemaPonte esquema = esquemaPonte(PONTE_URL);
const bool urlOk = urlPermitida(PONTE_URL, PONTE_HTTPS_OBRIGATORIO);

// Prepara a conexao. Devolve false (sem abrir nada) quando a URL e proibida ou, em https,
// quando o relogio ainda nao veio do SNTP: sem hora certa nao da para conferir a validade
// do certificado, e o certificado nunca e aceito sem conferir (nada de setInsecure).
bool abrirPonte(HTTPClient &http, NetworkClientSecure &cliente, const char *caminho) {
  if (!urlOk) return false;
  if (!podeAbrirConexao(esquema, (int64_t)time(nullptr))) {
    static uint32_t avisado = 0;
    if (millis() - avisado > 10000) { avisado = millis(); Serial.println("https: aguardando hora do SNTP"); }
    return false;
  }
  String url = String(PONTE_URL) + caminho;
  if (esquema == ESQ_HTTPS) return http.begin(cliente, url);   // valida cadeia, validade e nome/IP
  return http.begin(url);                                    // http:// como antes (rede local)
}

void tarefaRede(void *) {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  NetworkClientSecure cliente;
  cliente.setCACert(RAIZES_LETS_ENCRYPT);
  cliente.setHandshakeTimeout(10);   // segundos
  bool sntpIniciado = false;
  if (!urlOk) Serial.println("PONTE_URL recusada: com PONTE_HTTPS_OBRIGATORIO 1 ela precisa comecar com https://");
  uint32_t proximaBusca = 0;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      xSemaphoreTake(trava, portMAX_DELAY);
      if (redeLink != CONECTANDO && redeLink != SEM_WIFI) { redeLink = SEM_WIFI; redeVersao++; }
      else if (redeLink == CONECTANDO && millis() > 15000) { redeLink = SEM_WIFI; redeVersao++; }
      xSemaphoreGive(trava);
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }
    // SNTP em segundo plano: nao bloqueia; abrirPonte espera a hora chegar.
    if (esquema == ESQ_HTTPS && !sntpIniciado) {
      configTime(0, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");
      sntpIniciado = true;
    }
    // acao pendente primeiro
    String id, tipo;
    xSemaphoreTake(trava, portMAX_DELAY);
    id = acaoId; tipo = acaoTipo; acaoId = ""; acaoTipo = "";
    xSemaphoreGive(trava);
    if (id.length()) {
      HTTPClient http;
      http.setTimeout(5000);
      if (!abrirPonte(http, cliente, "/api/acao")) {
        Serial.println("acao descartada: ponte indisponivel");
        xSemaphoreTake(trava, portMAX_DELAY); acaoCod = -1; xSemaphoreGive(trava);
      }
      else {
      http.addHeader("X-Token", PONTE_TOKEN);
      http.addHeader("Content-Type", "application/json");
      int cod = http.POST("{\"id\":\"" + id + "\",\"acao\":\"" + tipo + "\"}");
      Serial.printf("acao %s em %s: HTTP %d\n", tipo.c_str(), id.c_str(), cod);
      xSemaphoreTake(trava, portMAX_DELAY);
      acaoCod = (cod == 0 ? -2 : cod) | (tipo == "aprovar" ? 0x10000 : 0);
      xSemaphoreGive(trava);
      http.end();
      }
      proximaBusca = 0;
    }
    // pedido avulso da tela
    Trabalho tb;
    xSemaphoreTake(trava, portMAX_DELAY);
    tb = trabPedido; trabPedido = Trabalho();
    xSemaphoreGive(trava);
    if (tb.id) {
      HTTPClient http;
      http.setTimeout(tb.binario ? 90000 : 20000);   // a 1a transcricao carrega o modelo na VPS
      int cod = -1;
      String resp;
      if (abrirPonte(http, cliente, tb.caminho.c_str())) {
        http.addHeader("X-Token", PONTE_TOKEN);
        if (tb.binario) { http.addHeader("Content-Type", "application/octet-stream"); cod = http.POST((uint8_t *)tb.dados, tb.n); }
        else if (tb.post) { http.addHeader("Content-Type", "application/json"); cod = http.POST(tb.corpo); }
        else cod = http.GET();
        if (cod > 0) resp = http.getString();
      }
      http.end();
      Serial.printf("%s %s: HTTP %d\n", tb.post || tb.binario ? "POST" : "GET", tb.caminho.c_str(), cod);
      xSemaphoreTake(trava, portMAX_DELAY);
      trabFeitoId = tb.id; trabCod = cod; trabResp = resp;
      xSemaphoreGive(trava);
      proximaBusca = 0;
    }
    if (millis() >= proximaBusca) {
      proximaBusca = millis() + 3000;
      HTTPClient http;
      http.setTimeout(5000);
      int cod = -1;
      if (abrirPonte(http, cliente, "/api/estado")) {
        http.addHeader("X-Token", PONTE_TOKEN);
        cod = http.GET();
      }
      Link novo = SEM_PONTE;
      std::vector<Sessao> lidas;
      String h;
      if (cod == 200) {
        JsonDocument doc;
        DeserializationError erro = deserializeJson(doc, http.getString());
        if (!erro) {
          novo = PONTE_OK;
          h = doc["hora"] | "";
          for (JsonObject o : doc["sessoes"].as<JsonArray>()) {
            Sessao s;
            s.id = o["id"] | ""; s.title = o["title"] | ""; s.repo = o["repo"] | ""; s.branch = o["branch"] | "";
            s.status = o["status"] | "idle"; s.ago = o["ago"] | ""; s.last = o["last"] | ""; s.reply = o["reply"] | "";
            if (!o["ask"].isNull()) { s.askTool = o["ask"]["tool"] | ""; s.askText = o["ask"]["text"] | ""; }
            lidas.push_back(s);
          }
          std::stable_sort(lidas.begin(), lidas.end(), [](const Sessao &a, const Sessao &b) { return ordem(a.status) < ordem(b.status); });
        } else Serial.printf("json invalido: %s\n", erro.c_str());
      } else if (cod != -1 || esquema == ESQ_HTTP) Serial.printf("ponte: HTTP %d (%s)\n", cod, cod == 401 ? "token errado" : http.errorToString(cod).c_str());
      http.end();
      xSemaphoreTake(trava, portMAX_DELAY);
      bool mudou = novo != redeLink || lidas.size() != redeSessoes.size() || h != redeHora;
      for (size_t i = 0; !mudou && i < lidas.size(); i++) {
        const Sessao &a = lidas[i], &b = redeSessoes[i];
        mudou = a.id != b.id || a.status != b.status || a.ago != b.ago || a.last != b.last || a.askText != b.askText || a.title != b.title || a.reply != b.reply || a.repo != b.repo;
      }
      if (novo == PONTE_OK) { redeSessoes = lidas; redeHora = h; }
      redeLink = novo;
      if (mudou) redeVersao++;
      xSemaphoreGive(trava);
    }
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// ---- microfone (INMP441, I2S) --------------------------------------------------------------
constexpr int PIN_MIC_SCK = 15, PIN_MIC_WS = 16, PIN_MIC_SD = 17;
// O amplificador (MAX98357A, opcional) divide o SCK e o WS com o microfone. Com SOM 1 os dois usam o mesmo
// I2S em full duplex (o som sai pelo 18) e, sem som tocando, o DMA manda zeros. Com SOM 0 o DIN fica em 0,
// porque solto ele vira chiado no alto-falante enquanto os relógios do microfone rodam.
constexpr int PIN_AMP_DIN = 18;
#ifndef SOM
#define SOM 1             // 0 = sem som (config.h pode mudar)
#endif
#ifndef SOM_VOLUME
#define SOM_VOLUME 0.4f   // 0 a 1 (config.h pode mudar)
#endif
constexpr int TAXA = 16000, MAX_SEG = 20, MAX_AMOSTRAS = TAXA * MAX_SEG;
I2SClass mic;
int16_t *audio = nullptr;          // PSRAM: ate 20 s de PCM 16 bits (640 KB)
volatile bool gravando = false;
volatile size_t nAmostras = 0;
volatile float nivelMic = 0;       // volume atual (0..1), para as barras
bool micOk = false;
volatile bool somTocando = false;  // enquanto um som toca, a gravacao ignora o microfone (para nao gravar o bipe)

// Le o microfone sem parar (o DMA nao pode encher) e guarda so enquanto "gravando".
void tarefaAudio(void *) {
  static int32_t bloco[256];
  float dc = 0;
  for (;;) {
    size_t n = mic.readBytes((char *)bloco, sizeof(bloco)) / sizeof(int32_t);
    if (!n) { vTaskDelay(1); continue; }
    float soma = 0;
    for (size_t i = 0; i < n; i++) {
      float x = (float)(bloco[i] >> 14);   // 24 bits do INMP441 -> 16 bits, com ganho 4x
      dc += (x - dc) * 0.001f;             // tira o nivel continuo
      float y = x - dc;
      soma += fabsf(y);
      if (gravando && !somTocando && nAmostras < (size_t)MAX_AMOSTRAS) audio[nAmostras++] = (int16_t)constrain((int)y, -32768, 32767);
    }
    nivelMic = soma / n / 32768.0f;
  }
}

// ---- som (amplificador MAX98357A no DIN 18) ------------------------------------------------------
// Cada som e uma sequencia curta de notas com ataque rapido e decaimento ("plim"). Uma tarefa propria
// gera as amostras e escreve no I2S; tocarSom so enfileira, entao nunca trava a tela.
struct Nota { uint16_t hz, ms; };
const Nota N_CLIQUE[] = {{1800, 14}}, N_GRAVAR[] = {{880, 70}}, N_ENVIAR[] = {{1320, 60}, {990, 90}},
           N_PLIM[] = {{988, 90}, {1319, 260}}, N_FESTA[] = {{1047, 80}, {1319, 80}, {1568, 80}, {2093, 300}},
           N_AVISO[] = {{1319, 170}, {988, 240}}, N_APROVADO[] = {{880, 70}, {1320, 170}}, N_RECUSADO[] = {{660, 90}, {440, 190}},
           N_ERRO[] = {{330, 160}, {247, 300}}, N_COCEGAS[] = {{1100, 45}, {1300, 45}, {1100, 45}, {1500, 80}};
struct SomInfo { const Nota *notas; uint8_t qtd; float vol; };
const SomInfo SONS[] = {{N_CLIQUE, 1, .4f}, {N_GRAVAR, 1, 1}, {N_ENVIAR, 2, 1}, {N_PLIM, 2, 1}, {N_FESTA, 4, 1}, {N_AVISO, 2, 1},
                        {N_APROVADO, 2, 1}, {N_RECUSADO, 2, 1}, {N_ERRO, 2, 1}, {N_COCEGAS, 4, .8f}};
QueueHandle_t filaSom = nullptr;   // so existe com SOM 1 e o I2S funcionando

void tocarSom(Som s) {
  if (!filaSom || gravando) return;   // gravando: o som entraria na gravacao
  if (xQueueSend(filaSom, &s, 0) == pdTRUE) somTocando = true;
}

void tarefaSom(void *) {
  static int32_t bloco[256];
  Som s;
  for (;;) {
    if (xQueueReceive(filaSom, &s, portMAX_DELAY) != pdTRUE) continue;
    somTocando = true;
    const SomInfo &info = SONS[s];
    const float amp = constrain((float)SOM_VOLUME, 0.0f, 1.0f) * info.vol * 2.1e9f;   // amostras de 32 bits
    float fase = 0;
    for (uint8_t k = 0; k < info.qtd; k++) {
      const int total = TAXA * info.notas[k].ms / 1000, ataque = TAXA / 250, soltura = TAXA / 125;   // 4 ms e 8 ms
      const float passoF = 2 * PI * info.notas[k].hz / TAXA, tau = total * 0.45f;
      for (int i = 0; i < total;) {
        int m = min(256, total - i);
        for (int j = 0; j < m; j++, i++) {
          float env = expf(-i / tau);
          if (i < ataque) env *= (float)i / ataque;
          if (total - i < soltura) env *= (float)(total - i) / soltura;
          bloco[j] = (int32_t)((sinf(fase) + .25f * sinf(2 * fase)) * .8f * env * amp);   // um pouco de brilho, estilo 8 bits
          fase += passoF;
          if (fase > 2 * PI) fase -= 2 * PI;
        }
        mic.write(bloco, m * sizeof(int32_t));
      }
    }
    memset(bloco, 0, sizeof(bloco));
    for (int z = 0; z < 6; z++) mic.write(bloco, sizeof(bloco));   // silencio ate o DMA esvaziar (~100 ms)
    if (!uxQueueMessagesWaiting(filaSom)) somTocando = false;
  }
}

// ---- estado do mascote -----------------------------------------------------------------
const char *NOME[] = {"repouso", "ouvindo", "pensando", "respondendo", "trabalhando", "alerta"};
Tela tela = T_MASCOTE;
String atualId;          // sessao aberta
String respostaCasa;     // ultima resposta fora de sessao
constexpr float TYPE_CPS = 40;

struct {
  Estado estado = REPOUSO;
  float t = 0;
  float eyeH = 1, eyeDy = 0;
  int eyeDx = 0, mouth = 0;
  float blinkAt = 3, blinkT = -1;
  float glanceAt = 5, glanceUntil = 0; int glanceDx = 0;
  float mouthNext = 0;
  int typed = 0;
  String texto;
  float bars[16] = {0}, barsAlvo[16] = {0};
} m;

float rnd() { return (float)esp_random() / 4294967296.0f; }

Sessao *sessaoAtual() {
  for (auto &s : sessoes) if (s.id == atualId) return &s;
  return nullptr;
}
int aguardando() { int n = 0; for (auto &s : sessoes) n += s.status == "waiting"; return n; }

Estado estadoDeRepouso() {
  if (tela == T_SESSAO) {
    Sessao *s = sessaoAtual();
    if (s && s->status == "waiting") return ALERTA;
    if (s && s->status == "working") return TRABALHANDO;
    return REPOUSO;
  }
  return aguardando() ? ALERTA : REPOUSO;
}

String resumoCasa() {
  if (conexao != PONTE_OK) return conexao == SEM_WIFI ? "Estou sem Wi-Fi. Confira o nome e a senha no config.h." : "Nao consigo falar com a ponte. Ela esta rodando?";
  String esp, trab;
  int ne = 0, nt = 0;
  for (auto &s : sessoes) {
    if (s.status == "waiting") { esp += (ne ? "; " : "") + s.title + " quer rodar " + s.askText; ne++; }
    if (s.status == "working") { trab += (nt ? ", " : "") + s.title; nt++; }
  }
  String r;
  if (ne) r += String(ne) + (ne > 1 ? " sessoes esperam" : " sessao espera") + " sua aprovacao: " + esp + ". ";
  if (nt) r += String(nt) + (nt > 1 ? " estao trabalhando: " : " esta trabalhando: ") + trab + ".";
  return r.length() ? r : "Nenhuma sessao precisa de voce agora.";
}

struct {
  FaseVoz fase = V_NADA;
  String texto;                    // o que a ponte entendeu
  String aviso;                    // mensagem curta no rodape (4 s)
  uint16_t avisoCor = 0;
  uint32_t avisoAte = 0;
} voz;
Proposito trabProposito = PR_NADA;
uint32_t trabId = 0, trabSeq = 0;
uint32_t assinaturaMascote = 0, assinaturaRodape = 0;

void avisar(const String &txt, uint16_t cor) {
  voz.aviso = txt; voz.avisoCor = cor; voz.avisoAte = millis() + 4000;
  assinaturaRodape = 0xFFFFFFFF;
  Serial.printf("aviso: %s\n", txt.c_str());
}

bool pedirRede(Proposito p, bool post, const String &caminho, const String &corpo = "", const uint8_t *dados = nullptr, size_t n = 0) {
  if (trabProposito != PR_NADA) return false;   // um por vez
  Trabalho t;
  t.id = ++trabSeq; t.post = post; t.binario = dados != nullptr; t.caminho = caminho; t.corpo = corpo; t.dados = dados; t.n = n;
  xSemaphoreTake(trava, portMAX_DELAY);
  trabPedido = t;
  xSemaphoreGive(trava);
  trabProposito = p; trabId = t.id;
  return true;
}

// menu generico (filtro, repositorios, branches)
std::vector<ItemMenu> menuItens;
Menu menuTipo = M_FILTRO;
String menuTitulo, menuCarregando;  // menuCarregando: texto enquanto espera a ponte
int menuRolagem = 0;
String filtro;                      // "" = todas; "-" = sem repositorio; senao o repositorio
String novaTexto, novaRepo;         // sessao nova em montagem
Tela telaAntesDoMenu = T_MASCOTE;
bool vinculando = false;            // menus de repo/branch servem para vincular repo a sessao atual
String vincularId;
// resposta do Claude: ultimo reply mostrado por sessao (hash) e espera depois de enviar mensagem
std::vector<std::pair<String, uint32_t>> replyMostrado;
String esperandoRespId;
uint32_t hashTxt(const String &t) { uint32_t h = 2166136261u; for (size_t i = 0; i < t.length(); i++) h = (h ^ (uint8_t)t[i]) * 16777619u; return h; }
uint32_t &replyVisto(const String &id) {
  for (auto &p : replyMostrado) if (p.first == id) return p.second;
  if (replyMostrado.size() > 40) replyMostrado.erase(replyMostrado.begin());
  replyMostrado.push_back({id, 0});
  return replyMostrado.back().second;
}
bool semRepoVps(Sessao *s) { return s && !s->repo.length() && !s->id.startsWith("session_"); }
constexpr int VINC_X = 300, VINC_W = 96;   // botao 'vincular repo' no cabecalho da sessao

void entrar(Estado e) {
  m.estado = e; m.t = 0;
  m.eyeH = 1; m.eyeDy = 0; m.eyeDx = 0; m.mouth = 0; m.typed = 0;
  m.blinkT = -1; m.blinkAt = 3 + rnd() * 3; m.glanceAt = 4 + rnd() * 5; m.glanceUntil = 0;
  if (e == OUVINDO) { m.eyeH = 1.5f; m.eyeDy = -0.5f; }
  if (e == PENSANDO || e == TRABALHANDO) m.eyeDx = 1;
  if (e == RESPONDENDO) {
    Sessao *s = sessaoAtual();
    m.texto = tela == T_SESSAO && s ? (s->reply.length() ? s->reply : s->last) : resumoCasa();
    if (tela != T_SESSAO) respostaCasa = m.texto;
  }
  if (e == ALERTA) { m.eyeH = 1.5f; m.eyeDy = -0.5f; m.mouth = 1; }
  Serial.printf("estado: %s\n", NOME[e]);
}

void atualizar(float dt) {
  m.t += dt;
  float t = m.t;
  if (m.estado != PENSANDO && m.estado != ALERTA) {
    if (m.blinkT < 0 && t >= m.blinkAt) m.blinkT = 0;
    if (m.blinkT >= 0) { m.blinkT += dt; if (m.blinkT > 0.16f) { m.blinkT = -1; m.blinkAt = t + 3 + rnd() * 3; } }
  } else m.blinkT = -1;
  if (m.estado == REPOUSO) {
    if (t >= m.glanceAt) { m.glanceDx = rnd() < .5f ? -1 : 1; m.glanceUntil = t + .9f + rnd() * .8f; m.glanceAt = t + 4 + rnd() * 5; }
    m.eyeDx = t < m.glanceUntil ? m.glanceDx : 0;
  }
  if (m.estado == OUVINDO) {
    float env = min(1.0f, nivelMic * 14);   // volume real do microfone
    for (int i = 0; i < 16; i++) {
      if (rnd() < .3f) m.barsAlvo[i] = env * (.3f + rnd() * .7f);
      m.bars[i] += (m.barsAlvo[i] - m.bars[i]) * min(1.0f, dt * 14);
    }
  } else for (int i = 0; i < 16; i++) m.bars[i] *= .8f;
  if (m.estado == RESPONDENDO) {
    int len = m.texto.length();
    m.typed = (int)(t * TYPE_CPS);
    if (m.typed < len) {
      if (t >= m.mouthNext) { const int seq[] = {0, 1, 2, 1}; m.mouth = seq[esp_random() % 4]; m.mouthNext = t + .07f + rnd() * .08f; }
    } else {
      m.mouth = 0;
      if (t > len / TYPE_CPS + 1.5f) entrar(estadoDeRepouso());
    }
  }
}

// ---- desenho: utilidades -----------------------------------------------------------------
String cortar(LovyanGFX &g, const String &s, int largura) {
  if (g.textWidth(s.c_str()) <= largura) return s;
  String r = s;
  while (r.length() && g.textWidth((r + "...").c_str()) > largura) r.remove(r.length() - 1);
  return r + "...";
}

int quebrar(const String &txt, String linhas[], int maxLinhas, int largura) {
  String resto = txt, atual;
  int qtd = 0;
  while (resto.length() && qtd < maxLinhas) {
    int sp = resto.indexOf(' ');
    String palavra = sp < 0 ? resto : resto.substring(0, sp + 1);
    resto = sp < 0 ? "" : resto.substring(sp + 1);
    if (rodape.textWidth((atual + palavra).c_str()) > largura && atual.length()) { linhas[qtd++] = atual; atual = ""; }
    atual += palavra;
  }
  if (atual.length() && qtd < maxLinhas) linhas[qtd++] = atual;
  return qtd;
}

void seta(LovyanGFX &g, int x, int y, uint16_t c, char dir) {  // setas em pixels 3x3
  const int R[5][2] = {{0, -6}, {3, -3}, {6, 0}, {3, 3}, {0, 6}}, L[5][2] = {{6, -6}, {3, -3}, {0, 0}, {3, 3}, {6, 6}};
  for (int i = 0; i < 5; i++) { const int *p = dir == 'r' ? R[i] : L[i]; g.fillRect(x + p[0], y + p[1], 3, 3, c); }
}

uint16_t corStatus(const String &st) { return st == "waiting" ? C_WARN : st == "working" ? C_BODY : st == "done" ? C_OK : C_DIM; }
const char *rotuloStatus(const String &st) { return st == "waiting" ? "aguardando" : st == "working" ? "trabalhando" : st == "done" ? "concluida" : "parada"; }

void glifo(LovyanGFX &g, const String &st, int x, int y) {
  uint16_t c = corStatus(st);
  if (st == "idle") { g.fillRect(x, y, 16, 3, c); g.fillRect(x, y + 13, 16, 3, c); g.fillRect(x, y, 3, 16, c); g.fillRect(x + 13, y, 3, 16, c); return; }
  g.fillRect(x, y, 16, 16, c);
  if (st == "waiting") { g.fillRect(x + 6, y + 3, 4, 7, C_BG); g.fillRect(x + 6, y + 11, 4, 3, C_BG); }
  if (st == "done") { const int p[5][2] = {{3, 8}, {5, 10}, {7, 8}, {9, 6}, {11, 4}}; for (auto &q : p) g.fillRect(x + q[0], y + q[1], 3, 3, C_BG); }
}

// ---- desenho: mascote ---------------------------------------------------------------------
void px(int x, int y, int w, int h, uint16_t c) { area.fillRect(x - AREA_X, y - AREA_Y, w, h, c); }
void textoCena(int x, int y, const char *t, uint16_t c) {   // "z" e "ha" das particulas
  area.setFont(&fonts::Font4);
  area.setTextDatum(middle_center);
  area.setTextColor(c);
  area.drawString(t, x - AREA_X, y - AREA_Y);
}

// ---- Camarim: acessorios, fundos, animacoes e particulas ----------------------------------------
// Porte 1 para 1 de docs/camarim/index.html. As coordenadas abaixo sao as da previa (corpo em
// BX=105, BY=96); r() converte para a tela (y - 96 + BODY_Y) e soma o deslocamento da cena
// (cenaDy abaixa o corpo quando ha chapeu; cenaDx empurra a cena para a esquerda no Camarim).
// rt() desenha em coordenadas da tela (ceu, estrelas, nuvens, lua, check e X), como a previa
// faz logo abaixo do cabecalho. O bloco entre os marcadores HOST e compilado tambem pelo teste
// de host (testes_host/render_camarim.cpp), que gera as imagens de conferencia.
// >>> HOST
constexpr uint16_t K(uint32_t h) { return (uint16_t)(((h >> 8) & 0xF800) | ((h >> 5) & 0x07E0) | ((h >> 3) & 0x001F)); }
constexpr int PBX = 105, PBY = 96;                  // corpo na previa
constexpr uint16_t FB_BG = K(0x141210), FB_FLOOR = K(0x1b1613), FB_SHADOW = K(0x0b0908), FB_FG = K(0xede6dc), FB_DIM = K(0x8a8178),
                   FB_OK = K(0x6fbf73), FB_BAD = K(0xe0675a), FB_WARN = K(0xe6b450), FB_WARN_HI = K(0xf6d27e);
const uint16_t PALETAS[7][5] = {
  {K(0xf0a07c), K(0xe5896a), K(0xd97757), K(0xbf6446), K(0x8f4731)},   // laranja
  {K(0x9cc4f0), K(0x7fb0e8), K(0x5f97d9), K(0x467bbf), K(0x2f5490)},   // azul
  {K(0xa8dc8c), K(0x8fcf72), K(0x74bd57), K(0x5aa040), K(0x3b7029)},   // verde
  {K(0xc9a6f0), K(0xb48de6), K(0x9c72d9), K(0x7f56bf), K(0x573690)},   // roxo
  {K(0xf6d27e), K(0xecc061), K(0xe0aa45), K(0xc18c2c), K(0x8a6219)},   // dourado
  {K(0xf5a9c8), K(0xec8db4), K(0xe0719f), K(0xc4567f), K(0x8f3757)},   // rosa
  {K(0xc8c4bf), K(0xb0aba5), K(0x96918b), K(0x7a756f), K(0x524e49)},   // cinza
};
const char *const NOME_CAMADA[N_CAMADAS] = {"Cabeca", "Olhos", "Bigode", "Boca", "Peito", "Mao", "Cor", "Fundo"};
const char *const CHAVE_CAMADA[N_CAMADAS] = {"cabeca", "olhos", "bigode", "boca", "peito", "mao", "cor", "fundo"};   // chaves da NVS
const char *const IT_CAB[] = {"Nada", "Cartola", "Bone", "Cowboy", "Coroa", "Capacete", "Fone", "Gorro", "Festa"};
const char *const IT_OLH[] = {"Nada", "Oculos", "Escuros", "Monoculo", "Tapa-olho"};
const char *const IT_BIG[] = {"Nada", "Classico", "Guidao"};
const char *const IT_BOC[] = {"Nada", "Cigarro", "Charuto", "Cachimbo"};
const char *const IT_PEI[] = {"Nada", "Borboleta", "Gravata", "Cachecol"};
const char *const IT_MAO[] = {"Nada", "Caneca", "Chave", "Bandeira"};
const char *const IT_COR[] = {"Laranja", "Azul", "Verde", "Roxo", "Dourado", "Rosa", "Cinza"};
const char *const IT_FUN[] = {"Liso", "Estrelas", "Por do sol", "Grama", "Neve"};
const char *const *const ITENS[N_CAMADAS] = {IT_CAB, IT_OLH, IT_BIG, IT_BOC, IT_PEI, IT_MAO, IT_COR, IT_FUN};
const uint8_t N_ITENS[N_CAMADAS] = {9, 5, 3, 4, 4, 4, 7, 5};
const AnimInfo ANIMS[N_ANIMS] = {
  {"", 0}, {"Comemorar", 3}, {"Pedir aprovacao", 5}, {"Aprovado", 2.2f}, {"Recusado", 2.2f}, {"Tonto", 3.5f},
  {"Trabalhando", 4}, {"Ouvindo", 4}, {"Cochilo", 8}, {"Cocegas", 2.2f}, {"Dancinha", 5.4f}, {"Arrumar bigode", 4.4f},
};

uint8_t esc[N_CAMADAS] = {0, 0, 0, 0, 0, 0, COR_LARANJA, FUN_LISO};   // escolha atual (indices)
Anim animId = A_NENHUMA;
float animT0 = 0;            // relogio (s) em que a animacao comecou
bool animFeito = false;      // confete ja lancado
float bigodeCurl = 0;        // depois de arrumar, as pontas ficam enroladas e voltam devagar
float emitT[E_N];            // ultima emissao de cada tipo de particula
constexpr int MAX_PART = 64;
Particula parts[MAX_PART];   // vetor fixo: nada de new/String no laco de desenho
int nParts = 0;
float OX = 0, OY = 0;        // deslocamento da peca (em(...) da previa)
int cenaDx = 0, cenaDy = 0;
struct Estrela { int16_t x, y; float f, v; };
Estrela ceu[46];
int camarimAba = 0, camarimRolagem = 0;   // 0 = Animar, 1 = Visual
bool cochiloAuto = false;  // cochilo por inatividade: so termina com um toque

inline float jsr(float v) { return floorf(v + 0.5f); }   // Math.round
inline float lerpf(float a, float b, float k) { return a + (b - a) * k; }
inline float limf(float v, float a, float b) { return v < a ? a : v > b ? b : v; }
bool solido(int x, int y) { return y >= 0 && y < BODY_H && x >= 0 && x < BODY_W && SPRITE[y][x] == '#'; }

// retangulo em coordenadas da previa (relativas ao corpo)
void r(float x, float y, float w, float h, uint16_t c) {
  int W2 = (int)jsr(w), H2 = (int)jsr(h);
  if (W2 <= 0 || H2 <= 0) return;
  px((int)jsr(x + OX) + cenaDx, (int)jsr(y + OY) - PBY + BODY_Y + cenaDy, W2, H2, c);
}
// retangulo em coordenadas da tela (ceu)
void rt(float x, float y, float w, float h, uint16_t c) {
  int W2 = (int)jsr(w), H2 = (int)jsr(h);
  if (W2 <= 0 || H2 <= 0) return;
  px((int)jsr(x) + cenaDx, (int)jsr(y), W2, H2, c);
}

void iniciarCeu() {
  for (auto &e : ceu) { e.x = (int)(rnd() * 160) * 3; e.y = 34 + (int)(rnd() * 68) * 3; e.f = rnd() * 6; e.v = 1 + rnd() * 2; }
}
bool cada(int chave, float intervalo, float t) {
  if (t - emitT[chave] >= intervalo) { emitT[chave] = t; return true; }
  return false;
}
void addPart(TipoParticula tipo, float x, float y, float vx, float vy, float vida, uint16_t c = 0, uint8_t w = 0, uint8_t h = 0, const char *txt = nullptr) {
  for (auto &p : parts) {
    if (p.tipo != P_LIVRE) continue;
    p.tipo = tipo; p.x = x; p.y = y; p.vx = vx; p.vy = vy; p.vida = p.max = vida; p.seed = rnd() * 6; p.c = c; p.w = w; p.h = h; p.txt = txt;
    nParts++;
    return;
  }
}
void limparParticulas(TipoParticula so = P_LIVRE) {   // P_LIVRE = todas
  for (auto &p : parts) if (p.tipo != P_LIVRE && (so == P_LIVRE || p.tipo == so)) { p.tipo = P_LIVRE; nParts--; }
}
void tocarAnim(Anim a, float agora) {
  animId = a; animT0 = agora; animFeito = false;
  for (auto &e : emitT) e = -1e9f;
  switch (a) {   // o som acompanha a animacao (no Camarim tambem, para ouvir cada um)
    case A_COMEMORAR: tocarSom(S_PLIM); break;
    case A_DANCINHA: tocarSom(S_FESTA); break;
    case A_APROVACAO: tocarSom(S_AVISO); break;
    case A_APROVADO: tocarSom(S_APROVADO); break;
    case A_RECUSADO: tocarSom(S_RECUSADO); break;
    case A_TONTO: tocarSom(S_ERRO); break;
    case A_COCEGAS: tocarSom(S_COCEGAS); break;
    default: break;
  }
}
void pararAnim() { animId = A_NENHUMA; }

// ---- animacoes: cada uma ajusta o quadro (PASSO da previa) ----
void passo(Anim id, Quadro &s, float a, float t) {
  switch (id) {
    case A_COMEMORAR: {
      float pulo = fabsf(sinf(a * PI * 2.2f));
      s.dy = a < 2.3f ? -pulo * 28 : 0; s.eye = O_FELIZ; s.mouth = 2;
      s.armR = s.armL = a < 2.3f ? 6 + pulo * 12 : 0;
      if (!animFeito) {
        animFeito = true;
        const uint16_t cs[6] = {K(0xe0675a), K(0x6fbf73), K(0x5f97d9), K(0xf6d27e), K(0xc9a6f0), K(0xede6dc)};
        for (int i = 0; i < 40; i++) addPart(P_CONFETE, rnd() * W, 28 - rnd() * 90, (rnd() - .5f) * 70, 70 + rnd() * 90, 3.2f, cs[(int)(rnd() * 6) % 6], 5, 8);
      }
      break;
    }
    case A_APROVACAO:
      s.eyeH = 1.5f; s.eyeDy = -.5f; s.mouth = 1; s.alerta = true;
      if (a < 2.2f) s.armR = 16 + sinf(a * 13) * 9;
      else s.legR = sinf(a * 14) > 0 ? 7 : 0;
      s.eyeDx = a < 2.2f ? -.6f : 0;
      break;
    case A_APROVADO:
      s.eye = O_FELIZ; s.check = a < 1.9f; s.mouth = 1;
      s.dy = a < .9f ? -fabsf(sinf(a * PI / .3f)) * 10 : 0;
      s.armR = a < 1.6f ? 14 : 0;
      break;
    case A_RECUSADO: {
      float k = fmaxf(0, 1 - a / 1.3f);
      s.dx = sinf(a * 18) * 9 * k; s.eyeDx = sinf(a * 18) * .4f * k; s.xis = a < 1.7f;
      break;
    }
    case A_TONTO: {
      s.eye = O_X; s.estrelas = true; s.mouth = 1;
      float bal = sinf(a * 3.2f);
      for (int i = 0; i < 4; i++) s.rowDx[i] = (int)jsr(bal * (3 - i) * 4);
      break;
    }
    case A_TRABALHANDO:
      s.eyeDx = 1; s.pontos = true; s.bodyDy = ((int)(a * 6) % 2) * 2;
      if (cada(E_SUOR, 1.1f, t)) addPart(P_GOTA, 144 + s.dx, 108, -6, 10, 1.3f, K(0x7fb0e8), 6, 9);
      break;
    case A_OUVINDO:
      s.eyeH = 1.5f; s.eyeDy = -.5f; s.barras = true;
      for (int i = 0; i < 4; i++) s.rowDx[i] = (3 - i) * 3;
      break;
    case A_COCHILO:
      s.eye = O_FECHADO;
      if (a < 1.4f) { s.mouth = a < 1.1f ? 2 : 1; s.armL = s.armR = a < 1.1f ? 10 : 0; break; }
      s.bodyDy = (int)jsr((sinf(a * 1.7f) + 1) * 2);
      if (cada(E_ZZZ, 1.3f, t)) addPart(P_TEXTO, 316, 108, 16, -20, 2.8f, 0, 0, 0, "z");
      break;
    case A_DANCINHA: {
      float fase = a * 2.2f * PI * 2; bool bate = sinf(fase) > 0;
      if (a < 4) {
        float lado = sinf(fase / 2);
        s.dx = lado * 14; s.dy = -fabsf(sinf(fase)) * 8;
        for (int i = 0; i < 4; i++) s.rowDx[i] = (int)jsr(lado * (3 - i) * 3);
        s.armL = bate ? 18 : 2; s.armR = bate ? 2 : 18;
        s.legL = bate ? 7 : 0; s.legR = bate ? 0 : 7;
        s.mouth = bate ? 1 : 0;
      } else {
        s.armL = s.armR = 24 * fminf(1, (a - 4) / .25f);
        s.dy = -fabsf(sinf((a - 4) * PI / 1.4f)) * 22; s.mouth = 2;
      }
      s.eye = O_FELIZ; s.disco = (int)floorf(a * 4.4f);
      if (cada(E_NOTA, .4f, t)) {
        const uint16_t cs[4] = {K(0xf6d27e), K(0xc9a6f0), K(0x7fb0e8), K(0xec8db4)};
        float x = rnd() < .5f ? 70 + rnd() * 50 : 370 + rnd() * 50;
        addPart(P_NOTA, x, 170, (rnd() - .5f) * 20, -36, 1.9f, cs[(int)(rnd() * 4) % 4]);
      }
      break;
    }
    case A_ARRUMAR: {
      s.bigode = BIG_GUIDAO;
      float ida = fminf(1, a / .6f), volta = a > 2.7f ? fminf(1, (a - 2.7f) / .5f) : 0, k = ida * (1 - volta);
      bool gira = a > .6f && a < 2.7f; float ang = t * 22;
      float ox = gira ? cosf(ang) * 4 : 0, oy = gira ? sinf(ang) * 4 : 0;
      if (k > .05f) {
        s.temMaos = true;
        s.maos[0][0] = lerpf(126, 152, k) + ox; s.maos[0][1] = lerpf(162, 136, k) + oy;
        s.maos[1][0] = lerpf(342, 315, k) - ox; s.maos[1][1] = lerpf(162, 136, k) + oy;
      }
      s.armL = s.armR = 8 * k;
      s.curl = a < .6f ? bigodeCurl : fmaxf(bigodeCurl, fminf(1, (a - .6f) / 2));
      s.torce[0] = gira ? (int)jsr(sinf(ang) * 3) : 0; s.torce[1] = gira ? (int)jsr(cosf(ang) * 3) : 0;
      if (a > 2.7f) bigodeCurl = 1;
      if (a < 3.2f) { s.eyeH = .5f; s.eyeDy = .5f; }   // olhar concentrado, meio fechado
      else { s.eye = O_PISCA; s.brilho = true; }      // piscadinha e brilho no bigode
      break;
    }
    case A_COCEGAS:
      s.dx = sinf(a * 42) * 3; s.eye = O_RISO; s.mouth = ((int)(a * 8) % 2) + 1; s.armL = s.armR = 8;
      if (cada(E_HA, .28f, t)) addPart(P_TEXTO, 330 + rnd() * 40, 112 + rnd() * 24, 12, -34, 1.1f, 0, 0, 0, "ha");
      break;
    default: break;
  }
}

// ---- fundo e chao ----
void ceuFaixas(const uint16_t *cs, int n, float y0, float y1) {   // em coordenadas da tela
  float h = (y1 - y0) / n;
  for (int i = 0; i < n; i++) rt(0, jsr(y0 + i * h), W, ceilf(h) + 1, cs[i]);
  for (int i = 1; i < n; i++) {
    float y = jsr(y0 + i * h) - 3;
    for (int x = 0; x < W; x += 6) { rt(x, y, 3, 3, cs[i]); rt(x + 3, y + 3, 3, 3, cs[i - 1]); }
  }
}
void disco(float cx, float cy, float raio, uint16_t c, float ateY = 999, bool tela = false) {   // circulo em degraus de 3 px
  for (float dy = -raio; dy < raio; dy += 3) {
    if (cy + dy >= ateY) break;
    float w = jsr(sqrtf(raio * raio - (dy + 1.5f) * (dy + 1.5f)) / 3) * 6;
    if (tela) rt(cx - w / 2, cy + dy, w, 3, c); else r(cx - w / 2, cy + dy, w, 3, c);
  }
}
void morros(float base, float alt, float freq, float fase, uint16_t c) {
  for (int x = 0; x < W; x += 6) {
    float h = jsr(alt * (.55f + .45f * sinf(x * freq + fase) * sinf(x * freq * .37f + fase * 2)) / 3) * 3;
    r(x, base - h, 6, h, c);
  }
}
void pinheiro(float x, float base, float h, uint16_t c) {
  r(x - 3, base - 9, 6, 9, c);
  for (int k = 0; k < 3; k++) {
    float topo = base - 9 - (k + 1) * h / 3;
    for (float y = 0; y < h / 3 + 6; y += 3) { float w = jsr((y + 6) * (1.3f - k * .25f) / 3) * 3; r(x - w / 2, topo + y, w, 3, c); }
  }
}
void nuvem(float x, float y) {
  const uint16_t C = K(0xeef3f8), S = K(0xc6d5e4);
  rt(x, y + 9, 60, 12, C); rt(x + 9, y + 3, 24, 9, C); rt(x + 27, y, 21, 12, C); rt(x + 3, y + 18, 54, 3, S);
}

void fundo(float t) {
  const float fy = PBY + 150;                     // chao, coordenadas da previa
  const float fyT = BODY_Y + 150 + cenaDy;        // chao, coordenadas da tela
  px(0, AREA_Y, W, AREA_H, FB_BG);
  switch (esc[CM_FUNDO]) {
    case FUN_ESTRELAS:
      for (auto &e : ceu) { float b = sinf(t * e.v + e.f); rt(e.x, e.y, 3, 3, b > .55f ? FB_FG : b > -.2f ? FB_DIM : K(0x3a3531)); }
      break;
    case FUN_PORSOL: {
      const uint16_t cs[6] = {K(0x1a1426), K(0x231830), K(0x30203a), K(0x45283f), K(0x5e3143), K(0x7c3c45)};
      ceuFaixas(cs, 6, 28, fyT);
      const int pts[5][2] = {{40, 46}, {150, 62}, {420, 40}, {300, 52}, {458, 78}};
      for (auto &p : pts) rt(p[0], p[1], 3, 3, K(0x8a7f99));
      disco(372, fy - 18, 42, K(0xf2a65a), fy);
      disco(372, fy - 18, 30, K(0xf7c27a), fy);
      const int lis[3][2] = {{42, 2}, {33, 3}, {24, 4}};
      for (auto &l : lis) r(320, fy - l[0], 110, l[1], K(0x7c3c45));   // listras do sol
      morros(fy, 30, .021f, 1.3f, K(0x3a1f36));
      morros(fy, 16, .034f, 4.1f, K(0x24142a));
      break;
    }
    case FUN_GRAMA: {
      const uint16_t cs[5] = {K(0x3c6fb0), K(0x4f82c0), K(0x6596cd), K(0x7fabda), K(0x9cc0e4)};
      ceuFaixas(cs, 5, 28, fyT);
      float dx = fmodf(t * 7, W + 120);
      nuvem(fmodf(40 + dx, W + 120) - 90, 46); nuvem(fmodf(300 + dx * .7f, W + 120) - 90, 74);
      morros(fy, 34, .016f, .4f, K(0x5e9e52));
      morros(fy, 18, .03f, 2.2f, K(0x4b8a40));
      break;
    }
    case FUN_NEVE: {
      const uint16_t cs[4] = {K(0x0f1626), K(0x141d31), K(0x19253c), K(0x1f2d47)};
      ceuFaixas(cs, 4, 28, fyT);
      for (auto &e : ceu) if (e.y < 150) rt(e.x, e.y, 3, 3, sinf(t * e.v + e.f) > .3f ? K(0xc6d5e4) : K(0x3a4a66));
      disco(66, 70, 18, K(0xe8e4da), 999, true); rt(58, 62, 6, 6, K(0xc9c4b8)); rt(70, 74, 6, 3, K(0xc9c4b8));
      const int pin[8][2] = {{30, 54}, {70, 42}, {118, 60}, {380, 48}, {420, 64}, {462, 40}, {196, 34}, {292, 38}};
      for (auto &p : pin) pinheiro(p[0], fy, p[1], K(0x18233a));
      // a previa nasce a neve em y=28 da previa (atras do cabecalho daqui); aqui nasce no topo da area
      if (cada(E_NEVE, .15f, t)) addPart(P_NEVE, rnd() * W, PBY - BODY_Y + AREA_Y - cenaDy, (rnd() - .5f) * 10, 22 + rnd() * 22, 12, K(0xeef3f8), 3, 3);
      break;
    }
    default: break;
  }
}

void chao(const Quadro &s) {
  const float cx = 240, fy = PBY + 150;
  const int fl[3][2] = {{300, 0}, {240, 6}, {180, 12}};
  uint8_t f = esc[CM_FUNDO];
  if (f == FUN_GRAMA) {
    r(0, fy, W, 30, K(0x3f8a34)); r(0, fy, W, 3, K(0x5aa848));
    for (int x = 0; x < W; x += 48) r(x, fy + 3, 24, 24, K(0x3a8030));
    r(0, fy + 27, W, 3, K(0x2a4a1f));
    const uint16_t fc[3] = {K(0xf6d27e), K(0xede6dc), K(0xec8db4)};
    for (int i = 0; i < 18; i++) r((i * 53 + 17) % 474, fy + 3 + (i * 7) % 18, 3, 3, fc[i % 3]);
    for (int x = 2; x < W; x += 9) { int h = 3 + ((x * 7) % 3) * 3; r(x, fy - h, 3, h, K(0x5aa848)); }
  } else if (f == FUN_NEVE) {
    r(0, fy, W, 30, K(0xdfe6ee)); r(0, fy + 18, W, 12, K(0xc6d1de));
    for (int x = 0; x < W; x += 60) { r(x + 6, fy - 3, 36, 3, K(0xdfe6ee)); r(x + 15, fy - 6, 18, 3, K(0xdfe6ee)); }
    for (int x = 11; x < W; x += 37) r(x, fy + 6 + (x % 9), 3, 3, K(0xffffff));
  } else if (f == FUN_PORSOL) {
    r(0, fy, W, 30, K(0x1d1020)); r(0, fy, W, 3, K(0x3a1f36));
  } else {
    for (auto &l : fl) r(cx - l[0] / 2, fy + 3 + l[1], l[0], 6, FB_FLOOR);
  }
  if (s.disco >= 0) {   // pista de danca piscando no ritmo
    const uint16_t cs[4] = {K(0x5f3a8f), K(0x2f5490), K(0x8f3757), K(0x3b7029)};
    for (int i = 0; i < 3; i++) for (int k = 0; k < fl[i][0] / 30; k++) r(cx - fl[i][0] / 2 + k * 30, fy + 3 + fl[i][1], 30, 6, cs[(k + i + s.disco) % 4]);
  }
  float k = fmaxf(.45f, 1 + s.dy / 55);
  const int sh[3] = {210, 150, 90};
  uint16_t cs = f == FUN_PORSOL ? K(0x140b16) : f == FUN_GRAMA ? K(0x2c6324) : f == FUN_NEVE ? K(0xa3b4c8) : FB_SHADOW;
  for (int i = 0; i < 3; i++) r(cx - sh[i] * k / 2 + s.dx, fy + 3 + i * 6, sh[i] * k, 6, cs);
}

void neveNoCorpo(float cx, float cy, const Quadro &s) {   // neve acumulada na cabeca e nos bracos
  const uint16_t N = K(0xeef3f8);
  OX = cx; OY = cy; r(152, 92, 176, 6, N); r(160, 88, 30, 4, N); r(212, 89, 40, 3, N); r(270, 88, 36, 4, N); r(152, 96, 176, 2, K(0xc6d5e4));
  OY = cy - s.armL; r(122, 152, 26, 4, N);
  OY = cy - s.armR; r(332, 152, 26, 4, N);
  OX = OY = 0;
}

// ---- corpo, olhos e boca ----
void corpo(const Quadro &s, const uint16_t *P) {
  for (int y = 0; y < BODY_H; y++) for (int x = 0; x < BODY_W; x++) {
    if (!solido(x, y)) continue;
    bool perna = y == 4;
    float X = PBX + x * PW + s.dx + (perna ? 0 : s.rowDx[y]);
    float Y = PBY + y * PH + s.dy + (perna ? 0 : s.bodyDy);
    if (y == 2 && x >= 15) Y -= s.armR;
    if (y == 2 && x <= 2) Y -= s.armL;
    if (perna && x == 13) Y -= s.legR;
    if (perna && x == 4) Y -= s.legL;
    r(X, Y, PW, PH, perna ? P[3] : P[2]);
    if (!solido(x - 1, y)) r(X, Y, 4, PH, perna ? P[2] : P[1]);
    if (!solido(x, y - 1) || (y == 2 && (x >= 15 || x <= 2))) r(X, Y, PW, 6, P[0]);
    if (!solido(x + 1, y)) r(X + PW - 4, Y, 4, PH, perna ? P[4] : P[3]);
    if (!solido(x, y + 1)) r(X, Y + PH - 8, PW, 8, perna ? P[4] : P[3]);
  }
}

void olhos(const Quadro &s, const uint16_t *P) {
  if (s.piscar) return;
  const uint16_t B = FB_BG;
  const int EX[2] = {5, 12};
  for (int ex : EX) {
    float x = PBX + (ex + s.eyeDx) * PW, y = PBY + (1 + s.eyeDy) * PH;
    if (s.eye == O_PISCA && ex == 5) r(x - 3, y + 20, PW + 6, 5, B);
    else if (s.eye == O_NORMAL || s.eye == O_PISCA) { r(x, y, PW, s.eyeH * PH, B); r(x, y - 4, PW, 4, P[4]); }
    else if (s.eye == O_FELIZ) { const int p[5][2] = {{-5, 20}, {0, 14}, {5, 9}, {10, 14}, {15, 20}}; for (auto &q : p) r(x + q[0], y + q[1], 6, 6, B); }
    else if (s.eye == O_FECHADO) r(x - 3, y + 20, PW + 6, 5, B);
    else if (s.eye == O_X) { const int p[5][2] = {{-2, 0}, {12, 0}, {5, 7}, {-2, 14}, {12, 14}}; for (auto &q : p) r(x + q[0], y + 5 + q[1], 6, 6, B); }
    else if (s.eye == O_RISO) {
      const int pe[5][2] = {{0, 0}, {5, 4}, {10, 8}, {5, 12}, {0, 16}}, pd[5][2] = {{10, 0}, {5, 4}, {0, 8}, {5, 12}, {10, 16}};
      for (int i = 0; i < 5; i++) { const int *q = ex == 5 ? pe[i] : pd[i]; r(x + q[0], y + 4 + q[1], 6, 6, B); }
    }
  }
}

void boca(const Quadro &s, const uint16_t *P) {
  if (s.mouth <= 0) return;
  float x = PBX + 8 * PW, y = PBY + 2.5f * PH, h = s.mouth == 1 ? 12 : 22;
  r(x, y, 2 * PW, h, FB_BG); r(x, y - 4, 2 * PW, 4, P[4]);
}

// ---- acessorios (retangulos, coordenadas da previa com o corpo parado) ----
void pecaCabeca(uint8_t i) {
  switch (i) {
    case CAB_CARTOLA: { const uint16_t Kc = K(0x1d1a18), L = K(0x3a3430); r(160, 86, 160, 10, Kc); r(160, 86, 160, 2, L); r(186, 36, 108, 50, Kc); r(186, 36, 108, 3, L); r(186, 72, 108, 10, K(0xc8463a)); break; }
    case CAB_BONE: { const uint16_t R = K(0xc8463a), D = K(0x8f2f26); r(234, 56, 12, 6, R); r(176, 62, 128, 6, R); r(164, 68, 152, 28, R); r(164, 90, 152, 6, D);
      r(304, 86, 62, 8, R); r(304, 92, 62, 4, D); r(206, 72, 16, 12, K(0xede6dc)); r(210, 76, 8, 4, R); break; }
    case CAB_COWBOY: { const uint16_t B = K(0x8a5a33), D = K(0x5e3b20); r(182, 46, 116, 40, B); r(222, 46, 36, 6, D); r(182, 46, 116, 3, K(0xa8744a)); r(182, 76, 116, 8, K(0x2a1a10));
      r(132, 86, 216, 10, B); r(132, 94, 216, 3, D); r(122, 76, 14, 14, B); r(344, 76, 14, 14, B); break; }
    case CAB_COROA: { const uint16_t G = K(0xe0aa45), L = K(0xf6d27e); r(176, 74, 128, 22, G); r(176, 74, 128, 3, L);
      r(176, 54, 18, 20, G); r(231, 46, 18, 28, G); r(286, 54, 18, 20, G); r(180, 48, 10, 6, L); r(235, 40, 10, 6, L); r(290, 48, 10, 6, L);
      r(204, 80, 10, 10, K(0xc8463a)); r(235, 80, 10, 10, K(0x5f97d9)); r(266, 80, 10, 10, K(0xc8463a)); break; }
    case CAB_OBRA: { const uint16_t Y = K(0xe6b450), L = K(0xf6d27e), D = K(0xb88a2e); r(184, 56, 112, 10, Y); r(184, 56, 112, 3, L); r(166, 64, 148, 28, Y);
      r(234, 52, 12, 40, D); r(148, 88, 184, 4, Y); r(148, 92, 184, 8, D); break; }
    case CAB_FONE: { const uint16_t D = K(0x2a2420), C = K(0x3a3430); r(162, 70, 156, 8, D); r(148, 78, 16, 10, D); r(316, 78, 16, 10, D); r(140, 88, 10, 30, D); r(330, 88, 10, 30, D);
      r(128, 114, 24, 42, C); r(328, 114, 24, 42, C); r(134, 122, 6, 6, FB_OK); r(146, 154, 5, 16, D); r(146, 168, 44, 5, D); r(188, 164, 12, 12, D); break; }
    case CAB_NATAL: { const uint16_t R = K(0xc8463a), Wt = K(0xefe9e0); r(160, 76, 160, 12, R); r(172, 64, 136, 12, R); r(188, 54, 108, 10, R); r(206, 46, 80, 8, R);
      r(232, 40, 64, 6, R); r(272, 38, 40, 6, R); r(302, 42, 22, 10, R); r(318, 40, 18, 18, Wt); r(150, 86, 180, 14, Wt); break; }
    case CAB_FESTA: { const uint16_t cs[2] = {K(0x5f97d9), K(0xf6d27e)}; const int ws[7] = {56, 48, 40, 32, 24, 16, 8};
      for (int k = 0; k < 7; k++) r(240 - ws[k] / 2, 88 - k * 8, ws[k], 8, cs[k % 2]);
      r(234, 28, 12, 12, K(0xe0675a));
      break; }
    default: break;
  }
}
void pecaOlhos(uint8_t i) {
  switch (i) {
    case OLH_OCULOS: { const uint16_t Kc = K(0x1d1a18); const int xs[2] = {170, 275};
      for (int x0 : xs) { r(x0 + 4, 118, 28, 4, Kc); r(x0 + 4, 160, 28, 4, Kc); r(x0, 122, 4, 38, Kc); r(x0 + 32, 122, 4, 38, Kc); }
      r(206, 132, 69, 4, Kc); r(150, 132, 20, 4, Kc); r(311, 132, 19, 4, Kc); break; }
    case OLH_ESCUROS: { const uint16_t Kc = K(0x0e0d0c); const int xs[2] = {166, 270};
      for (int x0 : xs) { r(x0, 122, 44, 26, Kc); r(x0 + 4, 148, 36, 6, Kc); r(x0 + 6, 126, 8, 4, K(0xede6dc)); }
      r(210, 126, 60, 6, Kc); r(150, 126, 16, 5, Kc); r(314, 126, 16, 5, Kc); break; }
    case OLH_MONOCULO: { const uint16_t G = K(0xe0aa45); r(281, 118, 24, 4, G); r(281, 160, 24, 4, G); r(277, 122, 4, 38, G); r(305, 122, 4, 38, G);
      for (int k = 0; k < 9; k++) r(306 + k * 2, 166 + k * 4, 3, 3, G);
      break; }
    case OLH_TAPAOLHO: { const uint16_t Kc = K(0x0e0d0c); r(172, 118, 32, 42, Kc); r(176, 160, 24, 4, Kc); r(150, 128, 22, 4, Kc);
      for (int k = 0; k < 11; k++) r(204 + k * 12, 120 - k * 2, 12, 4, Kc);
      break; }
    default: break;
  }
}
void pecaBigode(uint8_t i, const Quadro &s) {
  const uint16_t M = K(0x3b2a1f);
  if (i == BIG_CLASSICO) { r(216, 160, 48, 8, M); r(208, 164, 12, 8, M); r(260, 164, 12, 8, M); r(202, 170, 8, 4, M); r(270, 170, 8, 4, M); r(238, 160, 4, 4, K(0x5a4130)); }
  if (i == BIG_GUIDAO) {
    float curl = s.curl < 0 ? 0 : s.curl;
    int up = (int)jsr(curl * 6), yl = s.torce[0] - up, yr = s.torce[1] - up;
    // as pontas saem para os lados, por fora dos olhos, e sobem
    r(220, 160, 40, 8, M); r(204, 162, 18, 6, M); r(258, 162, 18, 6, M);
    r(188, 160, 18, 6, M); r(274, 160, 18, 6, M);
    r(178, 156 + jsr(yl / 2.0f), 12, 6, M); r(290, 156 + jsr(yr / 2.0f), 12, 6, M);
    r(172, 150 + yl, 8, 6, M); r(300, 150 + yr, 8, 6, M);
    if (curl > .5f) { r(167, 144 + yl, 6, 6, M); r(171, 139 + yl, 6, 5, M); r(307, 144 + yr, 6, 6, M); r(303, 139 + yr, 6, 5, M); }
  }
}
uint16_t brasa(float t) { bool forte = fmodf(t, 4) < .6f; return forte ? K(0xffd27a) : ((int)(t * 9) % 2 ? K(0xff6a2a) : K(0xe0503a)); }
void pecaBoca(uint8_t i, float t) {
  switch (i) {
    case BOC_CIGARRO: r(244, 172, 12, 6, K(0xc8925a)); r(256, 172, 30, 6, K(0xefe9e0)); r(286, 172, 4, 6, K(0x8a817b)); r(290, 172, 5, 6, brasa(t)); break;
    case BOC_CHARUTO: r(242, 170, 48, 9, K(0x6b4226)); r(242, 170, 48, 2, K(0x8a5a33)); r(252, 170, 7, 9, K(0xc8463a)); r(286, 170, 4, 9, K(0x8a817b)); r(290, 170, 5, 9, brasa(t)); break;
    case BOC_CACHIMBO: r(248, 174, 32, 5, K(0x4a2e1a)); r(276, 156, 18, 24, K(0x6b4226)); r(276, 156, 18, 3, K(0x8a5a33)); r(279, 156, 12, 4, fmodf(t, 4) < .6f ? K(0xffd27a) : K(0xe0503a)); break;
    default: break;
  }
}
void pecaPeito(uint8_t i) {
  switch (i) {
    case PEI_BORBOLETA: { const uint16_t Kc = K(0x1d1a18); r(234, 199, 12, 10, Kc); r(216, 196, 8, 18, Kc); r(224, 199, 10, 12, Kc); r(256, 196, 8, 18, Kc); r(246, 199, 10, 12, Kc); r(218, 198, 4, 5, K(0x3a3430)); break; }
    case PEI_GRAVATA: { const uint16_t B = K(0x5f97d9), D = K(0x2f5490); r(234, 196, 12, 7, D); r(232, 203, 16, 9, B); r(236, 212, 8, 4, B); r(232, 207, 16, 2, D); break; }
    case PEI_CACHECOL: { const uint16_t R = K(0xc8463a), Wt = K(0xefe9e0); r(150, 180, 180, 14, R); for (int x = 162; x < 330; x += 30) r(x, 180, 6, 14, Wt);
      r(290, 194, 18, 32, R); r(290, 204, 18, 5, Wt); for (int k = 0; k < 4; k++) r(291 + k * 5, 226, 3, 7, R); break; }
    default: break;
  }
}
void pecaMao(uint8_t i, float t) {
  switch (i) {
    case MAO_CANECA: { const uint16_t Wt = K(0xefe9e0); r(360, 148, 28, 36, Wt); r(360, 148, 28, 5, K(0x3a2418)); r(360, 164, 28, 6, K(0xd97757)); r(388, 156, 8, 4, Wt);
      r(392, 156, 4, 18, Wt); r(388, 170, 8, 4, Wt); r(384, 152, 4, 32, K(0xcfc8bf)); break; }
    case MAO_CHAVE: { const uint16_t G = K(0xa9a49e), D = K(0x6e6964); r(364, 124, 10, 56, G); r(372, 124, 2, 56, D); r(354, 100, 30, 24, G); r(354, 100, 30, 3, K(0xc8c4bf));
      r(362, 100, 14, 12, FB_BG); r(380, 108, 4, 16, D); break; }
    case MAO_BANDEIRA: {
      r(362, 78, 5, 108, K(0x8a5a33)); r(361, 74, 7, 6, K(0xe0aa45));
      const int lin[7][2] = {{83, 6}, {88, 20}, {93, 36}, {99, 44}, {105, 36}, {110, 20}, {115, 4}};
      for (int c = 0; c < 7; c++) {
        float dy = jsr(sinf(t * 5 - c * .8f) * 2), x = 367 + c * 8; OY += dy;
        r(x, 80, 8, 38, K(0x2f9e44));
        for (auto &l : lin) { float a = fmaxf(x, 395 - l[1]), b = fminf(x + 8, 395 + l[1]); if (b > a) r(a, l[0], b - a, 5, K(0xf6d000)); }
        float a = fmaxf(x, 386), b = fminf(x + 8, 404); if (b > a) { r(a, 91, b - a, 18, K(0x2b4fa0)); r(a, 98, b - a, 3, K(0xede6dc)); }
        OY -= dy;
      }
      break;
    }
    default: break;
  }
}

// ---- efeitos e particulas ----
void efeitos(const Quadro &s, float t, float cx, float cy) {
  if (s.alerta) { uint16_t c = ((int)(t * 3) % 2) ? FB_WARN_HI : FB_WARN; OX = cx; OY = cy; r(344, PBY, 12, 26, c); r(344, PBY + 34, 12, 12, c); OX = OY = 0; }
  if (s.pontos) { int p = (int)(t * 4) % 4; for (int i = 0; i < 3; i++) r(340 + i * 20, PBY - 4 - i * 6, 12, 12, i < p ? FB_FG : FB_DIM); }
  if (s.check) { const int p[5][2] = {{0, 14}, {7, 21}, {14, 14}, {21, 7}, {28, 0}}; for (auto &q : p) { rt(372 + q[0], 34 + q[1], 8, 8, FB_OK); rt(372 + q[0], 41 + q[1], 8, 4, FB_OK); } }
  if (s.xis) { const int p[9][2] = {{0, 0}, {28, 0}, {7, 7}, {21, 7}, {14, 14}, {7, 21}, {21, 21}, {0, 28}, {28, 28}}; for (auto &q : p) rt(372 + q[0], 34 + q[1], 8, 8, FB_BAD); }
  if (s.estrelas) for (int i = 0; i < 3; i++) {
    float ang = t * 4 + i * 2.094f, x = 240 + cosf(ang) * 112 + cx, y = 72 + sinf(ang) * 14 + cy;
    r(x - 2, y - 7, 4, 14, FB_WARN_HI); r(x - 7, y - 2, 14, 4, FB_WARN_HI);
  }
}

void particulas(float dt, float t) {
  for (auto &p : parts) {
    if (p.tipo == P_LIVRE) continue;
    p.vida -= dt;
    if (p.tipo == P_GOTA) p.vy += 160 * dt;
    p.x += (p.vx + (p.tipo == P_FUMACA || p.tipo == P_VAPOR ? sinf(t * 3 + p.seed) * 8 : 0)) * dt; p.y += p.vy * dt;
    if (p.tipo == P_NEVE && p.y > PBY + 152) p.vida = 0;
    if (p.vida <= 0) { p.tipo = P_LIVRE; nParts--; }
  }
  for (auto &p : parts) {
    if (p.tipo == P_LIVRE) continue;
    float f = 1 - p.vida / p.max;
    if (p.tipo == P_FUMACA) {
      const uint16_t cs[4] = {K(0x9a9088), K(0x6e6760), K(0x4a443f), K(0x2e2a27)};
      float sz = 4 + f * 8; r(p.x - sz / 2, p.y - sz / 2, sz, sz, cs[(int)fminf(3, f * 4)]);
    } else if (p.tipo == P_VAPOR) {
      const uint16_t cs[3] = {K(0xcfc8bf), K(0x8a8178), K(0x4a443f)};
      float sz = 4 + f * 4; r(p.x - sz / 2, p.y - sz / 2, sz, sz, cs[(int)fminf(2, f * 3)]);
    } else if (p.tipo == P_NOTA) {
      r(p.x, p.y, 8, 6, p.c); r(p.x + 6, p.y - 14, 2, 16, p.c); r(p.x + 8, p.y - 14, 5, 3, p.c); r(p.x + 11, p.y - 11, 2, 4, p.c);
    } else if (p.tipo == P_CONFETE) { int v = (int)(t * 7 + p.seed) % 2; r(p.x, p.y, v ? p.w : p.h, v ? p.h : p.w, p.c); }
    else if (p.tipo == P_TEXTO) textoCena((int)jsr(p.x) + cenaDx, (int)jsr(p.y) - PBY + BODY_Y + cenaDy, p.txt, f < .6f ? FB_FG : FB_DIM);
    else r(p.x, p.y, p.w, p.h, p.c);
  }
}

bool cenaAnimada() {   // precisa redesenhar sozinha (ate ~25 quadros/s)?
  uint8_t f = esc[CM_FUNDO];
  return animId != A_NENHUMA || nParts > 0 || f == FUN_ESTRELAS || f == FUN_GRAMA || f == FUN_NEVE || esc[CM_BOCA] != BOC_NADA
         || esc[CM_MAO] == MAO_BANDEIRA || esc[CM_MAO] == MAO_CANECA || bigodeCurl > 0;
}

// Desenha a cena inteira no sprite (quadro() da previa, sem cabecalho e rodape).
void cena(Quadro &s, float t, float dt) {
  if (animId != A_ARRUMAR) bigodeCurl = fmaxf(0, bigodeCurl - dt / 25);
  if (s.curl < 0) s.curl = bigodeCurl;
  const uint16_t *P = PALETAS[esc[CM_COR]];
  float cabX = s.dx + s.rowDx[0], cabY = s.dy + s.bodyDy, rosX = s.dx + s.rowDx[1], rosY = s.dy + s.bodyDy;
  float peiX = s.dx + s.rowDx[2], peiY = s.dy + s.bodyDy, maoX = peiX, maoY = s.dy + s.bodyDy - s.armR;
  uint8_t bc = esc[CM_BOCA];
  if (bc != BOC_NADA) {
    const float FU[4][3] = {{0, 0, 0}, {295, 172, .15f}, {295, 170, .11f}, {285, 152, .13f}};
    if (cada(E_FUMACA, fmodf(t, 4) < .6f ? FU[bc][2] / 2 : FU[bc][2], t)) addPart(P_FUMACA, FU[bc][0] + rosX, FU[bc][1] + rosY, 6 + rnd() * 8, -22 - rnd() * 12, 2.2f);
  }
  if (esc[CM_MAO] == MAO_CANECA && cada(E_VAPOR, .3f, t)) addPart(P_VAPOR, 366 + rnd() * 16 + maoX, 144 + maoY, (rnd() - .5f) * 6, -16, 1.4f);
  if (esc[CM_FUNDO] != FUN_NEVE) limparParticulas(P_NEVE);

  fundo(t); chao(s); corpo(s, P);
  OX = rosX; OY = rosY; olhos(s, P);
  OX = peiX; OY = peiY; boca(s, P);
  OX = OY = 0;
  if (esc[CM_FUNDO] == FUN_NEVE) neveNoCorpo(cabX, cabY, s);
  OX = peiX; OY = peiY; pecaPeito(esc[CM_PEITO]);
  OX = rosX; OY = rosY;
  pecaBigode(s.bigode >= 0 ? s.bigode : esc[CM_BIGODE], s);
  if (s.temMaos) for (auto &m2 : s.maos) {   // luvinhas brancas na frente do corpo
    float x = m2[0], y = m2[1];
    r(x, y, 14, 14, K(0xefe9e0)); r(x + 10, y, 4, 14, K(0xbdb5ab)); r(x, y + 11, 14, 3, K(0xbdb5ab)); r(x + 3, y - 3, 4, 3, K(0xefe9e0));
  }
  if (s.brilho && (int)(t * 1000 / 120) % 2) { const int xs[2] = {162, 318}; for (int x : xs) { r(x - 1, 124, 3, 11, FB_WARN_HI); r(x - 5, 128, 11, 3, FB_WARN_HI); } }
  pecaOlhos(esc[CM_OLHOS]);
  pecaBoca(bc, t);
  OX = cabX; OY = cabY; pecaCabeca(esc[CM_CABECA]);
  OX = maoX; OY = maoY; pecaMao(esc[CM_MAO], t);
  OX = OY = 0;
  efeitos(s, t, cabX, cabY);
  particulas(dt, t);
}

// ---- tela Camarim: coluna da direita (abas e lista) ----
constexpr int CAM_X = 320, CAM_W = W - CAM_X, CAM_ABA = 44, CAM_LH = 48, CAM_DX = -100;
constexpr int CAM_VOLTAR_X = 12, CAM_VOLTAR_Y = 262, CAM_VOLTAR_W = 120, CAM_VOLTAR_H = 44;
int camarimLinhas() { return camarimAba == 0 ? N_ANIMS - 1 : N_CAMADAS + 1; }
int camarimRolagemMax() { int v = camarimLinhas() * CAM_LH - (H - CAM_ABA); return v > 0 ? v : 0; }

void desenharColuna(LovyanGFX &g) {   // g: sprite de CAM_W x H
  g.fillScreen(C_PANEL);
  g.setFont(&fonts::Font2);
  const char *abas[2] = {"Animar", "Visual"};
  for (int i = 0; i < 2; i++) {
    bool on = camarimAba == i;
    g.fillRect(i * 80, 0, 80, CAM_ABA, on ? C_BG : C_PANEL);
    if (on) g.fillRect(i * 80 + 8, CAM_ABA - 5, 64, 3, C_BODY);
    g.setTextDatum(middle_center);
    g.setTextColor(on ? C_FG : C_DIM);
    g.drawString(abas[i], i * 80 + 40, CAM_ABA / 2);
  }
  g.fillRect(0, CAM_ABA - 1, CAM_W, 1, C_LINE);
  g.setClipRect(0, CAM_ABA, CAM_W, H - CAM_ABA);
  for (int k = 0; k < camarimLinhas(); k++) {
    int y = CAM_ABA + k * CAM_LH - camarimRolagem;
    if (y > H || y + CAM_LH < CAM_ABA) continue;
    g.fillRect(0, y + CAM_LH - 1, CAM_W, 1, C_LINE);
    if (camarimAba == 0) {
      Anim a = (Anim)(k + 1);
      bool on = animId == a;
      if (on) { g.fillRect(0, y, CAM_W, CAM_LH - 1, C_BG); g.fillRect(0, y, 4, CAM_LH - 1, C_BODY); }
      g.setTextDatum(middle_left);
      g.setTextColor(on ? C_FG : C_FG);
      g.drawString(ANIMS[a].nome, 14, y + CAM_LH / 2);
      if (on) g.fillRect(CAM_W - 24, y + CAM_LH / 2 - 5, 10, 10, C_BODY);   // tocando: toque de novo para parar
      else seta(g, CAM_W - 22, y + CAM_LH / 2 - 1, C_DIM, 'r');
    } else if (k < N_CAMADAS) {
      seta(g, 18, y + CAM_LH / 2 - 1, C_FG, 'l');
      seta(g, CAM_W - 24, y + CAM_LH / 2 - 1, C_FG, 'r');
      g.setTextDatum(middle_center);
      g.setTextColor(C_DIM);
      g.drawString(NOME_CAMADA[k], CAM_W / 2, y + 14);
      g.setTextColor(C_FG);
      g.drawString(ITENS[k][esc[k]], CAM_W / 2, y + 32);
      if (k == CM_COR) g.fillRect(CAM_W / 2 - 3, y + 42, 6, 3, PALETAS[esc[CM_COR]][2]);
    } else {
      g.drawRect(14, y + 7, CAM_W - 28, CAM_LH - 14, C_BODY); g.drawRect(15, y + 8, CAM_W - 30, CAM_LH - 16, C_BODY);
      g.setTextDatum(middle_center);
      g.setTextColor(C_FG);
      g.drawString("Sortear", CAM_W / 2, y + CAM_LH / 2);
    }
  }
  g.clearClipRect();
  int mx = camarimRolagemMax();
  if (mx > 0) {
    int trilho = H - CAM_ABA - 8, total = camarimLinhas() * CAM_LH, polegar = trilho * (H - CAM_ABA) / total;
    if (polegar < 24) polegar = 24;
    g.fillRect(CAM_W - 4, CAM_ABA + 4, 2, trilho, C_LINE);
    g.fillRect(CAM_W - 4, CAM_ABA + 4 + (trilho - polegar) * camarimRolagem / mx, 2, polegar, C_DIM);
  }
}

// titulo e rodape da esquerda (botao Voltar e o que esta tocando)
void desenharCamarimBase(LovyanGFX &g) {
  g.fillRect(0, 0, CAM_X, AREA_Y, C_BG);
  g.fillRect(0, FOOT_TOP, CAM_X, H - FOOT_TOP, C_BG);
  g.setFont(&fonts::Font2);
  g.setTextDatum(middle_left);
  g.setTextColor(C_FG, C_BG);
  g.drawString("Camarim", 12, AREA_Y / 2 + 1);
  g.drawRect(CAM_VOLTAR_X, CAM_VOLTAR_Y, CAM_VOLTAR_W, CAM_VOLTAR_H, C_LINE);
  g.drawRect(CAM_VOLTAR_X + 1, CAM_VOLTAR_Y + 1, CAM_VOLTAR_W - 2, CAM_VOLTAR_H - 2, C_LINE);
  seta(g, CAM_VOLTAR_X + 14, CAM_VOLTAR_Y + CAM_VOLTAR_H / 2 - 1, C_FG, 'l');
  g.drawString("Voltar", CAM_VOLTAR_X + 34, CAM_VOLTAR_Y + CAM_VOLTAR_H / 2 + 1);
  g.setTextColor(C_DIM, C_BG);
  g.drawString(animId ? ANIMS[animId].nome : "toque no corpo: cocegas", CAM_VOLTAR_X + CAM_VOLTAR_W + 14, CAM_VOLTAR_Y + CAM_VOLTAR_H / 2 + 1);
}

// cabide (abre o Camarim), no canto superior direito da tela inicial
void desenharCabide(LovyanGFX &g, int x, int y, uint16_t c) {
  g.fillRect(x + 9, y, 4, 3, c); g.fillRect(x + 12, y + 2, 3, 3, c); g.fillRect(x + 9, y + 5, 4, 3, c);
  for (int i = 0; i < 4; i++) { g.fillRect(x + 8 - i * 3, y + 8 + i * 2, 3, 3, c); g.fillRect(x + 11 + i * 3, y + 8 + i * 2, 3, 3, c); }
  g.fillRect(x - 2, y + 16, 26, 3, c);
}
// Altura extra quando ha chapeu: abaixa a cena para o chapeu caber abaixo do cabecalho.
int alturaChapeu() {
  const int topo[9] = {999, 36, 56, 46, 40, 52, 70, 38, 28};   // topo de cada chapeu na previa (nada, cartola, bone...)
  // ate 14 px: mais que isso o chao e a sombra somem atras do rodape (que fica igual)
  int falta = AREA_Y + 2 - (topo[esc[CM_CABECA]] - PBY + BODY_Y);
  return falta < 0 ? 0 : falta > 14 ? 14 : falta;
}

// <<< HOST

float relogio() { return millis() / 1000.0f; }

// Monta o quadro a partir do Estado (m) e da animacao que estiver tocando.
float ultimoCena = 0;
void montarQuadro(Quadro &s, float agora) {
  s.piscar = m.blinkT >= 0;
  s.eyeDx = m.eyeDx; s.eyeDy = m.eyeDy; s.eyeH = m.eyeH; s.mouth = m.mouth;
  if (m.estado == PENSANDO) s.pontos = true;
  if (animId != A_NENHUMA) {
    float a = agora - animT0;
    if (a > ANIMS[animId].dur) {
      if (animId == A_COCHILO && cochiloAuto) { animT0 = agora - 1.4f; a = 1.4f; }   // continua dormindo ate um toque
      else { pararAnim(); if (tela == T_CAMARIM) redesenharColuna(); }
    }
    if (animId != A_NENHUMA) { s = Quadro(); passo(animId, s, a, agora); return; }
  }
  if (m.estado == ALERTA) { s = Quadro(); passo(A_APROVACAO, s, m.t, agora); }        // aceno e, depois de 2 s, o pe batendo
  else if (m.estado == TRABALHANDO) { s = Quadro(); passo(A_TRABALHANDO, s, m.t, agora); s.piscar = m.blinkT >= 0; }   // com gota de suor
  else if (m.estado == OUVINDO) { s = Quadro(); passo(A_OUVINDO, s, m.t, agora); }    // cabeca inclinada
}

void desenharMascote() {
  float agora = relogio(), dt = ultimoCena > 0 ? fminf(.05f, agora - ultimoCena) : 0;
  ultimoCena = agora;
  Quadro s;
  montarQuadro(s, agora);
  cenaDy = alturaChapeu();
  cenaDx = tela == T_CAMARIM ? CAM_DX : 0;
  cena(s, agora, dt);
  if (tela == T_SESSAO) tft.setClipRect(0, HDR_S, W, FOOT_TOP - HDR_S);   // nao pisa no cabecalho da sessao
  if (tela == T_CAMARIM) tft.setClipRect(0, AREA_Y, CAM_X, AREA_H);       // nem na coluna do Camarim
  area.pushSprite(AREA_X, AREA_Y);
  tft.clearClipRect();
}

// ---- desenho: rodape (texto ou aprovacao) ----------------------------------------------------
int botaoApertado = 0;  // 1 = recusar, 2 = aprovar (realce enquanto o dedo esta em cima)

void desenharAprovacao(Sessao &s) {
  int y0 = FOOT_TOP;
  rodape.setTextDatum(middle_left);
  rodape.setTextColor(C_WARN);
  rodape.drawString(("PEDE PERMISSAO - " + s.askTool).c_str(), 16, 249 - y0);
  rodape.setTextColor(C_FG);
  rodape.drawString(cortar(rodape, s.askText, W - 32).c_str(), 16, 263 - y0);
  int xr = 16, xa = 16 + BTN_W + 12, by = BTN_Y - y0;
  rodape.fillRect(xr, by, BTN_W, BTN_H, botaoApertado == 1 ? C_BAD : C_BG);
  rodape.drawRect(xr, by, BTN_W, BTN_H, C_BAD); rodape.drawRect(xr + 1, by + 1, BTN_W - 2, BTN_H - 2, C_BAD);
  rodape.fillRect(xa, by, BTN_W, BTN_H, botaoApertado == 2 ? C_FG : C_OK);
  rodape.setTextDatum(middle_center);
  rodape.setTextColor(botaoApertado == 1 ? C_BG : C_BAD);
  rodape.drawString("Recusar", xr + BTN_W / 2, by + BTN_H / 2 + 1);
  rodape.setTextColor(C_BG);
  rodape.drawString("Aprovar", xa + BTN_W / 2, by + BTN_H / 2 + 1);
}

void desenharConfirmacao() {
  int y0 = FOOT_TOP;
  static String l[2];
  int q = quebrar("Voce disse: " + voz.texto, l, 2, W - 32);
  rodape.setTextDatum(middle_left);
  rodape.setTextColor(C_FG);
  for (int i = 0; i < q; i++) rodape.drawString((i == 1 && rodape.textWidth(("Voce disse: " + voz.texto).c_str()) > 2 * (W - 32)) ? cortar(rodape, l[i] + "...", W - 32).c_str() : l[i].c_str(), 16, 249 + i * 14 - y0);
  int xr = 16, xa = 16 + BTN_W + 12, by = BTN_Y - y0;
  rodape.fillRect(xr, by, BTN_W, BTN_H, botaoApertado == 3 ? C_BAD : C_BG);
  rodape.drawRect(xr, by, BTN_W, BTN_H, C_BAD); rodape.drawRect(xr + 1, by + 1, BTN_W - 2, BTN_H - 2, C_BAD);
  rodape.fillRect(xa, by, BTN_W, BTN_H, botaoApertado == 4 ? C_FG : C_OK);
  rodape.setTextDatum(middle_center);
  rodape.setTextColor(botaoApertado == 3 ? C_BG : C_BAD);
  rodape.drawString("Descartar", xr + BTN_W / 2, by + BTN_H / 2 + 1);
  rodape.setTextColor(C_BG);
  rodape.drawString(tela == T_SESSAO ? "Enviar" : "Nova sessao", xa + BTN_W / 2, by + BTN_H / 2 + 1);
}

void desenharRodape() {
  rodape.fillScreen(C_BG);
  int y0 = FOOT_TOP;
  Sessao *s = tela == T_SESSAO ? sessaoAtual() : nullptr;
  if (voz.fase == V_CONFIRMAR) { desenharConfirmacao(); rodape.pushSprite(0, FOOT_TOP); return; }
  if (s && s->status == "waiting" && (m.estado == ALERTA) && voz.fase == V_NADA) { desenharAprovacao(*s); rodape.pushSprite(0, FOOT_TOP); return; }
  int bw = 6, gap = 4, total = 16 * bw + 15 * gap, bx = (W - total) / 2, base = FOOT_Y - 6;
  for (int i = 0; i < 16; i++) {
    int h = max(2, (int)roundf(m.bars[i] * 14) * 2);
    rodape.fillRect(bx + i * (bw + gap), base - h - y0, bw, h, m.bars[i] > .05f ? PALETAS[esc[CM_COR]][2] : C_DIM);
  }
  String txt; uint16_t cor = C_DIM; bool repouso = m.estado == REPOUSO || m.estado == TRABALHANDO || m.estado == ALERTA;
  if (millis() < voz.avisoAte) { txt = voz.aviso; cor = voz.avisoCor; repouso = true; }
  else if (m.estado == OUVINDO) { txt = "ouvindo... solte para enviar"; cor = C_FG; }
  else if (voz.fase == V_TRANSCREVENDO) txt = "transcrevendo...";
  else if (voz.fase == V_ENVIANDO) txt = "enviando...";
  else if (m.estado == PENSANDO) txt = "";
  else if (m.estado == RESPONDENDO) { txt = m.texto.substring(0, m.typed); cor = C_FG; }
  else if (s && esperandoRespId == s->id) { txt = "aguardando resposta..."; cor = C_DIM; }
  else if (s) { txt = s->last; cor = C_FG; }
  else if (m.estado == ALERTA) { txt = String(aguardando()) + " aguardando - toque no topo"; cor = C_WARN; }
  else if (respostaCasa.length()) { txt = respostaCasa; cor = C_FG; }
  else txt = micOk ? "segure e fale para criar uma sessao" : "microfone nao iniciou (confira os fios)";
  static String linhas[24];
  int qtd = quebrar(txt, linhas, 24, W - 48);
  int ini = repouso ? 0 : max(0, qtd - 2);
  rodape.setTextDatum(top_center);
  rodape.setTextColor(cor);
  for (int i = 0; i < 2 && ini + i < qtd; i++) {
    String l = linhas[ini + i];
    if (repouso && i == 1 && qtd > 2) l = cortar(rodape, l + "...", W - 48);
    rodape.drawString(l.c_str(), W / 2, FOOT_Y + 4 + i * 16 - y0);
  }
  rodape.pushSprite(0, FOOT_TOP);
}

// ---- desenho: cabecalhos e lista -----------------------------------------------------------
void desenharTopo() {  // tela do mascote
  tft.fillRect(0, 0, W, AREA_Y, C_BG);
  tft.setFont(&fonts::Font2);
  int n = aguardando();
  uint16_t cor = conexao == PONTE_OK ? (n ? C_WARN : C_OK) : conexao == CONECTANDO ? C_DIM : C_BAD;
  tft.fillRect(12, TOP_BAR / 2 - 3, 6, 6, cor);
  String rot = conexao == CONECTANDO ? "conectando ao Wi-Fi..." : conexao == SEM_WIFI ? "sem Wi-Fi" : conexao == SEM_PONTE ? "sem ponte"
             : n ? String(n) + " aguardando aprovacao" : "ponte ok - " + String(sessoes.size()) + " sessoes";
  tft.setTextDatum(middle_left);
  tft.setTextColor(conexao == PONTE_OK && !n ? C_DIM : cor, C_BG);
  tft.drawString(rot.c_str(), 26, TOP_BAR / 2 + 1);
  seta(tft, 26 + tft.textWidth(rot.c_str()) + 10, TOP_BAR / 2 - 1, conexao == PONTE_OK && !n ? C_DIM : cor, 'r');
  tft.setTextDatum(middle_right);
  tft.setTextColor(C_DIM, C_BG);
  tft.drawString(hora.c_str(), W - 48, TOP_BAR / 2 + 1);
  desenharCabide(tft, W - 30, 4, C_DIM);   // abre o Camarim
}

void desenharCabecalhoSessao() {
  Sessao *s = sessaoAtual();
  tft.fillRect(0, 0, W, HDR_S, C_PANEL);
  tft.fillRect(0, HDR_S - 1, W, 1, C_LINE);
  seta(tft, 15, HDR_S / 2 - 1, C_FG, 'l');
  if (!s) return;
  tft.setFont(&fonts::Font2);
  tft.setTextDatum(middle_left);
  tft.setTextColor(C_FG, C_PANEL);
  bool vinc = semRepoVps(s);
  int larg = vinc ? VINC_X - 44 - 8 : W - 44 - 90;
  tft.drawString(cortar(tft, s->title, larg).c_str(), 44, 15);
  tft.setTextColor(C_DIM, C_PANEL);
  tft.drawString(cortar(tft, s->repo.length() ? s->repo + " - " + s->branch : "avulsa", larg).c_str(), 44, 33);
  if (vinc) {
    tft.drawRect(VINC_X, 8, VINC_W, HDR_S - 16, C_BODY); tft.drawRect(VINC_X + 1, 9, VINC_W - 2, HDR_S - 18, C_BODY);
    tft.setTextDatum(middle_center);
    tft.setTextColor(C_FG, C_PANEL);
    tft.drawString("vincular repo", VINC_X + VINC_W / 2, HDR_S / 2 + 1);
    tft.setTextDatum(middle_left);
  }
  glifo(tft, s->status, W - 30, 15);
  int outras = aguardando() - (s->status == "waiting");
  if (outras > 0) {
    tft.fillRect(W - 70, 13, 28, 20, C_WARN);
    tft.setTextDatum(middle_center);
    tft.setTextColor(C_BG, C_WARN);
    tft.drawString(("!" + String(outras)).c_str(), W - 56, 24);
  }
}

int rolagem = 0;
std::vector<int> visiveis;          // indices de sessoes que passam no filtro
void recalcVisiveis() {
  visiveis.clear();
  for (size_t i = 0; i < sessoes.size(); i++)
    if (filtro == "" || (filtro == "-" ? sessoes[i].repo == "" : sessoes[i].repo == filtro)) visiveis.push_back(i);
}
int rolagemMax() { return max(0, (int)visiveis.size() * RH - (H - HDR)); }
String rotuloFiltro() { return filtro == "" ? "todas" : filtro == "-" ? "sem repositorio" : filtro.substring(filtro.indexOf('/') + 1); }

void desenharLista() {
  lista.fillScreen(C_BG);
  lista.setFont(&fonts::Font2);
  for (size_t k = 0; k < visiveis.size(); k++) {
    int y = k * RH - rolagem;
    if (y > H - HDR || y + RH < 0) continue;
    Sessao &s = sessoes[visiveis[k]];
    if (s.status == "waiting") lista.fillRect(0, y, W, RH - 1, C_WARN_BG);
    lista.fillRect(0, y + RH - 1, W, 1, C_LINE);
    glifo(lista, s.status, 14, y + 21);
    lista.setTextDatum(middle_left);
    lista.setTextColor(C_FG);
    lista.drawString(cortar(lista, s.title, W - 44 - 110).c_str(), 44, y + 20);
    lista.setTextColor(C_DIM);
    lista.drawString(cortar(lista, s.repo.length() ? s.repo + " - " + s.branch : "avulsa", W - 44 - 110).c_str(), 44, y + 40);
    lista.setTextDatum(middle_right);
    lista.drawString(s.ago.c_str(), W - 14, y + 20);
    lista.setTextColor(corStatus(s.status));
    lista.drawString(rotuloStatus(s.status), W - 14, y + 40);
  }
  if (visiveis.empty()) {
    lista.setTextDatum(middle_center);
    lista.setTextColor(C_DIM);
    lista.drawString(conexao != PONTE_OK ? "sem ponte: as sessoes aparecem quando ela responder"
                     : sessoes.empty() ? "nenhuma sessao: toque em + para criar" : ("nenhuma sessao em " + rotuloFiltro()).c_str(), W / 2, 120);
  }
  if (millis() < voz.avisoAte) {     // aviso por cima da lista
    lista.fillRect(0, H - HDR - 28, W, 28, C_PANEL);
    lista.setTextDatum(middle_center);
    lista.setTextColor(voz.avisoCor);
    lista.drawString(cortar(lista, voz.aviso, W - 20).c_str(), W / 2, H - HDR - 14);
  }
  int mx = rolagemMax();
  if (mx > 0) {
    int trilho = H - HDR - 8, polegar = max(24, trilho * (H - HDR) / (int)(visiveis.size() * RH));
    lista.fillRect(W - 4, 4, 2, trilho, C_LINE);
    lista.fillRect(W - 4, 4 + (trilho - polegar) * rolagem / mx, 2, polegar, C_DIM);
  }
  lista.pushSprite(0, HDR);
}

void desenharCabecalhoLista() {
  tft.fillRect(0, 0, W, HDR, C_PANEL);
  tft.fillRect(0, HDR - 1, W, 1, C_LINE);
  seta(tft, 15, HDR / 2 - 1, C_FG, 'l');
  tft.setFont(&fonts::Font2);
  tft.setTextDatum(middle_left);
  tft.setTextColor(C_FG, C_PANEL);
  tft.drawString("Sessoes", 44, HDR / 2 + 1);
  // filtro por repositorio
  bool on = filtro != "";
  int bx = 150, bw = 264;
  tft.fillRect(bx, 6, bw, 24, C_BG);
  tft.drawRect(bx, 6, bw, 24, on ? C_BODY : C_LINE); tft.drawRect(bx + 1, 7, bw - 2, 22, on ? C_BODY : C_LINE);
  tft.setTextColor(on ? C_FG : C_DIM, C_BG);
  tft.drawString(cortar(tft, "repo: " + rotuloFiltro(), bw - 40).c_str(), bx + 10, 19);
  const int D[5][2] = {{-6, -3}, {-3, 0}, {0, 3}, {3, 0}, {6, -3}};
  for (auto &d : D) tft.fillRect(bx + bw - 18 + d[0], 17 + d[1], 3, 3, on ? C_BODY : C_DIM);
  // criar sessao
  tft.fillRect(424, 4, 44, 28, C_BODY);
  tft.fillRect(437, 16, 18, 4, C_BG); tft.fillRect(444, 9, 4, 18, C_BG);
}

// ---- menu (filtro, repositorios, branches) ----------------------------------------------------
constexpr int MH = 48;
int menuRolagemMax() { return max(0, (int)menuItens.size() * MH - (H - HDR)); }

void desenharMenu() {
  lista.fillScreen(C_BG);
  lista.setFont(&fonts::Font2);
  if (menuCarregando.length()) {
    lista.setTextDatum(middle_center);
    lista.setTextColor(C_DIM);
    lista.drawString(menuCarregando.c_str(), W / 2, 110);
  }
  for (size_t i = 0; !menuCarregando.length() && i < menuItens.size(); i++) {
    int y = i * MH - menuRolagem;
    if (y > H - HDR || y + MH < 0) continue;
    ItemMenu &it = menuItens[i];
    bool atual = menuTipo == M_FILTRO && it.valor == filtro;
    lista.fillRect(0, y + MH - 1, W, 1, C_LINE);
    if (atual) lista.fillRect(0, y, 4, MH - 1, C_BODY);
    lista.setTextDatum(middle_left);
    lista.setTextColor(atual ? C_BODY : C_FG);
    lista.drawString(cortar(lista, it.rotulo, W - 40 - 150).c_str(), 18, y + MH / 2);
    lista.setTextDatum(middle_right);
    lista.setTextColor(C_DIM);
    lista.drawString(cortar(lista, it.sub, 140).c_str(), W - 18, y + MH / 2);
  }
  if (millis() < voz.avisoAte) {
    lista.fillRect(0, H - HDR - 28, W, 28, C_PANEL);
    lista.setTextDatum(middle_center);
    lista.setTextColor(voz.avisoCor);
    lista.drawString(cortar(lista, voz.aviso, W - 20).c_str(), W / 2, H - HDR - 14);
  }
  int mx = menuRolagemMax();
  if (mx > 0) {
    int trilho = H - HDR - 8, polegar = max(24, trilho * (H - HDR) / (int)(menuItens.size() * MH));
    lista.fillRect(W - 4, 4, 2, trilho, C_LINE);
    lista.fillRect(W - 4, 4 + (trilho - polegar) * menuRolagem / mx, 2, polegar, C_DIM);
  }
  lista.pushSprite(0, HDR);
}

void desenharCabecalhoMenu() {
  tft.fillRect(0, 0, W, HDR, C_PANEL);
  tft.fillRect(0, HDR - 1, W, 1, C_LINE);
  seta(tft, 15, HDR / 2 - 1, C_FG, 'l');
  tft.setFont(&fonts::Font2);
  tft.setTextDatum(middle_left);
  tft.setTextColor(C_FG, C_PANEL);
  tft.drawString(cortar(tft, menuTitulo, W - 60).c_str(), 44, HDR / 2 + 1);
}

// ---- navegacao -----------------------------------------------------------------------------
void redesenharTudo() {
  assinaturaMascote = assinaturaRodape = 0xFFFFFFFF;  // forca o redesenho no proximo quadro
  if (tela == T_LISTA) { recalcVisiveis(); desenharCabecalhoLista(); desenharLista(); return; }
  if (tela == T_MENU) { desenharCabecalhoMenu(); desenharMenu(); return; }
  if (tela == T_CAMARIM) { desenharCamarimBase(tft); desenharColuna(coluna); coluna.pushSprite(CAM_X, 0); return; }
  if (tela == T_SESSAO) desenharCabecalhoSessao(); else desenharTopo();
}

void irPara(Tela t, const String &id = "") {
  tela = t;
  if (id.length()) atualId = id;
  if (t == T_SESSAO) { Sessao *s = sessaoAtual(); if (s) replyVisto(s->id) = hashTxt(s->reply); }  // nao repete resposta velha
  if (t == T_LISTA) { recalcVisiveis(); rolagem = min(rolagem, rolagemMax()); }
  if (t == T_MASCOTE || t == T_SESSAO || t == T_CAMARIM) entrar(estadoDeRepouso());
  if (t == T_CAMARIM) camarimRolagem = min(camarimRolagem, camarimRolagemMax());
  tft.fillScreen(C_BG);  // troca de tela: limpa tudo uma vez
  redesenharTudo();
  Serial.printf("tela: %s %s\n", t == T_MASCOTE ? "mascote" : t == T_LISTA ? "lista" : t == T_MENU ? "menu" : t == T_CAMARIM ? "camarim" : "sessao", t == T_SESSAO ? atualId.c_str() : "");
}

uint32_t ultimaAtividade = 0;      // ultimo toque ou mudanca nas sessoes (para o cochilo)
uint32_t assinaturaSessoes = 0;
// Gatilhos de comemorar/dancinha: compara o status de cada sessao antes e depois da leitura.
void gatilhosSessoes(const std::vector<Sessao> &antes) {
  bool algumaTerminou = false, aindaAtivas = false, haviaAtivas = false;
  for (auto &a : antes) haviaAtivas |= a.status == "working" || a.status == "waiting";
  for (auto &n : sessoes) {
    if (n.status == "working" || n.status == "waiting") aindaAtivas = true;
    if (n.status != "done") continue;
    for (auto &a : antes) if (a.id == n.id && (a.status == "working" || a.status == "waiting")) algumaTerminou = true;
  }
  uint32_t h = 2166136261u;
  for (auto &n : sessoes) h = (h ^ hashTxt(n.id)) * 16777619u ^ hashTxt(n.status);
  if (h != assinaturaSessoes) { assinaturaSessoes = h; ultimaAtividade = millis(); }
  bool novoPedido = false;   // alguma sessao acabou de pedir aprovacao: aviso sonoro
  for (auto &n : sessoes) {
    if (n.status != "waiting") continue;
    bool ja = false;
    for (auto &a : antes) if (a.id == n.id && a.status == "waiting") ja = true;
    novoPedido |= !ja;
  }
  if (novoPedido) tocarSom(S_AVISO);
  if (!algumaTerminou || m.estado == OUVINDO || voz.fase == V_GRAVANDO) return;
  cochiloAuto = false;
  tocarAnim(haviaAtivas && !aindaAtivas ? A_DANCINHA : A_COMEMORAR, relogio());   // todas concluidas: dancinha
  Serial.printf("animacao: %s\n", ANIMS[animId].nome);
}

void dadosNovos() {
  std::vector<Sessao> antes = sessoes;
  xSemaphoreTake(trava, portMAX_DELAY);
  sessoes = redeSessoes; hora = redeHora; conexao = redeLink; versaoVista = redeVersao;
  xSemaphoreGive(trava);
  if (conexao == PONTE_OK) gatilhosSessoes(antes);
  if (tela == T_SESSAO && !sessaoAtual() && conexao == PONTE_OK) { irPara(T_LISTA); return; }
  bool conversando = m.estado == OUVINDO || m.estado == PENSANDO || m.estado == RESPONDENDO || voz.fase != V_NADA;
  Sessao *sa = tela == T_SESSAO ? sessaoAtual() : nullptr;
  if (sa && esperandoRespId == sa->id && sa->status == "waiting") esperandoRespId = "";
  if (sa && !conversando && sa->status != "waiting" && sa->reply.length()) {
    uint32_t &visto = replyVisto(sa->id), h = hashTxt(sa->reply);
    if (h != visto && sa->status != "working") {   // resposta nova e completa: digita inteira
      visto = h; esperandoRespId = "";
      entrar(RESPONDENDO);
      redesenharTudo();
      return;
    }
  }
  if ((tela == T_MASCOTE || tela == T_SESSAO || tela == T_CAMARIM) && !conversando) {
    Estado e = estadoDeRepouso();
    if (e != m.estado) entrar(e);
  }
  if (tela == T_MENU || tela == T_CAMARIM) return;   // o menu e o Camarim nao dependem das sessoes
  if (tela == T_LISTA) { recalcVisiveis(); rolagem = min(rolagem, rolagemMax()); }
  redesenharTudo();
}

// ---- voz, sessao nova e menus -----------------------------------------------------------------
String jsonCorpo(JsonDocument &d) { String s; serializeJson(d, s); return s; }

void abrirMenu(Menu tipo, const String &titulo, const String &carregando) {
  if (tela != T_MENU) telaAntesDoMenu = tela;
  menuTipo = tipo; menuTitulo = titulo; menuCarregando = carregando; menuRolagem = 0;
  if (carregando.length()) menuItens.clear();
  irPara(T_MENU);
}

void abrirFiltro() {
  menuItens.clear();
  menuItens.push_back({"todas", String(sessoes.size()), ""});
  std::vector<String> repos;
  int semRepo = 0;
  for (auto &s : sessoes) {
    if (!s.repo.length()) { semRepo++; continue; }
    if (std::find(repos.begin(), repos.end(), s.repo) == repos.end()) repos.push_back(s.repo);
  }
  std::sort(repos.begin(), repos.end(), [](const String &a, const String &b) { return a.compareTo(b) < 0; });
  for (auto &r : repos) {
    int n = 0; for (auto &s : sessoes) n += s.repo == r;
    menuItens.push_back({r.substring(r.indexOf('/') + 1), String(n) + (n > 1 ? " sessoes" : " sessao"), r});
  }
  if (semRepo) menuItens.push_back({"sem repositorio", String(semRepo), "-"});
  abrirMenu(M_FILTRO, "Filtrar por repositorio", "");
}

void comecarNovaSessao(const String &texto) {
  novaTexto = texto; vinculando = false;
  if (!pedirRede(PR_REPOS, false, "/api/repos")) { avisar("aguarde: a ponte esta ocupada", C_DIM); return; }
  abrirMenu(M_REPOS, "Nova sessao: repositorio", "carregando repositorios...");
}

void abrirVincular() {
  Sessao *s = sessaoAtual();
  if (!semRepoVps(s)) return;
  if (!pedirRede(PR_REPOS, false, "/api/repos")) { avisar("aguarde: a ponte esta ocupada", C_DIM); return; }
  vinculando = true; vincularId = s->id;
  abrirMenu(M_REPOS, "Vincular repositorio", "carregando repositorios...");
}

void criarSessao(const String &repo, const String &branch) {
  JsonDocument d;
  d["origem"] = "vps";
  if (repo.length()) d["repo"] = repo; else d["repo"] = nullptr;
  if (branch.length()) d["branch"] = branch; else d["branch"] = nullptr;
  d["titulo"] = novaTexto.length() ? novaTexto.substring(0, 50) : "Sessao do mascote";
  if (novaTexto.length()) d["prompt"] = novaTexto; else d["prompt"] = nullptr;
  if (!pedirRede(PR_CRIAR, true, "/api/sessoes", jsonCorpo(d))) { avisar("aguarde: a ponte esta ocupada", C_DIM); return; }
  menuCarregando = "criando a sessao...";
  desenharMenu();
}

void escolheuRepo(const ItemMenu &it) {
  if (it.valor == "-") { criarSessao("", ""); return; }   // sessao sem repositorio
  novaRepo = it.valor;
  if (!pedirRede(PR_BRANCHES, false, "/api/repos/" + it.valor + "/branches")) { avisar("aguarde: a ponte esta ocupada", C_DIM); return; }
  // guarda a branch padrao no titulo do menu seguinte
  abrirMenu(M_BRANCHES, "Branch de " + it.rotulo + (it.sub.length() ? " (padrao " + it.sub + ")" : ""), "carregando branches...");
  menuCarregando = "carregando branches...";
  novaRepo = it.valor;
}

void escolheuBranch(const ItemMenu &it) {
  if (!vinculando) { criarSessao(novaRepo, it.valor); return; }
  JsonDocument d;
  d["repo"] = novaRepo; d["branch"] = it.valor;
  if (!pedirRede(PR_VINCULAR, true, "/api/sessoes/" + vincularId + "/vincular", jsonCorpo(d))) { avisar("aguarde: a ponte esta ocupada", C_DIM); return; }
  menuCarregando = "vinculando o repositorio...";
  desenharMenu();
}

void terminarFala() {
  gravando = false;
  size_t n = nAmostras;
  if (n < (size_t)TAXA / 2) { voz.fase = V_NADA; entrar(estadoDeRepouso()); avisar("muito curto: segure enquanto fala", C_DIM); return; }
  if (!pedirRede(PR_VOZ, true, "/api/voz", "", (const uint8_t *)audio, n * sizeof(int16_t))) {
    voz.fase = V_NADA; entrar(estadoDeRepouso()); avisar("aguarde: a ponte esta ocupada", C_DIM); return;
  }
  voz.fase = V_TRANSCREVENDO;
  tocarSom(S_ENVIAR);
  entrar(PENSANDO);
  Serial.printf("voz: %.1f s gravados\n", n / (float)TAXA);
}

void confirmarFala() {
  if (tela == T_SESSAO) {
    Sessao *s = sessaoAtual();
    if (!s) { voz.fase = V_NADA; return; }
    JsonDocument d; d["texto"] = voz.texto;
    if (!pedirRede(PR_MSG, true, "/api/sessoes/" + s->id + "/mensagem", jsonCorpo(d))) { avisar("aguarde: a ponte esta ocupada", C_DIM); return; }
    voz.fase = V_ENVIANDO;
    assinaturaRodape = 0xFFFFFFFF;
  } else {
    voz.fase = V_NADA;
    comecarNovaSessao(voz.texto);
  }
}

String erroDe(const String &resp) {
  JsonDocument d;
  if (deserializeJson(d, resp)) return "";
  return String((const char *)(d["erro"] | ""));
}

void resultadoRede() {
  if (trabProposito == PR_NADA) return;
  int cod; String resp; bool pronto;
  xSemaphoreTake(trava, portMAX_DELAY);
  pronto = trabFeitoId == trabId;
  if (pronto) { cod = trabCod; resp = trabResp; }
  xSemaphoreGive(trava);
  if (!pronto) return;
  Proposito p = trabProposito;
  trabProposito = PR_NADA;
  String erro = cod > 0 ? erroDe(resp) : (cod == -1 ? "sem ponte" : "rede");
  bool falhou = (p == PR_VOZ && cod != 200) || (p == PR_MSG && cod != 202) || ((p == PR_REPOS || p == PR_BRANCHES) && cod != 200)
                || ((p == PR_CRIAR || p == PR_VINCULAR) && cod != 202);
  if (falhou) { cochiloAuto = false; tocarAnim(A_TONTO, relogio()); }   // a ponte respondeu erro (ou nao respondeu)
  switch (p) {
    case PR_VOZ: {
      JsonDocument d;
      String txt = (cod == 200 && !deserializeJson(d, resp)) ? String((const char *)(d["texto"] | "")) : "";
      txt.trim();
      if (cod == 200 && txt.length()) { voz.texto = txt; voz.fase = V_CONFIRMAR; }
      else {
        voz.fase = V_NADA;
        avisar(cod == 200 ? "nao entendi: tente de novo" : cod == 503 ? "transcricao desligada na VPS" : "transcricao falhou (" + String(cod) + ")", cod == 200 ? C_DIM : C_BAD);
      }
      entrar(estadoDeRepouso());
      break;
    }
    case PR_MSG:
      voz.fase = V_NADA;
      if (cod == 202) { avisar("enviado", C_OK); if (Sessao *s = sessaoAtual()) esperandoRespId = s->id; }
      else if (cod == 409) avisar("sessao ocupada: espere ela parar", C_WARN);
      else if (cod == 403) avisar("so leitura: responda pelo app", C_WARN);
      else if (cod == 504) avisar("sem confirmacao: confira no app", C_WARN);
      else avisar("nao enviou (" + String(cod) + ") " + erro, C_BAD);
      entrar(estadoDeRepouso());
      break;
    case PR_REPOS: {
      JsonDocument d;
      if (cod != 200 || deserializeJson(d, resp)) { menuCarregando = "nao carregou (" + String(cod) + ") " + erro; desenharMenu(); break; }
      menuItens.clear();
      for (JsonObject o : d.as<JsonArray>()) {
        String nome = o["nome"] | "";
        menuItens.push_back({nome.substring(nome.indexOf('/') + 1), String((const char *)(o["branch_padrao"] | "")), nome});
      }
      std::sort(menuItens.begin(), menuItens.end(), [](const ItemMenu &a, const ItemMenu &b) { return a.rotulo.compareTo(b.rotulo) < 0; });
      if (!vinculando) menuItens.insert(menuItens.begin(), {"sem repositorio", "", "-"});
      menuCarregando = menuItens.empty() ? "nenhum repositorio" : "";
      if (tela == T_MENU && menuTipo == M_REPOS) desenharMenu();
      break;
    }
    case PR_BRANCHES: {
      JsonDocument d;
      if (cod != 200 || deserializeJson(d, resp)) { menuCarregando = "nao carregou (" + String(cod) + ") " + erro; desenharMenu(); break; }
      int ini = menuTitulo.indexOf("(padrao "), fim = menuTitulo.lastIndexOf(')');
      String padrao = ini >= 0 ? menuTitulo.substring(ini + 8, fim) : "";
      menuItens.clear();
      for (JsonObject o : d.as<JsonArray>()) {
        String b = o["nome"] | "";
        ItemMenu it{b, b == padrao ? "padrao" : "", b};
        if (b == padrao) menuItens.insert(menuItens.begin(), it); else menuItens.push_back(it);
      }
      menuCarregando = menuItens.empty() ? "nenhuma branch" : "";
      if (tela == T_MENU && menuTipo == M_BRANCHES) desenharMenu();
      break;
    }
    case PR_CRIAR:
      if (cod == 202) { avisar("sessao criada: aparece na lista em instantes", C_OK); filtro = ""; irPara(T_LISTA); }
      else { menuCarregando = ""; avisar("nao criou (" + String(cod) + ") " + erro, C_BAD); desenharMenu(); }
      break;
    case PR_VINCULAR:
      vinculando = false; menuCarregando = "";
      if (cod == 202) avisar("repo vinculado", C_OK);
      else if (cod == 409) avisar("espere a sessao parar", C_WARN);
      else avisar("nao vinculou (" + String(cod) + ") " + erro, C_BAD);
      irPara(T_SESSAO, vincularId);
      break;
    default: break;
  }
}

void agir(const char *tipo) {
  Sessao *s = sessaoAtual();
  if (!s) return;
  xSemaphoreTake(trava, portMAX_DELAY);
  acaoId = s->id; acaoTipo = tipo;
  xSemaphoreGive(trava);
  // otimista: a tela muda na hora; a proxima leitura da ponte confirma
  bool ok = strcmp(tipo, "aprovar") == 0;
  s->last = String(ok ? "Aprovado: " : "Recusado: ") + s->askText + (ok ? ". Enviando..." : ".");
  s->status = ok ? "working" : "idle";
  s->askTool = s->askText = "";
  Serial.printf("acao: %s\n", tipo);
  entrar(estadoDeRepouso());
  redesenharTudo();
}

// ---- Camarim: escolha na NVS e toques ----------------------------------------------------------
void carregarVisual() {
  prefs.begin("mascote", true);
  for (int c = 0; c < N_CAMADAS; c++) {
    uint8_t v = prefs.getUChar(CHAVE_CAMADA[c], esc[c]);
    esc[c] = v < N_ITENS[c] ? v : esc[c];
  }
  prefs.end();
}
void salvarCamada(int c) {
  prefs.begin("mascote", false);
  prefs.putUChar(CHAVE_CAMADA[c], esc[c]);
  prefs.end();
}
void trocarItem(int c, int passo) {
  esc[c] = (esc[c] + N_ITENS[c] + passo) % N_ITENS[c];
  salvarCamada(c);
  Serial.printf("camarim: %s = %s\n", NOME_CAMADA[c], ITENS[c][esc[c]]);
}
void sortearVisual() {
  for (int c = 0; c < N_CAMADAS; c++) {
    esc[c] = (c == CM_FUNDO && rnd() < .5f) ? FUN_LISO : (uint8_t)(esp_random() % N_ITENS[c]);
    salvarCamada(c);
  }
}
void redesenharColuna() { desenharColuna(coluna); coluna.pushSprite(CAM_X, 0); desenharCamarimBase(tft); }

// corpo na tela (para as cocegas), igual ao alvo da previa (x 140..340, y 90..250 com BY=96)
bool noCorpo(int x, int y) {
  int dx = tela == T_CAMARIM ? CAM_DX : 0, top = 90 - PBY + BODY_Y + alturaChapeu();
  return x >= 140 + dx && x < 340 + dx && y >= top && y < top + 160 && y < FOOT_TOP;
}

void tocouCamarim(int x, int y) {
  if (x < CAM_X) {
    if (x >= CAM_VOLTAR_X && x < CAM_VOLTAR_X + CAM_VOLTAR_W && y >= CAM_VOLTAR_Y - 6) { pararAnim(); irPara(T_MASCOTE); return; }
    if (noCorpo(x, y)) { tocarAnim(A_COCEGAS, relogio()); redesenharColuna(); }
    return;
  }
  if (y < CAM_ABA) { int aba = x < CAM_X + 80 ? 0 : 1; if (aba != camarimAba) { camarimAba = aba; camarimRolagem = 0; redesenharColuna(); } return; }
  int k = (y - CAM_ABA + camarimRolagem) / CAM_LH;
  if (k < 0 || k >= camarimLinhas()) return;
  if (camarimAba == 0) {
    Anim a = (Anim)(k + 1);
    cochiloAuto = false;
    if (animId == a) pararAnim(); else tocarAnim(a, relogio());
  } else if (k < N_CAMADAS) trocarItem(k, x < CAM_X + CAM_W / 2 ? -1 : 1);   // metade esquerda '<', direita '>'
  else sortearVisual();
  redesenharColuna();
}

// ---- toque ----------------------------------------------------------------------------------
struct {
  bool ativo = false, arrastando = false, falando = false;
  int x0 = 0, y0 = 0, x = 0, y = 0, rolagem0 = 0;
  uint32_t desde = 0, ultimo = 0;
} toque;

bool areaDeFala(int x, int y) {
  if (tela != T_MASCOTE && tela != T_SESSAO) return false;
  if (voz.fase != V_NADA || trabProposito != PR_NADA) return false;
  int topo = tela == T_SESSAO ? HDR_S : TOP_HIT;
  if (y < topo || y >= FOOT_TOP) return false;
  return true;
}

int botaoEm(int x, int y) {
  if (voz.fase == V_CONFIRMAR && (tela == T_MASCOTE || tela == T_SESSAO) && y >= BTN_Y - 6 && y <= BTN_Y + BTN_H + 6) {
    if (x >= 16 && x < 16 + BTN_W) return 3;
    if (x >= 16 + BTN_W + 12 && x < W - 16) return 4;
    return 0;
  }
  if (voz.fase != V_NADA) return 0;
  Sessao *s = sessaoAtual();
  if (tela != T_SESSAO || !s || s->status != "waiting" || y < BTN_Y - 6 || y > BTN_Y + BTN_H + 6) return 0;
  if (x >= 16 && x < 16 + BTN_W) return 1;
  if (x >= 16 + BTN_W + 12 && x < W - 16) return 2;
  return 0;
}

void tocou(int x, int y) {
  tocarSom(S_CLIQUE);
  int b0 = botaoEm(x, y);
  if (b0 == 3) { voz.fase = V_NADA; avisar("descartado", C_DIM); entrar(estadoDeRepouso()); return; }
  if (b0 == 4) { confirmarFala(); return; }
  if (tela == T_MASCOTE) {
    if (y < TOP_HIT && voz.fase == V_NADA) { if (x >= W - 60) irPara(T_CAMARIM); else irPara(T_LISTA); }
    return;
  }
  if (tela == T_CAMARIM) { tocouCamarim(x, y); return; }
  if (tela == T_LISTA) {
    if (y < HDR) {
      if (x < 120) irPara(T_MASCOTE);
      else if (x >= 150 && x < 414) abrirFiltro();
      else if (x >= 420) comecarNovaSessao("");
      return;
    }
    int k = (y - HDR + rolagem) / RH;
    if (k >= 0 && k < (int)visiveis.size()) irPara(T_SESSAO, sessoes[visiveis[k]].id);
    return;
  }
  if (tela == T_MENU) {
    if (y < HDR) {
      if (x >= 120) return;
      if (menuTipo == M_BRANCHES) { if (vinculando) abrirVincular(); else comecarNovaSessao(novaTexto); return; }
      if (vinculando) { vinculando = false; irPara(T_SESSAO, vincularId); return; }
      irPara(menuTipo == M_FILTRO ? T_LISTA : telaAntesDoMenu);
      return;
    }
    if (menuCarregando.length()) return;
    int k = (y - HDR + menuRolagem) / MH;
    if (k < 0 || k >= (int)menuItens.size()) return;
    ItemMenu it = menuItens[k];
    if (menuTipo == M_FILTRO) { filtro = it.valor; rolagem = 0; irPara(T_LISTA); }
    else if (menuTipo == M_REPOS) escolheuRepo(it);
    else escolheuBranch(it);
    return;
  }
  if (tela == T_SESSAO) {
    if (y < HDR_S) {
      if (x < 120) irPara(T_LISTA);
      else if (x >= VINC_X && x < VINC_X + VINC_W && voz.fase == V_NADA && semRepoVps(sessaoAtual())) abrirVincular();
      return;
    }
    int b = botaoEm(x, y);
    if (b == 1) agir("recusar");
    if (b == 2) agir("aprovar");
  }
}

void lerToque(uint32_t agora) {
  int32_t tx, ty;
  bool leu = tft.getTouch(&tx, &ty);
  if (leu) { toque.ultimo = agora; toque.x = tx; toque.y = ty; }
  bool apertado = leu || (toque.ativo && agora - toque.ultimo < 150);  // o resistivo falha por instantes
  if (apertado && !toque.ativo) {
    ultimaAtividade = agora;
    if (animId == A_COCHILO) {   // qualquer toque acorda, e esse toque nao abre nada
      pararAnim(); cochiloAuto = false;
      if (tela == T_CAMARIM) redesenharColuna();
      toque = {}; toque.ativo = true; toque.arrastando = toque.falando = true; toque.desde = toque.ultimo = agora;   // nao grava nem abre
      return;
    }
    toque = {};
    toque.ativo = true; toque.x0 = toque.x = tx; toque.y0 = toque.y = ty; toque.desde = toque.ultimo = agora; toque.rolagem0 = rolagem;
    int b = botaoEm(tx, ty);
    if (b) { botaoApertado = b; assinaturaRodape = 0xFFFFFFFF; }
    if (tela == T_MENU) toque.rolagem0 = menuRolagem;
    if (tela == T_CAMARIM) toque.rolagem0 = camarimRolagem;
  } else if (apertado) {
    int dy = toque.y - toque.y0;
    if (tela == T_CAMARIM) {
      if (abs(dy) > 8 && toque.x0 >= CAM_X) toque.arrastando = true;
      int nova = constrain(toque.rolagem0 - dy, 0, camarimRolagemMax());
      if (toque.arrastando && abs(nova - camarimRolagem) >= 3) { camarimRolagem = nova; desenharColuna(coluna); coluna.pushSprite(CAM_X, 0); }
    } else if (tela == T_LISTA || tela == T_MENU) {
      if (abs(dy) > 8) toque.arrastando = true;
      if (toque.arrastando && tela == T_LISTA) {
        int nova = constrain(toque.rolagem0 - dy, 0, rolagemMax());
        if (abs(nova - rolagem) >= 3) { rolagem = nova; desenharLista(); }
      }
      if (toque.arrastando && tela == T_MENU) {
        int nova = constrain(toque.rolagem0 - dy, 0, menuRolagemMax());
        if (abs(nova - menuRolagem) >= 3) { menuRolagem = nova; desenharMenu(); }
      }
    } else if (!toque.falando && agora - toque.desde > 250 && areaDeFala(toque.x0, toque.y0) && !botaoEm(toque.x0, toque.y0)) {
      toque.falando = true;
      if (!micOk) avisar("microfone nao iniciou: confira os fios", C_BAD);
      else { tocarSom(S_GRAVAR); nAmostras = 0; gravando = true; voz.fase = V_GRAVANDO; entrar(OUVINDO); }
    }
  } else if (toque.ativo) {
    toque.ativo = false;
    if (botaoApertado) { botaoApertado = 0; assinaturaRodape = 0xFFFFFFFF; }
    if (toque.falando) { if (voz.fase == V_GRAVANDO) terminarFala(); }
    else if (!toque.arrastando && agora - toque.desde < 250 && tela == T_MASCOTE && toque.y0 >= TOP_HIT && voz.fase == V_NADA && noCorpo(toque.x0, toque.y0)) {
      cochiloAuto = false; tocarAnim(A_COCEGAS, relogio());   // toque curto no corpo: cocegas (segurar continua sendo voz)
    }
    else if (!toque.arrastando && agora - toque.desde < 800) tocou(toque.x0, toque.y0);
  }
}

// ---- programa principal ---------------------------------------------------------------------
uint32_t ultimoQuadro = 0;

// Gatilhos que dependem do tempo: resposta de /api/acao, ponte fora, cochilo e arrumar o bigode.
void gatilhosLoop(uint32_t agora) {
  int cod;
  xSemaphoreTake(trava, portMAX_DELAY);
  cod = acaoCod; acaoCod = 0;
  xSemaphoreGive(trava);
  if (cod) {
    bool aprovar = cod > 0 && (cod & 0x10000);
    int http = cod > 0 ? (cod & 0xFFFF) : cod;
    cochiloAuto = false;
    tocarAnim(http == 200 ? (aprovar ? A_APROVADO : A_RECUSADO) : A_TONTO, relogio());
  }
  static uint32_t foraDesde = 0; static bool avisouFora = false;
  if (conexao == PONTE_OK) { foraDesde = 0; avisouFora = false; }
  else if (!foraDesde) foraDesde = agora;
  else if (!avisouFora && agora - foraDesde > 60000) { avisouFora = true; cochiloAuto = false; tocarAnim(A_TONTO, relogio()); }
  bool parado = animId == A_NENHUMA && m.estado == REPOUSO && voz.fase == V_NADA && trabProposito == PR_NADA && !toque.ativo;
  if (tela == T_MASCOTE && parado && agora - ultimaAtividade > 10UL * 60 * 1000) { cochiloAuto = true; tocarAnim(A_COCHILO, relogio()); }
  static uint32_t proximoBigode = 0;
  if (!proximoBigode || !parado) proximoBigode = agora + 180000 + esp_random() % 180000;   // 3 a 6 min de repouso
  if (parado && (tela == T_MASCOTE || tela == T_SESSAO) && esc[CM_BIGODE] == BIG_GUIDAO && agora >= proximoBigode) {
    tocarAnim(A_ARRUMAR, relogio());
    proximoBigode = 0;
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  tft.init();
  tft.setRotation(1);
  tft.setBrightness(220);
  C_BG = tft.color565(0x14, 0x12, 0x10);   C_FLOOR = tft.color565(0x1b, 0x16, 0x13); C_SHADOW = tft.color565(0x0b, 0x09, 0x08);
  C_HI = tft.color565(0xf0, 0xa0, 0x7c);   C_MID = tft.color565(0xe5, 0x89, 0x6a);   C_BODY = tft.color565(0xd9, 0x77, 0x57);
  C_LO = tft.color565(0xbf, 0x64, 0x46);   C_DEEP = tft.color565(0x8f, 0x47, 0x31);  C_FG = tft.color565(0xed, 0xe6, 0xdc);
  C_DIM = tft.color565(0x8a, 0x81, 0x78);  C_OK = tft.color565(0x6f, 0xbf, 0x73);    C_BAD = tft.color565(0xe0, 0x67, 0x5a);
  C_WARN = tft.color565(0xe6, 0xb4, 0x50); C_WARN_HI = tft.color565(0xf6, 0xd2, 0x7e); C_WARN_BG = tft.color565(0x23, 0x1b, 0x0f);
  C_PANEL = tft.color565(0x1a, 0x16, 0x13); C_LINE = tft.color565(0x2a, 0x24, 0x20);
  tft.fillScreen(C_BG);

  for (LGFX_Sprite *s : {&area, &rodape, &lista, &coluna}) { s->setPsram(true); s->setColorDepth(16); }
  if (!area.createSprite(AREA_W, AREA_H) || !rodape.createSprite(W, FOOT_H) || !lista.createSprite(W, H - HDR) || !coluna.createSprite(CAM_W, H)) {
    tft.setTextColor(TFT_RED); tft.drawString("Sem memoria: confira PSRAM = OPI PSRAM", 10, 150);
    Serial.println("Falha ao criar os desenhos: PSRAM esta em OPI PSRAM nas Ferramentas?");
    while (true) delay(1000);
  }
  rodape.setFont(&fonts::Font2);
  carregarVisual();
  iniciarCeu();
  for (auto &e : emitT) e = -1e9f;

  trava = xSemaphoreCreateMutex();
  xTaskCreatePinnedToCore(tarefaRede, "rede", 12288, nullptr, 1, nullptr, 0);

  audio = (int16_t *)ps_malloc(MAX_AMOSTRAS * sizeof(int16_t));
#if SOM
  mic.setPins(PIN_MIC_SCK, PIN_MIC_WS, PIN_AMP_DIN, PIN_MIC_SD);   // full duplex: microfone no 17, som no 18
#else
  pinMode(PIN_AMP_DIN, OUTPUT);
  digitalWrite(PIN_AMP_DIN, LOW);
  mic.setPins(PIN_MIC_SCK, PIN_MIC_WS, -1, PIN_MIC_SD);
#endif
  micOk = audio && mic.begin(I2S_MODE_STD, TAXA, I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO, I2S_STD_SLOT_LEFT);
  if (micOk) xTaskCreatePinnedToCore(tarefaAudio, "audio", 4096, nullptr, 2, nullptr, 1);
#if SOM
  if (micOk) {
    filaSom = xQueueCreate(4, sizeof(Som));
    xTaskCreatePinnedToCore(tarefaSom, "som", 4096, nullptr, 1, nullptr, 1);
  }
#endif
  else Serial.println("microfone: falhou ao iniciar o I2S (fios SCK 15, WS 16, SD 17?)");

  entrar(REPOUSO);
  redesenharTudo();
  ultimoQuadro = ultimaAtividade = millis();
  Serial.printf("memoria livre: interna %u B, PSRAM %u B\n", (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL), (unsigned)ESP.getFreePsram());
}

void loop() {
  uint32_t agora = millis();
  float dt = (agora - ultimoQuadro) / 1000.0f;
  ultimoQuadro = agora;

  if (redeVersao != versaoVista) dadosNovos();
  resultadoRede();
  lerToque(agora);
  // aviso que acabou de expirar na lista/menu: redesenha para apagar a faixa
  static bool avisoAtivo = false;
  bool av = millis() < voz.avisoAte;
  if (av != avisoAtivo) { avisoAtivo = av; if (tela == T_LISTA) desenharLista(); if (tela == T_MENU) desenharMenu(); }

  gatilhosLoop(agora);
  if (tela == T_MASCOTE || tela == T_SESSAO || tela == T_CAMARIM) {
    atualizar(dt);
    uint32_t a = m.estado;
    a = a * 31u + (m.blinkT >= 0);
    a = a * 31u + (uint32_t)(m.eyeDx + 2);
    a = a * 31u + (uint32_t)(m.eyeH * 10);
    a = a * 31u + (uint32_t)(m.eyeDy * 10 + 20);
    a = a * 31u + (uint32_t)m.mouth;
    if (m.estado == PENSANDO || m.estado == TRABALHANDO) a = a * 31u + (uint32_t)(m.t * 4) % 4;
    if (m.estado == ALERTA) a = a * 31u + (uint32_t)(m.t * 3) % 2;
    a = a * 31u + animId + esc[CM_CABECA] * 7u + esc[CM_OLHOS] * 11u + esc[CM_BIGODE] * 13u + esc[CM_BOCA] * 17u + esc[CM_PEITO] * 19u
        + esc[CM_MAO] * 23u + esc[CM_COR] * 29u + esc[CM_FUNDO] * 37u + tela * 41u;
    // em repouso so redesenha quando muda; com animacao, particulas ou fundo animado, ate ~25 quadros/s
    bool movendo = cenaAnimada() || m.estado == ALERTA || m.estado == TRABALHANDO || m.estado == OUVINDO;
    static uint32_t ultimoDesenho = 0;
    if ((movendo && agora - ultimoDesenho >= 40) || a != assinaturaMascote) { desenharMascote(); assinaturaMascote = a; ultimoDesenho = agora; }
    uint32_t b = m.estado * 7u + m.typed * 131u + botaoApertado * 17u + versaoVista * 1009u + voz.fase * 7919u + av * 104729u
               + voz.texto.length() * 31u + (uint32_t)voz.avisoAte;
    for (int i = 0; i < 16; i++) b = b * 31u + (uint32_t)(m.bars[i] * 14);
    if (b != assinaturaRodape && tela != T_CAMARIM) { desenharRodape(); assinaturaRodape = b; }
  }
  delay(16);
}
