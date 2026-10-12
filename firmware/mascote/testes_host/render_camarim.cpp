// Gera imagens (PPM) de quadros do Camarim usando o MESMO codigo de desenho do firmware.
// O bloco entre "// >>> HOST" e "// <<< HOST" de mascote.ino e extraido para camarim_host.inc
// (ver render_camarim.sh) e compilado aqui com uma LovyanGFX de mentira (so retangulos;
// o texto vira uma barra cinza, porque a fonte da placa nao existe no host).
// Uso: ./render_camarim.sh <pasta de saida>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <algorithm>
#include "tipos.h"

constexpr float PI = 3.14159265358979f;
constexpr int W = 480, H = 320, PW = 15, PH = 30, BODY_W = 18, BODY_H = 5, BODY_X = 105, BODY_Y = 68;
constexpr int TOP_BAR = 28, AREA_X = 0, AREA_Y = TOP_BAR, AREA_W = W, AREA_H = 242 - TOP_BAR, FOOT_TOP = AREA_Y + AREA_H;
const char *SPRITE[BODY_H] = {"...############...", "...############...", ".################.", "...############...", "....#.#....#.#...."};

static uint16_t tela[H][W];
uint32_t semente = 12345;
float rnd() { semente = semente * 1664525u + 1013904223u; return (semente >> 8) / 16777216.0f; }
uint32_t esp_random() { return (uint32_t)(rnd() * 4294967295.0f); }

// LovyanGFX minima: desenha num retangulo da tela (x0,y0,w,h) com recorte
enum { middle_left, middle_center, top_center };
namespace fonts { struct F {}; inline F Font2, Font4; }
struct LovyanGFX {
  int x0 = 0, y0 = 0, w = W, h = H, cx = 0, cy = 0, cw = W, ch = H, datum = 0; uint16_t tc = 0xFFFF;
  void fillRect(int x, int y, int ww, int hh, uint16_t c) {
    int a = std::max({x, cx, 0}), b = std::max({y, cy, 0}), e = std::min({x + ww, cx + cw, w}), f = std::min({y + hh, cy + ch, h});
    for (int j = b; j < f; j++) for (int i = a; i < e; i++) if (j + y0 >= 0 && j + y0 < H && i + x0 >= 0 && i + x0 < W) tela[j + y0][i + x0] = c;
  }
  void drawRect(int x, int y, int ww, int hh, uint16_t c) { fillRect(x, y, ww, 1, c); fillRect(x, y + hh - 1, ww, 1, c); fillRect(x, y, 1, hh, c); fillRect(x + ww - 1, y, 1, hh, c); }
  void fillScreen(uint16_t c) { fillRect(0, 0, w, h, c); }
  void setFont(fonts::F *) {}
  void setTextDatum(int d) { datum = d; }
  void setTextColor(uint16_t c, uint16_t = 0) { tc = c; }
  void setClipRect(int x, int y, int ww, int hh) { cx = x; cy = y; cw = ww; ch = hh; }
  void clearClipRect() { cx = cy = 0; cw = w; ch = h; }
  void drawString(const char *s, int x, int y) {   // texto: um bloco 5x8 por letra (sem fonte no host)
    int n = strlen(s), tw = n * 7;
    int xi = datum == middle_left ? x : x - tw / 2, yi = datum == top_center ? y : y - 4;
    for (int i = 0; i < n; i++) if (s[i] != ' ') fillRect(xi + i * 7, yi, 5, 8, tc);
  }
};
LovyanGFX area, coluna, tft;
uint16_t C_BG = 0x10A2, C_PANEL = 0x18A2, C_LINE = 0x2924, C_FG = 0xEF3B, C_DIM = 0x8C0F, C_BODY = 0xDBAA;
void px(int x, int y, int w, int h, uint16_t c) { area.fillRect(x - AREA_X, y - AREA_Y, w, h, c); }
void textoCena(int x, int y, const char *t, uint16_t c) { area.setTextDatum(middle_center); area.setTextColor(c); area.drawString(t, x - AREA_X, y - AREA_Y); }
void seta(LovyanGFX &g, int x, int y, uint16_t c, char dir) {
  const int R[5][2] = {{0, -6}, {3, -3}, {6, 0}, {3, 3}, {0, 6}}, L[5][2] = {{6, -6}, {3, -3}, {0, 0}, {3, 3}, {6, 6}};
  for (int i = 0; i < 5; i++) { const int *p = dir == 'r' ? R[i] : L[i]; g.fillRect(x + p[0], y + p[1], 3, 3, c); }
}

#include "camarim_host.inc"

void salvar(const std::string &nome) {
  FILE *f = fopen(nome.c_str(), "wb");
  fprintf(f, "P6\n%d %d\n255\n", W, H);
  for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
    uint16_t c = tela[y][x]; unsigned char rgb[3] = {(unsigned char)((c >> 11) << 3), (unsigned char)(((c >> 5) & 63) << 2), (unsigned char)((c & 31) << 3)};
    fwrite(rgb, 1, 3, f);
  }
  fclose(f);
}

int foraDaArea = 0;   // conta pixels pintados fora do sprite (deveria ser 0: o sprite recorta)
void quadro(Anim a, float meio, int dxCena = 0) {
  memset(tela, 0, sizeof(tela));
  for (auto &p : parts) p.tipo = P_LIVRE;
  nParts = 0;
  for (auto &e : emitT) e = -1e9f;
  area.x0 = AREA_X; area.y0 = AREA_Y; area.w = AREA_W; area.h = AREA_H; area.clearClipRect();
  bigodeCurl = 0;
  if (a) tocarAnim(a, 0);
  // simula ate o instante "meio" a 25 quadros/s, para as particulas estarem no lugar
  float t = 0;
  for (; t < meio; t += .04f) {
    Quadro s; if (a) passo(a, s, t - animT0, t);
    cenaDx = dxCena; cenaDy = alturaChapeu();
    cena(s, t, .04f);
  }
  (void)t;
}

int main(int argc, char **argv) {
  std::string dir = argc > 1 ? argv[1] : ".";
  iniciarCeu();
  // 1) cartola + bigode guidao + fundo estrelas, em repouso
  esc[CM_CABECA] = CAB_CARTOLA; esc[CM_BIGODE] = BIG_GUIDAO; esc[CM_FUNDO] = FUN_ESTRELAS;
  quadro(A_NENHUMA, 1); salvar(dir + "/00_cartola_guidao_estrelas.ppm");
  // 2) cada animacao num quadro intermediario (com um visual variado)
  const float meio[N_ANIMS] = {0, 1.0f, 3.0f, 0.5f, 0.4f, 1.7f, 2.0f, 2.0f, 4.0f, 1.0f, 2.3f, 1.6f};
  const char *nomes[N_ANIMS] = {"", "comemorar", "aprovacao", "aprovado", "recusado", "tonto", "trabalhando", "ouvindo", "cochilo", "cocegas", "dancinha", "arrumar"};
  uint8_t visuais[N_ANIMS][N_CAMADAS] = {
    {}, {CAB_FESTA, OLH_ESCUROS, 0, 0, PEI_BORBOLETA, 0, COR_LARANJA, FUN_LISO}, {CAB_BONE, 0, BIG_CLASSICO, BOC_CIGARRO, 0, 0, COR_AZUL, FUN_GRAMA},
    {CAB_COROA, 0, 0, 0, PEI_GRAVATA, MAO_BANDEIRA, COR_VERDE, FUN_GRAMA}, {CAB_OBRA, 0, BIG_CLASSICO, 0, 0, MAO_CHAVE, COR_CINZA, FUN_LISO},
    {CAB_COWBOY, 0, BIG_GUIDAO, BOC_CIGARRO, PEI_CACHECOL, 0, COR_LARANJA, FUN_PORSOL}, {CAB_FONE, OLH_OCULOS, 0, 0, 0, MAO_CANECA, COR_ROXO, FUN_LISO},
    {CAB_NADA, OLH_TAPAOLHO, BIG_GUIDAO, BOC_CACHIMBO, PEI_CACHECOL, 0, COR_ROSA, FUN_ESTRELAS}, {CAB_NATAL, 0, 0, 0, PEI_CACHECOL, MAO_CANECA, COR_LARANJA, FUN_NEVE},
    {CAB_NADA, OLH_MONOCULO, 0, BOC_CHARUTO, 0, 0, COR_DOURADO, FUN_LISO}, {CAB_FESTA, OLH_ESCUROS, 0, 0, PEI_BORBOLETA, 0, COR_LARANJA, FUN_ESTRELAS},
    {CAB_CARTOLA, OLH_MONOCULO, BIG_GUIDAO, BOC_CHARUTO, PEI_BORBOLETA, 0, COR_LARANJA, FUN_LISO},
  };
  for (int a = 1; a < N_ANIMS; a++) {
    memcpy(esc, visuais[a], N_CAMADAS);
    quadro((Anim)a, meio[a]);
    char nome[64]; snprintf(nome, sizeof nome, "/%02d_%s.ppm", a, nomes[a]); salvar(dir + nome);
  }
  // 3) tela Camarim, abas Visual e Animar (cena empurrada para a esquerda, coluna a direita)
  esc[CM_CABECA] = CAB_CARTOLA; esc[CM_OLHOS] = OLH_NADA; esc[CM_BIGODE] = BIG_GUIDAO; esc[CM_BOCA] = BOC_NADA; esc[CM_PEITO] = PEI_BORBOLETA;
  esc[CM_MAO] = MAO_NADA; esc[CM_COR] = COR_LARANJA; esc[CM_FUNDO] = FUN_ESTRELAS;
  for (int aba = 0; aba < 2; aba++) {
    camarimAba = aba; camarimRolagem = 0;
    quadro(aba == 0 ? A_DANCINHA : A_NENHUMA, aba == 0 ? 1.2f : 1, CAM_DX);
    if (aba == 1) animId = A_NENHUMA;
    for (int y = AREA_Y; y < H; y++) for (int x = CAM_X; x < W; x++) tela[y][x] = 0;   // o firmware recorta a cena antes da coluna
    for (int y = 0; y < AREA_Y; y++) for (int x = 0; x < W; x++) tela[y][x] = C_BG;
    tft.x0 = tft.y0 = 0; tft.w = W; tft.h = H; desenharCamarimBase(tft);
    coluna.x0 = CAM_X; coluna.y0 = 0; coluna.w = CAM_W; coluna.h = H; desenharColuna(coluna);
    salvar(dir + (aba ? "/21_camarim_visual.ppm" : "/20_camarim_animar.ppm"));
  }
  // 4) cabide no canto superior direito da tela inicial
  memset(tela, 0, sizeof(tela)); tft.clearClipRect(); desenharCabide(tft, W - 30, 4, C_DIM); salvar(dir + "/30_cabide.ppm");
  printf("ok: %d imagens em %s\n", N_ANIMS + 3, dir.c_str());
  return 0;
}
