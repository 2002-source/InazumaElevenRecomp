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
std::vector<uint32_t> g_fondo_abajo;         // fondo del menu de entrenamiento (256x192 ARGB)
std::vector<uint32_t> g_fondo_ficha;         // fondo de la ficha (pagina 2) para la pantalla de arriba
std::vector<uint8_t> g_itemdat, g_cmddat, g_cmdstr;   // nombres de objetos y supertecnicas
std::vector<uint8_t> g_lvup;                          // umbrales de grado por categoria (lvup_command.dat)
std::vector<uint8_t> g_fuente12, g_fuente8;           // fuentes del juego (NFTR)
std::vector<uint8_t> g_smstat;                        // sprites de la ficha (SMStat.SPF_, comprimido)
std::vector<uint8_t> g_z05;                           // etiquetas de tipo de tecnica (msup_z05.pac_)
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
            if (leer(dir / mod / "fondo_entrenamiento.argb", f) && f.size() == 256u * 192u * 4u) {
                g_fondo_abajo.resize(256 * 192);
                std::memcpy(g_fondo_abajo.data(), f.data(), f.size());
                logf("[mods] '%s': menu de entrenamiento disponible (se abre hablando con el NPC entrenador)", mod.c_str());
            }
        }
        const auto raiz = dir / mod;
        std::error_code ec;
        if (!std::filesystem::is_directory(raiz, ec)) { logf("[mods] '%s' no existe; se omite", mod.c_str()); continue; }
        unsigned n = 0, desconocidos = 0;
        for (const auto& e : std::filesystem::recursive_directory_iterator(raiz, ec)) {
            if (!e.is_regular_file(ec)) continue;
            std::string rel = std::filesystem::relative(e.path(), raiz, ec).generic_string();
            if (rel == "mod.txt" || rel == "trucos.txt" || rel == "fondo_entrenamiento.argb" || rel == "fondo_ficha.argb") continue;
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
    copiar("/data_iz/logic/en/unitno.dat", g_unitno);
    copiar("/data_iz/logic/en/unitstat.dat", g_unitstat);
    copiar("/data_iz/logic/status_up.dat", g_curvas);
    copiar("/data_iz/logic/en/item.dat", g_itemdat);      // (ya con el idioma elegido)
    copiar("/data_iz/logic/en/command.dat", g_cmddat);
    copiar("/data_iz/logic/lvup_command.dat", g_lvup);
    copiar("/data_iz/logic/en/command.STR", g_cmdstr);
    copiar("/data_iz/font/FONT12T.NFTR", g_fuente12);   // la de los menus: 2 bits, con sombra
    copiar("/data_iz/font/FONT8.NFTR", g_fuente8);
    copiar("/data_iz/pic2d/menu/en/SMStat.SPF_", g_smstat);   // digitos, PE/PT, posiciones, elementos
    copiar("/data_iz/pic2d/menu/en/msup_z05.pac_", g_z05);    // Regate / Bloqueo / Tiro / Atajo / ? / Talento
    copiar("/data_iz/face2d/fac.pkh", g_fac_h); copiar("/data_iz/face2d/fac.pkb", g_fac_b);
    copiar("/data_iz/face2d/fab.pkh", g_fab_h); copiar("/data_iz/face2d/fab.pkb", g_fab_b);
    copiar("/data_iz/pic3d/ih.pkh", g_ih_h); copiar("/data_iz/pic3d/ih.pkb", g_ih_b);
    copiar("/data_iz/pic2d/cmd/en/mbd_c.pkh", g_mbd_h); copiar("/data_iz/pic2d/cmd/en/mbd_c.pkb", g_mbd_b);
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
IE1_EXPORT void ie1_mods_fotograma_v1(const Ie1ModsMem* mem) {
    if (mem && mem->version >= 1) g_mem = mem;
    ie1_senal_npc();
    ie1_niveles_tick();
    if (const char* e = std::getenv("IE1_PRUEBA_GANCHO"); e && *e == '1') ie1_inyeccion_tick();
    if (const char* e = std::getenv("IE1_PRUEBA_GANCHO"); e && *e == '2') ie1_prueba2_tick();
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
        if (m.tr_pe[k] + n > 50) { m.ok = false; m.motivo = "Máximo +50"; }
        else if (maxlv + m.tr_pe[k] + n > 999) { m.ok = false; m.motivo = "Máximo 999"; }
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
        if (n > permitido) { m.ok = false; m.motivo = m.tr[i] + n > 50 ? "Máximo +50" : "Pareja al mínimo"; }
        const int exceso = n - std::min(n, lib);
        if (exceso > 0 && m.base[p] - exceso < 1) { m.ok = false; m.motivo = "Pareja al mínimo"; }
        m.tr[i] += n; m.base[i] += n; m.disp[i] += n;
        if (exceso > 0) { m.tr[p] -= exceso; m.base[p] -= exceso; m.disp[p] -= exceso; }
        if (m.base[i] > 255) { m.ok = false; m.motivo = "Máximo 255"; }
    }
    m.lib = std::max(0, libre());
    return m;
}

bool puede_sumar(int j, int f) {
    int prueba[kFilas];
    std::copy(std::begin(asig), std::end(asig), prueba);
    ++prueba[f];
    if (uint64_t(total_asig() + 1) * kCoste > r32(kPasion)) { aviso = J("Pasión insuficiente"); return false; }
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
    aviso = J("Entrenamiento aplicado");
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
    static const struct { const char* u; char g; } k[] = {
        {"\xC3\xA1", '\xB2'}, {"\xC3\xA9", '\xBA'}, {"\xC3\xAD", '\xBE'}, {"\xC3\xB3", '\xC4'},
        {"\xC3\xBA", '\xCA'}, {"\xC3\xB1", '\xC2'}, {"\xC3\x91", '\xA9'}, {"\xC3\xBC", '\xCC'},
        {"\xC3\x81", '\xD1'}, {"\xC3\x89", '\xD9'}, {"\xC3\x8D", '\xA6'}, {"\xC3\x93", '\xAB'},
        {"\xC3\x9A", '\xA2'}, {"\xC2\xBF", '\xA5'}, {"\xC2\xA1", '\xDF'}};
    std::string r;
    for (const char* p = utf8; *p;) {
        bool hecho = false;
        if ((unsigned char)*p >= 0xC2 && fuente())
            for (const auto& e : k)
                if (!std::strncmp(p, e.u, 2)) { r += e.g; p += 2; hecho = true; break; }
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
struct Zona { int x = 0, w = 0; } g_boton_a, g_boton_b;
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
// Posicion de la etiqueta de la Libertad en el fondo (su ancho cambia con el idioma:
// "Libertad", "Freedom"...). Se busca el texto claro en la cabecera (y 5..30).
struct Etiqueta { int x1 = 224, y0 = 12, y1 = 22; bool hecha = false; } g_etq;
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
        else texto(172, 16, "Niv." + nv, 0xFFB4E6FF, 0xFF64B4E6);
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
void tic() {                            // una vez por fotograma con el menu abierto
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
    if (!abajo) { tq_fila = -1; rep_cont = 0; return; }
    if (!nuevo || !abierto) return;
    rep_cont = 0;
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
    if (y >= 174 && y <= 186 && x >= 150 && x <= 170) cambiar_jugador(-1);                         // L
    else if ((y >= 174 && y <= 186 && x >= 236 && x <= 254) || (y >= 4 && y <= 28 && x >= 6 && x <= 120))
        cambiar_jugador(1);                                                                        // R / tocar el nombre
}
}  // namespace ent

IE1_EXPORT void ie1_mods_overlay_toque_v1(int x, int y, int abajo) { ent::toque(x, y, abajo != 0); }
// Tecla T: desactivada. El menu solo se abre desde el NPC entrenador (su guion
// manda la senal). Para pruebas se puede volver a activar con IE1_TECLA_T=1.
IE1_EXPORT int ie1_mods_overlay_disponible_v1() {
    static const bool tecla_t = [] { const char* e = std::getenv("IE1_TECLA_T"); return e && *e == '1'; }();
    return (!g_fondo_abajo.empty() && tecla_t) ? 1 : 0;
}
IE1_EXPORT int ie1_mods_overlay_activo_v1() { return ent::abierto ? 1 : 0; }
IE1_EXPORT void ie1_mods_overlay_alternar_v1() {
    if (g_fondo_abajo.empty() || !g_mem) return;
    ent::abierto = !ent::abierto;
    if (ent::abierto) {
        ent::cargar_lista();
        if (std::find(ent::lista.begin(), ent::lista.end(), ent::jug) == ent::lista.end()) ent::jug = ent::lista[0];
        std::fill(std::begin(ent::asig), std::end(ent::asig), 0);
        ent::fila = 2;                            // empieza en Tiro
        ent::prev = 0xFFFF;                       // ignorar los botones que ya estaban pulsados
    }
}
// Botones DS (bit 0 A, 1 B, 2 Select, 3 Start, 4 der, 5 izq, 6 arr, 7 aba, 8 R, 9 L)
IE1_EXPORT void ie1_mods_overlay_teclas_v1(uint16_t pulsados) {
    using namespace ent;
    if (!abierto) { prev = pulsados; mantenidos = 0; return; }
    const uint16_t nuevos = uint16_t(pulsados & ~prev);
    prev = pulsados;
    mantenidos = pulsados == 0xFFFF ? 0 : pulsados;
    if (nuevos & 0xF0) rep_cont = 0;              // nueva direccion: reinicia la repeticion
    if (nuevos & 0x40) fila = (fila + kFilas - 1) % kFilas;
    if (nuevos & 0x80) fila = (fila + 1) % kFilas;
    if (nuevos & 0x10) accion(fila, 1);           // derecha (Ctrl: el maximo posible)
    if (nuevos & 0x20) accion(fila, -1);          // izquierda (Ctrl: quitar todo)
    if (nuevos & 0x100) cambiar_jugador(1);       // R
    if (nuevos & 0x200) cambiar_jugador(-1);      // L
    if (nuevos & 0x01) { aplicar(jug); aviso_t = 120; }
    if (nuevos & 0x02) abierto = false;
}
IE1_EXPORT int ie1_mods_overlay_dibujar_v1(const uint32_t* arriba, int ancho_arriba,
                                          const uint32_t* abajo, int ancho_abajo,
                                          const uint32_t** sal_arriba, const uint32_t** sal_abajo) {
    using namespace ent;
    (void)abajo; (void)ancho_abajo;
    if (!abierto || g_fondo_abajo.empty() || !g_mem) return 0;
    tic();                                        // repeticion al mantener pulsado
    std::memcpy(buf, g_fondo_abajo.data(), sizeof(buf));
    const uint32_t b = base(jug);
    // cabecera: icono de la cara, nombre (blanco), nivel con los graficos del juego y aptitud
    if (!icono_lista(jug, 4, 1)) icono(jug, 6, 6, 22);     // icono de las listas del juego
    texto(36, 7, nombre(jug), 0xFFF8F8F8, 0xFFF8F8F8);
    {
        const std::string nv = std::to_string(r8(b + 0xAA));
        if (sprite("MSUP_F08", 1, 2, 1, 36, 19)) numero("MSUP_F10", nv, 70, 14);
        else texto(36, 17, "Niv." + nv, 0xFFB4E6FF, 0xFF64B4E6);
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
    texto(12, 162, J("Pasión"));
    texto(146, 162, std::to_string(pasion >= coste ? pasion - coste : 0), 0xFFF0FFFF, 0xFF8CDCF0, true);
    texto(12, 173, "Coste", 0xFFB4C8DC, 0xFF8CA0B4);
    texto(146, 173, coste ? "-" + std::to_string(coste) : "0", 0xFFFFF58C, 0xFFF0AA28, true);
    // Botones como los del juego: caja oscura redondeada, circulo naranja con la letra
    {   // anchos segun el texto (cambia con el idioma)
        const std::string ta = J("Aceptar"), tb = J("Salir");
        const int wa = ancho(ta) + 17, wb = ancho(tb) + 17;
        g_boton_a = {251 - wb - 3 - wa, wa}; g_boton_b = {251 - wb, wb};
        boton(g_boton_a.x, 162, wa, "A", ta);
        boton(g_boton_b.x, 162, wb, "B", tb);
    }
    // Cambiar de jugador: L / R (o tocar el nombre)
    texto(153, 175, "L", 0xFFB4E6FF, 0xFF64B4E6); flecha(160, 177, true, 0xFF96E6FA);
    flecha(240, 177, false, 0xFF96E6FA); texto(246, 175, "R", 0xFFB4E6FF, 0xFF64B4E6);
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
void ie1_niveles_tick() {
    static int activo = -1;
    if (!g_mem) return;
    if (activo < 0) {
        activo = 0;
        for (size_t i = 0; i + 28 <= g_cmddat.size(); i += 28) if (g_cmddat[i + 0x10]) { activo = 1; break; }
        if (activo && g_lvup.empty()) activo = 0;
        if (activo) logf("[mods] niveles de supertecnicas: aviso \"Nv +\" activo");
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
                    avisos.push_back({b, 0});
                    logf("[mods] niveles: %s sube de grado (tecnica 0x%X, %d usos)", ent::nombre(j).c_str(), n.tec[s], n.usos[s]);
                }
        p = n;
    }
    for (size_t i = 0; i < avisos.size();) {
        Aviso& a = avisos[i];
        const uint32_t ev = g_mem->r32(a.bloque + 0xE8);
        bool hecho = false;
        if (ev >= 0x02000000u && ev < 0x02400000u && (ev & 3u) == 0) {
            if (g_mem->r8(ev + 0x1C) == 0) {          // sin otro evento: cartel "Nv +"
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
    static const uint32_t stub[] = {
        0xE92D500Fu, 0xE5970060u, 0xE59D1098u, 0xE59F2060u, 0xE3A03000u, 0xE1D2C0B0u, 0xE35C0000u, 0x0A000007u,
        0xE15C0001u, 0x1A000003u, 0xE1D2C0B2u, 0xE15C0000u, 0x05923004u, 0x0A000001u, 0xE2822008u, 0xEAFFFFF4u,
        0xE59F2030u, 0xE0823183u, 0xE5873064u, 0xE59F2028u, 0xE5820000u, 0xE5821004u, 0xE5823008u, 0xE592C00Cu,
        0xE28CC001u, 0xE582C00Cu, 0xE8BD500Fu, 0xE1D500DBu, 0xEAF56E31u, kTablaMarca, kNombresMarca, kDiagMarca};
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
            t.push_back(uint32_t(ie1_marca(tec, g_mem->r8(b + 0xA4 + uint32_t(s)))));
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
    if (!hay && g_mem->version >= 2 && g_mem->copiar && ++espera >= 20) {   // ~3 veces por segundo
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
    leer(unitno, g_unitno); leer(unitstat, g_unitstat); leer("/tmp/pc/archivos/data_iz/logic/status_up.dat", g_curvas);
    leer("/tmp/pc/archivos/data_iz/logic/en/item.dat", g_itemdat); leer("/tmp/pc/archivos/data_iz/logic/en/command.dat", g_cmddat);
    leer("/tmp/pc/archivos/data_iz/logic/en/command.STR", g_cmdstr);
    if (const char* e = std::getenv("IE1_TEST_CMD")) leer(e, g_cmddat);          // command.dat con el mod de niveles
    if (const char* e = std::getenv("IE1_TEST_LVUP")) leer(e, g_lvup);
    leer("/tmp/pc/archivos/data_iz/font/FONT12T.NFTR", g_fuente12);
    leer("/tmp/pc/archivos/data_iz/pic2d/menu/en/SMStat.SPF_", g_smstat);
    leer("/tmp/pc/archivos/data_iz/pic2d/menu/en/msup_z05.pac_", g_z05);
    leer("/tmp/pc/archivos/data_iz/face2d/fac.pkh", g_fac_h); leer("/tmp/pc/archivos/data_iz/face2d/fac.pkb", g_fac_b);
    leer("/tmp/pc/archivos/data_iz/face2d/fab.pkh", g_fab_h); leer("/tmp/pc/archivos/data_iz/face2d/fab.pkb", g_fab_b);
    leer("/tmp/pc/archivos/data_iz/pic3d/ih.pkh", g_ih_h); leer("/tmp/pc/archivos/data_iz/pic3d/ih.pkb", g_ih_b);
    leer("/tmp/pc/archivos/data_iz/pic2d/cmd/en/mbd_c.pkh", g_mbd_h); leer("/tmp/pc/archivos/data_iz/pic2d/cmd/en/mbd_c.pkb", g_mbd_b);
}
#endif
