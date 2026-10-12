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

// ---- geometria (igual ao prototipo web) ------------------------------------------------
constexpr int W = 480, H = 320, PW = 15, PH = 30;
constexpr int BODY_W = 18, BODY_H = 5;
constexpr int EYE_L = 5, EYE_R = 12, EYE_ROW = 1;
constexpr int BODY_X = (W - BODY_W * PW) / 2;  // 105
constexpr int BODY_Y = 68;
constexpr int TOP_BAR = 28, TOP_HIT = 40, FOOT_Y = H - 44;
constexpr int HDR = 36, HDR_S = 46, RH = 58;
constexpr int BTN_Y = 272, BTN_H = 40, BTN_W = (W - 32 - 12) / 2;
constexpr int AREA_X = 88, AREA_Y = 48, AREA_W = 316, AREA_H = 194;  // abaixo do cabecalho da sessao
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
      if (!abrirPonte(http, cliente, "/api/acao")) { Serial.println("acao descartada: ponte indisponivel"); }
      else {
      http.addHeader("X-Token", PONTE_TOKEN);
      http.addHeader("Content-Type", "application/json");
      int cod = http.POST("{\"id\":\"" + id + "\",\"acao\":\"" + tipo + "\"}");
      Serial.printf("acao %s em %s: HTTP %d\n", tipo.c_str(), id.c_str(), cod);
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
constexpr int TAXA = 16000, MAX_SEG = 20, MAX_AMOSTRAS = TAXA * MAX_SEG;
I2SClass mic;
int16_t *audio = nullptr;          // PSRAM: ate 20 s de PCM 16 bits (640 KB)
volatile bool gravando = false;
volatile size_t nAmostras = 0;
volatile float nivelMic = 0;       // volume atual (0..1), para as barras
bool micOk = false;

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
      if (gravando && nAmostras < (size_t)MAX_AMOSTRAS) audio[nAmostras++] = (int16_t)constrain((int)y, -32768, 32767);
    }
    nivelMic = soma / n / 32768.0f;
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
bool solido(int x, int y) { return y >= 0 && y < BODY_H && x >= 0 && x < BODY_W && SPRITE[y][x] == '#'; }
void px(int x, int y, int w, int h, uint16_t c) { area.fillRect(x - AREA_X, y - AREA_Y, w, h, c); }

void desenharMascote() {
  area.fillScreen(C_BG);
  int cx = BODY_X + BODY_W * PW / 2, fy = BODY_Y + BODY_H * PH;
  const int fl[3][2] = {{300, 0}, {240, 6}, {180, 12}};
  for (auto &f : fl) px(cx - f[0] / 2, fy + 3 + f[1], f[0], 6, C_FLOOR);
  const int sh[3] = {210, 150, 90};
  for (int i = 0; i < 3; i++) px(cx - sh[i] / 2, fy + 3 + i * 6, sh[i], 6, C_SHADOW);
  for (int y = 0; y < BODY_H; y++)
    for (int x = 0; x < BODY_W; x++) {
      if (!solido(x, y)) continue;
      int X = BODY_X + x * PW, Y = BODY_Y + y * PH;
      bool perna = y == BODY_H - 1;
      px(X, Y, PW, PH, perna ? C_LO : C_BODY);
      if (!solido(x - 1, y)) px(X, Y, 4, PH, perna ? C_BODY : C_MID);
      if (!solido(x, y - 1)) px(X, Y, PW, 6, C_HI);
      if (!solido(x + 1, y)) px(X + PW - 4, Y, 4, PH, perna ? C_DEEP : C_LO);
      if (!solido(x, y + 1)) px(X, Y + PH - 8, PW, 8, perna ? C_DEEP : C_LO);
    }
  if (m.blinkT < 0) {
    for (int ex : {EYE_L, EYE_R}) {
      int x = BODY_X + (ex + m.eyeDx) * PW, y = BODY_Y + (int)((EYE_ROW + m.eyeDy) * PH);
      px(x, y, PW, (int)(m.eyeH * PH), C_BG);
      px(x, y - 4, PW, 4, C_DEEP);
    }
  }
  if (m.mouth > 0) {
    int x = BODY_X + 8 * PW, y = BODY_Y + (int)(2.5f * PH), h = m.mouth * PH / 2;
    px(x, y, 2 * PW, h, C_BG);
    px(x, y - 4, 2 * PW, 4, C_DEEP);
  }
  if (m.estado == PENSANDO || m.estado == TRABALHANDO) {
    int passo = (int)(m.t * 4) % 4, d = 12, x0 = BODY_X + 15 * PW + 10, y0 = BODY_Y - 4;
    for (int i = 0; i < 3; i++) px(x0 + i * (d + 8), y0 - i * 6, d, d, i < passo ? C_FG : C_DIM);
  }
  if (m.estado == ALERTA) {
    uint16_t c = ((int)(m.t * 3) % 2) ? C_WARN_HI : C_WARN;
    int x = BODY_X + 15 * PW + 14;
    px(x, BODY_Y, 12, 26, c); px(x, BODY_Y + 34, 12, 12, c);
  }
  area.pushSprite(AREA_X, AREA_Y);
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
    rodape.fillRect(bx + i * (bw + gap), base - h - y0, bw, h, m.bars[i] > .05f ? C_BODY : C_DIM);
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
  tft.drawString(hora.c_str(), W - 12, TOP_BAR / 2 + 1);
}

void desenharCabecalhoSessao() {
  Sessao *s = sessaoAtual();
  tft.fillRect(0, 0, W, HDR_S, C_PANEL);
  tft.fillRect(0, HDR_S - 1, W, 1, C_LINE);
  tft.fillRect(0, HDR_S, W, AREA_Y - HDR_S, C_BG);
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
  if (tela == T_SESSAO) desenharCabecalhoSessao(); else desenharTopo();
}

void irPara(Tela t, const String &id = "") {
  tela = t;
  if (id.length()) atualId = id;
  if (t == T_SESSAO) { Sessao *s = sessaoAtual(); if (s) replyVisto(s->id) = hashTxt(s->reply); }  // nao repete resposta velha
  if (t == T_LISTA) { recalcVisiveis(); rolagem = min(rolagem, rolagemMax()); }
  if (t == T_MASCOTE || t == T_SESSAO) entrar(estadoDeRepouso());
  tft.fillScreen(C_BG);  // troca de tela: limpa tudo uma vez
  redesenharTudo();
  Serial.printf("tela: %s %s\n", t == T_MASCOTE ? "mascote" : t == T_LISTA ? "lista" : t == T_MENU ? "menu" : "sessao", t == T_SESSAO ? atualId.c_str() : "");
}

void dadosNovos() {
  xSemaphoreTake(trava, portMAX_DELAY);
  sessoes = redeSessoes; hora = redeHora; conexao = redeLink; versaoVista = redeVersao;
  xSemaphoreGive(trava);
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
  if ((tela == T_MASCOTE || tela == T_SESSAO) && !conversando) {
    Estado e = estadoDeRepouso();
    if (e != m.estado) entrar(e);
  }
  if (tela == T_MENU) return;                    // o menu nao depende das sessoes
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
  int b0 = botaoEm(x, y);
  if (b0 == 3) { voz.fase = V_NADA; avisar("descartado", C_DIM); entrar(estadoDeRepouso()); return; }
  if (b0 == 4) { confirmarFala(); return; }
  if (tela == T_MASCOTE) { if (y < TOP_HIT && voz.fase == V_NADA) irPara(T_LISTA); return; }
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
    toque = {};
    toque.ativo = true; toque.x0 = toque.x = tx; toque.y0 = toque.y = ty; toque.desde = toque.ultimo = agora; toque.rolagem0 = rolagem;
    int b = botaoEm(tx, ty);
    if (b) { botaoApertado = b; assinaturaRodape = 0xFFFFFFFF; }
    if (tela == T_MENU) toque.rolagem0 = menuRolagem;
  } else if (apertado) {
    int dy = toque.y - toque.y0;
    if (tela == T_LISTA || tela == T_MENU) {
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
      else { nAmostras = 0; gravando = true; voz.fase = V_GRAVANDO; entrar(OUVINDO); }
    }
  } else if (toque.ativo) {
    toque.ativo = false;
    if (botaoApertado) { botaoApertado = 0; assinaturaRodape = 0xFFFFFFFF; }
    if (toque.falando) { if (voz.fase == V_GRAVANDO) terminarFala(); }
    else if (!toque.arrastando && agora - toque.desde < 800) tocou(toque.x0, toque.y0);
  }
}

// ---- programa principal ---------------------------------------------------------------------
uint32_t ultimoQuadro = 0;

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

  for (LGFX_Sprite *s : {&area, &rodape, &lista}) { s->setPsram(true); s->setColorDepth(16); }
  if (!area.createSprite(AREA_W, AREA_H) || !rodape.createSprite(W, FOOT_H) || !lista.createSprite(W, H - HDR)) {
    tft.setTextColor(TFT_RED); tft.drawString("Sem memoria: confira PSRAM = OPI PSRAM", 10, 150);
    Serial.println("Falha ao criar os desenhos: PSRAM esta em OPI PSRAM nas Ferramentas?");
    while (true) delay(1000);
  }
  rodape.setFont(&fonts::Font2);

  trava = xSemaphoreCreateMutex();
  xTaskCreatePinnedToCore(tarefaRede, "rede", 12288, nullptr, 1, nullptr, 0);

  audio = (int16_t *)ps_malloc(MAX_AMOSTRAS * sizeof(int16_t));
  mic.setPins(PIN_MIC_SCK, PIN_MIC_WS, -1, PIN_MIC_SD);
  micOk = audio && mic.begin(I2S_MODE_STD, TAXA, I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO, I2S_STD_SLOT_LEFT);
  if (micOk) xTaskCreatePinnedToCore(tarefaAudio, "audio", 4096, nullptr, 2, nullptr, 1);
  else Serial.println("microfone: falhou ao iniciar o I2S (fios SCK 15, WS 16, SD 17?)");

  entrar(REPOUSO);
  redesenharTudo();
  ultimoQuadro = millis();
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

  if (tela == T_MASCOTE || tela == T_SESSAO) {
    atualizar(dt);
    uint32_t a = m.estado;
    a = a * 31u + (m.blinkT >= 0);
    a = a * 31u + (uint32_t)(m.eyeDx + 2);
    a = a * 31u + (uint32_t)(m.eyeH * 10);
    a = a * 31u + (uint32_t)(m.eyeDy * 10 + 20);
    a = a * 31u + (uint32_t)m.mouth;
    if (m.estado == PENSANDO || m.estado == TRABALHANDO) a = a * 31u + (uint32_t)(m.t * 4) % 4;
    if (m.estado == ALERTA) a = a * 31u + (uint32_t)(m.t * 3) % 2;
    if (a != assinaturaMascote) { desenharMascote(); assinaturaMascote = a; }
    uint32_t b = m.estado * 7u + m.typed * 131u + botaoApertado * 17u + versaoVista * 1009u + voz.fase * 7919u + av * 104729u
               + voz.texto.length() * 31u + (uint32_t)voz.avisoAte;
    for (int i = 0; i < 16; i++) b = b * 31u + (uint32_t)(m.bars[i] * 14);
    if (b != assinaturaRodape) { desenharRodape(); assinaturaRodape = b; }
  }
  delay(16);
}
