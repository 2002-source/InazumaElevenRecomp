// ============================================================================
//  ie1_mods.dll - complemento CARGADOR DE MODS para el port de Inazuma Eleven
//
//  Sin este archivo junto al ejecutable, el juego ignora los mods.
//  Con el: al arrancar, aplica en memoria (nunca en la ROM) los mods activos.
//
//  Estructura:
//    mods\mods.cfg            un mod activo por linea, en orden (# = comentario)
//    mods\<mod>\mod.txt       opcional: nombre, autor, descripcion
//    mods\<mod>\data_iz\...   archivos que sustituyen a los de la ROM, con la
//                             MISMA ruta que tienen dentro de ella
//  Si dos mods tocan el mismo archivo, gana el ultimo de mods.cfg.
//  Los mods se aplican despues del idioma.
//
//  Compilar: bash scripts/compilar_mods.sh
// ============================================================================
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <string>
#include <vector>
#include <sstream>
#include <iterator>
#include <ctime>

#include "ie1_ar.hpp"   // interprete de codigos Action Replay (trucos.txt)

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>         // GetKeyState (Ctrl en el menu de entrenamiento)
#define IE1_EXPORT extern "C" __declspec(dllexport)
#else
#define IE1_EXPORT extern "C" __attribute__((visibility("default")))
#endif

// Interfaz con el ejecutable (version 1). Debe coincidir con ie1_idiomas.cpp.
struct Ie1ModsHost {
    uint32_t version;
    void* ctx;
    uint8_t* (*datos)(void* ctx);
    size_t (*tamano)(void* ctx);
    int (*redimensionar)(void* ctx, size_t minimo);   // el host lo deja en potencia de dos
    void (*log)(const char* texto);
};

namespace {
const Ie1ModsHost* H = nullptr;
void (*g_log)(const char*) = nullptr;     // funcion de log del ejecutable (sigue valida despues)
std::vector<ArCode> g_trucos;          // codigos de trucos.txt de los mods activos
std::vector<uint8_t> g_unitno, g_unitstat;   // datos de jugadores (para la Libertad)
std::vector<uint8_t> g_curvas;               // status_up.dat: curvas de crecimiento (99 niveles, cada 0x68 bytes)
std::vector<uint8_t> g_lvup_exp;             // lvup_exp.dat: EXP por nivel (16 tipos x 98 u32, jugador +0x40 = tipo)
std::vector<uint32_t> g_fondo_abajo;         // fondo del menu de entrenamiento (256x192 ARGB)
std::vector<uint32_t> g_fondo_ficha;         // fondo de la ficha (pagina 2) para la pantalla de arriba
// Fondos del menu de entrenamiento por idioma: el diseno en espanol y en ingles (con sus
// etiquetas) y uno "limpio" sin textos, al que se le ponen las etiquetas del juego en el
// idioma elegido (pic2d/menu/en/msup_bg02.pac_, ya con el idioma). La pantalla de arriba
// sale de msup_bg03.pac_ (pagina 2 de la ficha) del idioma elegido.
std::vector<uint32_t> g_fondo_es, g_fondo_en, g_fondo_limpio;
std::vector<uint8_t> g_msup_bg02, g_msup_bg03;
std::vector<uint8_t> g_itemdat, g_cmddat, g_cmdstr;   // nombres de objetos y supertecnicas
std::string g_idioma_textos = "en";                     // idioma de los textos (en, es...)
// Texto del complemento en el idioma de los textos (en, es, fr, de, it; el resto, ingles)
inline int idioma_indice() {
    const std::string& l = g_idioma_textos;
    return l == "es" ? 1 : l == "fr" ? 2 : (l == "de" || l == "ge") ? 3 : l == "it" ? 4 : 0;
}
inline const char* T5(const char* en, const char* es, const char* fr, const char* de, const char* it) {
    const char* v[5] = {en, es, fr, de, it};
    return v[idioma_indice()];
}
std::vector<uint8_t> g_lvup;                          // umbrales de grado por categoria (lvup_command.dat)
std::vector<uint8_t> g_unitcalc;                      // coeficientes del "valor" de cada accion (unitcalc.dat)
// Panel de "Valor total" del juego (pic3d/en/mbd_*.pac_): digitos, panel izquierdo y derechos por equipo
std::vector<uint8_t> g_mbd_num, g_mbd_izq;
std::vector<uint8_t> g_exp_x2_pac;    // grafico "x2!!" del IE2 (mods/mecanicas_ie2/exp_x2.pac)
bool g_mod_valor = false;                              // mod "valor en las escenas" activo (valor.cfg)
bool g_mod_talentos = false;                           // mod "talentos del IE2" activo (talentos.cfg)
bool g_mod_colores = false;                            // mod "colores por afinidad" activo (colores.cfg)
bool g_mod_tiro = false;                               // mod "tiro del IE2" activo (tiro.cfg): boton T y tiro largo
bool g_mod_ojeo = false;                               // mod "ojeo instantaneo" activo (ojeo.cfg)
bool g_mod_filtros = false;                            // mod "filtros de supertecnicas" activo (filtros.cfg)
bool g_mod_capitan = false;                            // Mark se puede quitar del equipo tras el final (capitan.cfg)
bool g_mod_exp_x2 = false;                             // EXP x2 en encuentros ganados por 5+ sin encajar (exp_x2.cfg)
// El panel solo funciona con el mod activado (o IE1_VALOR=1 / IE1_VALOR_PRUEBA=1 para pruebas);
// IE1_POTENCIA=1 por si solo es el registro de calculos, sin panel.
bool ie1_valor_activo() {
    static const bool env = [] {
        const char* a = std::getenv("IE1_VALOR"); const char* b = std::getenv("IE1_VALOR_PRUEBA");
        return (a && *a == '1') || (b && *b == '1');
    }();
    return g_mod_valor || env;
}
std::map<int, std::vector<uint8_t>> g_mbd_der;
std::vector<uint8_t> g_fuente12, g_fuente8;           // fuentes del juego (NFTR)
std::vector<uint8_t> g_smstat;                        // sprites de la ficha (SMStat.SPF_, comprimido)
std::vector<uint8_t> g_z05;                           // etiquetas de tipo de tecnica (msup_z05.pac_)
std::vector<uint8_t> g_wd_l, g_wd_d, g_sh_l, g_sh_d;  // texturas de menu: waza_den (boton X) y shop (flechas)
std::vector<uint8_t> g_bkr;   // bocadillos de los jugadores (ply_bkr01): el cartel "Nv +" es su animacion 9
int g_bkr_anims = -1;         // (solo la tienen los del IE2; se cuenta al activar los niveles)
std::vector<uint8_t> g_fac_h, g_fac_b, g_fab_h, g_fab_b;  // caras: cabezas (fac) y cuerpos (fab)
std::vector<uint8_t> g_ih_h, g_ih_b;                  // iconos de cabeza de las listas (pic3d/ih)
std::vector<uint8_t> g_mbd_h, g_mbd_b;                // nombres de supertecnicas dibujados (pic2d/cmd/en/mbd_c)

// trucos.txt: codigos Action Replay, dos palabras hexadecimales por linea.
// Lineas vacias, con '#' o con '[' (titulos) se ignoran. Una linea vacia o un
// titulo separa codigos distintos.
unsigned cargar_trucos(const std::filesystem::path& p) {
    std::ifstream f(p);
    if (!f) return 0;
    unsigned n = 0;
    ArCode actual;
    auto cerrar = [&] { if (!actual.w.empty()) { g_trucos.push_back(actual); actual.w.clear(); ++n; } };
    for (std::string l; std::getline(f, l);) {
        while (!l.empty() && (l.back() == '\r' || l.back() == ' ' || l.back() == '\t')) l.pop_back();
        if (l.empty() || l[0] == '[') { cerrar(); continue; }
        if (l[0] == '#') continue;
        unsigned a = 0, b = 0;
        if (std::sscanf(l.c_str(), "%x %x", &a, &b) == 2) { actual.w.push_back(a); actual.w.push_back(b); }
    }
    cerrar();
    return n;
}

void logf(const char* fmt, ...) {
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    // OJO: H apunta a una estructura del ejecutable que solo existe mientras se
    // compone la ROM; despues se usa la funcion de log guardada (g_log).
    if (g_log) g_log(buf);
    else std::fprintf(stderr, "%s\n", buf);
}
uint8_t* D() { return H->datos(H->ctx); }
size_t N() { return H->tamano(H->ctx); }
uint32_t rd32(size_t o) {
    const uint8_t* r = D();
    return uint32_t{r[o]} | uint32_t{r[o + 1]} << 8 | uint32_t{r[o + 2]} << 16 | uint32_t{r[o + 3]} << 24;
}
void wr32(size_t o, uint32_t v) {
    uint8_t* r = D();
    r[o] = uint8_t(v); r[o + 1] = uint8_t(v >> 8); r[o + 2] = uint8_t(v >> 16); r[o + 3] = uint8_t(v >> 24);
}
bool leer(const std::filesystem::path& p, std::vector<uint8_t>& d) {
    std::ifstream f(p, std::ios::binary | std::ios::ate);
    if (!f) return false;
    const std::streamsize n = f.tellg();
    if (n < 0) return false;
    d.resize(size_t(n));
    f.seekg(0);
    return n == 0 || bool(f.read(reinterpret_cast<char*>(d.data()), n));
}
std::filesystem::path carpeta_mods() {
    if (const char* e = std::getenv("IE1_MODS_DIR"); e && *e) return e;
    std::error_code ec;
    for (const char* c : {"mods", "../mods"})
        if (std::filesystem::is_directory(c, ec)) return c;
    return "mods";
}
}  // namespace

// ---- Paquetes de Level-5 (.pkh indice + .pkb datos) ------------------------
//  .pkh: cabecera de 0x30 bytes ("PackNum..."; +0x10 tamano del pkh, +0x16 numero
//        de entradas, +0x1C tamano maximo de entrada), entradas de 12 bytes
//        (id, desplazamiento, tamano) ordenadas por id, y un cierre.
//  Combinar: sustituye o anade entradas (por id) sin tocar las demas.
IE1_EXPORT int ie1_pk_combinar(const uint8_t* h, size_t hn, const uint8_t* b, size_t bn,
                               const std::map<uint32_t, std::vector<uint8_t>>* cambios,
                               std::vector<uint8_t>* hsal, std::vector<uint8_t>* bsal) {
    // Las entradas originales se quedan EXACTAMENTE donde estaban (mismo
    // desplazamiento en el .pkb): las que cambian o se anaden van al final.
    // Asi nada que recuerde desplazamientos del paquete se descoloca.
    if (hn < 0x30 || std::memcmp(h, "PackNum", 7) != 0) return 0;
    auto r32 = [&](size_t o) { return uint32_t(h[o] | h[o + 1] << 8 | h[o + 2] << 16 | uint32_t(h[o + 3]) << 24); };
    const uint32_t n = h[0x16] | h[0x17] << 8;
    if (0x30 + size_t(n) * 12 > hn) return 0;
    std::map<uint32_t, std::pair<uint32_t, uint32_t>> ent;      // id -> (desplazamiento, tamano)
    for (uint32_t k = 0; k < n; ++k) {
        const uint32_t id = r32(0x30 + 12 * k), of = r32(0x34 + 12 * k), sz = r32(0x38 + 12 * k);
        if (size_t(of) + sz > bn) return 0;
        ent[id] = {of, sz};
    }
    bsal->assign(b, b + bn);
    uint32_t maxt = r32(0x1C);
    for (const auto& c : *cambios) {
        while (bsal->size() % 16) bsal->push_back(0);
        ent[c.first] = {uint32_t(bsal->size()), uint32_t(c.second.size())};
        bsal->insert(bsal->end(), c.second.begin(), c.second.end());
        maxt = std::max<uint32_t>(maxt, uint32_t(c.second.size()));
    }
    const std::vector<uint8_t> cierre(h + 0x30 + size_t(n) * 12, h + hn);
    hsal->assign(h, h + 0x30);
    auto w32 = [](std::vector<uint8_t>& v, uint32_t x) { for (int i = 0; i < 4; ++i) v.push_back(uint8_t(x >> (8 * i))); };
    for (const auto& e : ent) { w32(*hsal, e.first); w32(*hsal, e.second.first); w32(*hsal, e.second.second); }
    hsal->insert(hsal->end(), cierre.begin(), cierre.end());
    auto p32 = [&](size_t o, uint32_t x) { for (int i = 0; i < 4; ++i) (*hsal)[o + i] = uint8_t(x >> (8 * i)); };
    p32(0x10, uint32_t(hsal->size()));
    (*hsal)[0x16] = uint8_t(ent.size()); (*hsal)[0x17] = uint8_t(ent.size() >> 8);
    p32(0x1C, maxt);
    return 1;
}

// ---- Mod "tiro del IE2": graficos (se preparan al componer la ROM) ------------
// 1) Marcas L / B en los botones de supertecnica del partido, como el IE2:
//    los nombres de los botones son imagenes (pic2d/cmd/en/mbd_c.pkb, una pieza por
//    tecnica: paleta, mapa y 28 tiles = 112x16 px). El IE2 trae la marca dibujada
//    en la imagen: una "L" verde (color 4; "T" en espanol, frances e italiano) para los tiros largos (atributo 1 de
//    command.dat, byte +0x0F) y una "B" granate (color 5) para los bloqueos (2) y los
//    bloqueos de tiro (4), justo despues del nombre, arriba (filas 0..7). La paleta
//    del IE1 es la misma. Se hace sobre el archivo del idioma elegido, asi que vale
//    para todos. Si el nombre no deja sitio (la marca acabaria pasada la columna 83,
//    el limite que usa el IE2), se estrecha el nombre quitando columnas repetidas.
// 2) Boton T: el grafico del boton de tiro (pic3d/en/gmdn_c02.pac_) trae una "S"
//    (Shoot) en todas las versiones; con los textos en espanol, frances o italiano
//    se cambia por una "T" del mismo estilo en sus 11 dibujos (normal y contador).
namespace tirogfx {
const char* const kMarcaL[8] = {"FFFF....", "F44F....", "F44F....", "F44F....",
                                "F44FFFFF", "F444444F", "F444444F", "FFFFFFFF"};
const char* const kMarcaB[8] = {"FFFFFFF.", "F55555FF", "F55FF55F", "F55555FF",
                                "F55FF55F", "F55FF55F", "F55555FF", "FFFFFFF."};
// "T" verde de los tiros largos en espanol, frances e italiano (la L es "Lungo"/"Long"
// solo en ingles y aleman): copiada de los botones del IE2 de esos idiomas.
const char* const kMarcaT[8] = {"FFFFFFFF", "F444444F", "F444444F", "FFF44FFF",
                                "..F44F..", "..F44F..", "..F44F..", "..FFFF.."};
// La "T" del boton de tiro del IE2 en espanol, frances e italiano (pic3d/xx/common.pkb):
// columnas 5..18, filas 5..18 de cada dibujo de 24x24. Con la regla de boton_t sale
// el archivo del IE2 identico byte a byte (comprobado).
const char* const kLetraT[14] = {
    "6666666666666.", "6E999999999E61", "6EFFFFFFFFFE61", "6E999999999E61",
    "66666E9E666661", ".1116E9E611111", "....6E9E61....", "....6E9E61....",
    "....6E9E61....", "....6E9E61....", "....6E9E61....", "....6EEE61....",
    "....666661....", ".....11111...."};
int hexv(char c) { return c == '.' ? -1 : (c <= '9' ? c - '0' : c - 'A' + 10); }

// Pieza de mbd_c (sin comprimir): devuelve false si no tiene el formato esperado.
bool marcar_pieza(uint8_t* d, size_t n, const char* const marca[8]) {
    if (n < 64 || d[0] != 3 || d[1] || d[2] || d[3]) return false;
    auto u32 = [&](size_t o) { return uint32_t(d[o]) | uint32_t(d[o + 1]) << 8 | uint32_t(d[o + 2]) << 16 | uint32_t(d[o + 3]) << 24; };
    const uint32_t mo = u32(12), ml = u32(16), po = u32(20), pl = u32(24);
    if (ml != 56 || pl != 28u * 32u || size_t(po) + pl > n || size_t(mo) + ml > n) return false;
    for (uint32_t k = 0; k < 28; ++k)                       // mapa: tiles 0..27 en orden
        if (uint32_t(d[mo + 2 * k] | d[mo + 2 * k + 1] << 8) != k) return false;
    uint8_t g[16][112];
    for (int t = 0; t < 28; ++t)
        for (int i = 0; i < 32; ++i) {
            const uint8_t b = d[po + t * 32 + i];
            const int x = (t % 14) * 8 + (i % 4) * 2, y = (t / 14) * 8 + i / 4;
            g[y][x] = b & 15; g[y][x + 1] = b >> 4;
        }
    int xi = 112, xf = -1;
    for (int y = 0; y < 16; ++y)
        for (int x = 0; x < 112; ++x)
            if (g[y][x]) { xi = std::min(xi, x); xf = std::max(xf, x); }
    if (xf < 0) return false;
    for (int y = 0; y < 8; ++y)                             // ya tiene marca (color 4 o 5 arriba)
        for (int x = 0; x < 112; ++x)
            if (g[y][x] == 4 || g[y][x] == 5) return false;
    const int limite = 83 - 8;                              // ultima columna del nombre
    if (xf > limite) {                                      // estrechar: quitar columnas repetidas
        std::vector<int> cols;
        for (int x = xi; x <= xf; ++x) cols.push_back(x);
        int sobra = xf - limite;
        auto igual = [&](int a, int b) { for (int y = 0; y < 16; ++y) if (g[y][a] != g[y][b]) return false; return true; };
        std::vector<int> rep;                               // columnas iguales a la anterior
        for (size_t k = 1; k < cols.size(); ++k) if (igual(cols[k], cols[k - 1])) rep.push_back(int(k));
        std::vector<bool> quitar(cols.size(), false);
        const int nq = std::min<int>(sobra, int(rep.size()));
        for (int q = 0; q < nq; ++q) quitar[size_t(rep[size_t((q * 2 + 1) * int(rep.size()) / (2 * nq))])] = true;
        sobra -= nq;
        for (int q = 0; q < sobra; ++q) {                   // si aun falta: repartidas a lo largo
            size_t k = size_t((q * 2 + 1) * int(cols.size()) / (2 * sobra));
            while (k < cols.size() && quitar[k]) ++k;
            if (k < cols.size()) quitar[k] = true;
        }
        uint8_t h[16][112] = {};
        int x2 = xi;
        for (size_t k = 0; k < cols.size(); ++k) {
            if (quitar[k]) continue;
            for (int y = 0; y < 16; ++y) h[y][x2] = g[y][cols[k]];
            ++x2;
        }
        for (int y = 0; y < 16; ++y)
            for (int x = xi; x < 112; ++x) g[y][x] = h[y][x];
        xf = x2 - 1;
    }
    const int x0 = xf + 1;
    for (int y = 0; y < 8; ++y)
        for (int x = 0; x < 8; ++x) {
            const int v = hexv(marca[y][x]);
            if (v >= 0 && x0 + x < 112) g[y][x0 + x] = uint8_t(v);
        }
    for (int t = 0; t < 28; ++t)
        for (int i = 0; i < 32; ++i) {
            const int x = (t % 14) * 8 + (i % 4) * 2, y = (t / 14) * 8 + i / 4;
            d[po + t * 32 + i] = uint8_t(g[y][x] | g[y][x + 1] << 4);
        }
    return true;
}

std::vector<uint8_t> lz10_des(const std::vector<uint8_t>& d) {
    std::vector<uint8_t> o;
    if (d.size() < 4 || d[0] != 0x10) return o;
    const size_t n = d[1] | d[2] << 8 | d[3] << 16;
    size_t p = 4;
    while (o.size() < n && p < d.size()) {
        const uint8_t f = d[p++];
        for (int b = 0; b < 8 && o.size() < n && p < d.size(); ++b) {
            if (f & (0x80 >> b)) {
                if (p + 1 >= d.size()) return {};
                const int x = d[p] << 8 | d[p + 1]; p += 2;
                const size_t l = size_t(x >> 12) + 3, ds = size_t(x & 0xFFF) + 1;
                if (ds > o.size()) return {};
                for (size_t k = 0; k < l; ++k) o.push_back(o[o.size() - ds]);
            } else o.push_back(d[p++]);
        }
    }
    if (o.size() > n) o.resize(n);
    return o.size() == n ? o : std::vector<uint8_t>{};
}
std::vector<uint8_t> lz10_literal(const std::vector<uint8_t>& d) {   // LZ10 valido sin repeticiones
    std::vector<uint8_t> o = {0x10, uint8_t(d.size()), uint8_t(d.size() >> 8), uint8_t(d.size() >> 16)};
    for (size_t i = 0; i < d.size(); i += 8) {
        o.push_back(0);
        for (size_t k = i; k < std::min(d.size(), i + 8); ++k) o.push_back(d[k]);
    }
    while (o.size() % 4) o.push_back(0);
    return o;
}

// gmdn_c02 (ya descomprimido): S -> T en los dibujos de 24x24.
bool boton_t(std::vector<uint8_t>& d) {
    auto u32 = [&](size_t o) { return uint32_t(d[o]) | uint32_t(d[o + 1]) << 8 | uint32_t(d[o + 2]) << 16 | uint32_t(d[o + 3]) << 24; };
    auto u16 = [&](size_t o) { return uint32_t(d[o]) | uint32_t(d[o + 1]) << 8; };
    if (d.size() < 28 || u32(0) != 3) return false;
    const uint32_t po = u32(4), pl = u32(8), dso = u32(20), dsl = u32(24);
    if (size_t(po) + pl > d.size() || size_t(dso) + dsl > d.size() || dsl < 8) return false;
    const uint32_t nfr = u16(dso), w = 8u << d[dso + 2];
    if (nfr < 11 || dsl < 8 + 8 * nfr) return false;
    auto ci = [&](uint32_t x, uint32_t y) -> int {
        const size_t o = po + (size_t(y) * w + x) / 2;
        if (o >= size_t(po) + pl) return -1;
        return (x & 1) ? d[o] >> 4 : d[o] & 15;
    };
    auto pon = [&](uint32_t x, uint32_t y, int v) {
        const size_t o = po + (size_t(y) * w + x) / 2;
        d[o] = (x & 1) ? uint8_t((d[o] & 0x0F) | v << 4) : uint8_t((d[o] & 0xF0) | v);
    };
    const uint32_t fx = u16(dso + 8), fy = u16(dso + 10);
    if (u16(dso + 12) != 24 || u16(dso + 14) != 24) return false;
    int s[24][19], npix = 0;
    for (int y = 0; y < 24; ++y)
        for (int x = 0; x < 19; ++x) { s[y][x] = ci(fx + x, fy + y); if (s[y][x] < 0) return false; npix += s[y][x] > 0; }
    if (npix < 100) return false;
    for (uint32_t f = 0; f < nfr; ++f) {
        const uint32_t gx = u16(dso + 8 + 8 * f), gy = u16(dso + 10 + 8 * f);
        for (int y = 0; y < 24; ++y)
            for (int x = 0; x < 19; ++x) {
                const int act = ci(gx + x, gy + y);
                int nuevo = 0;
                if (y >= 5 && y < 19 && x >= 5) { const int v = hexv(kLetraT[y - 5][x - 5]); nuevo = v < 0 ? 0 : v; }
                if (act != s[y][x] && nuevo == 0) continue;   // numero del contador: se queda
                if (nuevo != act) pon(gx + x, gy + y, nuevo);
            }
    }
    return true;
}

template <class FArchivo, class FPoner>
void preparar(FArchivo&& archivo, FPoner&& poner, const std::string& idioma) {
    // Como el IE2: L (ingles, aleman) o T (espanol, frances, italiano) para los tiros
    // largos; B para los bloqueos en todos; boton de tiro con S o con T igual.
    const bool letra_t = idioma == "es" || idioma == "fr" || idioma == "it";
    std::vector<uint8_t> cmd, h, b;
    archivo("/data_iz/logic/en/command.dat", cmd);
    const int fh = archivo("/data_iz/pic2d/cmd/en/mbd_c.pkh", h), fb = archivo("/data_iz/pic2d/cmd/en/mbd_c.pkb", b);
    int nl = 0, nb = 0;
    if (fh >= 0 && fb >= 0 && cmd.size() >= 512 * 28) {
        for (size_t o = 0x30; o + 12 <= h.size(); o += 12) {
            const uint32_t id = h[o] | h[o + 1] << 8 | h[o + 2] << 16 | uint32_t(h[o + 3]) << 24;
            if (id == 0xFFFFFFFFu) break;
            const uint32_t of = h[o + 4] | h[o + 5] << 8 | h[o + 6] << 16 | uint32_t(h[o + 7]) << 24;
            const uint32_t sz = h[o + 8] | h[o + 9] << 8 | h[o + 10] << 16 | uint32_t(h[o + 11]) << 24;
            if (id >= 512 || size_t(of) + sz > b.size()) continue;
            const uint8_t at = cmd[id * 28 + 0x0F];
            const char* const* marca = (at & 1) ? (letra_t ? kMarcaT : kMarcaL) : (at & 6) ? kMarcaB : nullptr;
            if (!marca) continue;
            if (marcar_pieza(b.data() + of, sz, marca)) ((at & 1) ? nl : nb)++;
        }
        if (nl + nb && poner(uint32_t(fb), b))
            logf("[mods] tiro del IE2: marcas en los botones de supertecnica (%d %s, %d B)", nl, letra_t ? "T" : "L", nb);
    }
    if (letra_t) {
        std::vector<uint8_t> c;
        const int fc = archivo("/data_iz/pic3d/en/gmdn_c02.pac_", c);
        std::vector<uint8_t> d = lz10_des(c);
        if (fc >= 0 && !d.empty() && boton_t(d) && poner(uint32_t(fc), lz10_literal(d)))
            logf("[mods] tiro del IE2: boton de tiro con T (idioma %s)", idioma.c_str());
    }
}
}  // namespace tirogfx

// ---- Nombres de las supertecnicas con el color de su afinidad (como Victory Road) ------
// Afinidad = command.dat +8 (1 aire, 2 bosque, 3 fuego, 4 montana; 0 = sin afinidad).
//  - Cartel de la escena: pic3d/script/en/mbv_cNNN.pac_ (NNN = tecnica; LZ10; textura
//    4 bits). El texto es blanco (color 15) con sombra gris (5 y 2) y borde negro (1):
//    esos tres colores pasan a los del elemento, de claro a oscuro.
//  - Botones del selector del partido: piezas de pic2d/cmd/en/mbd_c.pkb (sin comprimir;
//    paleta en +4). El nombre va en rojo (color 9): pasa al color del elemento.
//    Las marcas L/T (color 4) y B (color 5) no se tocan.
namespace colores {
// Cada afinidad: relleno (claro), sombra (medio) y contorno (oscuro), del mismo color para
// que contraste con el relleno (antes el contorno era blanco o negro).
struct Tono { uint8_t relleno[3], sombra[3], contorno[3]; };
const Tono kTonos[5] = {
    {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}},                                   // (sin afinidad)
    {{112, 200, 255}, {40, 128, 232}, {0, 40, 128}},                     // aire: azul
    {{120, 224, 80}, {48, 176, 48}, {0, 80, 16}},                        // bosque: verde
    {{240, 8, 8}, {208, 40, 24}, {104, 0, 0}},                           // fuego: el rojo del juego
    {{248, 184, 96}, {192, 120, 40}, {96, 48, 8}},                       // montana: cafe
};
uint16_t bgr(const uint8_t c[3]) { return uint16_t((c[0] >> 3) | (c[1] >> 3) << 5 | (c[2] >> 3) << 10); }
uint16_t mezcla(const uint8_t a[3], const uint8_t b[3]) {
    const uint8_t m[3] = {uint8_t((a[0] + b[0]) / 2), uint8_t((a[1] + b[1]) / 2), uint8_t((a[2] + b[2]) / 2)};
    return bgr(m);
}
void poner16(uint8_t* p, uint16_t v) { p[0] = uint8_t(v); p[1] = uint8_t(v >> 8); }

// Piezas de mbd_c (112x16, 28 tiles en orden). Se ven en dos sitios con paletas distintas:
//  - menus (ficha, listas): con la paleta de la pieza, pero varias tecnicas a la vez
//    comparten UNA paleta (la de la ultima cargada);
//  - selector del partido: con la paleta del boton (pic2d/cmd/en/mbd_c000b.pac azul,
//    mbd_c000s.pac rojo), no con la de la pieza.
// Asi que cada afinidad usa sus propios indices de color, iguales en todas las piezas y en
// los botones. El nombre usa 9 (relleno rojo de ataque), 12 (relleno azul de defensa),
// 15 (contorno blanco) y 7 (sombra gris); las marcas L/T y B usan 4 (verde) y 5.
// El dibujo de los botones usa 1, 8, 10, 11, 14 (etiqueta "PT") y el fondo: 13 en el azul
// y 3 en el rojo. El rojo pasa su fondo de 3 a 13 (con el mismo color), asi 3 queda libre
// en los dos, ademas de 2 y 6. Y la sombra gris de los nombres sin afinidad (7) pasa al
// gris claro 8, asi 7 tambien queda libre.
//   rellenos: fuego 9 (el rojo de siempre), aire 2, bosque 4 (el verde de la marca L/T,
//   mas claro), montana 6;  contornos: aire 3 (azul marino), bosque 7 (verde oscuro),
//   fuego 5 (rojo oscuro; la marca B, que es granate, queda un poco mas oscura) y
//   montana 1 (marron oscuro). 12 se queda como estaba (nombres de defensa).
const uint8_t kRelleno[5] = {0, 2, 4, 9, 6}, kContorno[5] = {0, 3, 7, 5, 1};
const uint8_t kOscuroCalido[3] = {72, 32, 8}, kMarino[3] = {0, 16, 72}, kVerdeOscuro[3] = {0, 72, 16},
              kRojoOscuro[3] = {112, 0, 16};
void paleta_nombres(uint8_t* pal) {            // 16 colores BGR555
    for (int e = 1; e <= 4; ++e) poner16(pal + 2 * kRelleno[e], bgr(kTonos[e].relleno));
    poner16(pal + 2 * 1, bgr(kOscuroCalido));
    poner16(pal + 2 * 3, bgr(kMarino));
    poner16(pal + 2 * 5, bgr(kRojoOscuro));
    poner16(pal + 2 * 7, bgr(kVerdeOscuro));
}

// Carteles de la escena (pic2d/cmd/en/mbv_c.pkb y pic3d/script/en/mbv_cNNN): en un duelo
// los dos carteles comparten una paleta (la de la tecnica del jugador), asi que tambien
// van por indices: cada afinidad tiene relleno, sombra y contorno propios. Los normales
// usan 15 (blanco), 5 y 2 (grises) y 1 (negro); los dibujados a varios colores no se tocan.
const uint8_t kCartel[5][3] = {{15, 2, 1}, {3, 4, 6}, {7, 8, 9}, {10, 11, 12}, {13, 14, 5}};
const uint8_t kFuegoCartel[3] = {255, 104, 80};
void paleta_cartel(uint8_t* pal) {
    for (int e = 1; e <= 4; ++e) {
        const Tono& k = kTonos[e];
        const uint8_t* rel = e == 3 ? kFuegoCartel : k.relleno;   // el rojo de los botones es oscuro para el cartel
        poner16(pal + 2 * kCartel[e][0], bgr(rel));
        poner16(pal + 2 * kCartel[e][1], mezcla(rel, k.sombra));
        poner16(pal + 2 * kCartel[e][2], bgr(k.contorno));
    }
}
bool pintar_cartel(uint8_t* tex, uint32_t tl, uint8_t* pal, int el) {
    int otros = 0;
    for (uint32_t i = 0; i < tl; ++i)
        for (int c : {tex[i] & 15, tex[i] >> 4})
            if (c && c != 1 && c != 2 && c != 5 && c != 15) ++otros;
    if (otros > 8) return false;
    if (el < 0 || el > 4) el = 0;
    const uint8_t* k = kCartel[el];
    auto m = [&](int c) { return c == 15 ? k[0] : (c == 5 || c == 2) ? k[1] : c == 1 ? k[2] : c; };
    for (uint32_t i = 0; i < tl; ++i) tex[i] = uint8_t(m(tex[i] & 15) | m(tex[i] >> 4) << 4);
    paleta_cartel(pal);
    return true;
}
// Talentos (tipo 9, ids 51..75): nombre morado con contorno morado oscuro. Sus piezas usan
// el relleno 12 (como los nombres de defensa, que siguen azules): en las de talento 12 -> 13
// y 15/7 -> 14. 13 y 14 son morados en las paletas de las piezas, que usan los menus y,
// con colores_sel, tambien los nombres del selector del partido.
const uint8_t kMorado[3] = {216, 120, 255}, kMoradoOscuro[3] = {72, 16, 112};
bool pintar_boton(uint8_t* d, size_t n, int el, bool talento = false) {
    if (n < 64 || d[0] != 3 || d[1] || d[2] || d[3]) return false;
    auto u32 = [&](size_t o) { return uint32_t(d[o]) | uint32_t(d[o + 1]) << 8 | uint32_t(d[o + 2]) << 16 | uint32_t(d[o + 3]) << 24; };
    const uint32_t po = u32(4), mo = u32(12), ml = u32(16), to = u32(20), tl = u32(24);
    if (ml != 56 || tl != 28u * 32u || size_t(to) + tl > n || size_t(mo) + ml > n || size_t(po) + 32 > n) return false;
    for (uint32_t i = 0; i < 28; ++i)
        if (uint32_t(d[mo + 2 * i] | d[mo + 2 * i + 1] << 8) != i) return false;
    paleta_nombres(d + po);                 // los colores de las cuatro afinidades en todas
    poner16(d + po + 2 * 13, bgr(kMorado));  // talentos (solo en las piezas)
    poner16(d + po + 2 * 14, bgr(kMoradoOscuro));
    const uint32_t to2 = to;
    if (el < 1 || el > 4) {                 // sin afinidad: la sombra 7 pasa al gris claro 8
        auto m = [&](int c) { return talento ? (c == 12 ? 13 : (c == 15 || c == 7) ? 14 : c) : (c == 7 ? 8 : c); };
        for (uint32_t i = 0; i < tl; ++i) {
            uint8_t& b2 = d[to2 + i];
            b2 = uint8_t(m(b2 & 15) | m(b2 >> 4) << 4);
        }
        return true;
    }
    uint8_t g[16][112];
    for (int t = 0; t < 28; ++t)
        for (int i = 0; i < 32; ++i) {
            const uint8_t b = d[to + t * 32 + i];
            const int x = (t % 14) * 8 + (i % 4) * 2, y = (t / 14) * 8 + i / 4;
            g[y][x] = b & 15; g[y][x + 1] = b >> 4;
        }
    bool marca[16][112] = {};
    for (int y = 0; y < 16; ++y)
        for (int x = 0; x < 112; ++x)
            if (g[y][x] == 4 || g[y][x] == 5)
                for (int dy = -1; dy <= 1; ++dy)
                    for (int dx = -1; dx <= 1; ++dx)
                        if (y + dy >= 0 && y + dy < 16 && x + dx >= 0 && x + dx < 112) marca[y + dy][x + dx] = true;
    for (int y = 0; y < 16; ++y)
        for (int x = 0; x < 112; ++x) {
            if (marca[y][x]) continue;
            uint8_t& c = g[y][x];
            c = c == 9 ? kRelleno[el] : (c == 15 || c == 7) ? kContorno[el] : c;
        }
    for (int t = 0; t < 28; ++t)
        for (int i = 0; i < 32; ++i) {
            const int x = (t % 14) * 8 + (i % 4) * 2, y = (t / 14) * 8 + i / 4;
            d[to + t * 32 + i] = uint8_t(g[y][x] | g[y][x + 1] << 4);
        }
    return true;
}

template <class FIds, class FArchivo, class FPoner>
void preparar(const FIds& fids, FArchivo&& archivo, FPoner&& poner) {
    std::vector<uint8_t> cmd;
    archivo("/data_iz/logic/en/command.dat", cmd);
    if (cmd.size() < 512 * 28) return;
    auto afinidad = [&](uint32_t t) { return t < 512 ? int(cmd[t * 28 + 8]) : 0; };
    // 1) carteles: texto 15 (relleno), 5 y 2 (sombras) y 1 (contorno)
    int nc = 0;
    const std::string pre = "/data_iz/pic3d/script/en/mbv_c";
    for (const auto& f : fids) {
        const std::string& r = f.first;
        if (r.size() != pre.size() + 8 || r.compare(0, pre.size(), pre) || r.compare(r.size() - 5, 5, ".pac_")) continue;
        const int t = std::atoi(r.c_str() + pre.size());
        const int el = afinidad(uint32_t(t));
        if (t < 100 || t >= 512) continue;
        std::vector<uint8_t> c;
        if (archivo(r, c) < 0) continue;
        std::vector<uint8_t> d = tirogfx::lz10_des(c);
        auto u32 = [&](size_t o) { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0u; };
        if (d.size() < 28 || u32(0) < 2) continue;
        const uint32_t po = u32(12), pl = u32(16), t0 = u32(4), tl = u32(8);
        if (pl < 32 || size_t(po) + 32 > d.size() || size_t(t0) + tl > d.size()) continue;
        if (!pintar_cartel(&d[t0], tl, &d[po], el)) continue;   // los de varios colores no
        if (poner(f.second, tirogfx::lz10_literal(d))) ++nc;
    }
    // 2) botones del selector y listas de los menus (las mismas piezas de mbd_c)
    std::vector<uint8_t> h, b;
    const int fh = archivo("/data_iz/pic2d/cmd/en/mbd_c.pkh", h), fb = archivo("/data_iz/pic2d/cmd/en/mbd_c.pkb", b);
    int nb = 0;
    if (fh >= 0 && fb >= 0) {
        for (size_t o = 0x30; o + 12 <= h.size(); o += 12) {
            const uint32_t id = h[o] | h[o + 1] << 8 | h[o + 2] << 16 | uint32_t(h[o + 3]) << 24;
            if (id == 0xFFFFFFFFu) break;
            const uint32_t of = h[o + 4] | h[o + 5] << 8 | h[o + 6] << 16 | uint32_t(h[o + 7]) << 24;
            const uint32_t sz = h[o + 8] | h[o + 9] << 8 | h[o + 10] << 16 | uint32_t(h[o + 11]) << 24;
            const int el = afinidad(id);
            if (id >= 512 || size_t(of) + sz > b.size()) continue;
            const bool talento = cmd[id * 28] == 9;
            if (pintar_boton(b.data() + of, sz, el, talento) && (talento || (el >= 1 && el <= 4))) ++nb;   // todas: paleta comun
        }
        if (!(nb && poner(uint32_t(fb), b))) nb = 0;
    }
    // 3) los fondos de los botones del partido (mbd_c000b/s.pac) ya no se tocan: su paleta
    //    (ranura 9 de objetos) la comparten el boton Aceptar y otros graficos. Los nombres del
    //    selector se dibujan con la ranura 8, que el juego carga con la paleta de una pieza
    //    de mbd_c (las de este mod llevan los colores de las afinidades): colores_sel::tick.
    // 4) cartel de la escena en version 2D (pic2d/cmd/en/mbv_c.pkb, piezas sin comprimir con
    //    la misma paleta que los mbv_cNNN de pic3d)
    std::vector<uint8_t> vh, vb;
    const int fvh = archivo("/data_iz/pic2d/cmd/en/mbv_c.pkh", vh), fvb = archivo("/data_iz/pic2d/cmd/en/mbv_c.pkb", vb);
    int nv = 0;
    if (fvh >= 0 && fvb >= 0) {
        for (size_t o = 0x30; o + 12 <= vh.size(); o += 12) {
            const uint32_t id = vh[o] | vh[o + 1] << 8 | vh[o + 2] << 16 | uint32_t(vh[o + 3]) << 24;
            if (id == 0xFFFFFFFFu) break;
            const uint32_t of = vh[o + 4] | vh[o + 5] << 8 | vh[o + 6] << 16 | uint32_t(vh[o + 7]) << 24;
            const uint32_t sz = vh[o + 8] | vh[o + 9] << 8 | vh[o + 10] << 16 | uint32_t(vh[o + 11]) << 24;
            const int el = afinidad(id);
            if (id < 100 || id >= 512 || size_t(of) + sz > vb.size() || sz < 28) continue;
            uint8_t* d = vb.data() + of;
            if (d[0] != 3 || d[1] || d[2] || d[3]) continue;
            auto u32 = [&](size_t q) { return uint32_t(d[q] | d[q + 1] << 8 | d[q + 2] << 16 | uint32_t(d[q + 3]) << 24); };
            const uint32_t po = u32(4), to = u32(20), tl = u32(24);
            if (size_t(po) + 32 > sz || size_t(to) + tl > sz) continue;
            if (pintar_cartel(d + to, tl, d + po, el)) ++nv;
        }
        if (!(nv && poner(uint32_t(fvb), vb))) nv = 0;
    }
    nc += nv;
    logf("[mods] colores por afinidad: %d carteles y %d botones de supertecnica", nc, nb);
}
}  // namespace colores

void ie1_traza_preparar(const std::vector<uint8_t>& h, const std::vector<uint8_t>& b);   // modo traza (mas abajo)
IE1_EXPORT int ie1_mods_componer_v1(const Ie1ModsHost* host) {
    if (!host || host->version != 1) return 0;
    H = host;
    g_log = host ? host->log : nullptr;
    // Los mods son del Inazuma Eleven 1 europeo (codigo YEEP): con otro juego
    // (por ejemplo el Inazuma Eleven 2) el complemento no hace nada.
    if (N() < 0x200 || std::memcmp(D() + 12, "YEEP", 4) != 0) {
        logf("[mods] el juego no es Inazuma Eleven 1 (EUR): mods desactivados");
        return 1;
    }
    const auto dir = carpeta_mods();
    std::ifstream cfg(dir / "mods.cfg");
    if (!cfg) { logf("[mods] cargador presente; sin %s/mods.cfg, no hay mods activos", dir.string().c_str()); return 1; }
    std::vector<std::string> activos;
    for (std::string l; std::getline(cfg, l);) {
        while (!l.empty() && (l.back() == '\r' || l.back() == ' ')) l.pop_back();
        if (!l.empty() && l[0] != '#') activos.push_back(l);
    }
    if (activos.empty()) { logf("[mods] cargador presente; ningun mod activo"); return 1; }
    if (N() < 0x200) return 0;

    // Ruta -> numero de archivo (tabla de nombres de la ROM)
    const uint32_t fnt_off = rd32(0x40), fnt_size = rd32(0x44), fat_off = rd32(0x48), fat_size = rd32(0x4C);
    std::map<std::string, uint32_t> fids;
    std::function<void(uint32_t, const std::string&, int)> recorrer = [&](uint32_t id, const std::string& ruta, int prof) {
        if (prof > 32) return;
        const size_t ent = fnt_off + size_t(id & 0xFFFu) * 8u;
        if (ent + 8 > size_t(fnt_off) + fnt_size) return;
        size_t p = fnt_off + rd32(ent);
        uint32_t fid = uint32_t{D()[ent + 4]} | uint32_t{D()[ent + 5]} << 8;
        while (p < size_t(fnt_off) + fnt_size) {
            const uint8_t n = D()[p++];
            if (n == 0) break;
            const std::string nombre(reinterpret_cast<const char*>(D() + p), n & 0x7Fu);
            p += n & 0x7Fu;
            if (n & 0x80u) {
                const uint32_t sid = uint32_t{D()[p]} | uint32_t{D()[p + 1]} << 8;
                p += 2;
                recorrer(sid, ruta + nombre + "/", prof + 1);
            } else {
                fids[ruta + nombre] = fid++;
            }
        }
    };
    recorrer(0xF000u, "/", 0);

    uint64_t fin = 0;
    for (uint32_t i = 0; i < fat_size / 8u; ++i) fin = std::max<uint64_t>(fin, rd32(fat_off + i * 8u + 4u));
    fin = (fin + 0x1FFu) & ~uint64_t{0x1FFu};

    auto copiar = [&](const char* ruta, std::vector<uint8_t>& v) {
        const auto it = fids.find(ruta);
        if (it == fids.end()) return;
        const size_t ent = fat_off + size_t(it->second) * 8u;
        const uint32_t a = rd32(ent), b = rd32(ent + 4);
        if (b > a && b <= N()) v.assign(D() + a, D() + b);
    };
    // Idioma de los textos (para los archivos de mods/<mod>/idioma/<xx>/):
    // IE1_TEXTOS o idiomas.cfg (textos=xx), como el ejecutable
    std::string idioma = "en";
    if (const char* e = std::getenv("IE1_TEXTOS"); e && *e) idioma = e;
    else {
        std::ifstream c("idiomas.cfg");
        for (std::string l; std::getline(c, l);)
            if (l.rfind("textos=", 0) == 0) { idioma = l.substr(7); while (!idioma.empty() && (idioma.back() == '\r' || idioma.back() == ' ')) idioma.pop_back(); }
    }
    g_idioma_textos = idioma;
    // Sustituir un archivo de la imagen (en su sitio si cabe; si no, al final)
    auto poner = [&](uint32_t fid, const std::vector<uint8_t>& v) -> bool {
        const size_t ent = fat_off + size_t(fid) * 8u;
        const uint32_t s0 = rd32(ent), e0 = rd32(ent + 4);
        if (v.size() <= uint64_t{e0} - s0) {
            std::memcpy(D() + s0, v.data(), v.size());
            wr32(ent + 4, s0 + uint32_t(v.size()));
            return true;
        }
        const uint64_t need = fin + v.size();
        if (need > N() && !H->redimensionar(H->ctx, size_t(need))) return false;
        std::memcpy(D() + fin, v.data(), v.size());
        wr32(ent, uint32_t(fin));
        wr32(ent + 4, uint32_t(need));
        fin = (need + 0x1FFu) & ~uint64_t{0x1FFu};
        return true;
    };
    auto archivo = [&](const std::string& ruta, std::vector<uint8_t>& v) -> int {
        const auto it = fids.find(ruta);
        if (it == fids.end()) return -1;
        const size_t ent = fat_off + size_t(it->second) * 8u;
        v.assign(D() + rd32(ent), D() + rd32(ent + 4));
        return int(it->second);
    };
    // Piezas de paquetes de todos los mods: pk/<paquete>/<id>.lz
    //   pk/eve/...              -> /data_iz/script/eve.pkh/.pkb
    //   pk/evet/<idioma>/...    -> /data_iz/script/en/evet.pkh/.pkb (solo con ese idioma de textos)
    std::map<std::string, std::map<uint32_t, std::vector<uint8_t>>> piezas;
    // Parches de bytes: mods/<mod>/parches.txt, lineas "<ruta> <desplazamiento hex> <bytes hex...>".
    // Se aplican despues de idiomas, archivos y piezas: valen para cualquier idioma.
    struct ParcheBytes { std::string ruta; uint32_t off; std::vector<uint8_t> bytes; std::string mod; };
    std::vector<ParcheBytes> parches;
    std::map<std::string, std::string> autor_pieza;   // para avisar de choques entre mods
    std::vector<uint8_t> datos;
    for (const auto& mod : activos) {
        {   // menu de entrenamiento: fondo en formato bruto (preparar_entrenamiento.py)
            std::vector<uint8_t> f;
            if (leer(dir / mod / "fondo_ficha.argb", f) && f.size() == 256u * 192u * 4u) {
                g_fondo_ficha.resize(256 * 192);
                std::memcpy(g_fondo_ficha.data(), f.data(), f.size());
            }
            auto fondo = [&](const char* nombre, std::vector<uint32_t>& v) {
                std::vector<uint8_t> b;
                if (!leer(dir / mod / nombre, b) || b.size() != 256u * 192u * 4u) return false;
                v.resize(256 * 192);
                std::memcpy(v.data(), b.data(), b.size());
                return true;
            };
            bool hay = fondo("fondo_entrenamiento.argb", g_fondo_abajo);       // version antigua (espanol)
            hay = fondo("fondo_entrenamiento_es.argb", g_fondo_es) | hay;
            hay = fondo("fondo_entrenamiento_en.argb", g_fondo_en) | hay;
            hay = fondo("fondo_entrenamiento_limpio.argb", g_fondo_limpio) | hay;
            if (hay) {
                if (g_fondo_abajo.empty())
                    g_fondo_abajo = !g_fondo_es.empty() ? g_fondo_es : !g_fondo_en.empty() ? g_fondo_en : g_fondo_limpio;
                logf("[mods] '%s': menu de entrenamiento disponible (se abre hablando con el NPC entrenador)", mod.c_str());
            }
        }
        const auto raiz = dir / mod;
        std::error_code ec;
        if (!std::filesystem::is_directory(raiz, ec)) { logf("[mods] '%s' no existe; se omite", mod.c_str()); continue; }
        if (std::filesystem::exists(raiz / "filtros.cfg", ec)) {        // filtros de los cuadernos
            g_mod_filtros = true;
            logf("[mods] '%s': filtros en los cuadernos de supertecnicas (boton X)", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "talentos.cfg", ec)) {       // talentos del IE2
            g_mod_talentos = true;
            logf("[mods] '%s': talentos activos en los partidos (como el IE2)", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "tiro.cfg", ec)) {           // boton T y tiro largo del IE2
            g_mod_tiro = true;
            logf("[mods] '%s': boton T de tiro y tiro largo (como el IE2)", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "colores.cfg", ec)) {        // nombres de tecnica con el color de su afinidad
            g_mod_colores = true;
            logf("[mods] '%s': nombres de las supertecnicas con el color de su afinidad", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "ojeo.cfg", ec)) {           // ojeo instantaneo
            g_mod_ojeo = true;
            logf("[mods] '%s': ojeo instantaneo (las busquedas de Celia y Nelly terminan al momento)", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "exp_x2.cfg", ec)) {         // EXP x2 en encuentros (como el IE2)
            g_mod_exp_x2 = true;
            {
                std::ifstream xf(raiz / "exp_x2.pac", std::ios::binary);
                g_exp_x2_pac.assign(std::istreambuf_iterator<char>(xf), std::istreambuf_iterator<char>());
            }
            logf("[mods] '%s': EXP x2 en los encuentros ganados por 5 o mas goles sin encajar", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "capitan.cfg", ec)) {        // Mark libre tras el final (como el IE2)
            g_mod_capitan = true;
            logf("[mods] '%s': Mark se puede quitar del equipo con la historia terminada", mod.c_str());
        }
        if (std::filesystem::exists(raiz / "valor.cfg", ec)) {          // valor en las escenas
            g_mod_valor = true;
            logf("[mods] '%s': valor de duelos, tiros y paradas en las escenas de las tecnicas", mod.c_str());
        }
        unsigned n = 0, desconocidos = 0;
        for (const auto& e : std::filesystem::recursive_directory_iterator(raiz, ec)) {
            if (!e.is_regular_file(ec)) continue;
            std::string rel = std::filesystem::relative(e.path(), raiz, ec).generic_string();
            if (rel == "mod.txt" || rel == "trucos.txt" || rel == "fondo_entrenamiento.argb" || rel == "fondo_ficha.argb" || rel == "valor.cfg" || rel == "ojeo.cfg" || rel == "tiro.cfg" || rel == "talentos.cfg" || rel == "filtros.cfg" || rel == "colores.cfg" || rel == "capitan.cfg" || rel == "exp_x2.cfg" || rel == "exp_x2.pac") continue;
            if (rel == "parches.txt") {               // cambios de bytes en archivos (se aplican al final)
                std::ifstream pf(e.path());
                for (std::string l; std::getline(pf, l);) {
                    while (!l.empty() && (l.back() == '\r' || l.back() == ' ')) l.pop_back();
                    if (l.empty() || l[0] == '#') continue;
                    std::istringstream is(l);
                    std::string ruta, off;
                    if (!(is >> ruta >> off)) continue;
                    ParcheBytes pb{ruta, uint32_t(std::strtoul(off.c_str(), nullptr, 16)), {}, mod};
                    for (std::string b; is >> b;) pb.bytes.push_back(uint8_t(std::strtoul(b.c_str(), nullptr, 16)));
                    if (!pb.bytes.empty()) parches.push_back(std::move(pb));
                }
                continue;
            }
            if (rel.rfind("pk/", 0) == 0) {              // pieza de un paquete: pk/<paquete>[/<idioma>]/<id>.lz
                std::string resto = rel.substr(3), paquete;
                if (resto.rfind("eve/", 0) == 0) { paquete = "/data_iz/script/eve"; resto = resto.substr(4); }
                else if (resto.rfind("act/", 0) == 0) {          // guiones de tecnicas: act/<id> o act/<idioma>/<id>
                    paquete = "/data_iz/script/act"; resto = resto.substr(4);
                    const size_t b2 = resto.find('/');
                    if (b2 != std::string::npos) {
                        if (resto.substr(0, b2) != idioma) continue;   // version para otro idioma
                        resto = resto.substr(b2 + 1);
                    }
                }
                else if (resto.rfind("evet/", 0) == 0) {
                    resto = resto.substr(5);
                    const size_t b2 = resto.find('/');
                    if (b2 == std::string::npos || resto.substr(0, b2) != idioma) continue;
                    paquete = "/data_iz/script/en/evet"; resto = resto.substr(b2 + 1);
                } else { ++desconocidos; continue; }
                const uint32_t id = uint32_t(std::strtoul(resto.c_str(), nullptr, 10));
                if (!id || !leer(e.path(), datos)) continue;
                const std::string clave = paquete + "#" + std::to_string(id);
                if (autor_pieza.count(clave))
                    logf("[mods] aviso: '%s' y '%s' cambian la misma pieza (%s); gana '%s'",
                         autor_pieza[clave].c_str(), mod.c_str(), clave.c_str(), mod.c_str());
                autor_pieza[clave] = mod;
                piezas[paquete][id] = datos;
                ++n;
                continue;
            }
            if (rel.rfind("idioma/", 0) == 0) {          // archivos de un idioma concreto: idioma/<xx>/ruta
                const size_t barra = rel.find('/', 7);
                if (barra == std::string::npos || rel.substr(7, barra - 7) != idioma) continue;
                rel = rel.substr(barra + 1);
            }
            const auto it = fids.find("/" + rel);
            if (it == fids.end()) { ++desconocidos; continue; }
            if (!leer(e.path(), datos)) continue;
            const size_t ent = fat_off + size_t(it->second) * 8u;
            const uint32_t s0 = rd32(ent), e0 = rd32(ent + 4);
            if (datos.size() <= uint64_t{e0} - s0) {
                std::memcpy(D() + s0, datos.data(), datos.size());
                wr32(ent + 4, s0 + uint32_t(datos.size()));
            } else {
                const uint64_t need = fin + datos.size();
                if (need > N() && !H->redimensionar(H->ctx, size_t(need))) {
                    logf("[mods] '%s': no hay memoria para %s", mod.c_str(), rel.c_str());
                    continue;
                }
                std::memcpy(D() + fin, datos.data(), datos.size());
                wr32(ent, uint32_t(fin));
                wr32(ent + 4, uint32_t(need));
                fin = (need + 0x1FFu) & ~uint64_t{0x1FFu};
            }
            ++n;
        }
        const unsigned t = cargar_trucos(raiz / "trucos.txt");
        logf("[mods] '%s': %u archivos aplicados%s%s", mod.c_str(), n,
             desconocidos ? " (algunos no existen en la ROM y se ignoraron)" : "",
             t ? (", " + std::to_string(t) + " trucos").c_str() : "");
    }
    {   // parches de bytes (despues de todo lo demas)
        std::map<std::string, int> por_archivo;
        int fallos = 0;
        for (const auto& pb : parches) {
            const auto it = fids.find(pb.ruta);
            if (it == fids.end()) { ++fallos; continue; }
            const size_t ent = fat_off + size_t(it->second) * 8u;
            const uint32_t s0 = rd32(ent), e0 = rd32(ent + 4);
            if (uint64_t{s0} + pb.off + pb.bytes.size() > e0) { ++fallos; continue; }
            std::memcpy(D() + s0 + pb.off, pb.bytes.data(), pb.bytes.size());
            ++por_archivo[pb.ruta];
        }
        for (const auto& pa : por_archivo)
            logf("[mods] %s: %d cambios de bytes aplicados", pa.first.c_str(), pa.second);
        if (fallos) logf("[mods] aviso: %d cambios de bytes no se pudieron aplicar (archivo o posicion fuera)", fallos);
    }
    for (const auto& pq : piezas) {
        std::vector<uint8_t> h, b, h2, b2;
        const int fh = archivo(pq.first + ".pkh", h), fb = archivo(pq.first + ".pkb", b);
        if (fh < 0 || fb < 0 || !ie1_pk_combinar(h.data(), h.size(), b.data(), b.size(), &pq.second, &h2, &b2)) {
            logf("[mods] no pude combinar el paquete %s", pq.first.c_str());
            continue;
        }
        if (!poner(uint32_t(fb), b2) || !poner(uint32_t(fh), h2)) { logf("[mods] sin memoria para %s", pq.first.c_str()); continue; }
        logf("[mods] paquete %s: %zu piezas de mods combinadas", pq.first.c_str(), pq.second.size());
    }
    if (g_mod_tiro) tirogfx::preparar(archivo, poner, idioma);
    if (g_mod_colores) colores::preparar(fids, archivo, poner);
    if (const char* e = std::getenv("IE1_TRAZA"); e && *e == '1') {
        std::vector<uint8_t> th, tb;
        copiar("/data_iz/script/eve.pkh", th); copiar("/data_iz/script/eve.pkb", tb);
        ie1_traza_preparar(th, tb);
    }
    copiar("/data_iz/logic/en/unitno.dat", g_unitno);
    copiar("/data_iz/logic/en/unitstat.dat", g_unitstat);
    copiar("/data_iz/logic/status_up.dat", g_curvas);
    copiar("/data_iz/logic/lvup_exp.dat", g_lvup_exp);
    copiar("/data_iz/logic/en/item.dat", g_itemdat);      // (ya con el idioma elegido)
    copiar("/data_iz/logic/en/command.dat", g_cmddat);
    copiar("/data_iz/logic/lvup_command.dat", g_lvup);
    copiar("/data_iz/logic/unitcalc.dat", g_unitcalc);
    copiar("/data_iz/pic3d/en/mbd_n00.pac_", g_mbd_num);       // panel de valor (con el idioma elegido)
    copiar("/data_iz/pic3d/en/mbd_s001l.pac_", g_mbd_izq);
    for (const auto& f : fids) {                                 // mbd_sNNNr: panel derecho de cada equipo
        const std::string& r = f.first;
        const std::string pre = "/data_iz/pic3d/en/mbd_s";
        if (r.size() == pre.size() + 9 && r.compare(0, pre.size(), pre) == 0 && r.compare(r.size() - 6, 6, "r.pac_") == 0) {
            const int eq = std::atoi(r.c_str() + pre.size());
            copiar(r.c_str(), g_mbd_der[eq]);
        }
    }
    copiar("/data_iz/logic/en/command.STR", g_cmdstr);
    copiar("/data_iz/font/FONT12T.NFTR", g_fuente12);   // la de los menus: 2 bits, con sombra
    copiar("/data_iz/font/FONT8.NFTR", g_fuente8);
    copiar("/data_iz/pic2d/menu/en/SMStat.SPF_", g_smstat);
    copiar("/data_iz/pic2d/menu/en/msup_bg02.pac_", g_msup_bg02);   // ficha pag. 1: etiquetas de las estadisticas
    copiar("/data_iz/pic2d/menu/en/msup_bg03.pac_", g_msup_bg03);   // ficha pag. 2: fondo de arriba del menu   // digitos, PE/PT, posiciones, elementos
    copiar("/data_iz/pic2d/menu/en/msup_z05.pac_", g_z05);    // Regate / Bloqueo / Tiro / Atajo / ? / Talento
    copiar("/data_iz/pic3d/en/waza_den.SPL", g_wd_l); copiar("/data_iz/pic3d/en/waza_den.SPD", g_wd_d);   // boton X
    copiar("/data_iz/pic3d/en/shop.SPL", g_sh_l); copiar("/data_iz/pic3d/en/shop.SPD", g_sh_d);           // flechas
    copiar("/data_iz/face2d/fac.pkh", g_fac_h); copiar("/data_iz/face2d/fac.pkb", g_fac_b);
    copiar("/data_iz/face2d/fab.pkh", g_fab_h); copiar("/data_iz/face2d/fab.pkb", g_fab_b);
    copiar("/data_iz/pic3d/ih.pkh", g_ih_h); copiar("/data_iz/pic3d/ih.pkb", g_ih_b);
    copiar("/data_iz/pic2d/cmd/en/mbd_c.pkh", g_mbd_h); copiar("/data_iz/pic2d/cmd/en/mbd_c.pkb", g_mbd_b);
    copiar("/data_iz/pic3d/en/ply_bkr01.pac_", g_bkr);        // (ya con el idioma y los mods)
    return 1;
}

// ---- Lista de mods para el menu de Esc ---------------------------------------
// Devuelve las carpetas de mods (orden alfabetico) y si estan activas en mods.cfg.
IE1_EXPORT int ie1_mods_lista_v1(char (*nombres)[64], int* activos, int max) {
    const auto dir = carpeta_mods();
    std::vector<std::string> todos, cfg;
    std::error_code ec;
    for (const auto& e : std::filesystem::directory_iterator(dir, ec))
        if (e.is_directory(ec)) todos.push_back(e.path().filename().string());
    std::sort(todos.begin(), todos.end());
    std::ifstream f(dir / "mods.cfg");
    for (std::string l; std::getline(f, l);) {
        while (!l.empty() && (l.back() == '\r' || l.back() == ' ')) l.pop_back();
        if (!l.empty() && l[0] != '#') cfg.push_back(l);
    }
    int n = 0;
    for (const auto& m : todos) {
        if (n >= max) break;
        std::snprintf(nombres[n], 64, "%s", m.c_str());
        activos[n] = std::find(cfg.begin(), cfg.end(), m) != cfg.end() ? 1 : 0;
        ++n;
    }
    return n;
}

// Reescribe mods.cfg: conserva el orden de los que ya estaban activos y anade
// al final los recien activados.
IE1_EXPORT void ie1_mods_guardar_v1(const char (*nombres)[64], const int* activos, int n) {
    const auto dir = carpeta_mods();
    std::vector<std::string> previo;
    {
        std::ifstream f(dir / "mods.cfg");
        for (std::string l; std::getline(f, l);) {
            while (!l.empty() && (l.back() == '\r' || l.back() == ' ')) l.pop_back();
            if (!l.empty() && l[0] != '#') previo.push_back(l);
        }
    }
    auto activo = [&](const std::string& m) {
        for (int i = 0; i < n; ++i) if (m == nombres[i]) return activos[i] != 0;
        return true;                               // no listado (p. ej. mas de los que caben): se respeta
    };
    std::vector<std::string> nuevo;
    for (const auto& m : previo) if (activo(m)) nuevo.push_back(m);
    for (int i = 0; i < n; ++i)
        if (activos[i] && std::find(nuevo.begin(), nuevo.end(), nombres[i]) == nuevo.end())
            nuevo.push_back(nombres[i]);
    std::ofstream o(dir / "mods.cfg");
    o << "# Un mod activo por linea, en orden (el ultimo gana)\n";
    for (const auto& m : nuevo) o << m << "\n";
}

// ---- Trucos (Action Replay), una vez por fotograma ----------------------------
struct Ie1ModsMem {
    uint32_t version;   // 1: lecturas/escrituras; 2: ademas copia rapida de bloques
    uint32_t (*r32)(uint32_t); uint16_t (*r16)(uint32_t); uint8_t (*r8)(uint32_t);
    void (*w32)(uint32_t, uint32_t); void (*w16)(uint32_t, uint16_t); void (*w8)(uint32_t, uint8_t);
    int (*copiar)(uint32_t, uint8_t*, uint32_t);
};
IE1_EXPORT int ie1_mods_trucos_v1() { return int(g_trucos.size()); }
static const Ie1ModsMem* g_mem = nullptr;   // acceso a la memoria del juego (tambien para el menu)
void ie1_senal_npc();   // mas abajo: el NPC entrenador pide abrir el menu
void ie1_niveles_tick(); // mas abajo: aviso "Nv +" al subir una supertecnica de grado
void ie1_inyeccion_tick(); // mas abajo: prueba de codigo inyectado (cartel de grado)
void ie1_prueba2_tick();   // mas abajo: prueba 2 (tecnica y jugador del cartel)
void ie1_potencia_tick();  // mas abajo: registro de cada calculo de valor (IE1_POTENCIA=1)
void ie1_ojeo_tick();      // mas abajo: ojeo instantaneo (mod ojeo_instantaneo)
void ie1_traza_tick();     // mas abajo: modo traza (IE1_TRAZA=1)
void ie1_tiro_t_tick();
void ie1_talentos_tick();  // mas abajo: talentos del IE2 (mod talentos.cfg)    // mas abajo: prueba del boton T y del tiro largo (IE1_TIRO_T=1/2)
namespace filtros {        // mas abajo: filtros de los cuadernos de supertecnicas
extern bool abierto;
void tick();
void teclas(uint16_t pulsados);
void toque(int x, int y, bool abajo);
const uint32_t* dibujar(const uint32_t* abajo, int ancho);
int vigilar_teclas(uint16_t pulsados);
int vigilar_toque(int x, int y, bool abajo);
}
namespace valorov { void mover_pt(); }   // mas abajo: barra de PT al centro

// ---- Mark libre despues del final (como el IE2) -----------------------------------------
// Cada jugador tiene banderas en +0xBA; la 0x400 = "tiene que seguir en el equipo": el menu
// de Miembros la copia y, si esta, sale "%s ha de quedarse como esta por el momento"
// (mensaje 152 del juego; ov29 0x0216CA14/0x0216CC78) y no deja quitarlo. En la historia
// solo la lleva Mark (unidad 1). El IE2 tiene la misma bandera y se la quita al terminar.
// Aqui: si la variable de guion 0x10033 (partida terminada, la misma que usa el NPC
// entrenador; el guion de despues de los creditos la pone a 1) vale 1, se le quita a Mark.
// Las variables 0x10000+n son u32 en 0x020DC078 + 4n (0x10004 = progreso, en 0x020DC088).
// Comprobado con 52 partidas: 1 en todas las terminadas (progreso 10135/10150), 0 en el resto.
// Ademas el menu de Jugadores (ov29) no deja elegir ni poner a nadie en la primera fila
// (el puesto del capitan): sus dos comprobaciones devuelven "no" si la fila ([obj+0x8ADC])
// es 0. Con la historia terminada se cambian en memoria mientras el overlay esta cargado:
//   0x0216CA5C  moveq r0,#0 -> moveq r0,#1   (elegir al jugador de la fila 0)
//   0x0216CCB8  cmp r1,#0   -> cmn r1,#1     (poner a alguien en la fila 0)
namespace capitan {
constexpr uint32_t kJug = 0x020E0480, kTam = 0xFC, kTerminada = 0x020DC078u + 4u * 0x33u;
struct Parche { uint32_t dir, antes_ctx, orig, nuevo; };
const Parche kParches[2] = {
    {0x0216CA5Cu, 0x13A00001u, 0x03A00000u, 0x03A00001u},   // antes: movne r0,#1
    {0x0216CCB8u, 0xE5901ADCu, 0xE3510000u, 0xE3710001u},   // antes: ldr r1,[r0,#0xadc]
};
void fila_capitan() {
    for (const Parche& p : kParches) {
        if (g_mem->r32(p.dir - 4) != p.antes_ctx) continue;           // ov29 no esta cargado
        const uint32_t v = g_mem->r32(p.dir);
        if (v == p.orig) {
            g_mem->w32(p.dir, p.nuevo);
            static int avisos = 0;
            if (avisos++ < 2) logf("[capitan] menu de Jugadores: primera fila libre (0x%08X)", p.dir);
        }
    }
}
void tick() {
    if (!g_mem) return;
    if (g_mem->r32(kTerminada) != 1) return;             // la historia no esta terminada
    fila_capitan();                                      // cada fotograma: el overlay puede recargarse
    static int cada = 0;
    if (++cada % 20) return;                             // la bandera de Mark, 3 veces por segundo
    for (int j = 0; j < 100; ++j) {
        const uint32_t b = kJug + uint32_t(j) * kTam;
        if (g_mem->r16(b + 0x42) != 1) continue;         // Mark = unidad 1
        const uint16_t f = g_mem->r16(b + 0xBA);
        if (f & 0x400) {
            g_mem->w16(b + 0xBA, uint16_t(f & ~0x400));
            logf("[capitan] partida terminada: Mark ya se puede quitar del equipo (jugador %d)", j);
        }
        break;
    }
}
}  // namespace capitan

// ---- Nombres del selector con su propia paleta (mod colores_afinidad) ---------------------
// El boton de supertecnica del selector (ov1 0x02108B48) dibuja el fondo y el nombre (pieza
// de mbd_c, 112x16) con la misma paleta de objetos: la ranura 9 (mbd_c000b.pac azul o
// mbd_c000s.pac rojo; 0x0210C7CC) o la 5 (mbd_c000p.pac, gris). La ranura 9 tambien la usan
// Aceptar y otros graficos, asi que no se le pueden cambiar colores. Al montar el selector
// (0x0210C70C) el juego carga en la ranura 8 la paleta de una pieza de mbd_c, que con este
// mod lleva los colores de las afinidades y el morado de los talentos (13/14). Se cambia
//   0x02108C70  strb r9, [sp, #0x34]   (paleta del nombre)
// por un salto a 0x023FCD80: con la paleta 9, el nombre usa la 8 (la 5 se queda).
namespace colores_sel {
constexpr uint32_t kInstr = 0x02108C70u, kOrig = 0xE5CD9034u, kStub = 0x023FCD80u;
void tick() {
    if (!g_mem) return;
    if (g_mem->r32(kInstr - 4) != 0xE1CDB3B2u || g_mem->r32(kInstr + 4) != 0xE3A01001u) return;  // ov1 no esta
    const uint32_t bl = 0xEB000000u | (((kStub - (kInstr + 8u)) >> 2) & 0x00FFFFFFu);
    const uint32_t v = g_mem->r32(kInstr);
    if (v == bl) return;
    if (v != kOrig) return;                                  // otro codigo: no tocar
    const uint32_t codigo[] = {
        0xE3590009u,                                         // cmp   r9, #9
        0x03A0C008u,                                         // moveq r12, #8
        0x11A0C009u,                                         // movne r12, r9
        0xE5CDC034u,                                         // strb  r12, [sp, #0x34]
        0xE12FFF1Eu};                                        // bx    lr
    for (size_t i = 0; i < sizeof(codigo) / 4; ++i) g_mem->w32(kStub + 4u * uint32_t(i), codigo[i]);
    g_mem->w32(kInstr, bl);
    static int avisos = 0;
    if (avisos++ < 2) logf("[colores] selector: nombres con la paleta de las piezas (ranura 8)");
}
}  // namespace colores_sel

// ---- EXP x2 en los encuentros (como el IE2) ----------------------------------------------
// El IE2 (ES, comprobado con save states en el partido, la victoria, el resultado y la EXP):
//  - la pantalla de reglas de los encuentros (practice_rule, ov39) pone a 1 el byte
//    0x020CA1A0+0x7E al preparar el partido;
//  - al acabar (ov67) lo borra salvo que goles a favor - en contra >= 5 y en contra == 0
//    (marcador en +0x88/+0x89);
//  - en la pantalla de EXP (ov64, 0x0216D9C4) total = base + "jugar bien", y si el byte
//    esta a 1, total << 1 (y cada jugador sale con "x2!!").
// El IE1 tiene las mismas pantallas y el mismo calculo sin ese byte:
//  - practice_rule = ov34 (0x02165D60); marcador en 0x020CA6E0+0x86 (nuestro) y +0x87;
//  - EXP = ov59: 0x0216A5F8 "add r1, r1, r0" (total) antes de "str r1, [r10, #0x60]".
// El mod: si se ha visto la pantalla de reglas y el partido acaba 5+ a 0 (o mejor), al
// cargar la pantalla de EXP pone un byte propio a 1 y cambia esa suma por un salto a un
// trozo que suma y, si el byte esta a 1, multiplica por 2. (La pasion y la amistad no.)
namespace exp_x2 {
bool g_doble = false;                  // la pantalla de EXP que se ve ahora lleva x2
constexpr uint32_t kSuma = 0x0216A5F8u, kCodigo = 0x023FCD00u, kByte = 0x023FCD40u;
constexpr uint32_t kMarcador = 0x020CA6E0u + 0x86u;
// "se vio la pantalla de reglas de un encuentro": en la RAM del juego (va en los estados
// guardados del port), no en una variable del complemento, para que cargar un estado en la
// pantalla de resultados siga sabiendo que era un encuentro
constexpr uint32_t kEncuentro = 0x023FCD41u;
bool reglas_cargadas() {   // ov34 (practice_rule) en 0x02165D60
    return g_mem->r32(0x02167748u) == 0xE3A01001u && g_mem->r32(0x0216774Cu) == 0xE5C2106Eu &&
           g_mem->r32(0x02167750u) == 0xE5C2106Fu;
}
bool exp_cargada(uint32_t salto) {   // ov59 (pantalla de EXP) en 0x02165D60
    const uint32_t v = g_mem->r32(kSuma);
    return g_mem->r32(kSuma - 4) == 0xE58A0054u && g_mem->r32(kSuma + 4) == 0xE59D000Cu &&
           g_mem->r32(kSuma + 8) == 0xE58A1060u && (v == 0xE0811000u || v == salto);
}
void tick() {
    if (!g_mem) return;
    static bool en_exp = false;
    static const bool forzar = [] { const char* e = std::getenv("IE1_EXP_X2_FORZAR"); return e && *e == '1'; }();
    if (reglas_cargadas() && g_mem->r8(kEncuentro) != 1) g_mem->w8(kEncuentro, 1);
    auto rama = [](uint32_t desde, uint32_t hasta) { return 0xEA000000u | (((hasta - (desde + 8u)) >> 2) & 0x00FFFFFFu); };
    const uint32_t salto = rama(kSuma, kCodigo);
    if (!exp_cargada(salto)) { en_exp = false; g_doble = false; return; }
    if (en_exp) return;                                  // ya preparado para esta pantalla
    en_exp = true;
    const int a_favor = g_mem->r8(kMarcador), en_contra = g_mem->r8(kMarcador + 1);
    if (g_mem->r32(kSuma) == salto && !forzar) {
        // el overlay recien cargado trae la suma original: si ya esta el salto es un estado
        // guardado en mitad de esta pantalla, y el byte dice si ya se doblo
        g_doble = g_mem->r8(kByte) == 1;
        g_mem->w8(kEncuentro, 0);
        logf("[exp_x2] pantalla de EXP (estado cargado): %s", g_doble ? "EXP x2" : "normal");
        return;
    }
    const bool encuentro_visto = g_mem->r8(kEncuentro) == 1;
    const bool doble = forzar || (encuentro_visto && a_favor - en_contra >= 5 && en_contra == 0);
    g_mem->w8(kEncuentro, 0);                            // cada encuentro cuenta una vez
    const uint32_t codigo[] = {
        0xE0811000u,                                     // add   r1, r1, r0       (lo de siempre)
        0xE59FC00Cu,                                     // ldr   r12, [pc, #0xC]  (=kByte)
        0xE5DCC000u,                                     // ldrb  r12, [r12]
        0xE35C0000u,                                     // cmp   r12, #0
        0x11A01081u,                                     // lslne r1, r1, #1       (x2)
        rama(kCodigo + 0x14u, kSuma + 4u),               // b     de vuelta
        kByte};
    for (size_t i = 0; i < sizeof(codigo) / 4; ++i) g_mem->w32(kCodigo + 4u * uint32_t(i), codigo[i]);
    g_mem->w8(kByte, doble ? 1 : 0);
    g_doble = doble;
    if (g_mem->r32(kSuma) != salto) g_mem->w32(kSuma, salto);
    logf("[exp_x2] pantalla de EXP: %s (%s, marcador %d-%d)", doble ? "EXP x2" : "normal",
         forzar ? "forzado con IE1_EXP_X2_FORZAR" : (encuentro_visto ? "encuentro" : "no es encuentro"), a_favor, en_contra);
}
const uint32_t* dibujar(const uint32_t* px, int ancho);   // mas abajo (usa el lector de PAC del panel)
}  // namespace exp_x2
IE1_EXPORT void ie1_mods_fotograma_v1(const Ie1ModsMem* mem) {
    if (mem && mem->version >= 1) g_mem = mem;
    ie1_senal_npc();
    ie1_niveles_tick();
    if (const char* e = std::getenv("IE1_PRUEBA_GANCHO"); e && *e == '1') ie1_inyeccion_tick();
    if (const char* e = std::getenv("IE1_PRUEBA_GANCHO"); e && *e == '2') ie1_prueba2_tick();
    {   // valores: registro (IE1_POTENCIA=1) y/o panel en las escenas (IE1_VALOR=1)
        static const bool pot = [] { const char* e = std::getenv("IE1_POTENCIA"); return e && *e == '1'; }();
        const bool val = ie1_valor_activo();
        if (pot || val) ie1_potencia_tick();
        if (val) valorov::mover_pt();
        if (g_mod_ojeo) ie1_ojeo_tick();
        static const bool traza = [] { const char* e = std::getenv("IE1_TRAZA"); return e && *e == '1'; }();
        if (traza) ie1_traza_tick();
        static const int tiro_t = [] { const char* e = std::getenv("IE1_TIRO_T"); return (e && *e >= '0' && *e <= '9') ? *e - '0' : 0; }();
        if (tiro_t || g_mod_tiro) ie1_tiro_t_tick();
        if (g_mod_talentos) ie1_talentos_tick();
        if (g_mod_filtros) filtros::tick();
        if (g_mod_capitan) capitan::tick();
        if (g_mod_colores) colores_sel::tick();
        if (g_mod_exp_x2) exp_x2::tick();
    }
    if (!mem || mem->version < 1 || g_trucos.empty()) return;
    const ArMem m{mem->r32, mem->r16, mem->r8, mem->w32, mem->w16, mem->w8};
    for (const auto& c : g_trucos) ar_ejecutar(c, m);
}

// ============================================================================
//  Menu de ENTRENAMIENTO LIBRE (tecla T): repartir puntos pagando Pasion.
//  Dibuja sobre la pantalla inferior y recibe los botones de la DS mientras
//  esta abierto (el juego no los ve).
// ============================================================================
#include "ie1_fuente.inc"
namespace ent {
constexpr uint32_t kJugadores = 0x020E0480, kTam = 0xFC, kPasion = 0x020CABA0;
constexpr uint32_t kCoste = 450;                 // Pasion por punto
constexpr int kMaxJug = 100, kFilas = 9;         // PE, PT y 7 estadisticas
bool abierto = false;
int jug = 0, fila = 2;
int asig[kFilas] = {};
uint16_t prev = 0;
std::vector<int> lista;                          // jugadores validos
uint32_t buf[256 * 192];
std::string aviso; int aviso_t = 0;
std::string J(const char* utf8);   // texto propio -> codificacion del juego (mas abajo)

uint8_t r8(uint32_t a) { return g_mem ? g_mem->r8(a) : 0; }
uint16_t r16(uint32_t a) { return g_mem ? g_mem->r16(a) : 0; }
uint32_t r32(uint32_t a) { return g_mem ? g_mem->r32(a) : 0; }
uint32_t base(int j) { return kJugadores + uint32_t(j) * kTam; }

void cargar_lista() {
    lista.clear();
    for (int j = 0; j < kMaxJug; ++j) {
        const uint32_t b = base(j);
        const uint8_t c0 = r8(b), nivel = r8(b + 0xAA);
        if (c0 >= 0x20 && c0 < 0x7F && nivel >= 1 && nivel <= 99) lista.push_back(j);
    }
    if (lista.empty()) lista.push_back(0);
}
std::string nombre(int j) {
    std::string n;
    for (int k = 0; k < 16; ++k) { const char c = char(r8(base(j) + k)); if (!c) break; n += c; }
    return n;
}
// Orden de las filas de estadisticas (como en la ficha): Tiro, Fisico, Control,
// Defensa, Rapidez, Aguante, Valor. En los datos del juego cada estadistica tiene
// un identificador (30..36) con otro orden: Tiro 30, Fisico 31, Defensa 32,
// Control 33, Rapidez 34, Valor 35, Aguante 36.
constexpr int kId[7] = {0, 1, 3, 2, 4, 6, 5};       // fila -> (identificador - 30)
// Estadistica "pareja" a la que el juego le quita puntos cuando ya no queda
// Libertad (funcion 0x0207D6BC): Tiro<->Control, Rapidez<->Aguante y
// Fisico->Defensa->Valor->Fisico.
constexpr int kPareja[7] = {2, 3, 0, 6, 5, 4, 1};

const uint8_t* registro(int j) {   // registro del jugador en unitstat.dat (0x50 bytes)
    const uint16_t id = r16(base(j) + 0x42) & 0xFFF;
    for (size_t i = 0; i + 1 < g_unitno.size(); i += 2)
        if ((g_unitno[i] | g_unitno[i + 1] << 8) == id) {
            const size_t o = i / 2 * 0x50;
            if (o + 0x50 <= g_unitstat.size()) return g_unitstat.data() + o;
        }
    return nullptr;
}
int actual(int j, int f) {
    const uint32_t b = base(j);
    if (f == 0) return r16(b + 0xD0);
    if (f == 1) return r16(b + 0xD2);
    return r8(b + 0xD8 + (f - 2));
}
int total_asig() { int t = 0; for (int v : asig) t += v; return t; }

// Simulacion exacta de las reglas del juego (funciones 0x0207D830 / 0x0207DAC0):
//  - lo entrenado de cada estadistica (con signo) va de -127 a +50;
//  - primero se gasta la Libertad (tope del jugador - suma de sus 7 estadisticas);
//  - sin Libertad, cada punto extra se le QUITA a la estadistica pareja;
//  - la pareja no puede bajar de 1.
// Valor natural de una estadistica a un nivel (funcion 0x0207D394):
//   nv1 + (nv99 - nv1) * curva[nivel] / 100, con la curva de status_up.dat
int natural(const uint8_t* entrada, int nivel) {
    const int nv1 = entrada[0], nv99 = entrada[1], curva = entrada[2];
    int pct = 0;
    const size_t o = size_t(curva) * 0x68 + size_t(nivel - 1);
    if (nivel >= 1 && nivel <= 99 && o < g_curvas.size()) pct = g_curvas[o];
    int v = nv1 + (nv99 - nv1) * pct / 100;
    return std::clamp(v, 0, 255);
}
struct Sim {
    int base[7], disp[7], tr[7];        // estadistica base, mostrada (con equipo), entrenado
    int tr_pe[2], val_pe[2];            // PE / PT: entrenado y valor maximo
    int lib = 0, tope = 0, suma = 0, libertad = 0;
    bool ok = true;
    const char* motivo = "";
};
// Reglas del juego al entrenar (0x0207D830, limites de 0x0207DAC0):
//  - lo entrenado de cada estadistica (con signo) llega como mucho a +50;
//  - primero se gasta la aptitud libre (tope del jugador - suma de sus 7
//    estadisticas actuales; a nivel 99 es la Libertad que le queda);
//  - sin aptitud libre, cada punto de mas se le QUITA a la estadistica pareja;
//  - la pareja no puede bajar de 1, ni su entrenado por debajo del limite del
//    juego (-127, mas estricto a niveles bajos).
Sim simular(int j, const int* a) {
    Sim m;
    const uint32_t b = base(j);
    const uint8_t* reg = registro(j);
    const int nivel = r8(b + 0xAA);
    for (int i = 0; i < 7; ++i) {
        m.base[i] = r8(b + 0xDF + i);
        m.disp[i] = r8(b + 0xD8 + i);
        m.tr[i] = int8_t(r8(b + 0xAF + kId[i]));
    }
    for (int k = 0; k < 2; ++k) { m.tr_pe[k] = int16_t(r16(b + 0x78 + 2 * k)); m.val_pe[k] = r16(b + 0xD0 + 2 * k); }
    m.tope = reg ? (reg[0x3C] | reg[0x3D] << 8) : 0;
    auto libre = [&]() { int s = 0; for (int i = 0; i < 7; ++i) s += m.base[i]; m.suma = s; return (m.tope ? m.tope : 0x7FFF) - s; };
    if (reg) {   // Libertad del jugador: tope - suma de sus valores naturales a nivel 99
        int s99 = 0; for (int i = 0; i < 7; ++i) s99 += reg[0x10 + 4 * kId[i] + 1];
        m.libertad = m.tope - s99;
    }
    for (int k = 0; k < 2; ++k) {                       // PE / PT
        const int n = a[k];
        if (!n) continue;
        const int maxlv = reg ? (reg[k * 8 + 2] | reg[k * 8 + 3] << 8) : 999;
        if (m.tr_pe[k] + n > 50) { m.ok = false; m.motivo = T5("Max. +50", "Máximo +50", "Max. +50", "Max. +50", "Max. +50"); }
        else if (maxlv + m.tr_pe[k] + n > 999) { m.ok = false; m.motivo = T5("Max. 999", "Máximo 999", "Max. 999", "Max. 999", "Max. 999"); }
        m.tr_pe[k] += n; m.val_pe[k] += n;
    }
    for (int i = 0; i < 7; ++i) {                       // estadisticas, en el orden de las filas
        const int n = a[2 + i];
        if (!n) continue;
        const int p = kPareja[i];
        const int lib = std::max(0, libre());
        // limite del juego (0x0207DAC0)
        int permitido = 50 - m.tr[i];
        if (reg) {
            const uint8_t* ep = reg + 0x10 + 4 * kId[p];
            const int nat_p = natural(ep, nivel);
            int t = -127 - (m.tr[p] - (ep[1] - nat_p));
            if (t < 0) t = -t;
            permitido = std::min(permitido, lib + t);
        }
        if (n > permitido) { m.ok = false; m.motivo = m.tr[i] + n > 50 ? T5("Max. +50", "Máximo +50", "Max. +50", "Max. +50", "Max. +50")
                                                              : T5("Partner stat at minimum", "Pareja al mínimo", "Partenaire au minimum", "Partnerwert am Minimum", "Coppia al minimo"); }
        const int exceso = n - std::min(n, lib);
        if (exceso > 0 && m.base[p] - exceso < 1) { m.ok = false; m.motivo = T5("Partner stat at minimum", "Pareja al mínimo", "Partenaire au minimum", "Partnerwert am Minimum", "Coppia al minimo"); }
        m.tr[i] += n; m.base[i] += n; m.disp[i] += n;
        if (exceso > 0) { m.tr[p] -= exceso; m.base[p] -= exceso; m.disp[p] -= exceso; }
        if (m.base[i] > 255) { m.ok = false; m.motivo = T5("Max. 255", "Máximo 255", "Max. 255", "Max. 255", "Max. 255"); }
    }
    m.lib = std::max(0, libre());
    return m;
}

bool puede_sumar(int j, int f) {
    int prueba[kFilas];
    std::copy(std::begin(asig), std::end(asig), prueba);
    ++prueba[f];
    if (uint64_t(total_asig() + 1) * kCoste > r32(kPasion)) { aviso = J(T5("Not enough Passion", "Pasión insuficiente", "Pas assez de Passion", "Nicht genug Leidenschaft", "Passione insufficiente")); return false; }
    const Sim m = simular(j, prueba);
    if (!m.ok) { aviso = J(m.motivo); return false; }
    return true;
}
void aplicar(int j) {
    const int t = total_asig();
    if (!t || !g_mem) return;
    const Sim m = simular(j, asig);
    if (!m.ok) { aviso = J(m.motivo); return; }
    const uint32_t b = base(j);
    for (int i = 0; i < 7; ++i) {
        g_mem->w8(b + 0xAF + kId[i], uint8_t(int8_t(m.tr[i])));
        g_mem->w8(b + 0xDF + i, uint8_t(m.base[i]));
        g_mem->w8(b + 0xD8 + i, uint8_t(m.disp[i]));
    }
    for (int k = 0; k < 2; ++k) {
        if (!asig[k]) continue;
        g_mem->w16(b + 0x78 + 2 * k, uint16_t(int16_t(m.tr_pe[k])));
        g_mem->w16(b + 0xD0 + 2 * k, uint16_t(r16(b + 0xD0 + 2 * k) + asig[k]));
        g_mem->w16(b + 0xD4 + 2 * k, uint16_t(r16(b + 0xD4 + 2 * k) + asig[k]));
    }
    g_mem->w32(kPasion, r32(kPasion) - uint32_t(t) * kCoste);
    std::fill(std::begin(asig), std::end(asig), 0);
    aviso = J(T5("Training applied", "Entrenamiento aplicado", "Entraînement appliqué", "Training angewendet", "Allenamento applicato"));
}

// ---- Reiniciar a nivel 1 (boton X del menu) -------------------------------------
// Gratis. El jugador conserva las supertecnicas que ya sabe y pierde lo entrenado
// (PE/PT +0x78/+0x7A y las 7 estadisticas +0xAF..+0xB5). Con el mod de niveles de
// supertecnicas, los usos de cada tecnica (+0xA4..+0xA9) vuelven a 0.
// Se hace como el juego al recalcular a un nivel (0x0207E334):
//  - base (0x0207DEC0): PE/PT +0xD4/+0xD6 = curva(nivel) + entrenado; estadisticas
//    +0xDF.. = natural(nivel) + entrenado. Al bajar no hay reparto (0x0207DE24 solo
//    actua si sube);
//  - mostrado (0x02081B44 + equipo): +0xD0/+0xD2 y +0xD8.. = base + bonos del equipo.
//    Los bonos se conservan como estaban (mostrado - base);
//  - PE/PT actuales (+0x94/+0x96) no pasan del nuevo maximo.
// EXP (+0x60) = 0, lo que pide el nivel 1 (0x0207D378): al ganar experiencia el juego
// vuelve a subirlo de nivel con sus propias reglas.
bool confirmar = false;                       // ventana "Volver al nivel 1" abierta
bool niveles_activos() {                      // mod de niveles de supertecnicas instalado
    static int v = -1;
    if (v < 0 && !g_cmddat.empty()) {
        v = 0;
        for (size_t i = 0; i + 28 <= g_cmddat.size(); i += 28) if (g_cmddat[i + 0x10]) { v = 1; break; }
        if (g_lvup.empty()) v = 0;
    }
    return v == 1;
}
int pe_natural(const uint8_t* e, int nivel) { // 0x0207D3F8: PE/PT a un nivel (0..999)
    const int v1 = e[0] | e[1] << 8, v99 = e[2] | e[3] << 8, curva = e[4];
    int pct = 0;
    const size_t o = size_t(curva) * 0x68 + size_t(nivel - 1);
    if (nivel >= 1 && nivel <= 99 && o < g_curvas.size()) pct = g_curvas[o];
    return std::clamp(v1 + (v99 - v1) * pct / 100, 0, 999);
}
bool ya_en_nivel_1(int j) {                   // nada que reiniciar
    const uint32_t b = base(j);
    if (r8(b + 0xAA) != 1 || r16(b + 0x78) || r16(b + 0x7A)) return false;
    for (int k = 0; k < 7; ++k) if (r8(b + 0xAF + uint32_t(k))) return false;
    if (niveles_activos()) for (int s = 0; s < 6; ++s) if (r8(b + 0xA4 + uint32_t(s))) return false;
    return true;
}
bool reiniciar(int j) {
    const uint8_t* reg = registro(j);
    if (!reg || !g_mem || g_curvas.empty()) {
        aviso = J(T5("Player data not found", "No encuentro los datos del jugador", "Données du joueur introuvables",
                     "Spielerdaten nicht gefunden", "Dati del giocatore non trovati"));
        return false;
    }
    const uint32_t b = base(j);
    for (int i = 0; i < 7; ++i) {             // estadisticas, en el orden de las filas
        const int vb = r8(b + 0xDF + uint32_t(i)), vd = r8(b + 0xD8 + uint32_t(i));
        const int nb = natural(reg + 0x10 + 4 * kId[i], 1);
        g_mem->w8(b + 0xAF + uint32_t(kId[i]), 0);
        g_mem->w8(b + 0xDF + uint32_t(i), uint8_t(nb));
        g_mem->w8(b + 0xD8 + uint32_t(i), uint8_t(std::clamp(nb + vd - vb, 0, 255)));
    }
    for (int k = 0; k < 2; ++k) {             // PE / PT
        const uint32_t o = 2u * uint32_t(k);
        const int vb = r16(b + 0xD4 + o), vd = r16(b + 0xD0 + o);
        const int nb = pe_natural(reg + 8 * k, 1);
        const int nd = std::clamp(nb + vd - vb, 0, 999);
        g_mem->w16(b + 0x78 + o, 0);
        g_mem->w16(b + 0xD4 + o, uint16_t(nb));
        g_mem->w16(b + 0xD0 + o, uint16_t(nd));
        if (r16(b + 0x94 + o) > nd) g_mem->w16(b + 0x94 + o, uint16_t(nd));
    }
    if (niveles_activos()) for (int s = 0; s < 6; ++s) g_mem->w8(b + 0xA4 + uint32_t(s), 0);
    g_mem->w32(b + 0x60, 0);
    g_mem->w8(b + 0xAA, 1);
    std::fill(std::begin(asig), std::end(asig), 0);
    logf("[mods] entrenamiento: %s vuelve al nivel 1", nombre(j).c_str());
    aviso = J(T5("Back to level 1", "Ha vuelto al nivel 1", "Retour au niveau 1", "Zurück auf Level 1", "Tornato al livello 1"));
    return true;
}
// ---- Subir de nivel (boton Y del menu) ---------------------------------------------
// Solo hacia arriba, pagando Pasion. Se hace nivel a nivel como el bucle del juego
// (0x0207DC10 -> 0x0207DBF4 -> 0x0207E334), sobre una copia del jugador:
//  - EXP (+0x60) = la que pide el nivel final (0x0207D378: lvup_exp.dat, tipo +0x40,
//    tabla[tipo * 98 + nivel - 2]; nivel 1 = 0). Comprobado con 20 jugadores reales.
//  - base: PE/PT y estadisticas = natural(nivel) + entrenado (0x0207DEC0) y, si la suma
//    pasa del tope del jugador, el reparto del juego (0x0207DE24): a cada estadistica que
//    crece se le quita lo que sobra, como mucho lo que ha crecido, de lo entrenado
//    (limitado a -127..127). Sin reparto si el jugador tiene la bandera +0xF0 & 0x40.
//  - mostrado = base + los bonos del equipo que ya tenia; +0xC1..C3 crecen como en el juego.
//  - tecnicas: las de su lista (unitstat +0x2C, 4 x [tecnica, nivel]) con nivel <= el
//    nuevo, en el primer hueco libre de las ranuras 0..3 (0x02072FE8 -> 0x020808E8), con
//    0 usos. Tambien las de varios jugadores (command.dat +0x0A): el juego las pone en la
//    ranura y luego intenta elegir companeros (0x02072BB8); si no los encuentra deja los
//    companeros a 0 (+0x7C/+0x7E de la ranura), que es "Al azar". Aqui se dejan asi.
// Coste de cada nivel: 225 de Pasion por cada punto que gana (estadisticas, PE y PT), la
// mitad que entrenar a mano (450), porque el nivel no deja elegir donde van. Minimo 100.
constexpr uint32_t kCostePunto = 225, kCosteMin = 100;
bool nivel_abierto = false;                   // ventana "Subir de nivel" abierta
int nivel_obj = 0;                            // nivel elegido en la ventana
uint32_t exp_nivel(int tipo, int nivel) {
    if (nivel <= 1) return 0;
    const size_t o = (size_t(tipo) * 98 + size_t(nivel - 2)) * 4;
    if (o + 4 > g_lvup_exp.size()) return 0xFFFFFFFFu;
    return g_lvup_exp[o] | g_lvup_exp[o + 1] << 8 | g_lvup_exp[o + 2] << 16 | uint32_t(g_lvup_exp[o + 3]) << 24;
}
struct Subida {
    bool ok = false;
    uint8_t p[kTam] = {};                     // jugador con los niveles subidos
    uint32_t coste = 0;
    int puntos = 0, tecnicas = 0, combos = 0;
};
Subida simular_subida(int j, int objetivo) {
    Subida r;
    const uint8_t* reg = registro(j);
    if (!reg || !g_mem || g_curvas.empty() || g_lvup_exp.empty()) return r;
    const uint32_t b = base(j);
    for (uint32_t k = 0; k < kTam; ++k) r.p[k] = r8(b + k);
    uint8_t* p = r.p;
    auto g16 = [&](int o) { return int(p[o] | p[o + 1] << 8); };
    auto s16 = [&](int o, int v) { p[o] = uint8_t(v); p[o + 1] = uint8_t(v >> 8); };
    int nivel = p[0xAA];
    objetivo = std::clamp(objetivo, nivel, 99);
    const int tope = (reg[0x3C] | reg[0x3D] << 8) ? (reg[0x3C] | reg[0x3D] << 8) : 0x7FFF;
    const bool reparto = !(g16(0xF0) & 0x40);
    while (nivel < objetivo) {
        ++nivel;
        int puntos = 0;
        // estadisticas (en el orden de las filas: DF + i <-> entrenado AF + kId[i])
        int antes[7], delta[7];
        for (int i = 0; i < 7; ++i) {
            antes[i] = p[0xDF + i];
            const int nb = (natural(reg + 0x10 + 4 * kId[i], nivel) + int8_t(p[0xAF + kId[i]])) & 0xFF;
            delta[i] = nb - antes[i];
            p[0xDF + i] = uint8_t(nb);
        }
        if (reparto)                          // 0x0207DE24, en el orden del juego (entrenado AF+k)
            for (int k = 0; k < 7; ++k) {
                const int i = kId[k];         // estadistica DF + i de lo entrenado AF + k
                int suma = 0;
                for (int m = 0; m < 7; ++m) suma += p[0xDF + m];
                int e = suma - tope;
                if (e <= 0 || delta[i] <= 0) continue;
                if (e > delta[i]) e = delta[i];
                int t = int8_t(p[0xAF + k]) - e;
                if (t > 127) { e -= t - 127; t = 127; }
                if (t < -127) { e -= -127 - t; t = -127; }
                p[0xAF + k] = uint8_t(int8_t(t));
                p[0xDF + i] = uint8_t(p[0xDF + i] - e);
            }
        for (int i = 0; i < 7; ++i) {
            const int d = p[0xDF + i] - antes[i];
            puntos += std::max(0, d);
            p[0xD8 + i] = uint8_t(std::clamp(p[0xD8 + i] + d, 0, 255));
        }
        for (int k = 0; k < 2; ++k) {         // PE / PT
            const int o = 2 * k;
            const int ab = g16(0xD4 + o);
            const int nb = std::clamp(pe_natural(reg + 8 * k, nivel) + int16_t(g16(0x78 + o)), 0, 999);
            const int d = nb - ab;
            puntos += std::max(0, d);
            s16(0xD4 + o, nb);
            s16(0xD0 + o, std::clamp(g16(0xD0 + o) + d, 0, 999));
        }
        for (int k = 0; k < 3; ++k)           // +0xC1..C3 (registro +0x3F/+0x41/+0x43)
            p[0xC1 + k] = uint8_t(std::min(100, int(int8_t(p[0xC1 + k])) + int(int8_t(reg[0x3F + 2 * k]))));
        for (int k = 0; k < 4; ++k) {         // tecnicas de su lista
            const int tec = reg[0x2C + 4 * k] | reg[0x2D + 4 * k] << 8, nv = reg[0x2E + 4 * k];
            if (!tec || nivel < nv) continue;
            bool ya = false; int hueco = -1;
            for (int s = 0; s < 4; ++s) {
                const int t = g16(0x98 + 2 * s);
                if (t == tec) ya = true;
                if (!t && hueco < 0) hueco = s;
            }
            if (ya || hueco < 0) continue;
            if (size_t(tec + 1) * 28 <= g_cmddat.size() && g_cmddat[size_t(tec) * 28 + 0x0A]) ++r.combos;   // companeros: Al azar
            s16(0x98 + 2 * hueco, tec);
            p[0xA4 + hueco] = 0;
            s16(0x7C + 4 * hueco, 0); s16(0x7E + 4 * hueco, 0);
            ++r.tecnicas;
        }
        r.puntos += puntos;
        r.coste += std::max(kCosteMin, uint32_t(puntos) * kCostePunto);
    }
    p[0xAA] = uint8_t(nivel);
    const uint32_t e = exp_nivel(p[0x40], nivel);
    const uint32_t ea = uint32_t(p[0x60] | p[0x61] << 8 | p[0x62] << 16) | uint32_t(p[0x63]) << 24;
    if (e != 0xFFFFFFFFu && e > ea) for (int k = 0; k < 4; ++k) p[0x60 + k] = uint8_t(e >> (8 * k));
    r.ok = true;
    return r;
}
// Nivel mas alto que se puede pagar con la Pasion que hay
int nivel_maximo_pagable(int j) {
    const int nv = r8(base(j) + 0xAA);
    const uint32_t pasion = r32(kPasion);
    int mejor = nv;
    for (int n = nv + 1; n <= 99; ++n) {
        const Subida s = simular_subida(j, n);
        if (!s.ok || s.coste > pasion) break;
        mejor = n;
    }
    return mejor;
}
bool subir_nivel(int j, int objetivo) {
    const Subida s = simular_subida(j, objetivo);
    if (!s.ok) { aviso = J(T5("Player data not found", "No encuentro los datos del jugador", "Données du joueur introuvables", "Spielerdaten nicht gefunden", "Dati del giocatore non trovati")); return false; }
    if (s.coste > r32(kPasion)) { aviso = J(T5("Not enough Passion", "Pasión insuficiente", "Pas assez de Passion", "Nicht genug Leidenschaft", "Passione insufficiente")); return false; }
    const uint32_t b = base(j);
    for (uint32_t k = 0; k < kTam; ++k) if (r8(b + k) != s.p[k]) g_mem->w8(b + k, s.p[k]);
    g_mem->w32(kPasion, r32(kPasion) - s.coste);
    std::fill(std::begin(asig), std::end(asig), 0);
    logf("[mods] entrenamiento: %s sube al nivel %d (%u de Pasion, %d puntos, %d tecnicas)", nombre(j).c_str(), objetivo, s.coste, s.puntos, s.tecnicas);
    aviso = J(T5("Level up!", "¡Ha subido de nivel!", "Niveau supérieur !", "Level aufgestiegen!", "Livello aumentato!"));
    return true;
}
void abrir_nivel() {                          // boton Y
    const int nv = r8(base(jug) + 0xAA);
    if (nv >= 99) { aviso = J(T5("Already at level 99", "Ya está en el nivel 99", "Déjà au niveau 99", "Schon auf Level 99", "Già al livello 99")); aviso_t = 120; return; }
    nivel_obj = nv + 1;
    nivel_abierto = true;
}
void cambiar_nivel(int dir, bool ctrl) {
    const int nv = r8(base(jug) + 0xAA);
    if (ctrl) nivel_obj = dir > 0 ? std::max(nv + 1, nivel_maximo_pagable(jug)) : nv + 1;
    else nivel_obj = std::clamp(nivel_obj + dir, nv + 1, 99);
}
void pedir_reinicio() {                       // boton X
    if (ya_en_nivel_1(jug)) {
        aviso = J(T5("Already at level 1", "Ya está en el nivel 1", "Déjà au niveau 1", "Schon auf Level 1", "Già al livello 1"));
        aviso_t = 120;
        return;
    }
    confirmar = true;
}

// ---- dibujo -------------------------------------------------------------------
inline void pix(int x, int y, uint32_t c) { if (x >= 0 && y >= 0 && x < 256 && y < 192) buf[y * 256 + x] = c; }
void rect(int x0, int y0, int x1, int y1, uint32_t c) { for (int y = y0; y <= y1; ++y) for (int x = x0; x <= x1; ++x) pix(x, y, c); }
uint32_t mezcla(uint32_t a, uint32_t b, int k, int n) {
    auto ch = [&](int s) { return ((int((a >> s) & 255) * (n - k) + int((b >> s) & 255) * k) / n) & 255; };
    return 0xFF000000u | uint32_t(ch(16)) << 16 | uint32_t(ch(8)) << 8 | uint32_t(ch(0));
}
// ---- Fuente del juego (formato NFTR de Nintendo) ------------------------------
struct Fuente {
    const std::vector<uint8_t>* d = nullptr;
    int cw = 0, ch = 0, bpg = 0, bpp = 1, gl = 0, wfirst = 0, wlast = -1, wd = 0;
    std::map<int, int> mapa;                    // codigo de caracter -> glifo
    bool ok() const { return d && cw > 0; }
    uint32_t u32(size_t o) const { const auto& v = *d; return v[o] | v[o + 1] << 8 | v[o + 2] << 16 | uint32_t(v[o + 3]) << 24; }
    int u16(size_t o) const { const auto& v = *d; return v[o] | v[o + 1] << 8; }
    void cargar(const std::vector<uint8_t>& v) {
        d = &v; mapa.clear(); cw = 0;
        if (v.size() < 0x20 || std::memcmp(v.data(), "RTFN", 4) != 0) return;
        for (size_t o = 0x10; o + 8 <= v.size();) {
            const uint32_t sz = u32(o + 4);
            if (!std::memcmp(&v[o], "PLGC", 4)) {
                cw = v[o + 8]; ch = v[o + 9]; bpg = u16(o + 10); bpp = v[o + 14]; gl = int(o + 16);
            } else if (!std::memcmp(&v[o], "HDWC", 4)) {
                wfirst = u16(o + 8); wlast = u16(o + 10); wd = int(o + 16);
            } else if (!std::memcmp(&v[o], "PAMC", 4)) {
                const int a = u16(o + 8), b = u16(o + 10), t = u16(o + 12);
                const size_t p = o + 20;
                if (t == 0) { const int base = u16(p); for (int k = a; k <= b; ++k) mapa[k] = base + k - a; }
                else if (t == 1) { for (int k = a; k <= b; ++k) { const int g = u16(p + 2 * size_t(k - a)); if (g != 0xFFFF) mapa[k] = g; } }
                else { const int n = u16(p); for (int i = 0; i < n; ++i) mapa[u16(p + 2 + 4 * size_t(i))] = u16(p + 4 + 4 * size_t(i)); }
            }
            if (!sz) break;
            o += sz;
        }
        if (bpp < 1 || bpp > 2) cw = 0;
    }
    void ancho(int g, int& izq, int& avance) const {
        if (g >= wfirst && g <= wlast) { const size_t o = size_t(wd) + 3 * size_t(g - wfirst); izq = int8_t((*d)[o]); avance = (*d)[o + 2]; }
        else { izq = 0; avance = cw; }
    }
    int pixel(int g, int x, int y) const {
        const size_t bit = size_t(y * cw + x) * size_t(bpp);
        const size_t o = size_t(gl) + size_t(g) * size_t(bpg) + bit / 8;
        if (o >= d->size()) return 0;
        return ((*d)[o] >> (8 - bpp - int(bit % 8))) & ((1 << bpp) - 1);
    }
    // bytes del juego -> codigos (los japoneses ocupan 2 bytes, como Shift-JIS)
    template <class F> void recorrer(const std::string& t, F f) const {
        for (size_t i = 0; i < t.size(); ++i) {
            int c = (unsigned char)t[i];
            if (((c >= 0x81 && c <= 0x9F) || (c >= 0xE0 && c <= 0xFC)) && i + 1 < t.size()) c = c << 8 | (unsigned char)t[++i];
            const auto it = mapa.find(c);
            f(it == mapa.end() ? -1 : it->second);
        }
    }
};
Fuente g_f12;
bool g_f12_cargada = false;
const Fuente* fuente() {
    if (!g_f12_cargada) { g_f12_cargada = true; g_f12.cargar(g_fuente12); }
    return g_f12.ok() ? &g_f12 : nullptr;
}

// Texto propio (UTF-8) -> codificacion del juego (tabla 0xA1-0xDF de sus fuentes)
std::string J(const char* utf8) {
    // Letras con tilde de la fuente del juego (FONT12T, codigos 0xA1-0xDF): las de los cinco
    // idiomas (es, fr, de, it). La ss alemana no esta en la fuente: se escribe "ss".
    static const struct { const char* u; char g; } k[] = {
        {"\xC3\x99", '\xA1'}, {"\xC3\x9A", '\xA2'}, {"\xC3\x9B", '\xA3'}, {"\xC3\x9C", '\xA4'}, {"\xC2\xBF", '\xA5'}, {"\xC3\x8D", '\xA6'},
        {"\xC3\x8F", '\xA7'}, {"\xC3\x91", '\xA9'}, {"\xC3\x92", '\xAA'}, {"\xC3\x93", '\xAB'}, {"\xC3\x94", '\xAC'}, {"\xC3\x95", '\xAD'},
        {"\xC3\x96", '\xAE'}, {"\xC3\x98", '\xAF'}, {"\xC3\xA0", '\xB1'}, {"\xC3\xA1", '\xB2'}, {"\xC3\xA2", '\xB3'}, {"\xC3\xA3", '\xB4'},
        {"\xC3\xA4", '\xB5'}, {"\xC5\x93", '\xB6'}, {"\xC3\xA6", '\xB7'}, {"\xC3\xA7", '\xB8'}, {"\xC3\xA8", '\xB9'}, {"\xC3\xA9", '\xBA'},
        {"\xC3\xAA", '\xBB'}, {"\xC3\xAB", '\xBC'}, {"\xC3\xAC", '\xBD'}, {"\xC3\xAD", '\xBE'}, {"\xC3\xAE", '\xBF'}, {"\xC3\xAF", '\xC0'},
        {"\xC3\xB1", '\xC2'}, {"\xC3\xB2", '\xC3'}, {"\xC3\xB3", '\xC4'}, {"\xC3\xB4", '\xC5'}, {"\xC3\xB5", '\xC6'}, {"\xC3\xB6", '\xC7'},
        {"\xC3\xB9", '\xC9'}, {"\xC3\xBA", '\xCA'}, {"\xC3\xBB", '\xCB'}, {"\xC3\xBC", '\xCC'}, {"\xC3\xBD", '\xCD'}, {"\xE2\x82\xAC", '\xCE'},
        {"\xC3\xBF", '\xCF'}, {"\xC3\x80", '\xD0'}, {"\xC3\x81", '\xD1'}, {"\xC3\x82", '\xD2'}, {"\xC3\x83", '\xD3'}, {"\xC3\x84", '\xD4'},
        {"\xC5\x92", '\xD5'}, {"\xC3\x86", '\xD6'}, {"\xC3\x87", '\xD7'}, {"\xC3\x88", '\xD8'}, {"\xC3\x89", '\xD9'}, {"\xC3\x8A", '\xDA'},
        {"\xC3\x8B", '\xDB'}, {"\xC3\x8C", '\xDC'}, {"\xC3\x8E", '\xDD'}, {"\xC5\xB8", '\xDE'}, {"\xC2\xA1", '\xDF'},
    };
    std::string r;
    for (const char* p = utf8; *p;) {
        bool hecho = false;
        if ((unsigned char)*p >= 0xC2 && fuente())
            for (const auto& e : k)
                if (!std::strncmp(p, e.u, std::strlen(e.u))) { r += e.g; p += std::strlen(e.u); hecho = true; break; }
        if (hecho) continue;
        if ((unsigned char)*p >= 0x80) { ++p; continue; }   // sin fuente: se quita la tilde
        r += *p++;
    }
    return r;
}
int ancho(const std::string& t);
int ancho_negrita(const std::string& t) { return ancho(t) + 1; }
int ancho(const std::string& t) {
    const Fuente* f = fuente();
    if (!f) return int(t.size()) * 6;
    int w = 0;
    f->recorrer(t, [&](int g) { int iz, av; if (g < 0) { w += 4; return; } f->ancho(g, iz, av); w += av; });
    return w;
}
// Texto con degradado vertical (arriba -> abajo) y sombra; der=true alinea a la derecha.
// Usa la fuente del juego (FONT12T) si esta disponible; si no, la fuente provisional.
void texto(int x, int y, const std::string& t, uint32_t c1 = 0xFFF0FFFF, uint32_t c2 = 0xFF8CDCF0, bool der = false,
           uint32_t sombra = 0xFF141846, bool negrita = false) {
    if (der) x -= ancho(t);
    if (const Fuente* f = fuente()) {
        int cx = x;
        f->recorrer(t, [&](int g) {
            if (g < 0) { cx += 4; return; }
            int iz, av; f->ancho(g, iz, av);
            for (int r = 0; r < f->ch; ++r)
                for (int c = 0; c < f->cw; ++c) {
                    const int v = f->pixel(g, c, r);
                    if (!v) continue;
                    // 1 = color del texto, 2 = sombra, 3 = borde claro
                    const uint32_t col = v == 1 ? mezcla(c1, c2, r, std::max(1, f->ch - 1))
                                       : v == 2 ? sombra : c2;
                    pix(cx + iz + c, y + r - 1, col);
                    if (negrita && v == 1) pix(cx + iz + c + 1, y + r - 1, col);   // trazo doble (letra gruesa)
                }
            cx += av;
        });
        return;
    }
    for (int pass = 0; pass < 2; ++pass)
        for (size_t k = 0; k < t.size(); ++k) {
            const int ch = (unsigned char)t[k];
            if (ch < 32 || ch > 126) continue;
            for (int r = 1; r < 11; ++r)
                for (int b = 0; b < 6; ++b)
                    if (kFuente[ch - 32][r] >> b & 1) {
                        if (pass == 0) pix(x + int(k) * 6 + b + 1, y + r, sombra);
                        else pix(x + int(k) * 6 + b, y + r - 1, mezcla(c1, c2, r - 1, 9));
                    }
        }
}
// ---- Sprites del juego (paquete SPF de Level-5 con piezas PAC) -----------------
//  SPF = LZ10( "SFP" + tabla de piezas (nombre, tamano, desplazamiento/32) + datos )
//  PAC = [n, (desp, tam) x n]: paleta (16 colores BGR555), entradas de tile, tiles 4bpp
std::vector<uint8_t> lz10(const std::vector<uint8_t>& in) {
    std::vector<uint8_t> out;
    if (in.size() < 4 || in[0] != 0x10) return out;
    const size_t n = in[1] | in[2] << 8 | in[3] << 16;
    out.reserve(n);
    size_t p = 4;
    while (out.size() < n && p < in.size()) {
        const uint8_t f = in[p++];
        for (int b = 0; b < 8 && out.size() < n && p < in.size(); ++b)
            if (f & (0x80 >> b)) {
                if (p + 1 >= in.size()) return out;
                const int x = in[p] << 8 | in[p + 1]; p += 2;
                const int len = (x >> 12) + 3, disp = (x & 0xFFF) + 1;
                if (size_t(disp) > out.size()) return out;
                for (int k = 0; k < len; ++k) out.push_back(out[out.size() - size_t(disp)]);
            } else out.push_back(in[p++]);
    }
    return out;
}
struct Pieza { uint32_t pal[16 * 16] = {}; std::vector<uint16_t> ent; std::vector<uint8_t> tiles; bool ok = false; };
std::map<std::string, Pieza> g_piezas;
bool g_piezas_cargadas = false;
void cargar_piezas() {
    if (g_piezas_cargadas) return;
    g_piezas_cargadas = true;
    const std::vector<uint8_t> d = lz10(g_smstat);
    if (d.size() < 0x220 || std::memcmp(d.data(), "SFP", 3)) return;
    auto u32 = [&](size_t o) { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0u; };
    for (size_t e = 0x20; e + 16 <= d.size(); e += 16) {
        const uint32_t nom = u32(e), tam = u32(e + 4), des = u32(e + 8);
        if (!nom || nom >= d.size()) break;
        std::string n(reinterpret_cast<const char*>(&d[nom]));
        if (n.find(".PAC") == std::string::npos) break;
        const size_t base = 0x220 + size_t(des) * 32;
        if (base + tam > d.size()) continue;
        const uint8_t* b = &d[base];
        auto v32 = [&](size_t o) { return uint32_t(b[o] | b[o + 1] << 8 | b[o + 2] << 16 | uint32_t(b[o + 3]) << 24); };
        if (v32(0) < 3) continue;
        Pieza pz;
        const uint32_t po = v32(4), ps = v32(8), mo = v32(12), ms = v32(16), to = v32(20), ts = v32(24);
        if (po + ps > tam || mo + ms > tam || to + ts > tam) continue;
        for (uint32_t i = 0; i < ps / 2 && i < 256; ++i) {
            const int c = b[po + 2 * i] | b[po + 2 * i + 1] << 8;
            pz.pal[i] = 0xFF000000u | uint32_t((c & 31) * 255 / 31) << 16 | uint32_t((c >> 5 & 31) * 255 / 31) << 8 | uint32_t((c >> 10 & 31) * 255 / 31);
        }
        for (uint32_t i = 0; i < ms / 2; ++i) pz.ent.push_back(uint16_t(b[mo + 2 * i] | b[mo + 2 * i + 1] << 8));
        pz.tiles.assign(b + to, b + to + ts);
        pz.ok = true;
        g_piezas[n.substr(0, n.find('.'))] = std::move(pz);
    }
}
bool pac_a_pieza(const std::vector<uint8_t>& comprimido, Pieza& pz, bool sin_comprimir = false) {
    const std::vector<uint8_t> d = sin_comprimir ? comprimido : lz10(comprimido);
    auto v32 = [&](size_t o) { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0u; };
    if (d.size() < 0x1C || v32(0) < 3) return false;
    const uint32_t po = v32(4), ps = v32(8), mo = v32(12), ms = v32(16), to = v32(20), ts = v32(24);
    if (size_t(po) + ps > d.size() || size_t(mo) + ms > d.size() || size_t(to) + ts > d.size()) return false;
    for (uint32_t i = 0; i < ps / 2 && i < 256; ++i) {
        const int c = d[po + 2 * i] | d[po + 2 * i + 1] << 8;
        pz.pal[i] = 0xFF000000u | uint32_t((c & 31) * 255 / 31) << 16 | uint32_t((c >> 5 & 31) * 255 / 31) << 8 | uint32_t((c >> 10 & 31) * 255 / 31);
    }
    for (uint32_t i = 0; i < ms / 2; ++i) pz.ent.push_back(uint16_t(d[mo + 2 * i] | d[mo + 2 * i + 1] << 8));
    pz.tiles.assign(d.begin() + to, d.begin() + to + ts);
    pz.ok = true;
    return true;
}
const Pieza* pieza(const char* nombre) {
    cargar_piezas();
    if (!g_piezas.count("Z05") && !g_z05.empty()) { Pieza pz; pac_a_pieza(g_z05, pz); g_piezas["Z05"] = std::move(pz); }
    const auto it = g_piezas.find(nombre);
    return it != g_piezas.end() && it->second.ok ? &it->second : nullptr;
}
// Dibuja el elemento 'indice' de una pieza formada por bloques de w x h tiles
bool sprite(const char* nombre, int indice, int w, int h, int x, int y) {
    const Pieza* pz = pieza(nombre);
    if (!pz) return false;
    const size_t per = size_t(w * h), o = size_t(indice) * per;
    if (o + per > pz->ent.size()) return false;
    for (int ty = 0; ty < h; ++ty)
        for (int tx = 0; tx < w; ++tx) {
            const uint16_t e = pz->ent[o + size_t(ty * w + tx)];
            const int t = e & 0x3FF, hf = e >> 10 & 1, vf = e >> 11 & 1, pb = e >> 12;
            if (size_t(t + 1) * 32 > pz->tiles.size()) continue;
            for (int py = 0; py < 8; ++py)
                for (int px = 0; px < 8; ++px) {
                    const uint8_t by = pz->tiles[size_t(t) * 32 + size_t(py * 4 + px / 2)];
                    const int ci = (px & 1) ? by >> 4 : by & 15;
                    if (!ci) continue;
                    pix(x + tx * 8 + (hf ? 7 - px : px), y + ty * 8 + (vf ? 7 - py : py), pz->pal[(pb * 16 + ci) & 255]);
                }
        }
    return true;
}
// Ultima columna con pixeles de un bloque de sprite (para colocar cosas detras)
int sprite_ultima_col(const char* nombre, int indice, int w, int h) {
    const Pieza* pz = pieza(nombre);
    if (!pz) return -1;
    const size_t per = size_t(w * h), o = size_t(indice) * per;
    if (o + per > pz->ent.size()) return -1;
    int ultima = -1;
    for (int ty = 0; ty < h; ++ty)
        for (int tx = 0; tx < w; ++tx) {
            const uint16_t e = pz->ent[o + size_t(ty * w + tx)];
            const int t = e & 0x3FF, hf = e >> 10 & 1;
            if (size_t(t + 1) * 32 > pz->tiles.size()) continue;
            for (int py = 0; py < 8; ++py)
                for (int px = 0; px < 8; ++px) {
                    const uint8_t by = pz->tiles[size_t(t) * 32 + size_t(py * 4 + px / 2)];
                    if (((px & 1) ? by >> 4 : by & 15) != 0) ultima = std::max(ultima, tx * 8 + (hf ? 7 - px : px));
                }
        }
    return ultima;
}
// Numero con los digitos del juego (cada digito: 1 x 2 tiles = 8 x 16 px), alineado a la derecha
bool numero(const char* digitos, const std::string& t, int x_der, int y) {
    if (!pieza(digitos)) return false;
    int x = x_der - int(t.size()) * 8;
    for (char c : t) {
        const int i = c == '/' ? 10 : c - '0';
        if (i >= 0 && i <= 10) sprite(digitos, i, 1, 2, x, y);
        x += 8;
    }
    return true;
}

// ---- Caras (face2d/*.pkh + *.pkb) ----------------------------------------------
//  .pkh: entradas de 12 bytes (identificador, desplazamiento, tamano) desde 0x30
//  .pkb: cada imagen comprimida con LZ10 -> PAC (paleta, mapa 8x8 tiles, tiles 4bpp)
//  Cabeza: id = cara * 100 + expresion (cara = +0x44 del bloque del jugador)
//  Cuerpo: 1010000 (equipacion de campo) / 1020000 (portero); se superponen en 64x64
struct Imagen64 { uint32_t px[64 * 64] = {}; bool ok = false; };
std::map<uint32_t, Imagen64> g_caras;
const Imagen64* imagen_pk(const std::vector<uint8_t>& h, const std::vector<uint8_t>& b, uint32_t id, uint32_t clave) {
    auto it = g_caras.find(clave);
    if (it != g_caras.end()) return it->second.ok ? &it->second : nullptr;
    Imagen64& im = g_caras[clave];
    auto u32 = [](const std::vector<uint8_t>& v, size_t o) { return uint32_t(v[o] | v[o + 1] << 8 | v[o + 2] << 16 | uint32_t(v[o + 3]) << 24); };
    for (size_t o = 0x30; o + 12 <= h.size(); o += 12) {
        if (u32(h, o) != id) continue;
        const uint32_t des = u32(h, o + 4), tam = u32(h, o + 8);
        if (size_t(des) + tam > b.size()) break;
        const std::vector<uint8_t> d = lz10(std::vector<uint8_t>(b.begin() + des, b.begin() + des + tam));
        if (d.size() < 0x28 || u32(d, 0) < 3) break;
        const uint32_t po = u32(d, 4), mo = u32(d, 12), ms = u32(d, 16), to = u32(d, 20), ts = u32(d, 24);
        if (size_t(to) + ts > d.size() || size_t(mo) + ms > d.size()) break;
        uint32_t pal[16];
        for (int i = 0; i < 16; ++i) {
            const int c = d[po + 2 * i] | d[po + 2 * i + 1] << 8;
            pal[i] = 0xFF000000u | uint32_t((c & 31) * 255 / 31) << 16 | uint32_t((c >> 5 & 31) * 255 / 31) << 8 | uint32_t((c >> 10 & 31) * 255 / 31);
        }
        for (uint32_t k = 0; k < ms / 2 && k < 64; ++k) {
            const int e = d[mo + 2 * k] | d[mo + 2 * k + 1] << 8;
            const int t = e & 0x3FF, hf = e >> 10 & 1, vf = e >> 11 & 1;
            if (size_t(t + 1) * 32 > ts) continue;
            for (int py = 0; py < 8; ++py)
                for (int pxx = 0; pxx < 8; ++pxx) {
                    const uint8_t by = d[to + size_t(t) * 32 + size_t(py * 4 + pxx / 2)];
                    const int ci = (pxx & 1) ? by >> 4 : by & 15;
                    if (!ci) continue;
                    const int X = int(k % 8) * 8 + (hf ? 7 - pxx : pxx), Y = int(k / 8) * 8 + (vf ? 7 - py : py);
                    im.px[Y * 64 + X] = pal[ci];
                }
        }
        im.ok = true;
        break;
    }
    return im.ok ? &im : nullptr;
}
// Retrato del jugador (cuerpo + cabeza) recortado al recuadro [x0,x1] x [y0,y1]
void retrato(int j, int x, int y, int x0, int y0, int x1, int y1) {
    const uint32_t b = base(j);
    const int cara = r16(b + 0x44);
    const bool portero = (r8(b + 0x55) >> 5) == 1;
    // Cuerpo: equipacion (101 campo / 102 portero) + tipo de cuerpo (+0x54: 0 normal,
    // 1 grande, 2 pequeno) * 100 + variante (+0x4E). Si no existe, el cuerpo basico.
    const uint32_t kit = portero ? 1020000u : 1010000u;
    const uint32_t id_cuerpo = kit + uint32_t(r8(b + 0x54)) * 100u + uint32_t(r8(b + 0x4E));
    const Imagen64* cuerpo = imagen_pk(g_fab_h, g_fab_b, id_cuerpo, 0x80000000u | id_cuerpo);
    if (!cuerpo) cuerpo = imagen_pk(g_fab_h, g_fab_b, kit, 0x80000000u | kit);
    const Imagen64* cabeza = imagen_pk(g_fac_h, g_fac_b, uint32_t(cara) * 100u, uint32_t(cara) * 100u);
    if (!cabeza) cabeza = imagen_pk(g_fac_h, g_fac_b, uint32_t(cara) * 100u + 1u, uint32_t(cara) * 100u + 1u);
    for (const Imagen64* im : {cuerpo, cabeza}) {
        if (!im) continue;
        for (int yy = 0; yy < 64; ++yy)
            for (int xx = 0; xx < 64; ++xx) {
                const uint32_t c = im->px[yy * 64 + xx];
                const int X = x + xx, Y = y + yy;
                if (c && X >= x0 && X <= x1 && Y >= y0 && Y <= y1) pix(X, Y, c);
            }
    }
}

// Icono de cabeza de las listas del juego (pic3d/ih): textura de 32x32 a 4 bits,
// lineal. Indice .pkh: entradas (id = cara, tamano comprimido); cada icono ocupa
// un hueco fijo del .pkb (el tamano maximo de la cabecera, +0x1C).
bool icono_lista(int j, int x, int y) {
    static std::map<int, std::vector<uint32_t>> cache;
    if (g_ih_h.size() < 0x30) return false;
    const int cara = r16(base(j) + 0x44);
    auto it = cache.find(cara);
    if (it == cache.end()) {
        std::vector<uint32_t> px;
        auto h32 = [&](size_t o) { return uint32_t(g_ih_h[o] | g_ih_h[o + 1] << 8 | g_ih_h[o + 2] << 16 | uint32_t(g_ih_h[o + 3]) << 24); };
        const uint32_t n = g_ih_h[0x16] | g_ih_h[0x17] << 8, hueco = h32(0x1C);
        for (uint32_t k = 0; k < n && 0x30 + 8 * size_t(k) + 8 <= g_ih_h.size(); ++k) {
            if (int(h32(0x30 + 8 * k)) != cara) continue;
            const size_t o = size_t(k) * hueco, tam = h32(0x34 + 8 * k);
            if (o + tam > g_ih_b.size()) break;
            const std::vector<uint8_t> d = lz10(std::vector<uint8_t>(g_ih_b.begin() + o, g_ih_b.begin() + o + tam));
            auto d32 = [&](size_t q) { return q + 4 <= d.size() ? uint32_t(d[q] | d[q + 1] << 8 | d[q + 2] << 16 | uint32_t(d[q + 3]) << 24) : 0u; };
            const uint32_t to = d32(4), po = d32(12);
            if (d.size() < size_t(to) + 512 || d.size() < size_t(po) + 32) break;
            uint32_t pal[16];
            for (int i = 0; i < 16; ++i) {
                const int c = d[po + 2 * i] | d[po + 2 * i + 1] << 8;
                pal[i] = 0xFF000000u | uint32_t((c & 31) * 255 / 31) << 16 | uint32_t((c >> 5 & 31) * 255 / 31) << 8 | uint32_t((c >> 10 & 31) * 255 / 31);
            }
            px.resize(32 * 32);
            for (int i = 0; i < 32 * 32; ++i) {
                const uint8_t v = d[to + size_t(i / 2)];
                const int c = (i & 1) ? v >> 4 : v & 15;
                px[size_t(i)] = c ? pal[c] : 0;
            }
            break;
        }
        it = cache.emplace(cara, std::move(px)).first;
    }
    if (it->second.empty()) return false;
    for (int yy = 0; yy < 32; ++yy)
        for (int xx = 0; xx < 32; ++xx)
            if (const uint32_t c = it->second[size_t(yy * 32 + xx)]) pix(x + xx, y + yy, c);
    return true;
}

// Nombre de una supertecnica como lo dibuja el juego: pic2d/cmd/en/mbd_c.pkb,
// una entrada por tecnica (id = numero de la tecnica), PAC sin comprimir de
// 14x2 tiles (112x16) con su paleta (rojo con contorno blanco).
bool nombre_tecnica_img(int id, int x, int y, int ancho_max) {
    static std::map<int, Pieza> cache;
    if (g_mbd_h.size() < 0x30) return false;
    auto it = cache.find(id);
    if (it == cache.end()) {
        Pieza pz;
        auto h32 = [&](size_t o) { return uint32_t(g_mbd_h[o] | g_mbd_h[o + 1] << 8 | g_mbd_h[o + 2] << 16 | uint32_t(g_mbd_h[o + 3]) << 24); };
        const uint32_t n = g_mbd_h[0x16] | g_mbd_h[0x17] << 8;
        for (uint32_t k = 0; k < n && 0x30 + 12 * size_t(k) + 12 <= g_mbd_h.size(); ++k) {
            if (int(h32(0x30 + 12 * k)) != id) continue;
            const uint32_t o = h32(0x34 + 12 * k), t = h32(0x38 + 12 * k);
            if (size_t(o) + t <= g_mbd_b.size())
                pac_a_pieza(std::vector<uint8_t>(g_mbd_b.begin() + o, g_mbd_b.begin() + o + t), pz, true);
            break;
        }
        it = cache.emplace(id, std::move(pz)).first;
    }
    const Pieza& pz = it->second;
    if (!pz.ok || pz.ent.size() < 28) return false;
    for (int ty = 0; ty < 2; ++ty)
        for (int tx = 0; tx < 14 && tx * 8 < ancho_max; ++tx) {
            const uint16_t e = pz.ent[size_t(ty * 14 + tx)];
            const int t = e & 0x3FF, hf = e >> 10 & 1, vf = e >> 11 & 1, pb = e >> 12;
            if (size_t(t + 1) * 32 > pz.tiles.size()) continue;
            for (int py = 0; py < 8; ++py)
                for (int px2 = 0; px2 < 8; ++px2) {
                    const uint8_t by = pz.tiles[size_t(t) * 32 + size_t(py * 4 + px2 / 2)];
                    const int ci = (px2 & 1) ? by >> 4 : by & 15;
                    if (ci) pix(x + tx * 8 + (hf ? 7 - px2 : px2), y + ty * 8 + (vf ? 7 - py : py), pz.pal[(pb * 16 + ci) & 255]);
                }
        }
    return true;
}

void icono(int j, int x, int y, int alto) {
    const int cara = r16(base(j) + 0x44);
    const Imagen64* cab = imagen_pk(g_fac_h, g_fac_b, uint32_t(cara) * 100u, uint32_t(cara) * 100u);
    if (!cab) cab = imagen_pk(g_fac_h, g_fac_b, uint32_t(cara) * 100u + 1u, uint32_t(cara) * 100u + 1u);
    if (!cab) return;
    // la cabeza ocupa la parte alta del cuadro: se reduce a 32x32 y se toman 'alto' filas desde arriba
    for (int yy = 0; yy < alto && yy < 32; ++yy)
        for (int xx = 0; xx < 32; ++xx) {
            int n = 0, r = 0, g = 0, bl = 0;
            for (int k = 0; k < 4; ++k) {
                const uint32_t c = cab->px[(yy * 2 + k / 2 + 2) * 64 + xx * 2 + (k & 1)];
                if (c) { ++n; r += (c >> 16) & 255; g += (c >> 8) & 255; bl += c & 255; }
            }
            if (n >= 2) pix(x + xx - 3, y + yy - 2, 0xFF000000u | uint32_t(r / n) << 16 | uint32_t(g / n) << 8 | uint32_t(bl / n));
        }
}

void flecha(int x, int y, bool izq, uint32_t c) {
    for (int i = 0; i < 4; ++i) for (int k = -i; k <= i; ++k) pix(izq ? x + i : x + 3 - i, y + 3 + k, c);
}
// Boton al estilo del juego ("A Cambiar", "B Salir"): caja gris oscura con borde
// redondeado, circulo naranja con la letra blanca y el texto en claro.
struct Zona { int x = 0, w = 0; } g_boton_a, g_boton_b, g_boton_x, g_boton_y, g_conf_a, g_conf_b;
constexpr int kConfY = 124;                     // fila de botones de la ventana "Volver al nivel 1"
void boton(int x, int y, int w, const char* letra, const std::string& txt) {
    const int h = 12;
    rect(x + 1, y, x + w - 2, y + h - 1, 0xFF2A2A30);
    rect(x, y + 1, x + w - 1, y + h - 2, 0xFF2A2A30);
    for (int i = x + 1; i < x + w - 1; ++i) { pix(i, y, 0xFF7C7C88); pix(i, y + h - 1, 0xFF101014); }
    // circulo naranja (diametro 10)
    static const char* kCirc[10] = {"...####...", ".########.", "##########", "##########", "##########",
                                    "##########", "##########", "##########", ".########.", "...####..."};
    for (int r = 0; r < 10; ++r)
        for (int c = 0; c < 10; ++c)
            if (kCirc[r][c] == '#') pix(x + 2 + c, y + 1 + r, r < 5 ? 0xFFF89838 : 0xFFE06810);
    texto(x + 4, y + 1, letra, 0xFFFFFFFF, 0xFFFFE8C8);
    texto(x + 14, y + 1, txt, 0xFFE8E8F0, 0xFFB0B0C0);
}
}  // namespace ent

namespace ent {
uint32_t buf_arriba[256 * 192];
// Fondo de 256x192 de un .pac_ de pic2d (LZ10; partes: paleta de 16 colores, mapa de 32x24
// entradas, tiles de 4 bits; el color 0 es transparente y se queda en "vacio")
bool render_pac(const std::vector<uint8_t>& comp, std::vector<uint32_t>& out, uint32_t vacio) {
    const std::vector<uint8_t> d = lz10(comp);
    if (d.size() < 28) return false;
    auto u32 = [&](size_t o) { return uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24); };
    if (u32(0) < 3) return false;
    const size_t po = u32(4), ps = u32(8), mo = u32(12), ms = u32(16), to = u32(20), ts = u32(24);
    if (ps < 32 || po + ps > d.size() || mo + ms > d.size() || to + ts > d.size() || ms < 32 * 24 * 2) return false;
    uint32_t pal[16];
    for (int i = 0; i < 16; ++i) {
        const uint16_t c = uint16_t(d[po + 2 * i] | d[po + 2 * i + 1] << 8);
        pal[i] = 0xFF000000u | uint32_t((c & 31) * 255 / 31) << 16 | uint32_t((c >> 5 & 31) * 255 / 31) << 8 |
                 uint32_t((c >> 10 & 31) * 255 / 31);
    }
    out.assign(256 * 192, vacio);
    for (int k = 0; k < 32 * 24; ++k) {
        const uint16_t e = uint16_t(d[mo + 2 * k] | d[mo + 2 * k + 1] << 8);
        const int t = e & 0x3FF, hf = e >> 10 & 1, vf = e >> 11 & 1, tx = (k % 32) * 8, ty = (k / 32) * 8;
        if (size_t(t + 1) * 32 > ts) continue;
        for (int py = 0; py < 8; ++py)
            for (int px = 0; px < 8; ++px) {
                const uint8_t by = d[to + size_t(t) * 32 + size_t(py * 4 + px / 2)];
                const int ci = (px & 1) ? by >> 4 : by & 15;
                if (ci) out[size_t((ty + (vf ? 7 - py : py)) * 256 + tx + (hf ? 7 - px : px))] = pal[ci];
            }
    }
    return true;
}
// Fondos del menu en el idioma de los textos (se hacen la primera vez que se abre):
//  - arriba: msup_bg03 del juego (antes, una copia fija en espanol);
//  - abajo: el diseno en espanol o en ingles; en otro idioma, el fondo limpio con las 7
//    etiquetas de msup_bg02 (Tiro, Fisico, Control, Defensa | Rapidez, Aguante, Valor) y la
//    palabra "Libertad" escrita con la fuente del juego (g_cabecera_propia).
bool g_fondos_hechos = false, g_cabecera_propia = false;
struct Etiqueta { int x1 = 224, y0 = 12, y1 = 22; bool hecha = false; } g_etq;
void preparar_fondos() {
    if (g_fondos_hechos) return;
    g_fondos_hechos = true;
    std::vector<uint32_t> f;
    if (!g_msup_bg03.empty() && render_pac(g_msup_bg03, f, 0xFF02344Du)) g_fondo_ficha = f;
    const std::string& l = g_idioma_textos;
    if (l == "es" && !g_fondo_es.empty()) { g_fondo_abajo = g_fondo_es; return; }
    if (l == "en" && !g_fondo_en.empty()) { g_fondo_abajo = g_fondo_en; return; }
    if (g_fondo_limpio.empty() || g_msup_bg02.empty() || !render_pac(g_msup_bg02, f, 0)) {
        if (!g_fondo_en.empty()) g_fondo_abajo = g_fondo_en;          // sin lo necesario: en ingles
        return;
    }
    // etiqueta = pixeles claros del texto en su barra de msup_bg02 (barras con la linea de
    // abajo en y = 88/104/120/136, columnas x 13-105 y 133-225); van a las barras del menu
    // (linea de abajo en y = 73 + 12 k), empezando en x = 124
    static const struct { int x0, x1, linea; } kOrigen[7] = {
        {13, 105, 88}, {13, 105, 104}, {13, 105, 120}, {13, 105, 136}, {133, 225, 88}, {133, 225, 104}, {133, 225, 120}};
    std::vector<uint32_t> fondo = g_fondo_limpio;
    auto claro = [](uint32_t c) { return (c >> 24) && (c >> 8 & 255) >= 180 && (c & 255) >= 180 && (c >> 16 & 255) >= 100; };
    for (int i = 0; i < 7; ++i) {
        const auto& o = kOrigen[i];
        int minx = 999;
        for (int y = o.linea - 13; y < o.linea; ++y)
            for (int x = o.x0; x <= o.x1; ++x)
                if (claro(f[size_t(y * 256 + x)])) minx = std::min(minx, x);
        if (minx == 999) continue;
        const int linea = 73 + 12 * i;
        for (int y = o.linea - 13; y < o.linea; ++y)
            for (int x = o.x0; x <= o.x1; ++x) {
                const uint32_t c = f[size_t(y * 256 + x)];
                const int dx = 124 + (x - minx), dy = linea + (y - o.linea);
                if (claro(c) && dx <= 207) fondo[size_t(dy * 256 + dx)] = c;
            }
    }
    g_fondo_abajo = fondo;
    g_cabecera_propia = true;
    g_etq.x1 = 223; g_etq.y0 = 14; g_etq.y1 = 22; g_etq.hecha = true;   // para el numero de la Libertad
}
// "Libertad" en la cabecera del fondo limpio, en el idioma de los textos
void cabecera_propia() {
    if (!g_cabecera_propia) return;
    const std::string w = J(T5("Freedom", "Libertad", "Libert\xC3\xA9", "Freiheit", "Libert\xC3\xA0"));
    texto(224 - ancho_negrita(w), 13, w, 0xFFCDFFF6, 0xFF83EEEE, false, 0xFF141846, true);   // como el diseno
}
// Posicion de la etiqueta de la Libertad en el fondo (su ancho cambia con el idioma:
// "Libertad", "Freedom"...). Se busca el texto claro en la cabecera (y 5..30).
void detectar_etiqueta() {
    if (g_etq.hecha || g_fondo_abajo.empty()) return;
    g_etq.hecha = true;
    int x1 = -1, y0 = 99, y1 = -1;
    for (int y = 7; y < 29; ++y)
        for (int x = 120; x < 250; ++x) {
            const uint32_t c = g_fondo_abajo[y * 256 + x];
            const int r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255;
            if (g > 200 && b > 200 && r > 120) { x1 = std::max(x1, x); y0 = std::min(y0, y); y1 = std::max(y1, y); }
        }
    if (x1 >= 0) { g_etq.x1 = x1; g_etq.y0 = y0; g_etq.y1 = y1; }
}
// Texto del juego -> ASCII de la fuente provisional (sin tildes)
std::string ascii(const uint8_t* p, size_t max) {
    std::string r;
    for (size_t i = 0; i < max && p[i]; ++i) {
        uint8_t c = p[i];
        static const char* kAcentos = "AAAAAAACEEEEIIIIDNOOOOOxOUUUUYPsaaaaaaaceeeeiiiidnooooo/ouuuuypy";
        if (c >= 0xC0) c = uint8_t(kAcentos[c - 0xC0]);
        else if (c == '\n') c = ' ';
        else if (c < 0x20 || c > 0x7E) continue;
        r += char(c);
    }
    return r;
}
std::string bruto(const uint8_t* p, size_t max) {
    std::string r;
    for (size_t i = 0; i < max && p[i]; ++i) r += p[i] == '\n' ? ' ' : char(p[i]);
    return r;
}
std::string texto_juego(const uint8_t* p, size_t max) { return fuente() ? bruto(p, max) : ascii(p, max); }
std::string nombre_objeto(int id) {
    if (id <= 0 || size_t(id + 1) * 48 > g_itemdat.size()) return "";
    return texto_juego(g_itemdat.data() + size_t(id) * 48, 32);
}
std::string nombre_tecnica(int id) {
    if (id <= 0 || size_t(id + 1) * 28 > g_cmddat.size()) return "";
    const size_t n = g_cmddat[size_t(id) * 28 + 20] | g_cmddat[size_t(id) * 28 + 21] << 8;
    if ((n + 1) * 32 > g_cmdstr.size()) return "";
    return texto_juego(g_cmdstr.data() + n * 32, 32);
}
int tipo_tecnica(int id) { return (id > 0 && size_t(id + 1) * 28 <= g_cmddat.size()) ? g_cmddat[size_t(id) * 28] : 0; }
int elemento_tecnica(int id) { return (id > 0 && size_t(id + 1) * 28 <= g_cmddat.size()) ? g_cmddat[size_t(id) * 28 + 8] : 0; }

void dibujar_ficha(int j) {
    // se dibuja en buf_arriba reutilizando las primitivas (que pintan en buf)
    static uint32_t copia[256 * 192];
    std::memcpy(copia, buf, sizeof(buf));
    preparar_fondos();
    if (g_fondo_ficha.size() != 256 * 192) { std::memcpy(buf, copia, sizeof(buf)); return; }
    std::memcpy(buf, g_fondo_ficha.data(), sizeof(buf));
    const uint32_t b = base(j);
    retrato(j, 8, 7, 10, 10, 70, 69);         // recuadro de la cara de la ficha
    {   // nombre completo y corto, centrados en sus barras, en blanco como en el juego
        const std::string n1 = nombre(j);
        uint8_t corto[16];
        for (int k = 0; k < 16; ++k) corto[k] = r8(b + 0x20 + k);
        const std::string n2 = texto_juego(corto, 16);
        texto(124 - ancho(n1) / 2, 19, n1, 0xFFF8F8F8, 0xFFF8F8F8);
        texto(125 - ancho(n2) / 2, 33, n2, 0xFFF8F8F8, 0xFFF8F8F8);
    }
    {   // "Niv." y el nivel con los graficos del juego
        const std::string nv = std::to_string(r8(b + 0xAA));
        if (sprite("MSUP_F08", 1, 2, 1, 176, 21)) {
            // "Niv" + punto (como el original) + un hueco + el nivel
            const int fin = 176 + std::max(10, sprite_ultima_col("MSUP_F08", 1, 2, 1));
            pix(fin + 2, 26, 0xFF83CDE6); pix(fin + 3, 27, 0xFF29295A);     // punto y su sombra
            numero("MSUP_F10", nv, fin + 5 + int(nv.size()) * 8, 15);
        }   // "Niv" = tiles 2-3 de F08
        else texto(172, 16, std::string(T5("Lv.", "Niv.", "Niv.", "Lv.", "Liv.")) + nv, 0xFFB4E6FF, 0xFF64B4E6);
    }
    {   // insignia de posicion (+0x55 >> 5: 1 PR, 2 DF, 3 MD, 4 DL) y elemento (+0x5A)
        static const int kInsignia[5] = {-1, 1, 2, 3, 0};   // orden en MSUP_F09: DL, PR, DF, MD
        const int pos = r8(b + 0x55) >> 5;
        if (pos >= 1 && pos <= 4) sprite("MSUP_F09", kInsignia[pos], 4, 3, 216, 8);
        static const char* kElem[5] = {nullptr, "MSUP_Z01", "MSUP_Z02", "MSUP_Z03", "MSUP_Z04"};
        const int el = r8(b + 0x5A);
        if (el >= 1 && el <= 4) sprite(kElem[el], 0, 4, 2, 216, 31);
        // genero (+0x52: 1 chico, 2 chica; MSUP_F12, 2x2) y dorsal (+0xB7: 1-16; MSUP_F07, 3x2)
        const int genero = r8(b + 0x52), dorsal = r8(b + 0xB7);
        if (genero >= 1 && genero <= 2) sprite("MSUP_F12", genero - 1, 2, 2, 168, 31);
        if (dorsal >= 1 && dorsal <= 16) sprite("MSUP_F07", dorsal - 1, 3, 2, 184, 33);
    }
    const std::string pe = std::to_string(r16(b + 0x94)) + "/" + std::to_string(r16(b + 0xD0));
    const std::string pt = std::to_string(r16(b + 0x96)) + "/" + std::to_string(r16(b + 0xD2));
    if (sprite("MSUP_F05", 0, 2, 2, 78, 47) && sprite("MSUP_F05", 1, 2, 2, 166, 47)) {
        numero("MSUP_F04", pe, 96 + int(pe.size()) * 8, 47);
        numero("MSUP_F03", pt, 184 + int(pt.size()) * 8, 47);
    } else {
        texto(80, 50, "PE " + pe, 0xFFFFF070, 0xFFF0A020);
        texto(166, 50, "PT " + pt, 0xFFB4FF8C, 0xFF50C850);
    }
    // Equipo: botas y dos accesorios
    texto(5, 101, nombre_objeto(r16(b + 0x70)), 0xFFF8F8F8, 0xFFF8F8F8);
    texto(5, 148, nombre_objeto(r16(b + 0x72)), 0xFFF8F8F8, 0xFFF8F8F8);
    texto(5, 169, nombre_objeto(r16(b + 0x74)), 0xFFF8F8F8, 0xFFF8F8F8);
    // Supertecnicas (6): etiqueta de tipo del juego (msup_z05: Regate, Bloqueo,
    // Tiro, Atajo, ?, Talento; 3x2 tiles) y el nombre en rojo sobre recuadros blancos
    static const int kEtiqueta[10] = {4, 4, 4, 4, 4, 0, 1, 2, 3, 5};
    for (int k = 0; k < 6; ++k) {
        const int id = r16(b + 0x98 + 2 * k);
        if (!id) continue;
        const int y = 90 + 16 * k;
        const int t = tipo_tecnica(id);
        const int yf = 87 + 16 * k;                         // a un pixel por encima de la linea de abajo, como el original                         // posiciones medidas sobre el original
        if (!sprite("Z05", kEtiqueta[t <= 9 ? t : 4], 3, 2, 128, yf)) rect(129, yf + 2, 150, yf + 11, 0xFF707080);
        if (nombre_tecnica_img(id, 152, yf, 100)) continue; // el nombre dibujado del propio juego
        std::string n = nombre_tecnica(id);
        while (!n.empty() && ancho_negrita(n) + 6 > 95) n.pop_back();   // que quepa en la fila
        // recuadro blanco con borde rojo detras de cada palabra
        int x = 158;
        size_t ini = 0;
        while (ini < n.size()) {
            size_t fin = n.find(' ', ini);
            if (fin == std::string::npos) fin = n.size();
            const std::string w = n.substr(ini, fin - ini);
            const int aw = ancho_negrita(w);
            if (aw > 0) {
                rect(x - 1, y, x + aw, y + 11, 0xFFD82828);
                rect(x, y + 1, x + aw - 1, y + 10, 0xFFF8F8F8);
                texto(x, y + 1, w, 0xFFE02020, 0xFFB01010, false, 0xFFF8F8F8, true);   // letra gruesa, como el juego
            }
            x += aw + 3;
            ini = fin + 1;
        }
    }
    std::memcpy(buf_arriba, buf, sizeof(buf));
    std::memcpy(buf, copia, sizeof(buf));
}

// ---- acciones sobre una fila --------------------------------------------------
bool ctrl_pulsado() {
#if defined(_WIN32)
    return (GetKeyState(VK_CONTROL) & 0x8000) != 0;
#else
    return false;
#endif
}
void sumar(int f) { if (puede_sumar(jug, f)) ++asig[f]; aviso_t = 90; }
void quitar(int f) { if (asig[f] > 0) --asig[f]; }
void sumar_max(int f) {                 // Ctrl + derecha: todo lo que se pueda
    for (int k = 0; k < 2000 && puede_sumar(jug, f); ++k) ++asig[f];
    aviso_t = 90;
}
void quitar_todo(int f) { asig[f] = 0; } // Ctrl + izquierda
void accion(int f, int dir) {
    if (dir > 0) { if (ctrl_pulsado()) sumar_max(f); else sumar(f); }
    else         { if (ctrl_pulsado()) quitar_todo(f); else quitar(f); }
}
void cambiar_jugador(int dir) {
    auto it = std::find(lista.begin(), lista.end(), jug);
    size_t i = it == lista.end() ? 0 : size_t(it - lista.begin());
    i = dir > 0 ? (i + 1) % lista.size() : (i + lista.size() - 1) % lista.size();
    jug = lista[i];
    std::fill(std::begin(asig), std::end(asig), 0);
}

// ---- mantener pulsado: repeticion (teclas y raton) ----------------------------
// Primer paso al pulsar; tras ~0.3 s repite cada 4 fotogramas y, tras 1 s, en
// cada fotograma.
uint16_t mantenidos = 0;                // botones DS mantenidos ahora
int rep_cont = 0;                       // fotogramas que lleva mantenida la accion
int tq_x = 0, tq_y = 0, tq_fila = -1, tq_dir = 0;   // raton mantenido sobre una flecha
bool toque_previo = false;
bool toca_repetir(int cont) {
    if (cont < 18) return false;
    if (cont < 60) return (cont - 18) % 4 == 0;
    return true;
}
int tq_nivel = 0;                       // raton mantenido sobre una flecha de la ventana de nivel (-1 / +1)
void tic() {                            // una vez por fotograma con el menu abierto
    if (nivel_abierto) {                // ventana de nivel: mantener la flecha (o el raton) repite
        int dir = 0;
        if (toque_previo && tq_nivel) dir = tq_nivel;
        else if (mantenidos & 0x10) dir = 1;
        else if (mantenidos & 0x20) dir = -1;
        if (dir) { ++rep_cont; if (toca_repetir(rep_cont)) cambiar_nivel(dir, false); }
        else rep_cont = 0;
        return;
    }
    if (confirmar) { rep_cont = 0; return; }
    int dir = 0, dv = 0;
    if (mantenidos & 0x10) dir = 1; else if (mantenidos & 0x20) dir = -1;
    if (mantenidos & 0x40) dv = -1; else if (mantenidos & 0x80) dv = 1;
    if (toque_previo && tq_fila >= 0) {
        const int yb = 42 + 12 * tq_fila;
        const bool dentro = tq_y >= yb - 3 && tq_y <= yb + 8 &&
                            ((tq_dir < 0 && tq_x >= 12 && tq_x <= 23) || (tq_dir > 0 && tq_x >= 58 && tq_x <= 69));
        if (dentro) { ++rep_cont; if (toca_repetir(rep_cont) && !ctrl_pulsado()) accion(tq_fila, tq_dir); }
        return;
    }
    if (dir || dv) {
        ++rep_cont;
        if (toca_repetir(rep_cont)) {
            if (dir && !ctrl_pulsado()) accion(fila, dir);
            if (dv && (rep_cont - 18) % 6 == 0) fila = (fila + kFilas + dv) % kFilas;
        }
    } else rep_cont = 0;
}

// ---- tactil / raton sobre la pantalla inferior ------------------------------
void toque(int x, int y, bool abajo) {
    const bool nuevo = abajo && !toque_previo;
    toque_previo = abajo;
    tq_x = x; tq_y = y;
    if (!abajo) { tq_fila = -1; tq_nivel = 0; rep_cont = 0; return; }
    if (!nuevo || !abierto) return;
    rep_cont = 0;
    if (nivel_abierto) {                                  // ventana "Subir de nivel"
        if (y >= 70 && y <= 88) { tq_nivel = x < 128 ? -1 : 1; cambiar_nivel(tq_nivel, ctrl_pulsado()); }
        else if (y >= kConfY && y <= kConfY + 11 && x >= g_conf_a.x && x < g_conf_a.x + g_conf_a.w) { if (subir_nivel(jug, nivel_obj)) nivel_abierto = false; aviso_t = 150; }
        else if (y >= kConfY && y <= kConfY + 11 && x >= g_conf_b.x && x < g_conf_b.x + g_conf_b.w) nivel_abierto = false;
        return;
    }
    if (confirmar) {                                      // ventana "Volver al nivel 1"
        if (y >= kConfY && y <= kConfY + 11 && x >= g_conf_a.x && x < g_conf_a.x + g_conf_a.w) { reiniciar(jug); aviso_t = 150; confirmar = false; }
        else if (y >= kConfY && y <= kConfY + 11 && x >= g_conf_b.x && x < g_conf_b.x + g_conf_b.w) confirmar = false;
        return;
    }
    for (int f = 0; f < kFilas; ++f) {                    // filas
        const int yb = 42 + 12 * f;
        if (y < yb - 3 || y > yb + 8) continue;
        fila = f;
        if (x >= 12 && x <= 23) { accion(f, -1); tq_fila = f; tq_dir = -1; }
        else if (x >= 58 && x <= 69) { accion(f, 1); tq_fila = f; tq_dir = 1; }
        return;
    }
    if (y >= 162 && y <= 173 && x >= g_boton_a.x && x < g_boton_a.x + g_boton_a.w) { aplicar(jug); aviso_t = 120; return; }  // A
    if (y >= 162 && y <= 173 && x >= g_boton_b.x && x < g_boton_b.x + g_boton_b.w) { abierto = false; return; }              // B
    if (y >= 174 && y <= 185 && x >= g_boton_x.x && x < g_boton_x.x + g_boton_x.w) { pedir_reinicio(); return; }             // X
    if (y >= 174 && y <= 185 && x >= g_boton_y.x && x < g_boton_y.x + g_boton_y.w) { abrir_nivel(); return; }                // Y
    if (y >= 174 && y <= 186 && x >= 150 && x <= 170) cambiar_jugador(-1);                         // L
    else if ((y >= 174 && y <= 186 && x >= 236 && x <= 254) || (y >= 4 && y <= 28 && x >= 6 && x <= 120))
        cambiar_jugador(1);                                                                        // R / tocar el nombre
}
}  // namespace ent

IE1_EXPORT void ie1_mods_overlay_toque_v1(int x, int y, int abajo) {
    if (filtros::abierto) { filtros::toque(x, y, abajo != 0); return; }
    ent::toque(x, y, abajo != 0);
}
// Con el menu propio cerrado: el ejecutable pasa aqui los botones y el tactil; si el
// complemento los usa (por ejemplo, X en los cuadernos abre los filtros), devuelve 1 y
// el juego no los recibe (parche_overlay_vigilar.py).
IE1_EXPORT int ie1_mods_vigilar_teclas_v1(uint16_t pulsados) { return filtros::vigilar_teclas(pulsados); }
IE1_EXPORT int ie1_mods_vigilar_toque_v1(int x, int y, int abajo) { return filtros::vigilar_toque(x, y, abajo != 0); }
// Tecla T: desactivada. El menu solo se abre desde el NPC entrenador (su guion
// manda la senal). Para pruebas se puede volver a activar con IE1_TECLA_T=1.
IE1_EXPORT int ie1_mods_overlay_disponible_v1() {
    static const bool tecla_t = [] { const char* e = std::getenv("IE1_TECLA_T"); return e && *e == '1'; }();
    return (!g_fondo_abajo.empty() && tecla_t) ? 1 : 0;
}
IE1_EXPORT int ie1_mods_overlay_activo_v1() { return (ent::abierto || filtros::abierto) ? 1 : 0; }
IE1_EXPORT void ie1_mods_overlay_alternar_v1() {
    if (g_fondo_abajo.empty() || !g_mem) return;
    ent::abierto = !ent::abierto;
    if (ent::abierto) {
        ent::cargar_lista();
        if (std::find(ent::lista.begin(), ent::lista.end(), ent::jug) == ent::lista.end()) ent::jug = ent::lista[0];
        std::fill(std::begin(ent::asig), std::end(ent::asig), 0);
        ent::confirmar = false;
        ent::nivel_abierto = false;
        ent::fila = 2;                            // empieza en Tiro
        ent::prev = 0xFFFF;                       // ignorar los botones que ya estaban pulsados
    }
}
// Botones DS (bit 0 A, 1 B, 2 Select, 3 Start, 4 der, 5 izq, 6 arr, 7 aba, 8 R, 9 L)
IE1_EXPORT void ie1_mods_overlay_teclas_v1(uint16_t pulsados) {
    if (filtros::abierto) { filtros::teclas(pulsados); return; }
    using namespace ent;
    if (!abierto) { prev = pulsados; mantenidos = 0; return; }
    const uint16_t nuevos = uint16_t(pulsados & ~prev);
    prev = pulsados;
    mantenidos = pulsados == 0xFFFF ? 0 : pulsados;
    if (nivel_abierto) {                          // ventana "Subir de nivel"
        if (nuevos & 0x30) rep_cont = 0;          // nueva direccion: reinicia la repeticion
        if (nuevos & 0x10) cambiar_nivel(1, ctrl_pulsado());
        if (nuevos & 0x20) cambiar_nivel(-1, ctrl_pulsado());
        if (nuevos & 0x01) { if (subir_nivel(jug, nivel_obj)) nivel_abierto = false; aviso_t = 150; }
        else if (nuevos & 0x802) nivel_abierto = false;
        return;
    }
    if (confirmar) {                              // ventana "Volver al nivel 1": A si, B / X no
        if (nuevos & 0x01) { reiniciar(jug); aviso_t = 150; confirmar = false; }
        else if (nuevos & 0x402) confirmar = false;
        return;
    }
    if (nuevos & 0xF0) rep_cont = 0;              // nueva direccion: reinicia la repeticion
    if (nuevos & 0x40) fila = (fila + kFilas - 1) % kFilas;
    if (nuevos & 0x80) fila = (fila + 1) % kFilas;
    if (nuevos & 0x10) accion(fila, 1);           // derecha (Ctrl: el maximo posible)
    if (nuevos & 0x20) accion(fila, -1);          // izquierda (Ctrl: quitar todo)
    if (nuevos & 0x100) cambiar_jugador(1);       // R
    if (nuevos & 0x200) cambiar_jugador(-1);      // L
    if (nuevos & 0x01) { aplicar(jug); aviso_t = 120; }
    if (nuevos & 0x02) abierto = false;
    if (nuevos & 0x400) pedir_reinicio();         // X: volver al nivel 1
    if (nuevos & 0x800) abrir_nivel();            // Y: subir de nivel
}
// ---- Panel de "Valor" en las escenas de las supertecnicas --------------------------
// Dibuja con los graficos del juego (mbd_*.pac_) encima de la pantalla de arriba, en
// coordenadas de la DS. Izquierda = tu jugador, derecha = el rival. Los numeros suben
// como en el juego y al final el ganador queda en rojo y el perdedor en morado.
namespace valorov {
struct Img { int w = 0, h = 0; std::vector<uint32_t> px; };   // 0 = transparente
// PAC: [n, (desplazamiento, tamano) x n]: textura 4bpp lineal, paleta de 16, descriptor de cuadros
// descriptor: [num u16, ?, log2(ancho/8), ...] y por cuadro (x, y, w, h) u16
std::vector<Img> decodificar(const std::vector<uint8_t>& comprimido) {
    std::vector<Img> r;
    if (comprimido.empty()) return r;
    const std::vector<uint8_t> d = ent::lz10(comprimido);
    if (d.size() < 28) return r;
    auto u32 = [&](size_t o) { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0u; };
    auto u16 = [&](size_t o) { return o + 2 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8) : 0u; };
    if (u32(0) < 3) return r;
    const size_t t0 = u32(4), tl = u32(8), p0 = u32(12), q0 = u32(20);
    if (q0 + 8 > d.size() || t0 + tl > d.size()) return r;
    uint32_t pal[16];
    for (int i = 0; i < 16; ++i) {
        const uint32_t c = u16(p0 + 2 * size_t(i));
        pal[i] = 0xFF000000u | ((c & 31) * 255 / 31) << 16 | ((c >> 5 & 31) * 255 / 31) << 8 | ((c >> 10 & 31) * 255 / 31);
    }
    const int ancho_tex = 8 << (d[q0 + 2] & 7);
    const int alto_tex = int(tl * 2 / size_t(ancho_tex));
    const int n = int(u16(q0));
    for (int k = 0; k < n; ++k) {
        const size_t e = q0 + 8 + 8 * size_t(k);
        if (e + 8 > d.size()) break;
        Img im;
        const int fx = int(u16(e)), fy = int(u16(e + 2));
        im.w = int(u16(e + 4)); im.h = int(u16(e + 6));
        im.px.assign(size_t(im.w * im.h), 0u);
        for (int y = 0; y < im.h; ++y)
            for (int x = 0; x < im.w; ++x) {
                const int tx = fx + x, ty = fy + y;
                if (tx >= ancho_tex || ty >= alto_tex) continue;
                const size_t o = t0 + size_t(ty * ancho_tex + tx) / 2;
                const int ci = (tx & 1) ? d[o] >> 4 : d[o] & 15;
                if (ci) im.px[size_t(y * im.w + x)] = pal[ci];
            }
        r.push_back(std::move(im));
    }
    return r;
}
std::vector<Img> g_dig, g_izq;
std::map<int, std::vector<Img>> g_der;
bool g_listo = false;
void preparar() {
    if (g_listo) return;
    g_listo = true;
    g_dig = decodificar(g_mbd_num);
    g_izq = decodificar(g_mbd_izq);
    for (const auto& e : g_mbd_der) g_der[e.first] = decodificar(e.second);
    logf("[valor] panel: %zu digitos, panel izquierdo %s, %zu paneles de equipo", g_dig.size(),
         g_izq.empty() ? "no" : "si", g_der.size());
}
std::vector<uint32_t> g_buf;
int g_w = 0;
void poner(int x, int y, uint32_t c) {
    if (x < 0 || y < 0 || x >= g_w || y >= 192) return;
    g_buf[size_t(y * g_w + x)] = c;
}
void imagen(const Img& im, int x, int y, int filas = 1 << 30) {
    for (int j = 0; j < im.h && j < filas; ++j)
        for (int i = 0; i < im.w; ++i)
            if (const uint32_t c = im.px[size_t(j * im.w + i)]) poner(x + i, y + j, c);
}
// colores del juego: relleno rojo (ganador), morado (perdedor), blanco mientras cuenta
constexpr uint32_t kRojo = 0xFFFF2C2Cu, kMorado = 0xFFBE45FFu;
void digito(int dgt, int x, int y, uint32_t relleno) {
    if (dgt < 0 || dgt >= int(g_dig.size())) return;
    const Img& im = g_dig[size_t(dgt)];
    for (int j = 0; j < 24; ++j)                 // el juego los estira en vertical (16 -> 24)
        for (int i = 0; i < im.w; ++i) {
            uint32_t c = im.px[size_t((j * im.h / 24) * im.w + i)];
            if (!c) continue;
            const int r = c >> 16 & 255, g = c >> 8 & 255, b = c & 255;
            if (relleno && r > 200 && g > 200 && b > 200) c = relleno;   // el blanco es el relleno
            poner(x + i, y + j, c);
        }
}
// numero alineado a la derecha: su borde derecho en x_der
void numero(int v, int x_der, int y, uint32_t relleno) {
    const std::string s = std::to_string(std::clamp(v, 0, 999));
    int x = x_der - 16 * int(s.size());
    for (char ch : s) { digito(ch - '0', x, y, relleno); x += 16; }
}
struct Estado {
    bool visible = false;
    int izq = -1, der = -1;          // -1 = sin valor en ese lado
    int ganador = 0;                 // 0 ninguno, 1 izquierda, 2 derecha
    int equipo_der = 1;              // panel derecho (equipo rival)
    int t = 0;                       // fotogramas desde que aparecio
    int dur = 600;                   // fotogramas que dura como mucho
    int rodar = 0;                   // fotogramas de "calculando" antes de ensenar el valor
} g_est;
constexpr int kCuenta = 24;          // fotogramas que tardan en subir los numeros
void panel_lado(bool izquierda, int v, int t) {
    const int px = izquierda ? 0 : 256 - 80, py = 0;
    const std::vector<Img>* p = izquierda ? &g_izq : nullptr;
    if (!izquierda) {
        auto it = g_der.find(g_est.equipo_der);
        if (it == g_der.end()) it = g_der.find(1);
        if (it != g_der.end()) p = &it->second;
    }
    // sin la placa con el nombre del equipo (filas 48-59): solo el titulo y la burbuja
    // (filas 0-43). IE1_VALOR_PLACA=1 para dibujarla tambien.
    static const bool placa = [] { const char* e = std::getenv("IE1_VALOR_PLACA"); return e && *e == '1'; }();
    if (p && !p->empty()) imagen((*p)[0], px, py, placa ? 64 : 44);
    if (v >= 0 && t < g_est.rodar) v = -2;   // "calculando" un rato antes de ensenar el valor
    else if (v >= 0) t -= g_est.rodar;
    if (v == -2) {                   // el juego aun no lo ha calculado: "calculando", numeros al azar
        static uint32_t r = 12345;
        r = r * 1103515245u + 12345u;
        numero(int(100 + (r >> 16) % 200), px + (izquierda ? 58 : 74), py + 13, 0);
        return;
    }
    const int mostrado = t >= kCuenta ? v : v * t / kCuenta;
    uint32_t relleno = 0;            // contando: como el juego, sin color de resultado todavia
    if (t >= kCuenta) {
        if (g_est.ganador == 0) relleno = kRojo;
        else relleno = ((g_est.ganador == 1) == izquierda) ? kRojo : kMorado;
    }
    numero(mostrado, px + (izquierda ? 58 : 74), py + 13, relleno);
}
void avanzar();   // mas abajo: fases del panel
// Compone el panel sobre la pantalla de arriba. Devuelve el bufer o nullptr.
void pantalla(const uint32_t* px, int ancho);
extern bool g_est_tiro, g_tiro_giraba, g_reg_panel;   // (mas abajo)
extern int g_giro_extra;
const uint32_t* dibujar(const uint32_t* arriba, int ancho) {
    if (arriba && ancho >= 256) pantalla(arriba, ancho);
    if (!g_est.visible || !arriba || ancho < 256) return nullptr;
    preparar();
    if (g_dig.size() < 10) return nullptr;
    g_w = ancho;
    g_buf.assign(arriba, arriba + size_t(ancho) * 192);
    const int t = g_est.t++;
    if (t > g_est.dur) { g_est.visible = false; return nullptr; }
    // Tiro "calculando" en una escena que no es la suya (la de despues del cartel) y que
    // dura mas de 3 segundos sin que el juego calcule el tiro: es un gol a puerta vacia
    // (sin portero el juego no lo calcula) y lo que se ve ya es el campo o la celebracion.
    // Los cortes del tiro son mas cortos. En la 3.a escena (la del portero) no se mira el
    // tiempo: el valor puede llegar tarde (Flecha Divina, 12 s despues del cartel); si no
    // llega, la quitan el limite de escenas o la fila 31.
    if (g_est_tiro && g_tiro_giraba && g_giro_extra == 1 && t > 180 &&
        (g_est.izq == -2 || g_est.der == -2)) {
        if (g_reg_panel) logf("[valor] panel: el tiro no se calculo (gol sin portero): se quita");
        g_tiro_giraba = false; g_est.visible = false; return nullptr;
    }
    if (g_est.izq >= 0 || g_est.izq == -2) panel_lado(true, g_est.izq, t);
    if (g_est.der >= 0 || g_est.der == -2) panel_lado(false, g_est.der, t);
    return g_buf.data();
}
// ---- Cuando sale y con que valores (a partir de cada calculo del juego) ----
// Duelo con supertecnica: el juego calcula regate (fila 1/25) y defensa (3/27) justo antes
// de la escena -> los dos valores; tu jugador a la izquierda, el rival a la derecha.
// Tiro (4, 5, 6, 9, 32): solo su valor, a la derecha. Portero (7, 8, 10): con cuanto llega
// el tiro (con la distancia) y la parada. Se quita al volver el juego normal (filas 15/31).
int g_duelo_izq = -1, g_duelo_der = -1, g_duelo_n = 0;
bool g_duelo_tec = false;
int g_tiro_llega = -1; bool g_tiro_aliado = true;
// Tu equipo o rival: el numero de unidad del jugador (+0x42) lleva 0x8000 en los rivales
// (comprobado: Thomas Feldt 0x8051, Neil Turner 0x805B; Kevin 0x000B, Mark 0x0001)
bool aliado(uint32_t jug) {
    if (!g_mem || jug < 0x02000000u || jug >= 0x023F0000u) return true;
    return (g_mem->r16(jug + 0x42u) & 0x8000u) == 0;
}
// Las escenas empiezan y acaban con la pantalla en negro. Los calculos del juego dejan
// "preparado" lo que hay que ensenar (una cola de fases); cada vez que la pantalla sale
// del negro empieza la siguiente fase, y cada vez que vuelve al negro se quita.
struct Fase { int izq = -1, der = -1, ganador = 0, rodar = 0; bool tiro = false; };   // tiro: solo el valor del tiro
// Un tiro solo: tu equipo a la izquierda, el rival a la derecha (v = -2: "calculando")
Fase fase_tiro(int v, bool aliado, int rodar = 0) {
    Fase f; f.rodar = rodar; f.tiro = true;
    if (aliado) f.izq = v; else f.der = v;
    return f;
}
std::vector<Fase> g_cola;            // fases preparadas para las proximas escenas
bool g_negro = true;                 // estado de la pantalla en el fotograma anterior
bool g_portero_repetido = false;     // lo que se ve es la repeticion de la parada (mas abajo)
bool g_panel_por_guion = false;    // el panel de la parada sigue al guion de su tecnica (mas abajo)
bool g_en_tecnica = false;           // ha salido un cartel de supertecnica desde el ultimo negro
bool g_est_tiro = false;             // lo que se ve es un tiro solo
// registro de las decisiones del panel: siempre (pocas lineas); IE1_VALOR_REG=0 lo quita
bool g_reg_panel = [] { const char* e = std::getenv("IE1_VALOR_REG"); return !(e && *e == '0'); }();
void aviso_panel_visto();        // (mas abajo) el panel se ha ensenado (para los avisos)
void mostrar_ya(const Fase& f) {
    if (g_reg_panel) logf("[valor] panel: ensenar %d contra %d (gana %d, calculando %d)", f.izq, f.der, f.ganador, f.rodar);
    g_est.visible = true; g_est.t = 0; g_est.dur = 1 << 30; g_est.rodar = f.rodar;
    g_est.izq = f.izq; g_est.der = f.der; g_est.ganador = f.ganador;
    g_est_tiro = f.tiro;
    g_portero_repetido = false;
    g_panel_por_guion = false;
    aviso_panel_visto();
}
int g_portero_rep_ocultar();   // (mas abajo)
void ocultar() { g_portero_rep_ocultar(); g_est.visible = false; g_cola.clear(); g_duelo_n = 0; g_duelo_tec = false; g_duelo_izq = g_duelo_der = -1; }
// Duelo listo (regate y defensa calculados) y parada lista: se ensenan en la escena de su
// supertecnica, es decir, cuando sale su cartel (asi nunca caen fuera de una escena)
Fase g_duelo_listo; bool g_hay_duelo = false;
// El de la tecnica pierde contra uno sin tecnica: el juego ensena despues la escena del
// fallo (y a veces solo esa, sin la de la tecnica: Robo rapido de Nathan). El duelo se
// ensena en la escena siguiente; si sale antes el cartel de la tecnica, en la de despues.
bool g_fallo_pend = false; int g_fallo_saltar = 0;
bool g_cartel_portero = false;       // ya salio el cartel de la parada en esta escena
Fase g_portero_listo; bool g_hay_portero = false;
// Parada con supertecnica: su escena tiene varios cortes (con negro entre ellos) y el cartel
// Registro del 2026-11-21 (Defensa triple, 169): el cartel sale con la pantalla en negro y
// la animacion es UN corte (465 fotogramas); el siguiente (3066) ya es el campo con el
// dialogo. Asi que:
//  - cartel en negro: el corte que empieza es la animacion; el panel ya esta puesto y no
//    se repite nada;
//  - cartel con imagen: puede llegar al final del corte anterior (tras el bloqueo de Jack,
//    2026-11-20: el negro lo quitaba antes de la animacion); se repite en el corte
//    siguiente, pero como mucho kPorteroMax fotogramas (si ese corte ya era el campo).
// Se deja de repetir con la fila 31 (alguien tiene el balon) o con otra jugada.
Fase g_portero_fase; int g_portero_rep = 0;
// Fase 2 (2026-11-21): si se pueden leer los guiones del juego, el panel de la parada se guia
// por el guion de su tecnica (el que corre cuando sale el cartel): se queda mientras corre,
// aunque haya negros, y se quita cuando acaba. Sin guiones, lo de arriba (respaldo).
bool dueno_cartel_ok();          // (mas abajo) el cartel tiene guion de tecnica conocido
void apuntar_guion_cartel();     // (mas abajo) apunta el guion que corre al salir el cartel
void apuntar_guion_tiro();       // (mas abajo) ese guion es el de una supertecnica de tiro
bool tiro_vigilado();            // (mas abajo) el tiro con tecnica se sigue por su guion
// Avisos automaticos (2026-11-21): el propio mod apunta en el registro "[valor] AVISO ..."
// cuando algo no cuadra, para no tener que vigilar el panel jugando:
//  - acaba el guion de una tecnica con cartel y el panel no se enseno en ningun momento;
//  - el panel lleva mas de kAvisoLargo fotogramas seguidos en pantalla.
struct AvisoCartel { int tecnica = 0, tipo = 0, k = -1; uint32_t act = 0; bool visto = false; };
AvisoCartel g_aviso_cartel;
void apuntar_aviso_cartel(int tecnica);   // (mas abajo)
void dueno_cartel_a_portero();   // (mas abajo) ese guion pasa a ser el del panel de la parada
bool dueno_corre();              // (mas abajo) el guion del panel sigue corriendo
// Duelos y bloqueos con tecnica (2026-11-21): igual que la parada, el panel sigue al guion
// de la tecnica. Corte giratorio de Erik (133): la pantalla parpadeo en negro 1 fotograma al
// empezar la animacion y el panel se quitaba a los 2 fotogramas.
void seguir_cartel() {
    if (!dueno_cartel_ok()) return;
    dueno_cartel_a_portero(); g_panel_por_guion = true;
}
// Tiro sin tecnica que llega al portero (ov87 0x021798xx..0x02179A74): el juego calcula el tiro
// (filas 4/5/6, con el ajuste de distancia) y la parada (7/8/10) SIN tirada de azar, y en
// 0x02179A30 los compara: si la parada >= tiro, gana el portero ahi mismo (devuelve 6 = con su
// tecnica, o 0) y no hay mas calculos; si no, despues viene el calculo de verdad (con azar).
// Caso: volea de Kevin 135 contra Poseidon 143 con tecnica (2026-11-21 01:11:49).
// Esa parada ganada se ensena con el cartel de la tecnica del portero.
Fase g_parada_prev; bool g_hay_parada_prev = false;
int g_prev_tiro_llega = -1; bool g_prev_tiro_aliado = true;
void portero_visto(const Fase& f) {
    g_portero_fase = f;
    if (dueno_cartel_ok()) { dueno_cartel_a_portero(); g_panel_por_guion = true; g_portero_rep = 0; return; }
    g_portero_rep = g_negro ? 0 : 1;
}
unsigned g_vfot = 0, g_vfot_escena = 0;   // fotogramas (para el registro: lo que dura cada corte)
constexpr unsigned kPorteroMax = 600;     // 10 s: la animacion mas larga vista dura 465
// Bloqueos (codigo del juego, overlay 15, 0x02143C70..0x02143DD0): al llegar el tiro al
// defensa, el juego vuelve a calcular el tiro con el ajuste de distancia de ese momento
// (es el ultimo tiro del registro) y despues el bloqueo (fila 28 con tecnica de defensa,
// fila 32 con tecnica de tiro). Los dos valores, como minimo 1.
//   fila 32: si el tiro >= bloqueo, pasa; si no, lo para.
//   fila 28: si el 75% del tiro >= bloqueo, pasa entero; si el 125% del tiro > bloqueo,
//            pasa debilitado (el juego lo vuelve a calcular con menos fuerza); si no, lo para.
struct UltimoTiro { bool hay = false; int llega = 0; bool aliado = true; };
UltimoTiro g_ult_tiro;
Fase g_contra_listo; bool g_hay_contra = false;   // bloqueo con tecnica de tiro: con su cartel
bool g_tiro_giraba = false;          // el panel del tiro espera su valor (calculando)
bool g_prev_tiro = false, g_espera_tiro = false;   // previsiones de tiro vistas -> la siguiente escena es el tiro
bool g_tiro_cerrado = false;         // ya se preparo la parada de este tiro: ignorar repeticiones
// Barra de PT: se coloca al crear la escena de la supertecnica, a veces en el mismo
// fotograma del calculo. Por eso tambien se adivina: tras una prevision de duelo, o
// despues de la escena de un tiro (lo siguiente es portero o bloqueo), salen dos valores.
bool g_pred_dos = false;
bool g_tiro_de_aliado = true;        // de quien es el tiro que se espera (para el lado del panel)
bool g_tiro_tecnica = false;
int g_giro_extra = 0;                // escenas siguientes en las que el tiro siguio "calculando"         // el tiro es una supertecnica (el portero sin tecnica tiene animacion)
int vis(int v) { return v < 0 ? 0 : v; }   // el panel no ensena negativos (-1 y -2 son marcas)
bool repeticion();   // mas abajo: el juego esta ensenando la repeticion del gol (limpia el panel)
void cartel(int tecnica, bool aliado_cartel) {
    if (repeticion()) return;
    g_en_tecnica = true;
    apuntar_guion_cartel();
    apuntar_aviso_cartel(tecnica);
    const int tipo = ent::tipo_tecnica(tecnica);
    if (tipo != 8 && tecnica != 0) { g_portero_rep = 0; g_hay_parada_prev = false; }   // otra jugada
    if (g_reg_panel) logf("[valor] panel: cartel de la tecnica %d (tipo %d, fotograma %u, pantalla %s)", tecnica, tipo, g_vfot, g_negro ? "en negro" : "con imagen");
    if (tipo == 7 && g_hay_contra) {                       // bloqueo con tecnica de tiro
        g_cola.clear(); g_hay_duelo = false; g_espera_tiro = false; g_tiro_giraba = false;
        mostrar_ya(g_contra_listo); g_hay_contra = false; seguir_cartel();
    } else if (tipo == 7) {                                // tiro: aun sin valor
        g_cola.clear(); g_hay_duelo = false; g_espera_tiro = false; g_tiro_de_aliado = aliado_cartel; g_tiro_tecnica = true;
        mostrar_ya(fase_tiro(-2, aliado_cartel)); g_tiro_llega = -1; g_tiro_giraba = true; g_tiro_cerrado = false;
        apuntar_guion_tiro();
        g_giro_extra = g_negro ? -1 : 0;                   // (el cartel sale antes de que empiece su escena)
    } else if ((tipo == 5 || tipo == 6) && g_hay_duelo) {
        mostrar_ya(g_duelo_listo);                          // regate o defensa con tecnica
        if (g_fallo_pend) g_fallo_saltar = g_negro ? 1 : 0;   // la escena que empieza es la de la tecnica
        seguir_cartel();
        if (g_panel_por_guion) g_fallo_saltar = 0;           // con guion, sus cortes no cuentan como escenas
    } else if (tecnica == 0 || tipo == 8) {                // parada con tecnica
        g_cartel_portero = true;                           // (por si su valor llega despues)
        if (g_hay_portero) { mostrar_ya(g_portero_listo); portero_visto(g_portero_listo); g_hay_portero = false; g_cola.clear(); }
        else if (g_hay_parada_prev) {                      // tiro sin tecnica parado sin calculo con azar
            mostrar_ya(g_parada_prev); portero_visto(g_parada_prev); g_hay_parada_prev = false; g_cola.clear();
        }
    }
}
// Guiones del juego (fase 2: saber por el juego cuando corre la animacion de una tecnica).
// Hay 9 interpretes de guion (punteros en 0x020DBEF8, objetos de 0x3C0 bytes): +0x23C = id del
// guion (act), +0x248 = 1 mientras corre, +0x268 = fotogramas. Estados del usuario
// (2026-11-21, Defensa triple de Mark): durante la animacion el interprete 2 corre el guion
// act 0x1929E con +0x248 = 1; antes y despues, todos a 0. De momento solo se registra cuando
// empieza y acaba cada guion en los partidos, para comprobarlo con todo tipo de jugadas.
constexpr uint32_t kInterpretes = 0x020DBEF8u;
uint32_t g_guion_act[9] = {}, g_guion_desde[9] = {};
bool g_guion_corre[9] = {};
// Guion de la tecnica del ultimo cartel (el que mas tarde empezo de los que corren; en los
// registros es siempre el interprete 2) y guion del que depende el panel de la parada
int g_cartel_k = -1; uint32_t g_cartel_act = 0;
int g_dueno_k = -1; uint32_t g_dueno_act = 0;
// Guion de la supertecnica de tiro que espera su valor ("calculando"). Registro del 2026-11-21
// 09:35:48: el tiro 142 de Jude se fue fuera; el juego no lo calculo y el panel seguia
// "calculando" 2 cortes mas. En los tiros que llegan al portero el valor llega siempre antes de
// que empiece el guion siguiente; si acabo el del tiro y empieza otro sin valor, se quita.
int g_tiro_k = -1; uint32_t g_tiro_act = 0;
bool g_guiones_ok = false;       // se estan leyendo (partido con el overlay 15)
void apuntar_guion_cartel() {
    g_cartel_k = -1;
    if (!g_guiones_ok) return;
    uint32_t mejor = 0;
    for (int k = 0; k < 9; ++k)
        if (g_guion_corre[k] && g_guion_act[k] != 0 && g_guion_act[k] != 0x7530u && (g_cartel_k < 0 || g_guion_desde[k] >= mejor)) {
            g_cartel_k = k; mejor = g_guion_desde[k];
        }
    if (g_cartel_k >= 0) g_cartel_act = g_guion_act[g_cartel_k];
}
bool dueno_cartel_ok() { return g_cartel_k >= 0 && g_guion_corre[g_cartel_k] && g_guion_act[g_cartel_k] == g_cartel_act; }
void dueno_cartel_a_portero() { g_dueno_k = g_cartel_k; g_dueno_act = g_cartel_act; }
void apuntar_guion_tiro() { if (dueno_cartel_ok()) { g_tiro_k = g_cartel_k; g_tiro_act = g_cartel_act; } else g_tiro_k = -1; }
bool tiro_vigilado() { return g_guiones_ok && g_tiro_k >= 0; }
void apuntar_aviso_cartel(int tecnica) {
    if (dueno_cartel_ok()) g_aviso_cartel = AvisoCartel{tecnica, ent::tipo_tecnica(tecnica), g_cartel_k, g_cartel_act, g_est.visible};
    else g_aviso_cartel = AvisoCartel{};
}
void aviso_panel_visto() {
    if (g_aviso_cartel.k >= 0 && g_guion_corre[g_aviso_cartel.k] && g_guion_act[g_aviso_cartel.k] == g_aviso_cartel.act) g_aviso_cartel.visto = true;
}
constexpr unsigned kAvisoLargo = 1200;   // 20 s: lo mas largo visto (tiro + corte siguiente) no llega a 1100
unsigned g_aviso_visible_desde = 0; bool g_aviso_largo_dado = false; int g_avisos = 0;
void avisos_tick() {
    // panel demasiado tiempo en pantalla
    if (g_est.visible) {
        if (g_aviso_visible_desde == 0) g_aviso_visible_desde = g_vfot;
        if (!g_aviso_largo_dado && g_vfot - g_aviso_visible_desde > kAvisoLargo) {
            g_aviso_largo_dado = true; ++g_avisos;
            logf("[valor] AVISO: el panel lleva %u fotogramas en pantalla (%s contra %s): no deberia durar tanto",
                 kAvisoLargo, std::to_string(g_est.izq).c_str(), std::to_string(g_est.der).c_str());
        }
    } else { g_aviso_visible_desde = 0; g_aviso_largo_dado = false; }
}
bool dueno_corre() { return g_dueno_k >= 0 && g_guion_corre[g_dueno_k] && g_guion_act[g_dueno_k] == g_dueno_act; }
void guiones_tick() {
    if (!g_mem) return;
    // solo en los partidos (overlay 15 cargado: el manejador del cartel en su sitio)
    if (g_mem->r32(0x02155B34u) != 0xEBFC2588u) {
        if (g_guiones_ok) { for (bool& c : g_guion_corre) c = false; g_guiones_ok = false; g_dueno_k = g_cartel_k = -1; }
        return;
    }
    g_guiones_ok = true;
    for (int k = 0; k < 9; ++k) {
        const uint32_t b = g_mem->r32(kInterpretes + 4u * uint32_t(k));
        const bool ok = b >= 0x02000000u && b < 0x023F0000u;
        const bool corre = ok && g_mem->r32(b + 0x248u) == 1u;
        const uint32_t act = ok ? g_mem->r32(b + 0x23Cu) : 0;
        if (corre && (!g_guion_corre[k] || act != g_guion_act[k])) {
            if (g_reg_panel) logf("[valor] guion %d empieza: act 0x%X (fotograma %u)", k, act, g_vfot);
            g_guion_desde[k] = g_vfot;
            // otro guion (no el del propio tiro, ni los de fondo 0 / 0x7530) con el tiro aun sin valor
            if (g_tiro_k >= 0 && act != 0 && act != 0x7530u && act != g_tiro_act &&
                !(g_guion_corre[g_tiro_k] && g_guion_act[g_tiro_k] == g_tiro_act)) {
                if (g_tiro_giraba && g_est.visible && g_est_tiro && (g_est.izq == -2 || g_est.der == -2)) {
                    if (g_reg_panel) logf("[valor] panel: el tiro acabo sin calculo (empieza el guion act 0x%X): se quita", act);
                    g_est.visible = false;
                }
                if (g_tiro_giraba) g_tiro_giraba = false;
                g_tiro_k = -1;
            }
        } else if (!corre && g_guion_corre[k]) {
            if (g_reg_panel) logf("[valor] guion %d acaba: act 0x%X (fotograma %u, duro %u)", k, g_guion_act[k], g_vfot, g_vfot - g_guion_desde[k]);
        }
        g_guion_corre[k] = corre; g_guion_act[k] = act;
    }
    // acabo el guion del ultimo cartel sin que el panel se ensenara
    if (g_aviso_cartel.k >= 0 && !(g_guion_corre[g_aviso_cartel.k] && g_guion_act[g_aviso_cartel.k] == g_aviso_cartel.act)) {
        if (!g_aviso_cartel.visto) {
            ++g_avisos;
            logf("[valor] AVISO: la tecnica %d (tipo %d, act 0x%X) acabo sin que saliera el panel", g_aviso_cartel.tecnica, g_aviso_cartel.tipo, g_aviso_cartel.act);
        }
        g_aviso_cartel = AvisoCartel{};
    }
    // acabo el guion de la parada: se quita su panel
    if (g_dueno_k >= 0 && !dueno_corre()) {
        if (g_panel_por_guion && g_est.visible) {
            if (g_reg_panel) logf("[valor] panel: acabo el guion de la tecnica (act 0x%X): se quita", g_dueno_act);
            g_est.visible = false;
        }
        g_panel_por_guion = false; g_dueno_k = -1;
    }
}
// Cada fotograma, con la imagen de la pantalla de las escenas
void pantalla(const uint32_t* px, int ancho) {
    if (repeticion()) return;
    long suma = 0; int n = 0;
    for (int y = 8; y < 192; y += 12)
        for (int x = 4; x < ancho; x += 12) {
            const uint32_t c = px[size_t(y * ancho + x)];
            suma += (c >> 16 & 255) + (c >> 8 & 255) + (c & 255); ++n;
        }
    const bool negro = n && suma / (3L * n) < 10;
    ++g_vfot;
    guiones_tick();
    if (g_est.visible) aviso_panel_visto();
    avisos_tick();
    if (g_portero_repetido && g_est.visible && !negro && g_vfot - g_vfot_escena > kPorteroMax) {
        if (g_reg_panel) logf("[valor] panel: la parada repetida pasa de %u fotogramas: se quita", kPorteroMax);
        g_est.visible = false; g_portero_repetido = false;
    }
    if (negro && !g_negro) {                                    // acaba la escena
        if (g_est.visible && g_est_tiro) g_pred_dos = true;         // era la de un tiro
        if (!(g_panel_por_guion && dueno_corre())) g_est.visible = false;   // la parada sigue con su guion
        g_en_tecnica = false; g_cartel_portero = false;
    }
    if (!negro && g_negro) {                                    // empieza una escena
        if (g_reg_panel) logf("[valor] panel: empieza una escena (%zu fases preparadas; la anterior duro %u fotogramas; fotograma %u)", g_cola.size(), g_vfot - g_vfot_escena, g_vfot);
        g_vfot_escena = g_vfot;
        if (g_panel_por_guion && dueno_corre()) {
            // otro corte (o un parpadeo) de la misma tecnica: el panel sigue, nada mas
        } else if (g_fallo_pend && g_fallo_saltar > 0) {
            --g_fallo_saltar;                                   // la de la tecnica (ya tiene su panel)
        } else if (g_fallo_pend) {                              // la del fallo del duelo
            g_fallo_pend = false;
            mostrar_ya(g_duelo_listo);
        } else if (g_espera_tiro) {                             // la escena de un tiro SIN tecnica
            // No se ensena nada (2026-11-21, pedido por el usuario): si lo bloquea un jugador
            // sin tecnica o lo para el portero, el "calculando" se quedaba un rato y se iba.
            // Sus valores salen cuando el juego los calcula (en la escena siguiente).
            g_espera_tiro = false; g_cola.clear();
            g_tiro_giraba = true; g_tiro_llega = -1; g_giro_extra = 0;
        } else if (!g_cola.empty()) {                           // siguiente fase preparada
            mostrar_ya(g_cola.front());
            g_cola.erase(g_cola.begin());
        } else if (g_portero_rep > 0) {                         // otro corte de la parada con tecnica
            --g_portero_rep;
            mostrar_ya(g_portero_fase);
            g_portero_repetido = true;
        } else if (g_tiro_giraba && g_tiro_tecnica && tiro_vigilado()) {     // con guion: hasta su valor u otro guion
            mostrar_ya(fase_tiro(-2, g_tiro_de_aliado));
        } else if (g_tiro_giraba && g_tiro_tecnica && g_giro_extra < 2) {   // supertecnica: sigue sin valor
            ++g_giro_extra;     // tiro normal: solo en la escena siguiente; supertecnica: sus cortes
            mostrar_ya(fase_tiro(-2, g_tiro_de_aliado));
        } else if (g_tiro_giraba) {
            // el juego no llego a calcular el tiro (gol a puerta vacia, sin portero): se
            // deja de esperar para no quedarse "calculando" en las pantallas siguientes
            g_tiro_giraba = false;
        }
    }
    g_negro = negro;
}
// Ultimo regate y ultima defensa de un duelo (el juego repite el calculo durante la escena)
struct Lado { bool hay = false; int valor = 0; bool aliado = true, tec = false; };
Lado g_reg, g_def;

// Repeticion del gol: el juego vuelve a jugar la jugada y repite sus calculos, y el panel
// ensenaba valores sueltos o se quedaba "calculando". 0x0206ACE8 (lo usa el texto
// "REPETICION" que parpadea, 0x0205F8A8) dice que hay repeticion si partido+0xC78 >= 0;
// en el juego normal vale -1. Mientras dura: sin panel y sin recoger nada.
bool repeticion() {
    if (g_mem->r32(0x02155B34u) != 0xEBFC2588u || g_mem->r32(0x02155B3Cu) != 0xE2800001u) return false;  // sin partido
    if (int32_t(g_mem->r32(0x020E88A0u + 0xC78u)) < 0) return false;
    static int aviso = 0;
    if (g_est.visible || !g_cola.empty() || g_tiro_giraba || g_espera_tiro) {
        if (g_reg_panel && aviso < 20) { ++aviso; logf("[valor] panel: repeticion del gol: sin panel"); }
    }
    g_est.visible = false; g_cola.clear(); g_portero_rep = 0;
    g_tiro_giraba = g_espera_tiro = g_prev_tiro = false;
    g_fallo_pend = false; g_hay_duelo = false; g_hay_portero = false; g_hay_contra = false;
    g_cartel_portero = false; g_en_tecnica = false; g_pred_dos = false; g_hay_parada_prev = false;
    g_reg.hay = g_def.hay = false;
    return true;
}
void evento(int fila, int valor, bool real, bool es_aliado, int pct_dist) {
    if (repeticion()) return;
    if (fila == 31) {                       // alguien tiene el balon: acabo la jugada
        g_pred_dos = false; g_tiro_giraba = false;
        if (g_portero_rep > 0 && !g_hay_portero && !g_cartel_portero) g_portero_rep = 0;
        // si aun se ve un tiro "calculando", su valor ya no va a llegar (el juego resolvio
        // el tiro sin calcularlo: algunos despejes y tiros de 3 jugadores): se quita
        if (g_est.visible && g_est_tiro && (g_est.izq == -2 || g_est.der == -2)) {
            if (g_reg_panel) logf("[valor] panel: el tiro acabo sin calculo: se quita");
            g_est.visible = false;
        }
    }
    if (!real) {                           // previsiones (sin dado): no se ensenan, pero las de
        if (fila == 4 || fila == 5 || fila == 6) {         // tiro + parada: viene un tiro
            g_prev_tiro = true; g_pred_dos = false; g_tiro_de_aliado = es_aliado; g_tiro_tecnica = false;
            g_prev_tiro_llega = valor + valor * pct_dist / 100; g_prev_tiro_aliado = es_aliado; g_hay_parada_prev = false;
        }
        else if ((fila == 7 || fila == 8 || fila == 10) && g_prev_tiro) {
            g_espera_tiro = true; g_prev_tiro = false; g_tiro_cerrado = false;
            if (g_prev_tiro_llega >= 0 && valor >= g_prev_tiro_llega) {   // gana el portero sin mas calculos
                Fase f;
                if (g_prev_tiro_aliado) { f.izq = vis(g_prev_tiro_llega); f.der = vis(valor); f.ganador = 2; }
                else { f.izq = vis(valor); f.der = vis(g_prev_tiro_llega); f.ganador = 1; }
                g_parada_prev = f; g_hay_parada_prev = true;
                if (g_reg_panel) logf("[valor] panel: el portero gana sin tirada (%d contra %d): con su tecnica, si la usa", valor, g_prev_tiro_llega);
            }
        }
        else if (fila != 14 && fila != 15 && fila != 31) g_prev_tiro = false;
        if (fila == 1 || fila == 3) g_pred_dos = true;              // viene un duelo
        return;
    }
    // duelos: regate (1/25) y defensa (3/27); solo si alguno usa supertecnica
    if (fila == 1 || fila == 25 || fila == 3 || fila == 27) {
        g_tiro_giraba = false; g_portero_rep = 0;
        if (g_est.visible) return;         // repeticiones durante la propia escena
        Lado& l = (fila == 1 || fila == 25) ? g_reg : g_def;
        l = Lado{true, valor, es_aliado, fila == 25 || fila == 27};
        if (g_reg.hay && g_def.hay) {
            g_hay_duelo = false;
            if (g_reg.tec || g_def.tec) {
                const bool gana_reg = g_reg.valor > g_def.valor;
                const Lado& a = g_reg.aliado ? g_reg : g_def;      // el tuyo a la izquierda
                const Lado& r = g_reg.aliado ? g_def : g_reg;
                const bool gana_aliado = (&a == &g_reg) ? gana_reg : !gana_reg;
                g_duelo_listo = Fase{vis(a.valor), vis(r.valor), gana_aliado ? 1 : 2};
                g_hay_duelo = true;
                // solo uno con tecnica y pierde: tambien en la escena del fallo
                g_fallo_pend = (g_reg.tec != g_def.tec) && ((g_reg.tec && !gana_reg) || (g_def.tec && gana_reg));
                g_fallo_saltar = 0;
                if (g_en_tecnica && !g_negro) { mostrar_ya(g_duelo_listo); seguir_cartel(); }   // ya en su escena
            }
            g_reg.hay = g_def.hay = false;
        }
        return;
    }
    // bloqueos: el defensa (fila 28 con tecnica de defensa, 32 con tecnica de tiro) contra
    // el tiro que le llega (el ultimo calculado)
    if (fila == 28 || fila == 32) {
        if (!g_ult_tiro.hay) return;
        const int tiro = std::max(1, g_ult_tiro.llega), bloq = std::max(1, valor);
        bool para;
        if (fila == 32) para = tiro < bloq;
        else para = !(tiro * 75 / 100 >= bloq) && !(tiro * 125 / 100 > bloq);
        // Debilitado (fila 28, pasa el 125% pero no el 75%): en la escena el defensa lo frena
        // (Apisonadora, El Muro...) y el tiro sigue con menos fuerza hacia el portero; en el
        // panel gana el defensa.
        const bool gana_def = para || (fila == 28 && !(tiro * 75 / 100 >= bloq));
        Fase f;
        if (es_aliado) { f.izq = vis(valor); f.der = vis(g_ult_tiro.llega); f.ganador = gana_def ? 1 : 2; }
        else { f.izq = vis(g_ult_tiro.llega); f.der = vis(valor); f.ganador = gana_def ? 2 : 1; }
        g_ult_tiro.hay = false;
        // el tiro que esperaba en la cola (tiro sin tecnica calculado antes de su escena, como
        // el tiro largo) no tiene escena propia: la que viene es la del bloqueo, con los dos
        // valores. Si se dejaba, tapaba el bloqueo ("118 calculando" contra Apisonadora).
        g_cola.erase(std::remove_if(g_cola.begin(), g_cola.end(), [](const Fase& c) { return c.tiro; }), g_cola.end());
        if (para) { g_tiro_llega = -1; g_tiro_cerrado = true; }   // el tiro ya no llega al portero
        if (fila == 28) {                                    // se ensena con su cartel (tipo defensa)
            g_duelo_listo = f; g_hay_duelo = true; g_fallo_pend = false;
            if (g_en_tecnica && !g_negro) { mostrar_ya(f); seguir_cartel(); }
        } else {                                             // con su cartel (tipo tiro)
            g_contra_listo = f; g_hay_contra = true;
            if (g_en_tecnica && !g_negro && g_tiro_giraba) { g_tiro_giraba = false; g_hay_contra = false; mostrar_ya(f); seguir_cartel(); }
        }
        return;
    }
    // tiro real (normal, volea, testarazo, vaselina o supertecnica)
    if (fila == 4 || fila == 5 || fila == 6 || fila == 9) {
        if (g_tiro_cerrado) return;        // el juego repite el calculo despues: ya esta ensenado
        g_hay_duelo = false; g_portero_rep = 0; g_hay_parada_prev = false;
        g_tiro_llega = valor + valor * pct_dist / 100;
        g_tiro_aliado = es_aliado;
        g_tiro_k = -1;
        g_ult_tiro = UltimoTiro{true, g_tiro_llega, es_aliado};
        g_espera_tiro = false;
        if (g_tiro_giraba) {               // su panel estaba "calculando"
            g_tiro_giraba = false;
            if (g_est.visible && g_est_tiro) mostrar_ya(fase_tiro(vis(valor), es_aliado));
        } else {
            // calculado antes de su escena: "calculando" un momento y su valor
            g_cola = {fase_tiro(vis(valor), es_aliado, 20)};
        }
        return;
    }
    // portero: con cuanto llega el tiro y la parada
    if (fila == 7 || fila == 8 || fila == 10) {
        if (g_tiro_llega < 0) return;
        const bool gol = g_tiro_llega > valor;
        Fase f;
        if (g_tiro_aliado) { f.izq = vis(g_tiro_llega); f.der = vis(valor); f.ganador = gol ? 1 : 2; }
        else { f.izq = vis(valor); f.der = vis(g_tiro_llega); f.ganador = gol ? 2 : 1; }
        if (fila == 10) {                                  // con su cartel
            g_portero_listo = f; g_hay_portero = true;
            if (g_cartel_portero && !g_negro) { mostrar_ya(f); portero_visto(f); g_hay_portero = false; }   // el cartel ya salio
        }
        if (gol || fila != 10) {
            // Gol: no hay escena del portero (ni con fila 10: el portero la intenta sin
            // cartel), asi que se ensena en la escena del tiro, o en la que esta saliendo
            // si ya estaba "calculando". Parada sin tecnica: en la escena del portero.
            // Supertecnica contra portero sin tecnica: despues de la escena del tiro sale la
            // animacion del portero intentando pararla: tambien ahi.
            // Si el tiro aun espera en la cola (calculado antes de su escena: tiros sin tecnica
            // como el tiro largo), la escena que viene es la del portero: alli los dos valores.
            bool puesto = false, en_cola = false;
            for (Fase& c : g_cola) if (c.tiro) { c = f; c.rodar = 20; puesto = en_cola = true; break; }
            bool en_tiro = false;
            if (!puesto && (gol || g_tiro_tecnica) && g_est.visible && g_est_tiro) { mostrar_ya(f); puesto = en_tiro = true; }
            // Gol de un tiro sin tecnica (volea, testarazo...): el valor llega al final de la
            // escena del tiro y casi no se ve, y despues sale el portero intentando pararlo
            // (Poseidon contra la volea de Kevin): tambien en esa escena.
            const bool animacion = fila != 10 && !en_cola && (g_tiro_tecnica || (gol && en_tiro));
            if (!puesto || animacion) g_cola.push_back(f);
        }
        g_tiro_llega = -1;
        g_tiro_cerrado = true;             // hasta el proximo tiro, no se vuelve a preparar
    }
}
void avanzar() {}
int g_portero_rep_ocultar() { return g_portero_rep = 0; }
// Barra de PT al centro en los duelos y las paradas (dos valores); en los tiros, en su sitio.
// La barra es un grupo de rectangulos 3D que crea 0x0205F15C al empezar cada escena de
// supertecnica, con mbd_g00 (marco, x=8) y mbd_g01/g02 (relleno, x=40), todos con y=8:
//   0x0205F2B0  mov r3, r4      (x del marco = 8)    -> mov r3, #74
//   0x0205F2D0  mov r5, #0x28   (x de los rellenos = 40) -> mov r5, #106
// Se elige antes de que empiece la escena, segun lo que se va a ensenar en ella.
void mover_pt() {
    if (!g_mem) return;
    // siempre centrada: en los duelos y paradas (dos valores) y tambien en los tiros (el
    // valor del tiro sale a la izquierda si es tuyo y a la derecha si es del rival)
    bool dos = true;
    for (const Fase& f : g_cola) if (f.izq != -1 && f.der != -1) dos = true;
    struct P { uint32_t dir, original, centro; };
    static const P kP[] = {{0x0205F2B0u, 0xE1A03004u, 0xE3A0304Au}, {0x0205F2D0u, 0xE3A05028u, 0xE3A0506Au}};
    for (const P& p : kP) {
        const uint32_t actual = g_mem->r32(p.dir);
        if (actual != p.original && actual != p.centro) return;    // no es el codigo esperado
        const uint32_t quiero = dos ? p.centro : p.original;
        if (actual != quiero) g_mem->w32(p.dir, quiero);
    }
}
// Prueba (IE1_VALOR_PRUEBA=1): valores fijos que se repiten cada 3 segundos
void prueba() {
    static int f = 0;
    const int ciclo = f++ % 180;
    g_est.visible = true;
    if (ciclo == 0) {
        static int n = 0;
        const int modo = n++ % 3;                 // duelo, tiro solo, duelo ganando el rival
        g_est.t = 0;
        g_est.izq = modo == 1 ? -1 : 123;
        g_est.der = modo == 1 ? 87 : (modo == 2 ? 145 : 87);
        g_est.ganador = modo == 1 ? 0 : (modo == 2 ? 2 : 1);
        g_est.equipo_der = 1;
    }
}
}  // namespace valorov
namespace exp_x2 {
// Pantalla de EXP con x2, como el IE2: "x2!!" (su pieza BGDN_B06 de cl_bonus, con la cola
// morada que pasa por debajo de "Niv.") en cada fila de jugador y el total de experiencia
// en magenta. Se dibuja encima de la pantalla. Filas del IE1: 2 columnas (x 2-126 y
// 130-254) de 8, cada 24 px, borde de arriba azul claro en y = 1 + 24 k; "Niv." empieza en
// x = 90 / 218 y el "!!" de la pieza acaba en su columna 22; va en x = 65 / 193 (2 px de aire),
// y = borde - 2 (la base del "x2" con la de "Niv."). La cola (columnas 23-31) solo se
// pinta donde no hay letras (pasa por debajo). El total: cifras en x 170-240, y 74-87 de la otra pantalla
// (contorno (73,56,32), mitad de arriba (243,251,251), de abajo (170,203,235)) que pasan a
// los colores del IE2 ((162,0,121), (251,219,251), (251,162,243)).
std::vector<uint32_t> g_buf, g_buf_total;
struct ImgX2 { int w = 0, h = 0; std::vector<uint32_t> px; } g_img;
bool g_img_hecha = false;
inline int rr(uint32_t c) { return c >> 16 & 255; }
inline int gg(uint32_t c) { return c >> 8 & 255; }
inline int bb(uint32_t c) { return c & 255; }
bool borde(const uint32_t* px, int ancho, int x, int y) {
    if (x < 0 || y < 0 || x >= ancho || y >= 192) return false;
    const uint32_t c = px[size_t(y * ancho + x)];
    return rr(c) > 100 && rr(c) < 175 && gg(c) > 185 && bb(c) > 205;    // (134,215,239)
}
bool fila(const uint32_t* px, int ancho, int col, int k, int& y_borde) {
    const int y0 = 1 + 24 * k, x0 = col ? 140 : 12;
    for (int dy = -1; dy <= 1; ++dy)
        if (borde(px, ancho, x0, y0 + dy) && borde(px, ancho, x0 + 50, y0 + dy) &&
            borde(px, ancho, x0 + 100, y0 + dy)) { y_borde = y0 + dy; return true; }
    return false;
}
bool cerca(uint32_t c, int r, int g, int b) {
    return std::abs(rr(c) - r) <= 8 && std::abs(gg(c) - g) <= 8 && std::abs(bb(c) - b) <= 8;
}
// cuantos pixeles de cifra del total hay (contorno + relleno) en la zona del total
int cifras_total(const uint32_t* px, int ancho) {
    int n = 0;
    for (int y = 74; y <= 87; ++y)
        for (int x = 170; x <= 240 && x < ancho; ++x) {
            const uint32_t c = px[size_t(y * ancho + x)];
            n += cerca(c, 243, 251, 251) || cerca(c, 170, 203, 235);
        }
    // fondo naranja del panel a la izquierda de la zona
    return cerca(px[size_t(72 * ancho + 160)], 146, 97, 48) ? n : 0;
}
const uint32_t* total_magenta(const uint32_t* px, int ancho) {
    if (!px || ancho < 256 || cifras_total(px, ancho) < 20) return nullptr;
    g_buf_total.assign(px, px + size_t(ancho) * 192);
    for (int y = 74; y <= 87; ++y)
        for (int x = 170; x <= 240; ++x) {
            uint32_t& c = g_buf_total[size_t(y * ancho + x)];
            const uint32_t a = c & 0xFF000000u;
            if (cerca(c, 73, 56, 32)) c = a | 0xA20079u;
            else if (cerca(c, 243, 251, 251)) c = a | 0xFBDBFBu;
            else if (cerca(c, 170, 203, 235)) c = a | 0xFBA2F3u;
        }
    return g_buf_total.data();
}
const uint32_t* filas_x2(const uint32_t* px, int ancho) {
    if (!px || ancho < 256) return nullptr;
    if (!g_img_hecha) {
        g_img_hecha = true;
        const auto v = valorov::decodificar(g_exp_x2_pac);
        if (!v.empty()) { g_img.w = v[0].w; g_img.h = v[0].h; g_img.px = v[0].px; }
        logf("[exp_x2] grafico x2: %s", g_img.px.empty() ? "no se pudo leer" : "listo");
    }
    if (g_img.px.empty()) return nullptr;
    int filas = 0, yb;
    for (int c = 0; c < 2; ++c) for (int k = 0; k < 8; ++k) filas += fila(px, ancho, c, k, yb);
    if (filas < 6) return nullptr;     // la pantalla de EXP tiene una fila por jugador (11+)
    g_buf.assign(px, px + size_t(ancho) * 192);
    for (int c = 0; c < 2; ++c)
        for (int k = 0; k < 8; ++k) {
            if (!fila(px, ancho, c, k, yb)) continue;
            const int x0 = c ? 193 : 65, y0 = yb - 2;
            for (int j = 0; j < g_img.h; ++j)
                for (int i = 0; i < g_img.w; ++i) {
                    const uint32_t v = g_img.px[size_t(j * g_img.w + i)];
                    const int x = x0 + i, y = y0 + j;
                    if (!v || x >= ancho || y < 0 || y >= 192) continue;
                    uint32_t& d = g_buf[size_t(y * ancho + x)];
                    // la cola (desde la columna 23) va por debajo de las letras de "Niv."
                    if (i >= 23 && rr(d) + gg(d) + bb(d) > 330) continue;
                    d = (d & 0xFF000000u) | (v & 0xFFFFFFu);
                }
        }
    return g_buf.data();
}
// pinta lo que toque en las dos pantallas; false si no hay nada de la pantalla de EXP
bool dibujar(const uint32_t* arriba, int ancho_arriba, const uint32_t* abajo, int ancho_abajo,
             const uint32_t** sal_arriba, const uint32_t** sal_abajo) {
    if (!g_doble || g_exp_x2_pac.empty()) return false;
    const uint32_t* fa = nullptr; const uint32_t* fb = nullptr;
    const uint32_t* ta = nullptr; const uint32_t* tb = nullptr;
    // El overlay de la pantalla de EXP se queda en memoria al salir de ella, asi que g_doble
    // puede seguir activo en el menu (sus fichas de jugador tambien tienen bordes azul claro):
    // solo se dibuja si en la otra pantalla esta el panel naranja de la EXP.
    auto panel = [](const uint32_t* px, int ancho) {
        return px && ancho >= 256 && cerca(px[size_t(72 * ancho + 160)], 146, 97, 48) &&
               cerca(px[size_t(72 * ancho + 100)], 146, 97, 48);
    };
    if (panel(arriba, ancho_arriba)) { fb = filas_x2(abajo, ancho_abajo); ta = total_magenta(arriba, ancho_arriba); }
    else if (panel(abajo, ancho_abajo)) { fa = filas_x2(arriba, ancho_arriba); tb = total_magenta(abajo, ancho_abajo); }
    if (!fa && !fb && !ta && !tb) return false;
    *sal_arriba = fa ? fa : (ta ? ta : arriba);
    *sal_abajo = fb ? fb : (tb ? tb : abajo);
    return true;
}
}  // namespace exp_x2
IE1_EXPORT int ie1_mods_overlay_dibujar_v1(const uint32_t* arriba, int ancho_arriba,
                                          const uint32_t* abajo, int ancho_abajo,
                                          const uint32_t** sal_arriba, const uint32_t** sal_abajo) {
    using namespace ent;
    if (!abierto) {
        if (const uint32_t* p = filtros::dibujar(abajo, ancho_abajo)) { *sal_arriba = arriba; *sal_abajo = p; return 1; }
    }
    if (!abierto && g_mod_exp_x2 && exp_x2::g_doble) {       // "x2!!" en la pantalla de EXP
        if (exp_x2::dibujar(arriba, ancho_arriba, abajo, ancho_abajo, sal_arriba, sal_abajo)) return 1;
    }
    if (!abierto) {                                   // panel de "Valor" (si toca) sobre la de arriba
        if (!ie1_valor_activo()) return 0;
        static const bool prueba = [] { const char* e = std::getenv("IE1_VALOR_PRUEBA"); return e && *e == '1'; }();
        if (prueba) valorov::prueba();
        // las escenas de los partidos salen en la pantalla de ABAJO (el juego intercambia las
        // pantallas); IE1_VALOR_PANTALLA=arriba para dibujar en la otra
        static const bool en_arriba = [] { const char* e = std::getenv("IE1_VALOR_PANTALLA"); return e && std::strcmp(e, "arriba") == 0; }();
        if (en_arriba) {
            if (const uint32_t* p = valorov::dibujar(arriba, ancho_arriba)) { *sal_arriba = p; *sal_abajo = abajo; return 1; }
        } else {
            if (const uint32_t* p = valorov::dibujar(abajo, ancho_abajo)) { *sal_arriba = arriba; *sal_abajo = p; return 1; }
        }
        return 0;
    }
    if (g_fondo_abajo.empty() || !g_mem) return 0;
    tic();                                        // repeticion al mantener pulsado
    preparar_fondos();
    std::memcpy(buf, g_fondo_abajo.data(), sizeof(buf));
    cabecera_propia();
    const uint32_t b = base(jug);
    // cabecera: icono de la cara, nombre (blanco), nivel con los graficos del juego y aptitud
    if (!icono_lista(jug, 4, 1)) icono(jug, 6, 6, 22);     // icono de las listas del juego
    texto(36, 7, nombre(jug), 0xFFF8F8F8, 0xFFF8F8F8);
    {
        const std::string nv = std::to_string(r8(b + 0xAA));
        if (sprite("MSUP_F08", 1, 2, 1, 36, 19)) numero("MSUP_F10", nv, 70, 14);
        else texto(36, 17, std::string(T5("Lv.", "Niv.", "Niv.", "Lv.", "Liv.")) + nv, 0xFFB4E6FF, 0xFF64B4E6);
    }
    const Sim sim = simular(jug, asig);
    // Aptitud: suma actual de las 7 estadisticas / tope del jugador (como IEditor)
    if (sim.tope) texto(78, 17, "Apt " + std::to_string(sim.suma) + "/" + std::to_string(sim.tope), 0xFFF8F8F8, 0xFFF8F8F8);
    // A la derecha: lo que queda libre antes de quitar a la pareja (a nivel 99 es la Libertad restante)
    detectar_etiqueta();
    {   // numero justo despues de la etiqueta, alineado con ella (vale para cualquier idioma)
        const int y = g_etq.y1 - 9;           // misma linea base que la etiqueta
        texto(g_etq.x1 + 5, y, sim.tope ? std::to_string(sim.lib) : "-", 0xFFF0FFFF, 0xFF8CDCF0);
    }
    // filas
    static const char* kEtiq[2] = {"PE", "PT"};
    for (int f = 0; f < kFilas; ++f) {
        const int yb = 42 + 12 * f, yt = yb - 3;
        if (f < 2 && !sprite("MSUP_F05", f, 2, 2, 124, yb - 9))     // etiqueta PE / PT del juego
            texto(124, yt, kEtiq[f], f == 0 ? 0xFFFFF070 : 0xFFB4FF8C, f == 0 ? 0xFFF0A020 : 0xFF50C850);
        if (f == fila) {
            rect(12, yb - 3, 69, yb + 8, 0xFFEC7818);
            rect(14, yb - 2, 21, yb + 7, 0xFF46B428); rect(60, yb - 2, 67, yb + 7, 0xFF46B428);
            flecha(16, yb, true, 0xFFEBFFD2); flecha(62, yb, false, 0xFFEBFFD2);
        }
        if (!numero("MSUP_F00", std::to_string(asig[f]), 44, yb - 9))
            texto(44, yt, std::to_string(asig[f]), 0xFFF0FFFF, 0xFF8CDCF0, true);
        const int v = actual(jug, f);
        const int nv = f < 2 ? sim.val_pe[f] : sim.disp[f - 2];
        // digitos del juego: blancos (estadisticas), amarillos (PE) y verdes (PT);
        // el valor nuevo en naranja si sube y en lila si baja, como en el menu de equipo
        const char* dig = f == 0 ? "MSUP_F04" : f == 1 ? "MSUP_F03" : "MSUP_F00";
        if (!numero(dig, std::to_string(v), 205, yb - 9))
            texto(205, yt, std::to_string(v), 0xFFF0FFFF, 0xFF8CDCF0, true);
        flecha(211, yb, false, 0xFF96E6FA);
        const char* dn = nv > v ? "MSUP_F01" : nv < v ? "MSUP_F02" : dig;
        if (!numero(dn, std::to_string(nv), 245, yb - 9)) {
            if (nv > v) texto(244, yt, std::to_string(nv), 0xFFFFF58C, 0xFFF0AA28, true);
            else if (nv < v) texto(244, yt, std::to_string(nv), 0xFFFF9C9C, 0xFFE04848, true);
            else texto(244, yt, std::to_string(nv), 0xFFF0FFFF, 0xFF8CDCF0, true);
        }
    }
    // pie: Pasion restante tras pagar + coste + ayuda
    const uint32_t pasion = r32(kPasion), coste = uint32_t(total_asig()) * kCoste;
    rect(8, 160, 150, 184, 0xFF181820);
    texto(12, 162, J(T5("Passion", "Pasión", "Passion", "Leidenschaft", "Passione")));
    texto(146, 162, std::to_string(pasion >= coste ? pasion - coste : 0), 0xFFF0FFFF, 0xFF8CDCF0, true);
    texto(12, 173, J(T5("Cost", "Coste", "Coût", "Kosten", "Costo")), 0xFFB4C8DC, 0xFF8CA0B4);
    texto(146, 173, coste ? "-" + std::to_string(coste) : "0", 0xFFFFF58C, 0xFFF0AA28, true);
    // Botones como los del juego: caja oscura redondeada, circulo naranja con la letra
    {   // anchos segun el texto (cambia con el idioma)
        const std::string ta = J(T5("OK", "Aceptar", "Valider", "OK", "OK")), tb = J(T5("Exit", "Salir", "Quitter", "Zurück", "Esci"));
        const int wa = ancho(ta) + 17, wb = ancho(tb) + 17;
        g_boton_a = {251 - wb - 3 - wa, wa}; g_boton_b = {251 - wb, wb};
        boton(g_boton_a.x, 162, wa, "A", ta);
        boton(g_boton_b.x, 162, wb, "B", tb);
    }
    // Cambiar de jugador: L / R (o tocar el nombre)
    texto(153, 175, "L", 0xFFB4E6FF, 0xFF64B4E6); flecha(160, 177, true, 0xFF96E6FA);
    flecha(240, 177, false, 0xFF96E6FA); texto(246, 175, "R", 0xFFB4E6FF, 0xFF64B4E6);
    {   // X: volver al nivel 1; Y: subir de nivel (entre L y R)
        const std::string tx = J(T5("Lv1", "Nv1", "Nv1", "Lv1", "Lv1"));
        const std::string ty = J(T5("Lv+", "Nv+", "Nv+", "Lv+", "Lv+"));
        const int wx = ancho(tx) + 16, wy = ancho(ty) + 16;
        const int x0 = 202 - (wx + 2 + wy) / 2;
        g_boton_y = {x0, wy}; g_boton_x = {x0 + wy + 2, wx};
        boton(g_boton_y.x, 174, wy, "Y", ty);
        boton(g_boton_x.x, 174, wx, "X", tx);
    }
    if (nivel_abierto) {   // ventana "Subir de nivel"
        for (uint32_t& c : buf) c = 0xFF000000u | (c >> 1 & 0x7F7F7Fu);
        rect(21, 44, 234, 141, 0xFF7C7C88);
        rect(22, 45, 233, 140, 0xFF181820);
        auto centro = [](int y, const std::string& t, uint32_t c1, uint32_t c2) { texto(128 - ancho(t) / 2, y, t, c1, c2); };
        const uint32_t bj = base(jug);
        const int nv = r8(bj + 0xAA);
        const Subida su = simular_subida(jug, nivel_obj);
        centro(48, J(T5("Level up", "Subir de nivel", "Monter de niveau", "Level erhöhen", "Aumenta livello")), 0xFFFFF58C, 0xFFF0AA28);
        centro(61, nombre(jug), 0xFFF8F8F8, 0xFFF8F8F8);
        {   // nivel: flechas para elegir
            const std::string t = J(T5("Lv.", "Nv.", "Niv.", "Lv.", "Liv.")) + std::to_string(nv) + "  >  " + std::to_string(nivel_obj);
            const int w = ancho(t), x = 128 - w / 2;
            flecha(x - 14, 78, true, 0xFF96E6FA); flecha(x + w + 8, 78, false, 0xFF96E6FA);
            texto(x, 75, t, 0xFFF0FFFF, 0xFF8CDCF0);
        }
        if (su.ok) {
            const uint32_t pasion = r32(kPasion);
            const bool alcanza = su.coste <= pasion;
            const std::string pe = "PE " + std::to_string(r16(bj + 0xD0)) + ">" + std::to_string(su.p[0xD0] | su.p[0xD1] << 8) +
                                   "   PT " + std::to_string(r16(bj + 0xD2)) + ">" + std::to_string(su.p[0xD2] | su.p[0xD3] << 8);
            centro(89, pe, 0xFFF0FFFF, 0xFF8CDCF0);
            int suma0 = 0, suma1 = 0;
            for (int i = 0; i < 7; ++i) { suma0 += r8(bj + 0xD8 + uint32_t(i)); suma1 += su.p[0xD8 + i]; }
            std::string st = J(T5("Stats", "Estadísticas", "Stats", "Werte", "Statistiche")) + " " + std::to_string(suma0) + ">" + std::to_string(suma1);
            if (su.tecnicas) st += "   " + J(T5("Moves", "Técnicas", "Techn.", "Techn.", "Tecniche")) + " +" + std::to_string(su.tecnicas);
            centro(101, st, 0xFFF0FFFF, 0xFF8CDCF0);
            const std::string co = J(T5("Cost", "Coste", "Coût", "Kosten", "Costo")) + " " + std::to_string(su.coste) + "  /  " +
                                   J(T5("Passion", "Pasión", "Passion", "Leidenschaft", "Passione")) + " " + std::to_string(pasion);
            if (alcanza) centro(113, co, 0xFFFFF58C, 0xFFF0AA28);
            else centro(113, co, 0xFFFF9C9C, 0xFFE04848);
        }
        const std::string ta = J(T5("Level up", "Subir", "Monter", "Erhöhen", "Aumenta")), tb = J(T5("Exit", "Salir", "Quitter", "Zurück", "Esci"));
        const int wa = ancho(ta) + 17, wb = ancho(tb) + 17;
        g_conf_a = {128 - 6 - wa, wa}; g_conf_b = {128 + 6, wb};
        boton(g_conf_a.x, kConfY, wa, "A", ta);
        boton(g_conf_b.x, kConfY, wb, "B", tb);
    }
    if (confirmar) {   // ventana de confirmacion, sobre el menu oscurecido
        for (uint32_t& c : buf) c = 0xFF000000u | (c >> 1 & 0x7F7F7Fu);
        rect(21, 50, 234, 141, 0xFF7C7C88);
        rect(22, 51, 233, 140, 0xFF181820);
        auto centro = [](int y, const std::string& t, uint32_t c1, uint32_t c2) { texto(128 - ancho(t) / 2, y, t, c1, c2); };
        centro(55, J(T5("Back to level 1?", "¿Volver al nivel 1?", "Revenir au niveau 1 ?", "Zurück auf Level 1?", "Tornare al livello 1?")), 0xFFFFF58C, 0xFFF0AA28);
        centro(69, nombre(jug), 0xFFF8F8F8, 0xFFF8F8F8);
        centro(85, J(T5("Keeps the moves learned", "Conserva sus supertécnicas", "Garde ses supertechniques", "Behält seine Supertechniken", "Conserva le sue supertecniche")), 0xFFF0FFFF, 0xFF8CDCF0);
        centro(97, J(T5("Loses all training", "Pierde todo lo entrenado", "Perd tout l'entraînement", "Verliert alles Trainierte", "Perde tutto l'allenamento")), 0xFFFF9C9C, 0xFFE04848);
        if (niveles_activos())
            centro(109, J(T5("Moves go back to 0 uses", "Las técnicas vuelven a 0 usos", "Techniques remises à 0 utilisation", "Techniken auf 0 Einsätze", "Tecniche a 0 usi")), 0xFFFF9C9C, 0xFFE04848);
        const std::string ta = J(T5("Yes", "Sí", "Oui", "Ja", "Sì")), tb = J(T5("No", "No", "Non", "Nein", "No"));
        const int wa = ancho(ta) + 17, wb = ancho(tb) + 17;
        g_conf_a = {128 - 6 - wa, wa}; g_conf_b = {128 + 6, wb};
        boton(g_conf_a.x, kConfY, wa, "A", ta);
        boton(g_conf_b.x, kConfY, wb, "B", tb);
    }
    if (aviso_t > 0 && !aviso.empty()) { --aviso_t; rect(40, 148, 216, 158, 0xFF181820); texto(128 - ancho(aviso) / 2, 148, aviso, 0xFFFFF58C, 0xFFF0AA28); }
    if (!g_fondo_ficha.empty() && ancho_arriba == 256) { dibujar_ficha(jug); *sal_arriba = buf_arriba; }
    else *sal_arriba = arriba;
    *sal_abajo = buf;
    return 1;
}

// ---- Aviso "Nv +" al subir una supertecnica de grado --------------------------
// Con el mod de niveles (categorias en command.dat), el juego ya sube el grado
// solo. Aqui se vigilan los contadores de usos de cada jugador (bloque +0xA4,
// uno por ranura; tecnicas en +0x98) y, si un uso cruza un umbral de su
// categoria (lvup_command.dat: filas de 41 bytes, [clase, umbral, bono, ...]),
// se lanza el evento del cartel "Nv +" del propio juego en el objeto de evento
// del jugador (puntero en bloque +0xE8: duracion +0x12, contador +0x14,
// tipo +0x1C; tipo 9 = cartel). Solo cuando no hay otro evento activo (tipo 0),
// y entre fotogramas, para no pisar nada a medio escribir.
int ie1_grado(int tecnica, int usos) {
    if (tecnica <= 0 || size_t(tecnica + 1) * 28 > g_cmddat.size()) return 0;
    const uint8_t cat = g_cmddat[size_t(tecnica) * 28 + 0x10];
    if (!cat) return 0;
    for (size_t f = 0; f + 41 <= g_lvup.size(); f += 41) {
        if (g_lvup[f] != cat) continue;
        int g = 0;
        for (size_t k = 1; k + 1 < 41; k += 2) {
            const uint8_t umbral = g_lvup[f + k];
            if (umbral == 0xFF) break;
            if (usos >= umbral) ++g;
        }
        return g;
    }
    return 0;
}
// Uso que sube de grado (2026-11-21, Defensa triple de Mark): el juego suma el uso al elegir la
// tecnica, antes del calculo y del cartel, asi que el cartel salia ya con el grado nuevo ("++"
// en vez de "+") y el "Nv +" despues. En el IE2 el cartel lleva el grado con el que se uso y la
// subida se avisa despues. Por eso, al ver ese uso, la tabla de marcas sigue con los usos de
// antes hasta que sale el cartel de esa tecnica (o 30 s), y entonces se lanza el "Nv +".
struct RetencionGrado { uint32_t bloque; int slot; uint16_t tec; uint8_t usos_antes; uint32_t carteles; int espera; };
std::vector<RetencionGrado> g_retenciones;
constexpr uint32_t kDiagMarcaG = 0x023FB0E0u;   // = kDiagMarca (mas abajo): tecnica, jugador, nombre, contador
int usos_para_marca(uint32_t bloque, int slot, int usos) {
    for (const RetencionGrado& r : g_retenciones) if (r.bloque == bloque && r.slot == slot) return r.usos_antes;
    return usos;
}
void ie1_niveles_tick() {
    static int activo = -1;
    if (!g_mem) return;
    if (activo < 0) {
        activo = 0;
        for (size_t i = 0; i + 28 <= g_cmddat.size(); i += 28) if (g_cmddat[i + 0x10]) { activo = 1; break; }
        if (activo && g_lvup.empty()) activo = 0;
        g_bkr_anims = 0;                                // animaciones de los bocadillos
        if (!g_bkr.empty()) {
            const std::vector<uint8_t> d = g_bkr[0] == 0x10 ? ent::lz10(g_bkr) : g_bkr;
            auto u32 = [&](size_t o) { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0u; };
            const uint32_t n = u32(0);
            if (n >= 1 && n < 16) { const uint32_t off = u32(4 + 8 * (n - 1)); if (off < d.size()) g_bkr_anims = d[off]; }
        }
        if (activo) logf("[mods] niveles de supertecnicas: activo (bocadillos con %d animaciones)", g_bkr_anims);
    }
    if (!activo) return;
    { void ie1_marcas_tick(); ie1_marcas_tick(); }
    struct Previo { bool ok = false; uint16_t tec[6]{}; uint8_t usos[6]{}; };
    static Previo prev[ent::kMaxJug];
    struct Aviso { uint32_t bloque; int espera; };
    static std::vector<Aviso> avisos;
    for (int j = 0; j < ent::kMaxJug; ++j) {
        const uint32_t b = ent::kJugadores + uint32_t(j) * ent::kTam;
        const uint8_t c0 = g_mem->r8(b), nivel = g_mem->r8(b + 0xAA);
        Previo& p = prev[j];
        if (c0 < 0x20 || c0 >= 0x7F || nivel < 1 || nivel > 99) { p.ok = false; continue; }
        Previo n; n.ok = true;
        for (int s = 0; s < 6; ++s) { n.tec[s] = g_mem->r16(b + 0x98 + 2u * uint32_t(s)); n.usos[s] = g_mem->r8(b + 0xA4 + uint32_t(s)); }
        if (p.ok)
            for (int s = 0; s < 6; ++s)
                if (n.tec[s] == p.tec[s] && n.usos[s] == uint8_t(p.usos[s] + 1) &&
                    ie1_grado(n.tec[s], n.usos[s]) > ie1_grado(n.tec[s], p.usos[s])) {
                    g_retenciones.push_back({b, s, n.tec[s], p.usos[s], g_mem->r32(kDiagMarcaG + 0xC), 0});
                    logf("[mods] niveles: %s sube de grado (tecnica 0x%X, %d usos): el cartel de este uso sale con el grado de antes",
                         ent::nombre(j).c_str(), n.tec[s], n.usos[s]);
                }
        p = n;
    }
    // se suelta la retencion cuando sale el cartel de esa tecnica (o a los 30 s) y se avisa "Nv +"
    for (size_t i = 0; i < g_retenciones.size();) {
        RetencionGrado& r = g_retenciones[i];
        const bool cartel = g_mem->r32(kDiagMarcaG + 0xC) != r.carteles && g_mem->r32(kDiagMarcaG) == r.tec;
        if (cartel || ++r.espera > 1800) {
            avisos.push_back({r.bloque, 0});
            g_retenciones.erase(g_retenciones.begin() + std::ptrdiff_t(i));
        } else ++i;
    }
    for (size_t i = 0; i < avisos.size();) {
        Aviso& a = avisos[i];
        const uint32_t ev = g_mem->r32(a.bloque + 0xE8);
        bool hecho = false;
        if (ev >= 0x02000000u && ev < 0x02400000u && (ev & 3u) == 0) {
            if (g_bkr_anims >= 0 && g_bkr_anims < 9) {
                hecho = true;                          // bocadillos sin el cartel (idioma sin los del IE2): no se lanza
            } else if (g_mem->r8(ev + 0x1C) == 0) {   // sin otro evento: cartel "Nv +"
                g_mem->w16(ev + 0x12, 40);
                g_mem->w16(ev + 0x14, 0);
                g_mem->w8(ev + 0x1C, 9);
                hecho = true;
            }
        }
        if (hecho || ++a.espera > 600) avisos.erase(avisos.begin() + std::ptrdiff_t(i));   // como mucho ~10 s esperando
        else ++i;
    }
}


// ---- Codigo nuevo en el juego (prueba 1 del cartel de grado) -------------------
// Para portar la marca de grado del IE2 hay que anadir codigo ARM al IE1. Esta
// primera prueba solo comprueba que el runner ejecuta codigo inyectado: el final
// de la funcion que crea el cartel de la tecnica (0x0205F15C, su "pop" en
// 0x0205F384) salta a un trozo de codigo en una zona libre de la RAM
// (0x023FA000) que suma 1 a un contador (0x023FB000) y vuelve a hacer el "pop".
// El complemento comprueba en cada fotograma que el codigo y el salto siguen ahi
// (al cargar un estado se restaura la memoria) y avisa cuando el contador cambia.
constexpr uint32_t kGanchoCartel = 0x0205F384u, kPopOriginal = 0xE8BD8FF0u;
constexpr uint32_t kZonaCodigo = 0x023FA000u, kContador = 0x023FB000u;
void ie1_inyeccion_tick() {
    if (!g_mem) return;
    static const uint32_t stub[] = {
        0xE92D100Fu,        // push {r0-r3, r12}
        0xE59F0010u,        // ldr  r0, [pc, #0x10]   (=kContador)
        0xE5901000u,        // ldr  r1, [r0]
        0xE2811001u,        // add  r1, r1, #1
        0xE5801000u,        // str  r1, [r0]
        0xE8BD100Fu,        // pop  {r0-r3, r12}
        kPopOriginal,       // pop  {r4-r11, pc}      (la instruccion original)
        kContador,
    };
    // solo si el ARM9 del IE1 europeo esta cargado (la instruccion original o ya el salto)
    const uint32_t salto = 0xEA000000u | (((kZonaCodigo - (kGanchoCartel + 8u)) >> 2) & 0x00FFFFFFu);
    const uint32_t actual = g_mem->r32(kGanchoCartel);
    if (actual != kPopOriginal && actual != salto) return;
    for (size_t i = 0; i < sizeof(stub) / 4; ++i)
        if (g_mem->r32(kZonaCodigo + 4u * uint32_t(i)) != stub[i]) g_mem->w32(kZonaCodigo + 4u * uint32_t(i), stub[i]);
    if (actual != salto) {
        g_mem->w32(kGanchoCartel, salto);
        static bool avisado = false;
        if (!avisado) { avisado = true; logf("[mods] cartel de grado: gancho instalado en 0x%08X -> 0x%08X", kGanchoCartel, kZonaCodigo); }
    }
    static uint32_t visto = 0;
    const uint32_t n = g_mem->r32(kContador);
    if (n != visto) { logf("[mods] cartel de grado: el codigo inyectado se ha ejecutado (%u veces)", n); visto = n; }
}


// ---- Prueba 2: leer la tecnica y el jugador del guion del cartel ---------------
// El manejador de la instruccion 0x3078 (overlay 15, 0x02155AC8) llama a la
// funcion del cartel y despues ejecuta "ldrsb r0,[r5,#0xB]" en 0x02155B38. Ahi se
// desvia a un codigo que copia: la escena ([r7]), la variable 2 del guion
// (tecnica, [r7+0x18]), la variable 6 ([r7+0x28]) y el propio interprete (r7).
// El overlay 15 solo esta cargado en los partidos: se vuelve a poner si hace falta.
constexpr uint32_t kGancho2 = 0x02155B38u, kZona2 = 0x023FA100u, kDatos2 = 0x023FB010u;
void ie1_prueba2_tick() {
    if (!g_mem) return;
    static const uint32_t stub[] = {
        0xE92D500Fu, 0xE59F0030u, 0xE5971000u, 0xE5801000u, 0xE5971018u, 0xE5801004u,
        0xE5971028u, 0xE5801008u, 0xE580700Cu, 0xE5901010u, 0xE2811001u, 0xE5801010u,
        0xE8BD500Fu, 0xE1D500DBu, 0xEAF56E7Fu, kDatos2};
    const uint32_t salto = 0xEA000000u | (((kZona2 - (kGancho2 + 8u)) >> 2) & 0x00FFFFFFu);
    // el overlay 15 tiene que estar cargado (las instrucciones de alrededor coinciden)
    if (g_mem->r32(kGancho2 - 4) != 0xEBFC2588u || g_mem->r32(kGancho2 + 4) != 0xE2800001u) return;
    const uint32_t actual = g_mem->r32(kGancho2);
    if (actual != 0xE1D500DBu && actual != salto) return;
    for (size_t i = 0; i < sizeof(stub) / 4; ++i)
        if (g_mem->r32(kZona2 + 4u * uint32_t(i)) != stub[i]) g_mem->w32(kZona2 + 4u * uint32_t(i), stub[i]);
    if (actual != salto) {
        g_mem->w32(kGancho2, salto);
        static bool avisado = false;
        if (!avisado) { avisado = true; logf("[mods] cartel de grado (prueba 2): gancho en 0x%08X", kGancho2); }
    }
    static uint32_t visto = 0;
    const uint32_t n = g_mem->r32(kDatos2 + 0x10);
    if (n == visto) return;
    visto = n;
    const uint32_t escena = g_mem->r32(kDatos2), tec = g_mem->r32(kDatos2 + 4), v6 = g_mem->r32(kDatos2 + 8), vm = g_mem->r32(kDatos2 + 0xC);
    logf("[mods] cartel (prueba 2) #%u: escena=%08X interprete=%08X var2=%u (0x%X, %s) var6=0x%08X",
         n, escena, vm, tec, tec, ent::nombre_tecnica(int(tec)).c_str(), v6);
    if (v6 >= 0x02000000u && v6 < 0x02400000u) {
        char linea[200]; int k = 0;
        for (uint32_t o = 0; o < 0x40; o += 4) k += std::snprintf(linea + k, sizeof(linea) - size_t(k), " %08X", g_mem->r32(v6 + o));
        logf("[mods]   var6 apunta a:%s", linea);
    }
    // variables 0..15 del guion, por si acaso
    char linea[260]; int k = 0;
    for (uint32_t i = 0; i < 16; ++i) k += std::snprintf(linea + k, sizeof(linea) - size_t(k), " %X", g_mem->r32(vm + 0x10 + 4u * i));
    logf("[mods]   variables del guion:%s", linea);
}


// ---- Marca de grado en el cartel de la tecnica (como el IE2) -------------------
// Los guiones de tecnica (modificados por crear_mod_niveles.py) guardan el numero
// de la tecnica en su variable 20 justo antes de la instruccion 0x3078 (la del
// cartel), y despues cargan en una ranura el grafico cuyo nombre este en su
// variable 21. Ese nombre lo pone este codigo inyectado, enganchado al final del
// manejador de 0x3078 (overlay 15, 0x02155B38): busca en una tabla (jugador,
// tecnica) -> marca, que el complemento mantiene al dia en cada fotograma, y
// deja en la variable 21 la direccion del nombre del grafico ("tt70".."tt78"
// = marcas mbv_c050..058 del IE2; "tt85" = vacio, sin marca).
constexpr uint32_t kGanchoMarca = 0x02155B38u, kCodigoMarca = 0x023FA200u;
constexpr uint32_t kTablaMarca = 0x023FB100u, kNombresMarca = 0x023FA400u;
constexpr uint32_t kDiagMarca = 0x023FB0E0u;   // ultimo cartel: tecnica, jugador, nombre elegido, contador
int ie1_marca(int tecnica, int usos) {
    if (tecnica <= 0 || size_t(tecnica + 1) * 28 > g_cmddat.size()) return 0;
    const int cat = g_cmddat[size_t(tecnica) * 28 + 0x10];
    if (!cat) return 0;
    const int g = ie1_grado(tecnica, usos);            // 0 = grado base (sin marca)
    if (g < 1) return 0;
    static const int kBase[3] = {4, -1, 1};            // como el IE2: tipo = categoria / 100
    const int tipo = cat / 100;
    if (tipo > 2) return 0;
    const int n = 50 + kBase[tipo] + g;                // mbv_c0NN del IE2
    return (n >= 50 && n <= 58) ? n - 49 : 0;          // 1..9 -> tt70..tt78
}
void ie1_marcas_tick() {
    // Version 2: ademas coloca el nombre como el IE2. El guion deja en su variable 22 la x
    // del nombre con marca y en la 23 la x sin marca; si no hay marca, var22 = var23
    // (crear_mod_niveles.py: el movimiento de descanso del nombre lee la variable 22).
    //   push {r0-r3,r12,lr}; r0 = var20 (tecnica); r1 = jugador; r2 = tabla; r3 = 0
    //   bucle: (jugador, tecnica) -> r3 = marca
    //   cmp r3,#0; ldreq r12,[r7,#0x6C]; streq r12,[r7,#0x68]      (var22 = var23)
    //   var21 = nombres + r3*8; diagnostico; pop; instruccion original; vuelta
    static const uint32_t stub[] = {
        0xE92D500Fu, 0xE5970060u, 0xE59D1098u, 0xE59F206Cu, 0xE3A03000u, 0xE1D2C0B0u, 0xE35C0000u, 0x0A000007u,
        0xE15C0001u, 0x1A000003u, 0xE1D2C0B2u, 0xE15C0000u, 0x05923004u, 0x0A000001u, 0xE2822008u, 0xEAFFFFF4u,
        0xE3530000u, 0x0597C06Cu, 0x0587C068u,
        0xE59F2030u, 0xE0823183u, 0xE5873064u, 0xE59F2028u, 0xE5820000u, 0xE5821004u, 0xE5823008u, 0xE592C00Cu,
        0xE28CC001u, 0xE582C00Cu, 0xE8BD500Fu, 0xE1D500DBu,
        0xEA000000u | ((((kGanchoMarca + 4u) - (kCodigoMarca + 0x7Cu + 8u)) >> 2) & 0x00FFFFFFu),
        kTablaMarca, kNombresMarca, kDiagMarca};
    if (!g_mem || g_cmddat.empty() || g_lvup.empty()) return;
    // nombres de los graficos: [0] vacio, [1..9] marcas
    static const char* kNombres[10] = {"tt85", "tt70", "tt71", "tt72", "tt73", "tt74", "tt75", "tt76", "tt77", "tt78"};
    for (int k = 0; k < 10; ++k)
        for (int c = 0; c < 8; ++c) {
            const uint8_t v = uint8_t(c < int(std::strlen(kNombres[k])) ? kNombres[k][c] : 0);
            if (g_mem->r8(kNombresMarca + uint32_t(k * 8 + c)) != v) g_mem->w8(kNombresMarca + uint32_t(k * 8 + c), v);
        }
    // tabla (jugador, tecnica, marca), terminada en jugador 0
    static std::vector<uint32_t> antes;
    std::vector<uint32_t> t;
    for (int j = 0; j < ent::kMaxJug; ++j) {
        const uint32_t b = ent::kJugadores + uint32_t(j) * ent::kTam;
        const uint8_t c0 = g_mem->r8(b), nivel = g_mem->r8(b + 0xAA);
        if (c0 < 0x20 || c0 >= 0x7F || nivel < 1 || nivel > 99) continue;
        const uint32_t unidad = g_mem->r16(b + 0x42);
        if (!unidad) continue;
        for (int s = 0; s < 6; ++s) {
            const int tec = g_mem->r16(b + 0x98 + 2u * uint32_t(s));
            if (!tec) continue;
            t.push_back(unidad | uint32_t(tec) << 16);
            t.push_back(uint32_t(ie1_marca(tec, usos_para_marca(b, s, g_mem->r8(b + 0xA4 + uint32_t(s))))));
        }
    }
    t.push_back(0); t.push_back(0);
    if (t.size() > 1200) t.resize(1200);              // la zona libre llega de sobra
    for (size_t i = 0; i < t.size(); ++i)
        if (i >= antes.size() || antes[i] != t[i] || g_mem->r32(kTablaMarca + 4u * uint32_t(i)) != t[i])
            g_mem->w32(kTablaMarca + 4u * uint32_t(i), t[i]);
    antes = t;
    // gancho en el manejador de 0x3078 (solo con el overlay 15 cargado)
    if (g_mem->r32(kGanchoMarca - 4) != 0xEBFC2588u || g_mem->r32(kGanchoMarca + 4) != 0xE2800001u) return;
    const uint32_t salto = 0xEA000000u | (((kCodigoMarca - (kGanchoMarca + 8u)) >> 2) & 0x00FFFFFFu);
    const uint32_t actual = g_mem->r32(kGanchoMarca);
    if (actual != 0xE1D500DBu && actual != salto) return;
    for (size_t i = 0; i < sizeof(stub) / 4; ++i)
        if (g_mem->r32(kCodigoMarca + 4u * uint32_t(i)) != stub[i]) g_mem->w32(kCodigoMarca + 4u * uint32_t(i), stub[i]);
    if (actual != salto) {
        g_mem->w32(kGanchoMarca, salto);
        static bool avisado = false;
        if (!avisado) { avisado = true; logf("[mods] niveles: marca de grado en el cartel activa (gancho en 0x%08X)", kGanchoMarca); }
    }
    // diagnostico: cada cartel que pasa por el gancho
    static uint32_t visto = 0;
    const uint32_t n = g_mem->r32(kDiagMarca + 0xC);
    if (n != visto) {
        visto = n;
        const uint32_t tec = g_mem->r32(kDiagMarca), uni = g_mem->r32(kDiagMarca + 4), nom = g_mem->r32(kDiagMarca + 8);
        char nb[9] = {};
        for (int c = 0; c < 8; ++c) nb[c] = char(g_mem->r8(nom + uint32_t(c)));
        logf("[mods] niveles: cartel #%u: jugador 0x%X, tecnica %u (0x%X) -> grafico \"%s\"", n, uni, tec, tec, nb);
        if (ie1_valor_activo()) valorov::cartel(int(tec), (uni & 0x8000u) == 0);
    }
}

// ---- Senal del NPC entrenador ----------------------------------------------
// Su guion, al contestar "Si", guarda en una variable del juego (la 0x10021,
// que ningun guion original usa) el valor kSenal. Las variables son
// de 32 bits en la RAM principal: la buscamos (de vez en cuando, hasta
// encontrarla), abrimos el menu de entrenamiento y la ponemos a 0.
constexpr uint32_t kSenal = 0x51E7A1A5u;
void ie1_senal_npc() {
    // Direcciones donde ha aparecido la senal (la variable global 0x21 vive en
    // 0x020DC0FC en la version europea; se comprueban en cada fotograma, sin esperar)
    static std::vector<uint32_t> conocidas = {0x020DC0FCu};
    static uint32_t dir = 0;
    static int espera = 0;
    static bool avisado = false;
    static std::vector<uint8_t> ram;
    if (!g_mem || g_fondo_abajo.empty()) return;
    if (!avisado) {
        avisado = true;
        if (g_mem->version < 2 || !g_mem->copiar)
            logf("[mods] NPC entrenador: el ejecutable es antiguo (sin copia de memoria); recompila con paso_mingw.sh");
        else
            logf("[mods] NPC entrenador: vigilando la senal del guion");
    }
    bool hay = false;
    for (uint32_t c : conocidas)
        if (g_mem->r32(c) == kSenal) { dir = c; hay = true; break; }
    // Busqueda por toda la RAM (4 MB, ~3 veces por segundo): solo para depurar, con
    // IE1_NPC_BUSCAR=1. Costaba unos 0,3 ms por fotograma de media y un tiron cada
    // 20 fotogramas, y daba falsos positivos (copias del guion en el monton) en los
    // que escribia 0. La variable 0x21 esta siempre en 0x020DC0FC en la version EU.
    static const bool buscar = [] { const char* e = std::getenv("IE1_NPC_BUSCAR"); return e && *e == '1'; }();
    if (!hay && buscar && g_mem->version >= 2 && g_mem->copiar && ++espera >= 20) {   // ~3 veces por segundo
        espera = 0;
        ram.resize(0x400000);
        bool ok = true;
        for (uint32_t o = 0; o < ram.size() && ok; o += 0x10000)          // por bloques de 64 KB
            ok = g_mem->copiar(0x02000000u + o, ram.data() + o, 0x10000) != 0;
        if (!ok) {
            static bool fallo = false;
            if (!fallo) { fallo = true; logf("[mods] NPC entrenador: no puedo copiar la memoria del juego"); }
            return;
        }
        for (size_t o = 4; o + 4 <= ram.size(); o += 4) {
            uint32_t v, antes; std::memcpy(&v, &ram[o], 4); std::memcpy(&antes, &ram[o - 4], 4);
            // la propia instruccion del guion lleva el valor detras del numero de variable: no es la senal
            if (v == kSenal && (antes >> 16) != 1u && (antes >> 16) != 2u) { dir = 0x02000000u + uint32_t(o); hay = true; break; }
        }
        if (hay) {
            logf("[mods] NPC entrenador: senal en 0x%08X", dir);
            if (std::find(conocidas.begin(), conocidas.end(), dir) == conocidas.end() && conocidas.size() < 8)
                conocidas.push_back(dir);
        }
    }
    if (!hay) return;
    g_mem->w32(dir, 0);
    if (!ent::abierto) ie1_mods_overlay_alternar_v1();
}

#ifdef IE1_TEST
IE1_EXPORT void ie1_mods_test_cargar(const char* unitno, const char* unitstat) {
    leer(unitno, g_unitno); leer(unitstat, g_unitstat); leer("/tmp/pc/archivos/data_iz/logic/status_up.dat", g_curvas); leer("/tmp/pc/archivos/data_iz/logic/lvup_exp.dat", g_lvup_exp);
    leer("/tmp/pc/archivos/data_iz/logic/en/item.dat", g_itemdat); leer("/tmp/pc/archivos/data_iz/logic/en/command.dat", g_cmddat);
    leer("/tmp/pc/archivos/data_iz/logic/en/command.STR", g_cmdstr);
    if (const char* e = std::getenv("IE1_TEST_CMD")) leer(e, g_cmddat);          // command.dat con el mod de niveles
    if (const char* e = std::getenv("IE1_TEST_LVUP")) leer(e, g_lvup);
    leer("/tmp/pc/archivos/data_iz/font/FONT12T.NFTR", g_fuente12);
    leer("/tmp/pc/archivos/data_iz/pic2d/menu/en/SMStat.SPF_", g_smstat);
    leer("/tmp/pc/archivos/data_iz/pic2d/menu/en/msup_z05.pac_", g_z05);
    leer("/tmp/pc/archivos/data_iz/pic3d/en/waza_den.SPL", g_wd_l); leer("/tmp/pc/archivos/data_iz/pic3d/en/waza_den.SPD", g_wd_d);
    leer("/tmp/pc/archivos/data_iz/pic3d/en/shop.SPL", g_sh_l); leer("/tmp/pc/archivos/data_iz/pic3d/en/shop.SPD", g_sh_d);
    leer("/tmp/pc/archivos/data_iz/face2d/fac.pkh", g_fac_h); leer("/tmp/pc/archivos/data_iz/face2d/fac.pkb", g_fac_b);
    leer("/tmp/pc/archivos/data_iz/face2d/fab.pkh", g_fab_h); leer("/tmp/pc/archivos/data_iz/face2d/fab.pkb", g_fab_b);
    leer("/tmp/pc/archivos/data_iz/pic3d/ih.pkh", g_ih_h); leer("/tmp/pc/archivos/data_iz/pic3d/ih.pkb", g_ih_b);
    leer("/tmp/pc/archivos/data_iz/pic2d/cmd/en/mbd_c.pkh", g_mbd_h); leer("/tmp/pc/archivos/data_iz/pic2d/cmd/en/mbd_c.pkb", g_mbd_b);
}
#endif


// ---- Registro del "valor" (forma total) de cada duelo, tiro y parada ---------
// El juego calcula el valor con 0x02069394 (fila de unitcalc.dat en r3, jugador
// en r1). Al salir (0x0206A05C, r0 = valor) se salta a un trozo de codigo que
// apunta en un anillo de 32 entradas: [jugador, fila, valor, arg2]. El
// complemento lo lee cada fotograma y lo escribe en el registro. Solo con
// IE1_POTENCIA=1 (la pagina de codigo tocada se ejecuta interpretada).
constexpr uint32_t kGanchoPot = 0x0206A05Cu, kCodigoPot = 0x023FA300u, kAnilloPot = 0x023FD000u;
constexpr uint32_t kGanchoAzar = 0x02069780u, kCodigoAzar = 0x023FA3A0u;   // add r5, r5, r0 (suma del azar)
constexpr uint32_t kGanchoCrit = 0x02069C30u, kCodigoCrit = 0x023FA3C0u;   // cmp r0, #10 (tirada de Critical!)
constexpr uint32_t kTempPot = kAnilloPot + 0x800u;                          // [azar, tirada critico]
const char* ie1_fila_valor(uint32_t f) {
    switch (f) {
        case 1: return "regate normal";
        case 3: return "entrada normal";
        case 4: return "tiro normal";
        case 5: return "tiro picado";
        case 6: return "tiro directo";
        case 7: return "parada normal contra super";
        case 8: return "parada normal";
        case 9: return "tiro con supertecnica";
        case 10: return "parada con supertecnica";
        case 14: return "fuerza del tiro";
        case 15: return "control (pase/recepcion)";
        case 20: return "portero (sin calculo)";
        case 25: return "regate con supertecnica";
        case 27: return "bloqueo con supertecnica";
        case 28: return "tiro-bloqueo (bloqueo)";
        case 31: return "forcejeo previo";
        case 32: return "tiro-bloqueo (tiro)";
        default: return "otra accion";
    }
}
const char* ie1_elemento(int e) {
    switch (e) { case 1: return "aire"; case 2: return "bosque"; case 3: return "fuego"; case 4: return "montana"; default: return "-"; }
}
// ventaja de elemento (como 0x020690A8): aire>montana, bosque>aire, fuego>bosque, montana>fuego
bool ie1_gana_elemento(int a, int b) {
    return (a == 1 && b == 4) || (a == 2 && b == 1) || (a == 3 && b == 2) || (a == 4 && b == 3);
}
// Supertecnica a partir de su registro en memoria (comparando sus 28 bytes con command.dat)
int ie1_tecnica_de_registro(uint32_t dir) {
    static std::map<uint32_t, int> cache;
    if (dir < 0x02000000u || dir >= 0x023F0000u || g_cmddat.empty()) return 0;
    uint8_t r[28];
    for (int k = 0; k < 28; ++k) r[k] = g_mem->r8(dir + uint32_t(k));
    auto it = cache.find(dir);
    if (it != cache.end() && std::memcmp(g_cmddat.data() + size_t(it->second) * 28, r, 28) == 0) return it->second;
    for (size_t t = 1; (t + 1) * 28 <= g_cmddat.size(); ++t)
        if (std::memcmp(g_cmddat.data() + t * 28, r, 28) == 0) { cache[dir] = int(t); return int(t); }
    return 0;
}
// Poder extra por nivel de la tecnica: lvup_command.dat, filas de 41 bytes
// [categoria, usos1, extra1, usos2, extra2, ...] (0xFF = fin); vale el ultimo umbral alcanzado
int ie1_bono_tecnica(int tecnica, int usos) {
    if (tecnica <= 0 || size_t(tecnica + 1) * 28 > g_cmddat.size()) return 0;
    const uint8_t cat = g_cmddat[size_t(tecnica) * 28 + 0x10];
    if (!cat) return 0;
    for (size_t f = 0; f + 41 <= g_lvup.size(); f += 41) {
        if (g_lvup[f] != cat) continue;
        int b = 0;
        for (size_t k = 1; k + 1 < 41; k += 2) {
            if (g_lvup[f + k] == 0xFF) break;
            if (usos >= g_lvup[f + k]) b = g_lvup[f + k + 1];
        }
        return b;
    }
    return 0;
}
void ie1_potencia_tick() {
    static const uint32_t stub[] = {
        0xE92D000Fu,   // stmdb sp!, {r0-r3}
        0xE59F107Cu,   // ldr   r1, =kAnilloPot
        0xE5912000u,   // ldr   r2, [r1]              (contador)
        0xE202301Fu,   // and   r3, r2, #31
        0xE0813283u,   // add   r3, r1, r3, lsl #5    (entradas de 32 bytes)
        0xE2833004u,   // add   r3, r3, #4
        0xE5838000u,   // str   r8, [r3]              jugador
        0xE5837004u,   // str   r7, [r3, #4]          fila
        0xE5830008u,   // str   r0, [r3, #8]          valor
        0xE59DC018u,   // ldr   r12, [sp, #0x18]      3.er argumento (tecnica)
        0xE583C00Cu,   // str   r12, [r3, #12]
        0xE281CB02u,   // add   r12, r1, #0x800       (temporales)
        0xE59C0000u,   // ldr   r0, [r12]             azar
        0xE5830010u,   // str   r0, [r3, #16]
        0xE59C0004u,   // ldr   r0, [r12, #4]         tirada de Critical!
        0xE5830014u,   // str   r0, [r3, #20]
        0xE3E00000u,   // mvn   r0, #0
        0xE58C0000u,   // str   r0, [r12]
        0xE58C0004u,   // str   r0, [r12, #4]
        0xE59D0108u,   // ldr   r0, [sp, #0x108]      rival (2.o argumento de pila)
        0xE5830018u,   // str   r0, [r3, #24]
        0xE59D0100u,   // ldr   r0, [sp, #0x100]      nivel de carga (1.er argumento de pila)
        0xE583001Cu,   // str   r0, [r3, #28]
        0xE59FC028u,   // ldr   r12, =0x020FA1A0      (porcentaje por distancia del tiro)
        0xE1DC00F0u,   // ldrsh r0, [r12]
        0xE202C01Fu,   // and   r12, r2, #31
        0xE081C10Cu,   // add   r12, r1, r12, lsl #2
        0xE28CCC06u,   // add   r12, r12, #0x600      (tabla aparte: anillo + 0x600)
        0xE58C0000u,   // str   r0, [r12]
        0xE2822001u,   // add   r2, r2, #1
        0xE5812000u,   // str   r2, [r1]
        0xE8BD000Fu,   // ldmia sp!, {r0-r3}
        0xE28DD0CCu,   // add   sp, sp, #0xCC         (original)
        0xE8BD8FF0u,   // ldmia sp!, {r4-r11, pc}    (original)
        kAnilloPot,
        0x020FA1A0u};
    static const uint32_t stub_azar[] = {
        0xE59FC008u,   // ldr   r12, =kTempPot
        0xE58C0000u,   // str   r0, [r12]             (el azar que ha salido)
        0xE0855000u,   // add   r5, r5, r0            (original)
        0u,            // b     kGanchoAzar + 4       (se calcula abajo)
        kTempPot};
    static const uint32_t stub_crit[] = {
        0xE59FC008u,   // ldr   r12, =kTempPot + 4
        0xE58C0000u,   // str   r0, [r12]             (tirada 0..99; critico si < 10)
        0xE350000Au,   // cmp   r0, #10               (original)
        0u,            // b     kGanchoCrit + 4
        kTempPot + 4u};
    if (!g_mem) return;
    auto rama = [](uint32_t desde, uint32_t hasta) { return 0xEA000000u | (((hasta - (desde + 8u)) >> 2) & 0x00FFFFFFu); };
    const uint32_t salto = rama(kGanchoPot, kCodigoPot);
    const uint32_t actual = g_mem->r32(kGanchoPot);
    if (actual != 0xE28DD0CCu && actual != salto) return;          // no es el codigo esperado
    if (g_mem->r32(kGanchoPot + 4) != 0xE8BD8FF0u) return;
    auto poner = [&](uint32_t dir, const uint32_t* w, size_t n) {
        for (size_t i = 0; i < n; ++i) if (g_mem->r32(dir + 4u * uint32_t(i)) != w[i]) g_mem->w32(dir + 4u * uint32_t(i), w[i]);
    };
    uint32_t sa[5], sc[5];
    std::memcpy(sa, stub_azar, sizeof sa); sa[3] = rama(kCodigoAzar + 12u, kGanchoAzar + 4u);
    std::memcpy(sc, stub_crit, sizeof sc); sc[3] = rama(kCodigoCrit + 12u, kGanchoCrit + 4u);
    poner(kCodigoPot, stub, sizeof(stub) / 4);
    poner(kCodigoAzar, sa, 5);
    poner(kCodigoCrit, sc, 5);
    // los dos ganchos pequenos (azar y Critical!), tambien tras cargar un estado
    if (g_mem->r32(kGanchoAzar) == 0xE0855000u) g_mem->w32(kGanchoAzar, rama(kGanchoAzar, kCodigoAzar));
    if (g_mem->r32(kGanchoCrit) == 0xE350000Au) g_mem->w32(kGanchoCrit, rama(kGanchoCrit, kCodigoCrit));
    static uint32_t visto = 0;
    if (actual != salto) {
        g_mem->w32(kTempPot, 0xFFFFFFFFu); g_mem->w32(kTempPot + 4, 0xFFFFFFFFu);
        visto = g_mem->r32(kAnilloPot);
        g_mem->w32(kGanchoPot, salto);
        static bool avisado = false;
        if (!avisado) { avisado = true; logf("[valor] registro de valores activo (ganchos en 0x%08X, 0x%08X y 0x%08X)", kGanchoPot, kGanchoAzar, kGanchoCrit); }
        return;
    }
    const uint32_t n = g_mem->r32(kAnilloPot);
    if (n - visto > 32) visto = n - 32;                             // si se acumulan, los 32 ultimos
    for (; visto != n; ++visto) {
        const uint32_t e = kAnilloPot + 4u + 32u * (visto & 31u);
        const uint32_t jug = g_mem->r32(e), fila = g_mem->r32(e + 4), arg = g_mem->r32(e + 12);
        const int32_t valor = int32_t(g_mem->r32(e + 8));
        if (fila == 20) continue;                                   // porteros: siempre 0, sin interes
        char nombre[33] = {};
        if (jug >= 0x02000000u && jug < 0x023F0000u)
            for (int c = 0; c < 32; ++c) {
                const uint8_t ch = g_mem->r8(jug + uint32_t(c));
                if (!ch) break;
                nombre[c] = char(ch >= 0x20 && ch < 0x7F ? ch : '?');
            }
        // estadisticas del jugador (+0xD8): Tiro, Fisico, Control, Defensa, Rapidez, Aguante, Valor
        uint8_t st[7] = {};
        const bool jug_ok = jug >= 0x02000000u && jug < 0x023F0000u;
        if (jug_ok)
            for (int k = 0; k < 7; ++k) st[k] = g_mem->r8(jug + 0xD8u + uint32_t(k));
        // supertecnica: el 3.er argumento apunta a su registro de command.dat en memoria
        int tec = ie1_tecnica_de_registro(arg);
        int poder = 0, bono = 0, usos = -1;
        if (tec > 0) {
            poder = int8_t(g_cmddat[size_t(tec) * 28 + 6]);
            if (jug_ok)
                for (int sl = 0; sl < 6; ++sl)
                    if (g_mem->r16(jug + 0x98u + 2u * uint32_t(sl)) == uint32_t(tec)) { usos = g_mem->r8(jug + 0xA4u + uint32_t(sl)); break; }
            if (usos >= 0) bono = ie1_bono_tecnica(tec, usos);
        }
        // parte fija del calculo (unitcalc.dat): lo que queda hasta el valor es azar y extras
        std::string fijo = "?";
        if (size_t(fila + 1) * 32 <= g_unitcalc.size() && jug_ok) {
            auto c = [&](int k) { return int(int16_t(g_unitcalc[fila * 32 + 2 * k] | g_unitcalc[fila * 32 + 2 * k + 1] << 8)); };
            // columnas 6..12 -> bytes de estadistica 0,1,3,2,4,6,5 (como las funciones del juego)
            static const int kByte[7] = {0, 1, 3, 2, 4, 6, 5};
            long base = long(poder + bono) * c(5);
            for (int k = 0; k < 7; ++k) base += long(st[kByte[k]]) * c(6 + k);
            const int f = int(base * 41 / 4096) + c(1);
            fijo = std::to_string(f) + " (+0.." + std::to_string(c(2)) + ")";
            fijo += ", azar y extras " + std::to_string(valor - f);
        }
        std::string tecs;
        if (tec > 0) {
            tecs = "  " + ent::nombre_tecnica(tec) + " (poder " + std::to_string(poder);
            if (usos >= 0) tecs += " + nivel " + std::to_string(bono) + ", " + std::to_string(usos) + " usos";
            tecs += ")";
        }
        // extras: azar, elemento, carga del tiro, Critical!
        const uint32_t azar = g_mem->r32(e + 16), tirada = g_mem->r32(e + 20), rival = g_mem->r32(e + 24);
        const int32_t carga = int32_t(g_mem->r32(e + 28));
        const bool riv_ok = rival >= 0x02000000u && rival < 0x023F0000u;
        const int el = jug_ok ? g_mem->r8(jug + 0x5Au) : 0, elr = riv_ok ? g_mem->r8(rival + 0x5Au) : 0;
        std::string ext;
        if (azar != 0xFFFFFFFFu) ext += " azar " + std::to_string(int32_t(azar));
        if (tec > 0 && g_cmddat[size_t(tec) * 28 + 8] == el && el) ext += ", tecnica de su elemento +10";
        if (riv_ok && el && elr) {
            if (ie1_gana_elemento(el, elr)) ext += ", ventaja de elemento";
            else if (ie1_gana_elemento(elr, el)) ext += ", desventaja de elemento";
        }
        if (carga > 0 && carga < 10) ext += ", carga del tiro " + std::to_string(carga);
        // tiros: el juego ajusta el valor segun la distancia a la porteria (0x0206FBD0 lo
        // calcula al tirar, 0x0206FDAC lo lee): valor + valor * porcentaje / 100
        if (fila == 4 || fila == 5 || fila == 6 || fila == 9 || fila == 32) {
            const int pct = int(int32_t(g_mem->r32(kAnilloPot + 0x600u + 4u * (visto & 31u))));
            ext += ", distancia " + std::string(pct >= 0 ? "+" : "") + std::to_string(pct) +
                   "% -> llega con " + std::to_string(valor + valor * pct / 100);
        }
        if (tirada != 0xFFFFFFFFu) ext += tirada < 10 ? ", *** CRITICO *** (tirada " + std::to_string(tirada) + ")"
                                                      : ", sin critico (tirada " + std::to_string(tirada) + ")";
        std::string rivs;
        if (riv_ok) {
            char rn[33] = {};
            for (int c = 0; c < 32; ++c) { const uint8_t ch = g_mem->r8(rival + uint32_t(c)); if (!ch) break; rn[c] = char(ch >= 0x20 && ch < 0x7F ? ch : '?'); }
            rivs = std::string("  contra ") + rn + " (" + ie1_elemento(elr) + ")";
        }
        // panel de las escenas: tu equipo son los bloques de la plantilla (0x020E0480...)
        const bool aliado = valorov::aliado(jug);
        {
            int pct = 0;
            if (fila == 4 || fila == 5 || fila == 6 || fila == 9 || fila == 32)
                pct = int(int32_t(g_mem->r32(kAnilloPot + 0x600u + 4u * (visto & 31u))));
            if (ie1_valor_activo()) {
                // registro corto de lo que recibe el panel (siempre: pocas lineas por partido),
                // con la hora para cuadrarlo con las notas de cada tanda
                if (valorov::g_reg_panel && fila != 14 && fila != 15) {
                    const std::time_t ahora = std::time(nullptr);
                    char hora[16] = "?";
                    if (const std::tm* lt = std::localtime(&ahora)) std::strftime(hora, sizeof hora, "%H:%M:%S", lt);
                    logf("[valor] %s fila %u = %d (%s%s) %s", hora, fila, valor, aliado ? "tu equipo" : "rival",
                         azar != 0xFFFFFFFFu ? "" : ", prevision", nombre[0] ? nombre : "?");
                }
                valorov::evento(int(fila), valor, azar != 0xFFFFFFFFu, aliado, pct);
            }
        }
        static const bool registrar = [] { const char* e2 = std::getenv("IE1_POTENCIA"); return e2 && *e2 == '1'; }();
        if (!registrar) continue;
        logf("[valor] %-20s %-26s (fila %2u) = %4d  fijo %s%s  |%s  [%s%s, %s, Ti %u Fi %u Co %u De %u Ra %u Ag %u Va %u, habilidades 0x%X]",
             nombre[0] ? nombre : "?", ie1_fila_valor(fila), fila, valor, fijo.c_str(), tecs.c_str(), ext.c_str(),
             ie1_elemento(el), rivs.c_str(), aliado ? "tu equipo" : "rival", st[0], st[1], st[2], st[3], st[4], st[5], st[6],
             jug_ok ? g_mem->r32(jug + 0xF8u) : 0);
    }
}

// ---- Ojeo instantaneo (de tu ROM hack, MOD003 F30, ampliado) ----------------------
// Las busquedas de Celia (evento 100) y Nelly (evento 200) son temporizadores de una tabla
// de 4 casillas (+0x624 evento, +0x628 fotogramas que faltan, de 8 en 8 bytes):
//  - 0x0209B1EC(tabla, evento, duracion) los registra: si es 100 o 200, duracion = 1;
//  - 0x0209B230(tabla, transcurrido) los descuenta cada fotograma: antes de descontar, a
//    los de 100 o 200 que les quede mas de 1 se les deja en 1. Asi tambien terminan al
//    momento los que ya estaban en marcha (por ejemplo, en una partida guardada).
// El resto de eventos y temporizadores quedan igual. (Mismas direcciones en la ROM inglesa
// y en la espanola.)
// ---- Mod "talentos del IE2" ----------------------------------------------------
// Los talentos son supertecnicas de tipo 9 (command.dat, ids 51..75). Al empezar el
// partido, una funcion del ITCM (IE1 0x01FFA3C4, igual que la del IE2 0x01FFA468) mira
// las 6 tecnicas de cada jugador y, por cada talento, pone un bit en +0xF8 del jugador,
// de sus companeros de una posicion o de todo el equipo (bits 0x1 a 0x1000000). Todo el
// codigo que usa esos bits durante el partido esta en el IE1 (los mismos 24 bits que en
// el IE2). Lo unico que falta: las dos funciones que ponen los bits estan vacias en el IE1:
//   0x0207D6A8  bx lr   (IE2 0x0207ED4C: jugador->+0xF8 |= bits)
//   0x0207D6AC  bx lr   (IE2 0x0207ED70: para cada jugador de una lista, +0xF8 |= bits)
// (en el IE2 ademas solo lo hacen con el modo del IE2 encendido; aqui, siempre con el mod).
// Se cambian por un salto a estas dos funciones, en memoria libre (0x023FA600).
constexpr uint32_t kTalUno = 0x0207D6A8u, kTalLista = 0x0207D6ACu, kTalCodigo = 0x023FA600u;
void ie1_talentos_tick() {
    if (!g_mem) return;
    static const uint32_t codigo[] = {
        // +0x00  uno (r0 partido, r1 jugador, r2 bits)
        0xE59130F8u,   // ldr  r3, [r1, #0xF8]
        0xE1833002u,   // orr  r3, r3, r2
        0xE58130F8u,   // str  r3, [r1, #0xF8]
        0xE12FFF1Eu,   // bx   lr
        // +0x10  lista (r0 partido, r1 lista de jugadores, r2 cuantos, r3 bits)
        0xE3520000u,   // cmp  r2, #0
        0xD12FFF1Eu,   // bxle lr
        0xE491C004u,   // ldr  r12, [r1], #4
        0xE59C00F8u,   // ldr  r0, [r12, #0xF8]
        0xE1800003u,   // orr  r0, r0, r3
        0xE58C00F8u,   // str  r0, [r12, #0xF8]
        0xE2522001u,   // subs r2, r2, #1
        0x1AFFFFF9u,   // bne  (ldr r12)
        0xE12FFF1Eu};  // bx   lr
    auto rama = [](uint32_t desde, uint32_t hasta) { return 0xEA000000u | (((hasta - (desde + 8u)) >> 2) & 0x00FFFFFFu); };
    const uint32_t s1 = rama(kTalUno, kTalCodigo), s2 = rama(kTalLista, kTalCodigo + 0x10u);
    const uint32_t a1 = g_mem->r32(kTalUno), a2 = g_mem->r32(kTalLista);
    if ((a1 != 0xE12FFF1Eu && a1 != s1) || (a2 != 0xE12FFF1Eu && a2 != s2)) return;   // no es el codigo esperado
    if (g_mem->r32(kTalLista + 4u) != 0xE3A00000u) return;                              // (mov r0, #0 de la que borra)
    for (size_t i = 0; i < sizeof(codigo) / 4; ++i)
        if (g_mem->r32(kTalCodigo + 4u * uint32_t(i)) != codigo[i]) g_mem->w32(kTalCodigo + 4u * uint32_t(i), codigo[i]);
    if (a1 != s1) g_mem->w32(kTalUno, s1);
    if (a2 != s2) g_mem->w32(kTalLista, s2);
    static bool avisado = false;
    if (!avisado) { avisado = true; logf("[mods] talentos: activos (saltos en 0x%08X y 0x%08X)", kTalUno, kTalLista); }
}

// ---- Mod "tiro del IE2": boton T de tiro y tiro largo --------------------------
// El IE1 ya tiene, sin usar, todo el codigo del boton T del IE2 (boton tactil 17,
// que se puede arrastrar; al tocarlo el juego hace como si se tocara la porteria) y
// del tiro largo. Los dos dependen de la funcion 0x0206D9A0:
//     partido+0x11918 != 0  y  (partido+0x21A & 8)
// El IE2 pone partido+0x119E4 (su equivalente de +0x11918) a 1 al empezar el partido
// (0x020717F4, desde el overlay 15); el IE1 solo lo pone a 0 (0x02062258) y nunca a 1.
// Con el mod (tiro.cfg) se hace lo mismo que IE1_TIRO_T=2: +0x11918 = 1 y bit 8 de
// +0x21A encendido, en cada fotograma de partido (solo partidos: en las pachangas no) (son datos del partido en curso: no
// se guardan en la partida, asi que quitar el mod no deja nada). Pruebas:
// IE1_TIRO_T=1 solo +0x11918; IE1_TIRO_T=2 los dos y apunta en el registro cada
// cambio de esos valores.
constexpr uint32_t kPartido = 0x020E88A0u;
void ie1_tiro_t_tick() {
    if (!g_mem) return;
    // solo en los partidos: overlay 15 cargado (mismas instrucciones que la prueba 2)
    if (g_mem->r32(0x02155B34u) != 0xEBFC2588u || g_mem->r32(0x02155B3Cu) != 0xE2800001u) return;
    static const int env = [] { const char* e = std::getenv("IE1_TIRO_T"); return (e && *e >= '0' && *e <= '9') ? *e - '0' : 0; }();
    const int modo = env ? env : 2;
    const uint32_t a_modo = kPartido + 0x11918u, a_reglas = kPartido + 0x21Au;
    // Solo en los partidos de verdad, no en las pachangas. El partido copia su ficha de
    // games.dat en +0x1FC: +0x20C son sus banderas y +0x21A sus reglas. En el games.dat
    // del IE2 el bit 8 de las reglas (boton T y tiro largo) esta justo en los partidos con
    // la bandera 0x80 (partido) y sin la 0x100 (la llevan las pachangas, 0x121 y 0x1A1).
    // En una pachanga se apaga, por si venia encendido del partido anterior (ninguna ficha
    // del IE1 con 0x100 trae el bit 8 de serie, asi que no se quita nada del juego).
    const uint16_t banderas = g_mem->r16(kPartido + 0x20Cu);
    const bool partido = (banderas & 0x80u) && !(banderas & 0x100u);
    if (!partido) {
        if (g_mem->r32(a_modo) != 0u) g_mem->w32(a_modo, 0u);
        const uint16_t r = g_mem->r16(a_reglas);
        if (r & 8u) g_mem->w16(a_reglas, uint16_t(r & ~8u));
    } else {
        if (modo >= 1 && g_mem->r32(a_modo) != 1u) g_mem->w32(a_modo, 1u);
        if (modo >= 2) {
            const uint16_t r = g_mem->r16(a_reglas);
            if (!(r & 8u)) g_mem->w16(a_reglas, uint16_t(r | 8u));
        }
    }
    const uint32_t v_modo = g_mem->r32(a_modo);
    const uint16_t v_reglas = g_mem->r16(a_reglas);
    const uint8_t largo = g_mem->r8(kPartido + 0x11902u), cont = g_mem->r8(kPartido + 0x11903u), carga = g_mem->r8(kPartido + 0x11904u);
    static uint32_t ult[5] = {0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu};
    const uint32_t ahora[5] = {v_modo, v_reglas, largo, cont, carga};
    if (!env || std::memcmp(ult, ahora, sizeof ult) == 0) return;
    std::memcpy(ult, ahora, sizeof ult);
    logf("[mods] tiro T: %s (banderas 0x%04X) +0x11918=%u +0x21A=0x%04X (bit8 %s) tiro largo=%u contador=%u carga=%u",
         partido ? "partido" : "pachanga", banderas, v_modo, v_reglas, (v_reglas & 8u) ? "si" : "no", largo, cont, carga);
}

void ie1_ojeo_tick() {
    if (!g_mem) return;
    auto rama = [](uint32_t desde, uint32_t hasta) { return 0xEA000000u | (((hasta - (desde + 8u)) >> 2) & 0x00FFFFFFu); };
    auto poner = [&](uint32_t dir, const uint32_t* w, size_t n) {
        for (size_t i = 0; i < n; ++i) if (g_mem->r32(dir + 4u * uint32_t(i)) != w[i]) g_mem->w32(dir + 4u * uint32_t(i), w[i]);
    };
    // 1) al registrar
    constexpr uint32_t kReg = 0x0209B1ECu, kRegCod = 0x023FCC00u, kRegOrig = 0xE92D4008u;
    const uint32_t reg[] = {
        0xE3510064u,                       // cmp   r1, #100      (busqueda de Celia)
        0x0A000001u,                       // beq   duracion
        0xE35100C8u,                       // cmp   r1, #200      (busqueda de Nelly)
        0x1A000001u,                       // bne   seguir
        0xE3520001u,                       // duracion: cmp r2, #1
        0xC3A02001u,                       // movgt r2, #1        (termina al momento)
        kRegOrig,                          // seguir: stmdb sp!, {r3, lr}   (original)
        rama(kRegCod + 28u, kReg + 4u),    // b     0x0209B1F0
    };
    // 2) al descontar (cada fotograma)
    constexpr uint32_t kDes = 0x0209B230u, kDesCod = 0x023FCC40u, kDesOrig = 0xE2802C06u;
    const uint32_t des[] = {
        0xE3A0C000u,                       // mov   r12, #0
        0xE080318Cu,                       // casilla: add r3, r0, r12, lsl #3
        0xE5932624u,                       // ldr   r2, [r3, #0x624]   (evento)
        0xE3520064u,                       // cmp   r2, #100
        0x135200C8u,                       // cmpne r2, #200
        0x1A000003u,                       // bne   siguiente
        0xE5932628u,                       // ldr   r2, [r3, #0x628]   (lo que falta)
        0xE3520001u,                       // cmp   r2, #1
        0xC3A02001u,                       // movgt r2, #1
        0xC5832628u,                       // strgt r2, [r3, #0x628]
        0xE28CC001u,                       // siguiente: add r12, r12, #1
        0xE35C0004u,                       // cmp   r12, #4
        0xBAFFFFF3u,                       // blt   casilla
        kDesOrig,                          // add   r2, r0, #0x600     (original)
        rama(kDesCod + 56u, kDes + 4u),    // b     0x0209B234
    };
    const uint32_t a1 = g_mem->r32(kReg), s1 = rama(kReg, kRegCod);
    const uint32_t a2 = g_mem->r32(kDes), s2 = rama(kDes, kDesCod);
    if ((a1 != kRegOrig && a1 != s1) || (a2 != kDesOrig && a2 != s2)) return;   // no es el codigo esperado
    poner(kRegCod, reg, sizeof(reg) / 4);
    poner(kDesCod, des, sizeof(des) / 4);
    if (a1 != s1) g_mem->w32(kReg, s1);
    if (a2 != s2) g_mem->w32(kDes, s2);
    static bool avisado = false;
    if (!avisado && (a1 != s1 || a2 != s2)) {
        avisado = true;
        logf("[mods] ojeo instantaneo: ganchos en 0x%08X (registrar) y 0x%08X (descontar)", kReg, kDes);
    }
}

// ---- Modo traza (IE1_TRAZA=1) --------------------------------------------------------
// Apunta lo que hace el juego: los guiones de eventos que se ejecutan (instruccion a
// instruccion, con sus datos), los temporizadores de eventos y su fin. Lo muestra en una
// ventana de consola y lo escribe en run/traza_FECHA.txt (y en el registro).
//  - Hilos de guion: 4, en 0x02195000 + 0x3C0*n; +0x2B0 = instruccion actual (entrada
//    decodificada: +0 puntero a la instruccion en el guion cargado).
//  - Instruccion: +0 numero (u16), +4 codigo (u16), +6 numero de datos, +8 tipos (4 bits),
//    despues los datos (u32).
//  - Guion cargado: empieza por "SSD\0"; se identifica comparando sus primeros bytes con
//    los guiones del paquete script/eve (ya con los mods).
//  - Temporizadores de eventos: tabla 0x020D3D20, 4 casillas (+0x624 evento, +0x628 resta).
namespace traza {
std::map<uint64_t, uint32_t> g_guiones;        // huella -> numero de guion
FILE* g_txt = nullptr;
#ifdef _WIN32
HANDLE g_con = INVALID_HANDLE_VALUE;
#endif
uint32_t g_fot = 0;
uint32_t g_tabla_vars = 0;                     // tabla de variables 65536+ (si ya se conoce)
bool g_volcar = false;                         // volcar la tabla completa en este fotograma
std::map<uint32_t, std::vector<uint32_t>> g_candidatos_vigilar;   // variable -> sitios posibles
void escribir(const char* fmt, ...) {
    char b[1024];
    va_list ap; va_start(ap, fmt); vsnprintf(b, sizeof b, fmt, ap); va_end(ap);
    char l[1100];
    snprintf(l, sizeof l, "f%07u %s", g_fot, b);
    if (g_txt) { std::fputs(l, g_txt); std::fputc('\n', g_txt); std::fflush(g_txt); }
#ifdef _WIN32
    if (g_con != INVALID_HANDLE_VALUE) {
        DWORD w; WriteConsoleA(g_con, l, DWORD(std::strlen(l)), &w, nullptr); WriteConsoleA(g_con, "\r\n", 2, &w, nullptr);
    }
#endif
}
void abrir() {
    static bool hecho = false;
    if (hecho) return;
    hecho = true;
    char nom[64];
    std::time_t t = std::time(nullptr);
    std::strftime(nom, sizeof nom, "traza_%Y%m%d-%H%M%S.txt", std::localtime(&t));
    g_txt = std::fopen(nom, "w");
#ifdef _WIN32
    if (AllocConsole()) {
        SetConsoleTitleA("Inazuma Eleven - traza");
        g_con = CreateFileA("CONOUT$", GENERIC_WRITE, FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
    }
#endif
    logf("[traza] modo traza activo: %s (%zu guiones conocidos)", nom, g_guiones.size());
    escribir("traza de Inazuma Eleven: guiones de eventos y temporizadores (f = fotograma)");
}
// Al cargar un guion, el juego cambia los textos de las instrucciones por punteros; lo
// demas no cambia. Huella: codigos y datos de todas las instrucciones, sin los textos
// (tipo 3). Distingue 1620 de los 1737 guiones; los que coinciden son copias identicas.
template <class R16, class R8, class R32> uint64_t huella(R16 r16, R8 r8, R32 r32, uint32_t n, size_t tam) {
    uint64_t h = 1469598103934665603ull;
    auto mez = [&](uint32_t v) { for (int i = 0; i < 4; ++i) { h ^= (v >> (8 * i)) & 0xFF; h *= 1099511628211ull; } };
    size_t o = 0x20;
    for (uint32_t k = 0; k < n && o + 4 <= tam; ++k) {
        const uint32_t sz = r16(o + 2);
        if (!sz) { mez(0xFFFFFFFFu); o += 4; continue; }
        if (sz < 8 || sz > 0x400) break;
        const uint32_t op = r16(o + 4), argc = r8(o + 6);
        mez(op);
        const size_t off0 = 8 + ((argc + 1) / 2 + 3) / 4 * 4;
        for (uint32_t i = 0; i < argc; ++i) {
            const uint8_t tb = r8(o + 8 + i / 2);
            const uint32_t tipo = (i & 1) ? (tb >> 4) : (tb & 15);
            mez(tipo == 3 ? 0xFFFFFFFEu : r32(o + off0 + 4 * i));
        }
        o += sz;
    }
    return h;
}
}  // namespace traza

void ie1_traza_preparar(const std::vector<uint8_t>& h, const std::vector<uint8_t>& b) {
    if (h.size() < 0x30) return;
    auto r32 = [&](size_t o) { return uint32_t(h[o] | h[o + 1] << 8 | h[o + 2] << 16 | uint32_t(h[o + 3]) << 24); };
    const uint32_t n = h[0x16] | h[0x17] << 8;
    for (uint32_t k = 0; k < n && 0x30 + 12 * size_t(k) + 12 <= h.size(); ++k) {
        const uint32_t id = r32(0x30 + 12 * k), of = r32(0x34 + 12 * k), sz = r32(0x38 + 12 * k);
        if (size_t(of) + sz > b.size()) continue;
        std::vector<uint8_t> c(b.begin() + of, b.begin() + of + sz);
        std::vector<uint8_t> d = ent::lz10(c);
        if (d.size() >= 0x20 && std::memcmp(d.data(), "SSD", 3) == 0) {
            auto r16 = [&](size_t o) { return o + 2 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8) : 0u; };
            auto r8 = [&](size_t o) { return o < d.size() ? uint32_t(d[o]) : 0u; };
            auto r32 = [&](size_t o) { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0u; };
            traza::g_guiones[traza::huella(r16, r8, r32, r16(0x0C), d.size())] = id;
        }
    }
}

void ie1_traza_tick() {
    using namespace traza;
    if (!g_mem) return;
    abrir();
    ++g_fot;
    // 0) foto de toda la RAM (4 MB) para localizar las variables: cuando un guion escribe
    //    una variable (0x7001 con dato de tipo 6), se buscan los bytes que han cambiado a
    //    ese valor desde el fotograma anterior
    static std::vector<uint8_t> foto_ant, foto;
    struct Escritura { uint32_t var, valor; };
    std::vector<Escritura> escrituras;
    // la instruccion que se ve es la que va a ejecutarse: su efecto aparece en el fotograma
    // siguiente. Por eso se compara la foto de ahora con la de antes de verla.
    static std::vector<Escritura> pendientes;
    static std::vector<uint8_t> foto_previa;
    const bool rapida = g_mem->version >= 2 && g_mem->copiar;
    if (rapida) {
        foto.resize(0x400000);
        g_mem->copiar(0x02000000u, foto.data(), 0x400000u);
    }
    // 1) hilos de guion
    static uint32_t ultimo[4] = {0, 0, 0, 0};          // instruccion (direccion) vista por hilo
    static uint32_t base_ant[4] = {0, 0, 0, 0};
    static std::map<uint32_t, uint32_t> id_de_base;    // direccion del guion cargado -> numero
    for (uint32_t t = 0; t < 4; ++t) {
        const uint32_t hilo = 0x02195000u + 0x3C0u * t;
        const uint32_t ent_ = g_mem->r32(hilo + 0x2B0u);
        if (ent_ < 0x02000000u || ent_ >= 0x023F0000u) { ultimo[t] = 0; continue; }
        const uint32_t ins = g_mem->r32(ent_);
        if (ins < 0x02000000u || ins >= 0x023F0000u || ins == ultimo[t]) continue;
        ultimo[t] = ins;
        // guion al que pertenece: hacia atras hasta "SSD\0"
        uint32_t base = 0;
        for (uint32_t a = ins & ~3u; a + 0x40000u > ins && a >= 0x02000000u; a -= 4)
            if (g_mem->r32(a) == 0x00445353u) { base = a; break; }
        uint32_t gid = 0;
        if (base) {
            auto it = id_de_base.find(base);
            if (it != id_de_base.end()) gid = it->second;
            else {
                auto r16 = [&](size_t o) { return uint32_t(g_mem->r16(base + uint32_t(o))); };
                auto r8 = [&](size_t o) { return uint32_t(g_mem->r8(base + uint32_t(o))); };
                auto r32 = [&](size_t o) { return g_mem->r32(base + uint32_t(o)); };
                auto g = g_guiones.find(huella(r16, r8, r32, r16(0x0C), 0x40000));
                gid = g != g_guiones.end() ? g->second : 0;
                id_de_base[base] = gid;
            }
        }
        if (base != base_ant[t]) {
            base_ant[t] = base;
            escribir("hilo %u: guion %#x (cargado en %08X)", t, gid, base);
            if (t == 0) g_volcar = true;
        }
        const uint32_t num = g_mem->r16(ins), op = g_mem->r16(ins + 4), n = g_mem->r8(ins + 6);
        char datos[512] = {};
        size_t p = 0;
        const uint32_t off0 = 8 + ((n + 1) / 2 + 3) / 4 * 4;
        for (uint32_t k = 0; k < n && k < 8; ++k) {
            const uint8_t tb = g_mem->r8(ins + 8 + k / 2);
            const uint32_t tipo = (k & 1) ? (tb >> 4) : (tb & 15);
            const uint32_t v = g_mem->r32(ins + off0 + 4 * k);
            p += size_t(snprintf(datos + p, sizeof datos - p, " (%u,%d)", tipo, int32_t(v)));
            if (p >= sizeof datos - 24) break;
        }
        escribir("hilo %u  guion %#x  instr %4u  op %04X%s", t, gid, num, op, datos);
        // momentos clave: ventanas de busqueda/lista, encargo, comprobacion de marcas
        if (g_tabla_vars && (op == 0x2004 || op == 0x2005 || op == 0x2008 || op == 0x4079 || op == 0x700F)) g_volcar = true;
        if (op == 0x7001 && n == 2) {                      // variable = valor
            const uint8_t tb = g_mem->r8(ins + 8);
            if ((tb & 15) == 6 && (tb >> 4) == 1)
                escrituras.push_back({g_mem->r32(ins + off0), g_mem->r32(ins + off0 + 4)});
            // El interprete (0x0215F740) resuelve la variable en la entrada decodificada de
            // la instruccion: +0x0C = direccion donde escribe, +0x10 = valor. Se apunta.
            const uint32_t var = g_mem->r32(ins + off0), dir = g_mem->r32(ent_ + 0x0Cu);
            if ((tb & 15) == 6 && dir >= 0x02000000u && dir < 0x023F0000u) {
                escribir("   -> la variable %u esta en %08X", var, dir);
                if (var >= 65536u && var < 65536u + 1024u) {
                    const uint32_t base = dir - 4u * (var - 65536u);
                    if (base != g_tabla_vars) {
                        g_tabla_vars = base;
                        escribir("tabla de variables 65536+ en %08X", base);
                    }
                }
            }
        }
    }
    std::swap(escrituras, pendientes);                    // se evaluan las del fotograma anterior
    if (rapida && foto_previa.size() == foto.size()) {
        // candidatos: palabras de 4 bytes (alineadas) que cambian y pasan a valer el valor
        // escrito; por cada variable se cruzan con los de sus escrituras anteriores
        static std::map<uint32_t, std::vector<uint32_t>> cand_var;
        for (const Escritura& e : escrituras) {
            std::vector<uint32_t> c;
            for (uint32_t o = 0; o + 4 <= 0x400000u; o += 4) {
                uint32_t a, b;
                std::memcpy(&a, &foto[o], 4); std::memcpy(&b, &foto_previa[o], 4);
                if (a != b && a == e.valor) c.push_back(0x02000000u + o);
            }
            auto it = cand_var.find(e.var);
            if (it == cand_var.end()) cand_var[e.var] = c;
            else {
                std::vector<uint32_t> x;
                std::set_intersection(it->second.begin(), it->second.end(), c.begin(), c.end(), std::back_inserter(x));
                if (!x.empty()) it->second = x;       // si no coincide ninguno, se queda lo anterior
            }
            const auto& v = cand_var[e.var];
            (void)g_candidatos_vigilar;   // vigilancia de candidatos desactivada: la direccion se lee del interprete
            std::string t;
            for (size_t i = 0; i < v.size() && i < 16; ++i) { char b[16]; snprintf(b, sizeof b, " %08X", v[i]); t += b; }
            escribir("variable %u = %u: %zu sitio(s) posibles:%s%s", e.var, e.valor, v.size(), t.c_str(), v.size() > 16 ? " ..." : "");
            // con un unico sitio para una variable 655xx, se deduce la tabla de variables
            // (4 bytes por variable desde la 65536) y quien apunta a ella
            if (v.size() == 1 && e.var >= 65536u && e.var < 65536u + 256u) {
                const uint32_t base = v[0] - 4u * (e.var - 65536u);
                if (base != g_tabla_vars) {
                    g_tabla_vars = base;
                    std::string pt;
                    int n = 0;
                    for (uint32_t o = 0; o + 4 <= 0x400000u && n < 8; o += 4) {
                        uint32_t w; std::memcpy(&w, &foto[o], 4);
                        if (w >= base - 0x40u && w <= base) { char b[40]; snprintf(b, sizeof b, " %08X(=%08X)", 0x02000000u + o, w); pt += b; ++n; }
                    }
                    escribir("tabla de variables 65536+ en %08X; punteros a ella:%s", base, pt.empty() ? " ninguno" : pt.c_str());
                }
            }
        }
    }
    // candidatos vigilados: los sitios posibles de cada variable 655xx se miran en cada
    // fotograma y se apunta cualquier cambio (para ver cuando y a que valor cambian)
    {
        static std::map<uint32_t, uint32_t> vistos;       // direccion -> ultimo valor
        for (auto& kv : g_candidatos_vigilar) {
            for (uint32_t a : kv.second) {
                const uint32_t v = g_mem->r32(a);
                auto it = vistos.find(a);
                if (it == vistos.end()) vistos[a] = v;
                else if (it->second != v) {
                    escribir("candidato de la variable %u en %08X: %u -> %u", kv.first, a, it->second, v);
                    it->second = v;
                }
            }
        }
    }
    // tabla completa (65536..65599) en los momentos clave y al descubrirla
    {
        static uint32_t tabla_volcada = 0;
        if (g_tabla_vars && (g_volcar || tabla_volcada != g_tabla_vars)) {
            tabla_volcada = g_tabla_vars;
            g_volcar = false;
            std::string t;
            for (uint32_t k = 0; k < 64; ++k) {
                char b[24]; snprintf(b, sizeof b, " %u=%u", 65536u + k, g_mem->r32(g_tabla_vars + 4u * k)); t += b;
            }
            escribir("tabla:%s", t.c_str());
        }
    }
    // variables 65536..65599 vigiladas (cuando ya se conoce su tabla)
    if (g_tabla_vars) {
        static uint32_t vars_ant[64];
        static uint32_t tabla_ant = 0;
        for (uint32_t k = 0; k < 64; ++k) {
            const uint32_t v = g_mem->r32(g_tabla_vars + 4u * k);
            if (tabla_ant == g_tabla_vars && v != vars_ant[k])
                escribir("var %u: %u -> %u", 65536u + k, vars_ant[k], v);
            vars_ant[k] = v;
        }
        tabla_ant = g_tabla_vars;
    }
    if (rapida) { foto_previa = foto_ant; foto_ant.swap(foto); }   // foto_previa: la de antes de ver las instrucciones
    // 2) memoria vigilada: datos de la partida justo antes de la plantilla (0x020E0000-
    //    0x020E0480, donde estan las variables de los guiones) y el registro de busqueda
    //    alrededor de los temporizadores (0x020D4300-0x020D4400). Se apuntan los cambios.
    {
        struct Zona { uint32_t ini, fin; };
        static const Zona zonas[] = {{0x020E0000u, 0x020E0480u}, {0x020D4300u, 0x020D4400u}};
        static std::vector<uint8_t> antes;
        size_t total = 0;
        for (const Zona& z : zonas) total += z.fin - z.ini;
        std::vector<uint8_t> ahora(total);
        size_t p = 0;
        for (const Zona& z : zonas) for (uint32_t a = z.ini; a < z.fin; ++a) ahora[p++] = g_mem->r8(a);
        if (antes.size() == total) {
            p = 0;
            int n = 0;
            for (const Zona& z : zonas)
                for (uint32_t a = z.ini; a < z.fin; ++a, ++p)
                    if (ahora[p] != antes[p] && n < 24) {
                        static std::map<uint32_t, int> veces;      // contadores (tiempo de juego...) fuera
                        const int v = ++veces[a];
                        if (v <= 20) escribir("memoria %08X: %02X -> %02X", a, antes[p], ahora[p]);
                        else if (v == 21) escribir("memoria %08X: cambia continuamente, deja de apuntarse", a);
                        ++n;
                    }
        }
        antes.swap(ahora);
    }
    // 3) temporizadores de eventos
    static uint32_t tid[4] = {0, 0, 0, 0}, tval[4] = {0, 0, 0, 0};
    for (uint32_t k = 0; k < 4; ++k) {
        const uint32_t id = g_mem->r32(0x020D3D20u + 0x624u + 8u * k), v = g_mem->r32(0x020D3D20u + 0x628u + 8u * k);
        if (id != tid[k] || (v == 0) != (tval[k] == 0)) {
            if (v && (id != tid[k] || !tval[k])) escribir("temporizador %u: evento %u registrado, %u fotogramas", k, id, v);
            else if (!v && tval[k]) escribir("temporizador %u: evento %u TERMINADO", k, tid[k]);
        }
        tid[k] = id; tval[k] = v;
    }
}

// ---- Filtros de los cuadernos de supertecnicas (Inventario > Supertecnicas > Aprender) ----
// El menu es el objeto del overlay 48 (tabla de funciones 0x0216F078; modo en +0x10, 3 =
// "Cuadernos secretos"). Su lista se crea en 0x02168BFC: pide los cuadernos con
// 0x0207697C (r0 = cuantos, r5 = numeros de objeto u16), los ordena por la lista de orden
// de los objetos (+0x205C, cuantos en +0x2060) y crea las fichas (tecnica, cantidad, objeto).
//  - Gancho F (0x02168C3C, justo despues de pedir los cuadernos): quita los que no pasan el
//    filtro y, si hay orden propio, los ordena por una tabla de puestos (0x023FC000, u16 por
//    objeto; 0xFFFF = fuera). Con orden propio, el orden del juego se anula (0x02168C4C:
//    numero de la lista de orden = 0).
//  - Gancho U (metodo 6 del objeto, cada fotograma): apunta el objeto y, si se lo piden,
//    vuelve a montar la ventana (0x0216B2B8) para que se vea la lista nueva.
// Boton X (o tocar el boton "Filtros", donde el juego tiene "Opciones" apagado): ventana
// con Tipo, Afinidad y Orden, dibujada con el estilo de la ventana de los cuadernos.
namespace filtros {
constexpr uint32_t kVtabla = 0x0216F078u, kVtabla0 = 0x0216EACCu, kMetodo6 = 0x0216F090u, kOrig6 = 0x0216E504u;
constexpr uint32_t kGanchoF = 0x02168C3Cu, kOrigF = 0xE1A08000u;      // mov r8, r0
constexpr uint32_t kOrden = 0x02168C4Cu, kOrigOrden = 0xE1D106B0u, kSinOrden = 0xE3A00000u;
constexpr uint32_t kStubF = 0x023FC800u, kStubU = 0x023FC900u, kPuestos = 0x023FC000u;
constexpr uint32_t kObj = 0x023FCA00u, kRefrescar = 0x023FCA04u, kActivo = 0x023FCA08u;
const uint32_t kCodF[] = {
    0xE59FC0D8u, 0xE59CC000u, 0xE35C0000u, 0x0A000030u, 0xE92D40DEu, 0xE59F30C8u, 0xE3A01000u, 0xE3A02000u,
    0xE1510000u, 0xAA00000Du, 0xE0854081u, 0xE1D460B0u, 0xE3560B01u, 0x2A000007u, 0xE0834086u, 0xE1D470B0u,
    0xE59F40A0u, 0xE1570004u, 0x0A000002u, 0xE0854082u, 0xE1C460B0u, 0xE2822001u, 0xE2811001u, 0xEAFFFFEFu,
    0xE1A00002u, 0xE59FC074u, 0xE59CC000u, 0xE31C0002u, 0x0A000016u, 0xE3A01001u, 0xE1510000u, 0xAA000013u,
    0xE0854081u, 0xE1D460B0u, 0xE0834086u, 0xE1D470B0u, 0xE2412001u, 0xE3520000u, 0xBA000008u, 0xE0854082u,
    0xE1D4C0B0u, 0xE083E08Cu, 0xE1DEE0B0u, 0xE15E0007u, 0x9A000002u, 0xE1C4C0B2u, 0xE2422001u, 0xEAFFFFF4u,
    0xE0854082u, 0xE1C460B2u, 0xE2811001u, 0xEAFFFFE9u, 0xE8BD40DEu, 0xE1A08000u, 0xE59FC00Cu, 0xE12FFF1Cu,
    0x023FCA08u, 0x023FC000u, 0x0000FFFFu, 0x02168C40u};
const uint32_t kCodU[] = {
    0xE92D401Fu, 0xE1A04000u, 0xE59FC03Cu, 0xE58C0000u, 0xE59FC038u, 0xE59C1000u, 0xE3510000u, 0x0A000007u,
    0xE3A01000u, 0xE58C1000u, 0xE5941010u, 0xE3510003u, 0x1A000002u, 0xE1A00004u, 0xE59FC014u, 0xE12FFF3Cu,
    0xE8BD401Fu, 0xE59FC00Cu, 0xE12FFF1Cu, 0x023FCA00u, 0x023FCA04u, 0x0216B2B8u, 0x0216E504u};
// botones de la barra de abajo (coordenadas DS)
// (el boton X ocupa el hueco de "Y Opciones": 56 x 24 en 152,168)
constexpr int kAx0 = 104, kAx1 = 151, kBx0 = 208, kBx1 = 255, kXx0 = 152, kXx1 = 207, kBy0 = 168, kBy1 = 191;
// filas de la ventana de los cuadernos
constexpr int kVx0 = 53, kVx1 = 202, kFila0 = 32, kAltoFila = 16;

bool abierto = false;
int tipo = 0, afin = 0, orden = 0;               // filtro aplicado
int e_tipo = 0, e_afin = 0, e_orden = 0, fila = 0; // en edicion
uint16_t prev_vig = 0, prev = 0;
bool toque_prev = false, toque_vig_prev = false;
std::vector<uint32_t> g_salida;
const int kTipos[] = {0, 7, 5, 6, 8, 9};         // todos, tiro, regate, bloqueo, parada, talento

bool es() { return g_idioma_textos == "es"; }
const char* L5(const char* en, const char* es_, const char* fr, const char* de, const char* it) { return T5(en, es_, fr, de, it); }
uint32_t r32(uint32_t a) { return g_mem ? g_mem->r32(a) : 0; }
void w32(uint32_t a, uint32_t v) { if (g_mem && g_mem->r32(a) != v) g_mem->w32(a, v); }
bool hay_menu() { return g_mod_filtros && g_mem && r32(kVtabla) == kVtabla0; }
uint32_t objeto() {
    const uint32_t o = r32(kObj);
    return (o >= 0x02000000u && o < 0x023F0000u && r32(o) == kVtabla) ? o : 0;
}
bool en_cuadernos() { const uint32_t o = hay_menu() ? objeto() : 0; return o && r32(o + 0x10) == 3; }
bool hay_filtro() { return tipo || afin || orden; }

const char* nombre_tipo(int i) {
    static const char* k[5][6] = {
        {"All", "Shoot", "Dribble", "Block", "Catch", "Skill"},
        {"Todas", "Tiro", "Regate", "Defensa", "Atajo", "Talento"},
        {"Toutes", "Tir", "Dribble", "Défense", "Arrêt", "Talent"},
        {"Alle", "Schuss", "Dribbling", "Abwehr", "Parade", "Talent"},
        {"Tutte", "Tiro", "Dribbling", "Difesa", "Parata", "Abilità"}};
    return k[idioma_indice()][i];
}
const char* nombre_afin(int i) {
    static const char* k[5][5] = {
        {"All", "Wind", "Wood", "Fire", "Earth"},
        {"Todas", "Aire", "Bosque", "Fuego", "Montaña"},
        {"Toutes", "Air", "Bois", "Feu", "Terre"},
        {"Alle", "Wind", "Holz", "Feuer", "Erde"},
        {"Tutte", "Aria", "Bosco", "Fuoco", "Terra"}};
    return k[idioma_indice()][i];
}
constexpr int kOrdenes = 5;                       // normal, PT de mas a menos, PT de menos a mas, A-Z, Z-A

int tecnica_de(int objeto_id) {
    if (objeto_id <= 0 || size_t(objeto_id + 1) * 48 > g_itemdat.size()) return 0;
    const size_t o = size_t(objeto_id) * 48 + 0x22;
    return g_itemdat[o] | g_itemdat[o + 1] << 8;
}
int pt_de(int t) { return (t > 0 && size_t(t + 1) * 28 <= g_cmddat.size()) ? g_cmddat[size_t(t) * 28 + 4] : 0; }

// puesto de cada tecnica por nombre (en el idioma de los textos)
const std::vector<uint16_t>& puestos_nombre() {
    static std::vector<uint16_t> p;
    if (!p.empty() || g_cmddat.empty()) return p;
    const int n = int(g_cmddat.size() / 28);
    std::vector<std::pair<std::string, int>> v;
    for (int t = 1; t < n; ++t) {
        std::string k = ent::nombre_tecnica(t);
        for (char& c : k) if (c >= 'A' && c <= 'Z') c = char(c - 'A' + 'a');
        v.push_back({k, t});
    }
    std::stable_sort(v.begin(), v.end());
    p.assign(size_t(n), 0xFFFE);
    for (size_t i = 0; i < v.size(); ++i) p[size_t(v[i].second)] = uint16_t(i);
    return p;
}

void aplicar() {
    if (!g_mem) return;
    const auto& pn = puestos_nombre();
    for (int obj = 0; obj < 1024; ++obj) {
        uint32_t puesto = 0;
        const int t = tecnica_de(obj);
        if (t > 0) {
            if (tipo && ent::tipo_tecnica(t) != kTipos[tipo]) puesto = 0xFFFF;
            else if (afin && ent::elemento_tecnica(t) != afin) puesto = 0xFFFF;
            else if (orden == 1) puesto = uint32_t(0x1000 - pt_de(t));
            else if (orden == 2) puesto = uint32_t(pt_de(t));
            else if (orden == 3) puesto = size_t(t) < pn.size() ? pn[size_t(t)] : 0xFFFEu;
            else if (orden == 4) puesto = size_t(t) < pn.size() && pn[size_t(t)] < 0xF000u ? 0xF000u - pn[size_t(t)] : 0xFFFEu;
        }
        const uint32_t a = kPuestos + 2u * uint32_t(obj);
        if (g_mem->r16(a) != puesto) g_mem->w16(a, uint16_t(puesto));
    }
    w32(kActivo, hay_filtro() ? (orden ? 3u : 1u) : 0u);
    w32(kRefrescar, 1);
    logf("[filtros] tipo %d, afinidad %d, orden %d (0 normal, 1 PT-, 2 PT+, 3 A-Z, 4 Z-A)", tipo, afin, orden);
}

void tick() {
    if (!hay_menu()) { if (abierto) abierto = false; return; }
    for (size_t i = 0; i < sizeof(kCodF) / 4; ++i) w32(kStubF + 4u * uint32_t(i), kCodF[i]);
    for (size_t i = 0; i < sizeof(kCodU) / 4; ++i) w32(kStubU + 4u * uint32_t(i), kCodU[i]);
    static bool avisado = false;
    const uint32_t salto = 0xEA000000u | (((kStubF - (kGanchoF + 8u)) >> 2) & 0x00FFFFFFu);
    const uint32_t m6 = r32(kMetodo6), gf = r32(kGanchoF), go = r32(kOrden);
    if (m6 != kOrig6 && m6 != kStubU) return;                 // no es el codigo esperado
    if (gf != kOrigF && gf != salto) return;
    if (go != kOrigOrden && go != kSinOrden) return;
    w32(kMetodo6, kStubU);
    w32(kGanchoF, salto);
    w32(kOrden, orden ? kSinOrden : kOrigOrden);
    if (!avisado) { avisado = true; logf("[filtros] ganchos del menu de supertecnicas en 0x%08X y 0x%08X", kGanchoF, kMetodo6); }
    if (abierto && !en_cuadernos()) abierto = false;
}

void abrir() {
    abierto = true;
    e_tipo = tipo; e_afin = afin; e_orden = orden; fila = 0;
    prev = 0xFFFF; toque_prev = true;
}
void cerrar(bool guardar) {
    abierto = false;
    if (guardar && (e_tipo != tipo || e_afin != afin || e_orden != orden)) {
        tipo = e_tipo; afin = e_afin; orden = e_orden;
        aplicar();
    }
}
void cambiar(int f, int d) {
    if (f == 0) e_tipo = (e_tipo + d + 6) % 6;
    else if (f == 1) e_afin = (e_afin + d + 5) % 5;
    else if (f == 2) e_orden = (e_orden + d + kOrdenes) % kOrdenes;
    else if (f == 3) { e_tipo = e_afin = e_orden = 0; }
}

int vigilar_teclas(uint16_t pulsados) {
    const uint16_t nuevos = uint16_t(pulsados & ~prev_vig);
    prev_vig = pulsados;
    if (abierto || !en_cuadernos()) return 0;
    if (nuevos & 0x400) { abrir(); return 1; }                // X
    return 0;
}
int vigilar_toque(int x, int y, bool abajo) {
    const bool nuevo = abajo && !toque_vig_prev;
    toque_vig_prev = abajo;
    if (abierto || !nuevo || !en_cuadernos()) return 0;
    if (x >= kXx0 && x <= kXx1 && y >= kBy0 && y <= kBy1) { abrir(); return 1; }
    return 0;
}
// Botones DS: 0 A, 1 B, 4 der, 5 izq, 6 arr, 7 aba, 10 X
void teclas(uint16_t pulsados) {
    const uint16_t nuevos = uint16_t(pulsados & ~prev);
    prev = pulsados;
    if (nuevos & 0x40) fila = (fila + 3) % 4;
    if (nuevos & 0x80) fila = (fila + 1) % 4;
    if (nuevos & 0x10) cambiar(fila, 1);
    if (nuevos & 0x20) cambiar(fila, -1);
    if (nuevos & 0x01) { if (fila == 3) cambiar(3, 0); else cerrar(true); }
    if (nuevos & 0x02) cerrar(false);
    if (nuevos & 0x400) cerrar(true);
}
void toque(int x, int y, bool abajo) {
    const bool nuevo = abajo && !toque_prev;
    toque_prev = abajo;
    if (!nuevo) return;
    if (y >= kBy0 && y <= kBy1) {
        if (x >= kAx0 && x <= kAx1) cerrar(true);
        else if (x >= kBx0 && x <= kBx1) cerrar(false);
        else if (x >= kXx0 && x <= kXx1) cerrar(true);
        return;
    }
    for (int f = 0; f < 4; ++f) {
        const int y0 = kFila0 + kAltoFila * f;
        if (y < y0 || y >= y0 + kAltoFila || x < kVx0 || x > kVx1) continue;
        fila = f;
        if (f == 3) cambiar(3, 0);
        else cambiar(f, x < 128 ? -1 : 1);
        return;
    }
}

// ---- dibujo ----
inline uint32_t& px(int x, int y) { return ent::buf[y * 256 + x]; }
bool claro(uint32_t c) { return ((c >> 16 & 255) + (c >> 8 & 255) + (c & 255)) > 560; }
// Texturas de los menus del juego (paquetes .SPL/.SPD de pic3d): cada pieza .PAC_ (LZ10) tiene
// los pixeles (4 bits, en lineas), la paleta y la lista de recuadros (x, y, ancho, alto).
struct Tex { std::vector<uint8_t> px; uint32_t pal[48] = {}; int w = 0; std::vector<std::array<int, 4>> fr; bool ok = false; };
bool cargar_tex(const std::vector<uint8_t>& L, const std::vector<uint8_t>& D, const char* nombre, Tex& t) {
    auto u32 = [](const std::vector<uint8_t>& v, size_t o) {
        return o + 4 <= v.size() ? uint32_t(v[o] | v[o + 1] << 8 | v[o + 2] << 16 | uint32_t(v[o + 3]) << 24) : 0u;
    };
    const size_t largo = std::strlen(nombre);
    for (size_t e = 0x20; e + 16 <= L.size(); e += 16) {
        const uint32_t nom = u32(L, e), tam = u32(L, e + 4), des = u32(L, e + 8);
        if (!nom || nom + largo >= L.size()) break;
        bool igual = L[nom + largo] == 0;
        for (size_t i = 0; igual && i < largo; ++i) igual = std::toupper(L[nom + i]) == std::toupper((unsigned char)nombre[i]);
        if (!igual) continue;
        const size_t a = size_t(des) * 32;
        if (a + tam > D.size() || !tam) return false;
        std::vector<uint8_t> d(D.begin() + long(a), D.begin() + long(a + tam));
        if (d[0] == 0x10) d = ent::lz10(d);
        if (u32(d, 0) < 3) return false;
        const uint32_t po = u32(d, 4), ps = u32(d, 8), lo = u32(d, 12), ls = u32(d, 16), so = u32(d, 20), ss = u32(d, 24);
        if (size_t(po) + ps > d.size() || size_t(lo) + ls > d.size() || size_t(so) + ss > d.size() || ss < 8) return false;
        t.px.assign(d.begin() + po, d.begin() + po + ps);
        for (uint32_t i = 0; i < ls / 2 && i < 48; ++i) {
            const int c = d[lo + 2 * i] | d[lo + 2 * i + 1] << 8;
            t.pal[i] = 0xFF000000u | uint32_t((c & 31) * 255 / 31) << 16 | uint32_t((c >> 5 & 31) * 255 / 31) << 8 | uint32_t((c >> 10 & 31) * 255 / 31);
        }
        const int n = d[so] | d[so + 1] << 8;
        t.w = 8 << d[so + 2];
        auto u16 = [&](size_t o) { return int(d[o] | d[o + 1] << 8); };
        for (int i = 0; i < n && 8u + 8u * uint32_t(i) + 8u <= ss; ++i) {
            const size_t f = so + 8 + 8 * size_t(i);
            t.fr.push_back({u16(f), u16(f + 2), u16(f + 4), u16(f + 6)});
        }
        t.ok = t.w > 0 && !t.fr.empty() && !t.px.empty();
        return t.ok;
    }
    return false;
}
int tex_ci(const Tex& t, int x, int y) {
    const size_t i = size_t(y) * size_t(t.w) + size_t(x);
    if (x < 0 || x >= t.w || i / 2 >= t.px.size()) return 0;
    return (i & 1) ? t.px[i / 2] >> 4 : t.px[i / 2] & 15;
}
// Dibuja el recuadro f; si 'ancho' es mayor que el del recuadro, lo alarga repitiendo la
// columna 'relleno' (una del cuerpo del boton, sin letras) entre 'izq' y las columnas de la derecha
// desde 'der'. Las columnas izq..der-1 tambien se rellenan (asi se borra el texto del boton).
bool tex_dibujar(const Tex& t, int f, int X, int Y, int ancho = 0, int izq = -1, int relleno = 0, int der = 0) {
    if (!t.ok || f < 0 || size_t(f) >= t.fr.size()) return false;
    const auto& r = t.fr[size_t(f)];
    const int fw = r[2], fh = r[3];
    if (ancho <= 0) ancho = fw;
    for (int y = 0; y < fh; ++y)
        for (int c = 0; c < ancho; ++c) {
            int sc = c;
            if (izq >= 0) sc = c < izq ? c : (c >= ancho - (fw - der) ? c - (ancho - fw) : relleno);
            const int ci = tex_ci(t, r[0] + sc, r[1] + y);
            const int x = X + c, yy = Y + y;
            if (ci && x >= 0 && x < 256 && yy >= 0 && yy < 192) px(x, yy) = t.pal[ci];
        }
    return true;
}
const Tex& tex_boton() {       // waza_den: MMDN_B00, recuadros 4 (X Equipar) y 5 (iluminado)
    static Tex t; static bool hecho = false;
    if (!hecho) { hecho = true; cargar_tex(g_wd_l, g_wd_d, "MMDN_B00.PAC_", t); if (t.fr.size() < 6) t.ok = false; }
    return t;
}
const Tex& tex_flechas() {     // tienda: SHDN_B00, 0 izquierda, 2 derecha (1 y 3 pulsadas)
    static Tex t; static bool hecho = false;
    if (!hecho) { hecho = true; cargar_tex(g_sh_l, g_sh_d, "SHDN_B00.PAC_", t); if (t.fr.size() < 4) t.ok = false; }
    return t;
}
void boton_x() {
    // Boton X del propio juego (el de "X Equipar" de la ensenanza de supertecnicas), alargado
    // al hueco de "Y Opciones" y con el texto del boton cambiado por "Filtros"
    const Tex& t = tex_boton();
    const int X = kXx0, Y = kBy0, W = kXx1 - kXx0 + 1;
    const std::string txt = ent::J(L5("Filters", "Filtros", "Filtres", "Filter", "Filtri"));
    // El texto del boton cambia de sitio y de largo segun el idioma ("Equip", "Equipar"...), asi
    // que no se copia ninguna columna de la zona del texto: se copian el circulo (columnas 0-16)
    // y el borde derecho (4 ultimas), y en medio se pone el cuerpo del boton (su color de la
    // fila 4, encima de las letras) en las filas del texto, y la columna 20 en las del borde.
    // Si alguna letra o su contorno llega a la columna 16 o al borde derecho, se tapa tambien.
    const int f = abierto ? 5 : 4;
    if (t.ok && size_t(f) < t.fr.size() && t.fr[size_t(f)][2] >= 40 && t.fr[size_t(f)][3] >= 20) {
        const auto& r = t.fr[size_t(f)];
        const int fw = r[2], fh = r[3];
        auto ci = [&](int c, int y) { return tex_ci(t, r[0] + c, r[1] + y); };
        const int cuerpo = ci(20, 4);
        int cuenta[16] = {};                                 // contorno de las letras
        for (int y = 5; y < 18; ++y)
            for (int c = 17; c < fw - 6; ++c)
                if (ci(c, y) == 15)
                    for (int v : {ci(c - 1, y), ci(c + 1, y)})
                        if (v && v != 15 && v != cuerpo) ++cuenta[v];
        int contorno = -1;
        for (int v = 1, mejor = 0; v < 16; ++v) if (cuenta[v] > mejor) { mejor = cuenta[v]; contorno = v; }
        auto letra = [&](int v) { return v == 15 || v == contorno; };
        for (int y = 0; y < fh; ++y) {
            const bool fila_texto = y >= 4 && y < 18;
            for (int c = 0; c < W; ++c) {
                int v;
                if (c <= 16) v = ci(c, y);
                else if (c >= W - 4) v = ci(c - (W - fw), y);
                else v = fila_texto ? cuerpo : ci(20, y);
                if (fila_texto && (c == 16 || c == W - 4) && letra(v)) v = cuerpo;
                const int x = X + c, yy = Y + y;
                if (v && x >= 0 && x < 256 && yy >= 0 && yy < 192) px(x, yy) = t.pal[v];
            }
        }
        const int zona = W - 17 - 5;                         // de la columna 17 al borde derecho
        ent::texto(X + 17 + (zona - ent::ancho(txt)) / 2, Y + (abierto ? 7 : 6), txt,   // iluminado: 1 px abajo, como el juego
                   hay_filtro() ? 0xFFFFF070 : 0xFFFFFFFF, hay_filtro() ? 0xFFF8D040 : 0xFFFFFFFF, false, t.pal[contorno > 0 ? contorno : 3]);
        return;
    }
    // sin la textura (no deberia pasar): recuadro sencillo
    for (int y = Y + 2; y <= Y + 20; ++y) for (int x = X + 2; x <= X + W - 4; ++x) px(x, y) = 0xFF3C3C3C;
    ent::texto(X + 6, Y + 6, "X " + txt, 0xFFFFFFFF, 0xFFFFFFFF, false, 0xFF737373);
}
void fila_vacia(int y0, bool sel) {
    for (int x = kVx0; x <= kVx1; ++x) {
        px(x, y0) = 0xFF513626;
        px(x, y0 + 1) = 0xFF9F4516;
        for (int y = y0 + 2; y < y0 + kAltoFila; ++y) px(x, y) = 0xFFBA3A04;
    }
    for (int y = y0 + 1; y < y0 + kAltoFila; ++y) { px(kVx0, y) = 0xFF68300E; px(kVx0 + 1, y) = 0xFF9F4418; }
    if (sel)
        for (int k = 0; k < 2; ++k) {
            for (int x = kVx0 - 1 + k; x <= kVx1 + 1 - k; ++x) { px(x, y0 + k) = 0xFFFFFFFF; px(x, y0 + kAltoFila - 1 - k) = 0xFFFFFFFF; }
            for (int y = y0 + k; y < y0 + kAltoFila - k; ++y) { px(kVx0 - 1 + k, y) = 0xFFFFFFFF; px(kVx1 + 1 - k, y) = 0xFFFFFFFF; }
        }
}
// Valor de cada fila con los graficos del juego: etiqueta de tipo (msup_z05), insignia de
// elemento (MSUP_Z01-Z04) y etiqueta "PT" (MSUP_F05) con flechas de la fuente del juego.
// Dibuja algo de prueba en (0,0) dentro de una zona de 64x32, mira que pixeles ha cambiado
// (su caja: columnas x0-x1, filas y0-y1) y deja la pantalla como estaba.
template <class F> bool medir(F dibujar, int& x0, int& x1, int& y0, int& y1) {
    constexpr int kW = 64, kH = 32, kOx = 8, kOy = 8;
    static uint32_t copia[kH][kW];
    for (int y = 0; y < kH; ++y) for (int x = 0; x < kW; ++x) copia[y][x] = px(x, y);
    // fondo de prueba de un color que no usan ni la etiqueta ni la letra
    for (int y = 0; y < kH; ++y) for (int x = 0; x < kW; ++x) px(x, y) = 0xFF010203;
    const bool ok = dibujar(kOx, kOy);
    x0 = kW; x1 = -1; y0 = kH; y1 = -1;
    for (int y = 0; y < kH; ++y)
        for (int x = 0; x < kW; ++x)
            if (px(x, y) != 0xFF010203) { x0 = std::min(x0, x); x1 = std::max(x1, x); y0 = std::min(y0, y); y1 = std::max(y1, y); }
    for (int y = 0; y < kH; ++y) for (int x = 0; x < kW; ++x) px(x, y) = copia[y][x];
    x0 -= kOx; x1 -= kOx; y0 -= kOy; y1 -= kOy;           // relativo al punto de dibujo
    return ok && x1 >= x0;
}
// Dibuja un grafico centrado (por lo que se ve de el) en el hueco del valor de la fila
template <class F> bool centrado(F dibujar, int y0) {
    int x0, x1, ya, yb;
    if (!medir(dibujar, x0, x1, ya, yb)) return false;
    const int cy = y0 + 2 + (kAltoFila - 2) / 2;
    return dibujar(153 - (x1 - x0 + 1) / 2 - x0, cy - (ya + yb + 1) / 2);
}
void texto_centro(const std::string& t, int y0) { ent::texto(153 - ent::ancho(t) / 2, y0 + 3, t, 0xFFFFFFFF, 0xFFFFE8C8); }
void valor(int f, int y0, const std::string& todas) {
    static const int kEtiqueta[10] = {4, 4, 4, 4, 4, 0, 1, 2, 3, 5};
    static const char* kElem[5] = {nullptr, "MSUP_Z01", "MSUP_Z02", "MSUP_Z03", "MSUP_Z04"};
    const std::string abajo = "\x81\xAB", arriba = "\x81\xAA", flecha = "\x81\xA8";   // flechas (Shift-JIS)
    if (f == 0) {
        if (!e_tipo || !centrado([&](int x, int y) { return ent::sprite("Z05", kEtiqueta[kTipos[e_tipo]], 3, 2, x, y); }, y0))
            texto_centro(e_tipo ? ent::J(nombre_tipo(e_tipo)) : todas, y0);
    } else if (f == 1) {
        if (!e_afin || !centrado([&](int x, int y) { return ent::sprite(kElem[e_afin], 0, 4, 2, x, y); }, y0))
            texto_centro(e_afin ? ent::J(nombre_afin(e_afin)) : todas, y0);
    } else if (e_orden == 0) {
        texto_centro(ent::J(L5("Default", "Normal", "Normal", "Normal", "Normale")), y0);
    } else if (e_orden <= 2) {                         // PT de mas a menos / de menos a mas
        const std::string fl = e_orden == 1 ? abajo : arriba;
        // La etiqueta y la flecha tienen margenes vacios (y la etiqueta puede cambiar con el
        // idioma): se miden dibujandolas de prueba y se centra lo que se ve de verdad.
        auto etiqueta = [&](int x, int y) { return ent::sprite("MSUP_F05", 1, 2, 2, x, y); };
        auto flechita = [&](int x, int y) { ent::texto(x, y, fl, 0xFFFFFFFF, 0xFFFFE8C8, false, 0xFF141846, true); return true; };
        int e0, e1, ey0, ey1, f0, f1, fy0, fy1;
        if (medir(etiqueta, e0, e1, ey0, ey1) && medir(flechita, f0, f1, fy0, fy1)) {
            const int hueco = 3, total = (e1 - e0 + 1) + hueco + (f1 - f0 + 1);
            const int xe = 153 - total / 2;                  // donde empieza lo visible
            const int cy = y0 + 2 + (kAltoFila - 2) / 2;      // centro de la parte naranja de la fila
            etiqueta(xe - e0, cy - (ey0 + ey1 + 1) / 2);
            flechita(xe + (e1 - e0 + 1) + hueco - f0, cy - (fy0 + fy1 + 1) / 2);
        } else {
            texto_centro(std::string(L5("TP ", "PT ", "PT ", "TP ", "PT ")) + fl, y0);
        }
    } else {                                          // nombre A-Z / Z-A
        texto_centro(e_orden == 3 ? "A" + flecha + "Z" : "Z" + flecha + "A", y0);
    }
}
void ventana() {
    // cabecera y barra de paginas: fondo de la ventana con el titulo "Filtros"
    for (int y = 8; y < kFila0; ++y) for (int x = kVx0; x <= kVx1; ++x) px(x, y) = 0xFF242424;
    ent::texto(60, 10, ent::J(L5("Filters", "Filtros", "Filtres", "Filter", "Filtri")), 0xFFF8C060, 0xFFE09030);
    ent::texto(60, 21, ent::J(L5("Left/Right: change   A: apply", "Izq./Der.: cambiar   A: aplicar",
                                 "G./D. : changer   A : valider", "Links/Rechts: ändern   A: OK",
                                 "Sin./Des.: cambia   A: applica")), 0xFFC7C7C7, 0xFF9A9A9A);
    const std::string etq[3] = {ent::J(L5("Type", "Tipo", "Type", "Typ", "Tipo")),
                                ent::J(L5("Element", "Afinidad", "Élément", "Element", "Affinità")),
                                ent::J(L5("Sort", "Orden", "Tri", "Ordnen", "Ordine"))};
    const std::string todas = ent::J(nombre_tipo(0));
    const Tex& fl = tex_flechas();
    for (int f = 0; f < 8; ++f) {
        const int y0 = kFila0 + kAltoFila * f;
        fila_vacia(y0, f == fila && f < 4);
        if (f < 3) {
            ent::texto(60, y0 + 3, etq[f], 0xFFF8F8F8, 0xFFE0E0E0);
            if (!tex_dibujar(fl, 0, 104, y0) || !tex_dibujar(fl, 2, 186, y0)) {
                ent::texto(110, y0 + 3, "<", 0xFFFFE070, 0xFFF0B030);
                ent::texto(196, y0 + 3, ">", 0xFFFFE070, 0xFFF0B030, true);
            }
            valor(f, y0, todas);
        } else if (f == 3) {
            const std::string t = ent::J(L5("Clear filters", "Quitar filtros", "Effacer les filtres", "Filter löschen", "Rimuovi filtri"));
            ent::texto(128 - ent::ancho(t) / 2, y0 + 3, t, 0xFFF8F8F8, 0xFFE0E0E0);
        }
    }
}
const uint32_t* dibujar(const uint32_t* abajo, int ancho) {
    if (!abajo || ancho < 256) return nullptr;
    if (!abierto && !en_cuadernos()) return nullptr;
    for (int y = 0; y < 192; ++y) std::memcpy(&ent::buf[y * 256], abajo + size_t(y) * size_t(ancho), 256 * 4);
    boton_x();
    if (abierto) ventana();
    g_salida.assign(abajo, abajo + size_t(ancho) * 192);
    for (int y = 0; y < 192; ++y) std::memcpy(&g_salida[size_t(y) * size_t(ancho)], &ent::buf[y * 256], 256 * 4);
    return g_salida.data();
}
}  // namespace filtros
