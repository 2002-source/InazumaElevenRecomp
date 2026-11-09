#!/usr/bin/env python3
"""
Integra en el runner la MEZCLA DE IDIOMAS de Inazuma Eleven (base inglesa YEEP):
al cargar la ROM, sustituye en la imagen del cartucho en memoria los archivos
de idioma por los de un paquete (idiomas/<idioma>/, creado con
crear_paquete_idioma.py) y ajusta la tabla de archivos (FAT).

Variables de entorno (las pone jugar.sh):
  IE1_TEXTOS=es       idioma de textos e imagenes con texto (en = original)
  IE1_VOCES=es        idioma de sonido/voces (carpeta sound/en)
  IE1_IDIOMAS_DIR=... carpeta de los paquetes (por defecto ./idiomas)

Crea runner/src/ie1_idiomas.cpp y modifica runner/src/io.cpp y CMakeLists.txt.
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/io.cpp runner/CMakeLists.txt
          y borra runner/src/ie1_idiomas.cpp (despues vuelve a ejecutar
          integrar_hle_cartucho.py, parche_pgo_clang.py y parche_perf.py).
"""
import os, sys
ROOT = "C:/dev/ndsrecomp/runner"

FUENTE = r'''// Mezcla de idiomas de Inazuma Eleven (integrar_idiomas.py, proyecto ie1recomp)
#include <algorithm>
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
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
#include "runtime_arm.h"   // bus_read_* / bus_write_* para los trucos

namespace {
uint32_t rd32(const std::vector<uint8_t>& r, std::size_t o) {
    return uint32_t{r[o]} | uint32_t{r[o + 1]} << 8 | uint32_t{r[o + 2]} << 16 |
           uint32_t{r[o + 3]} << 24;
}
void wr32(std::vector<uint8_t>& r, std::size_t o, uint32_t v) {
    r[o] = uint8_t(v); r[o + 1] = uint8_t(v >> 8);
    r[o + 2] = uint8_t(v >> 16); r[o + 3] = uint8_t(v >> 24);
}
bool leer(const std::filesystem::path& p, std::vector<uint8_t>& d) {
    // Lectura de golpe (antes era byte a byte, muy lento con 85 MB de paquetes)
    std::ifstream f(p, std::ios::binary | std::ios::ate);
    if (!f) return false;
    const std::streamsize n = f.tellg();
    if (n < 0) return false;
    d.resize(static_cast<std::size_t>(n));
    f.seekg(0);
    return n == 0 || static_cast<bool>(f.read(reinterpret_cast<char*>(d.data()), n));
}
bool vacio_o_en(const char* v) { return !v || !*v || std::strcmp(v, "en") == 0; }
}  // namespace

// ---- Configuracion guardada y API para el menu de Esc -----------------------
namespace {
std::filesystem::path carpeta_idiomas() {
    const char* d = std::getenv("IE1_IDIOMAS_DIR");
    std::filesystem::path dir = (d && *d) ? std::filesystem::path(d) : std::filesystem::path("idiomas");
    std::error_code ec;
    if (!std::filesystem::is_directory(dir, ec) && std::filesystem::is_directory("../idiomas", ec))
        dir = "../idiomas";
    return dir;
}
void poner_env(const char* k, const std::string& v) {
#if defined(_WIN32)
    _putenv_s(k, v.c_str());
#else
    setenv(k, v.c_str(), 1);
#endif
}
std::vector<std::string> g_codigos, g_nombres;
std::vector<const char*> g_desde_cfg;       // variables puestas desde idiomas.cfg
std::vector<const char*> g_nombres_c;
void cargar_lista() {
    if (!g_codigos.empty()) return;
    g_codigos.push_back("en");
    std::error_code ec;
    std::vector<std::string> otros;
    for (const auto& e : std::filesystem::directory_iterator(carpeta_idiomas(), ec))
        if (e.is_directory(ec) && e.path().filename().string() != "en")
            otros.push_back(e.path().filename().string());
    std::sort(otros.begin(), otros.end());
    for (auto& o : otros) g_codigos.push_back(o);
    const std::map<std::string, std::string> nombre = {
        {"en", "Ingles (original)"}, {"es", "Espanol"}, {"sp", "Espanol"}, {"fr", "Frances"},
        {"ge", "Aleman"}, {"de", "Aleman"}, {"it", "Italiano"}, {"jp", "Japones"}, {"ja", "Japones"}};
    for (auto& c : g_codigos) {
        auto it = nombre.find(c);
        g_nombres.push_back(it != nombre.end() ? it->second : c);
    }
    for (auto& n : g_nombres) g_nombres_c.push_back(n.c_str());
}
}  // namespace

// Lee idiomas.cfg (junto al juego) si no se eligio idioma con variables de entorno.
void ie1_idiomas_cargar_cfg() {
    static bool hecho = false;
    if (hecho) return;
    hecho = true;
#if defined(_WIN32)
    if (const char* pid = std::getenv("IE1_ESPERAR_PID"); pid && *pid) {
        if (HANDLE h = OpenProcess(SYNCHRONIZE, FALSE, DWORD(std::strtoul(pid, nullptr, 10)))) {
            WaitForSingleObject(h, 15000);
            CloseHandle(h);
        }
        poner_env("IE1_ESPERAR_PID", "");
    }
#endif
    std::ifstream f("idiomas.cfg");
    std::string linea;
    while (std::getline(f, linea)) {
        const auto eq = linea.find('=');
        if (eq == std::string::npos) continue;
        std::string k = linea.substr(0, eq), v = linea.substr(eq + 1);
        while (!v.empty() && (v.back() == '\r' || v.back() == ' ')) v.pop_back();
        const char* var = k == "textos" ? "IE1_TEXTOS" : k == "voces" ? "IE1_VOCES" : nullptr;
        const char* actual = var ? std::getenv(var) : nullptr;
        if (var && (!actual || !*actual)) {
            poner_env(var, v);
            g_desde_cfg.push_back(var);
        }
    }
}

extern "C" int ie1_idiomas_lista(const char* const** nombres) {
    cargar_lista();
    *nombres = g_nombres_c.data();
    return static_cast<int>(g_nombres_c.size());
}
extern "C" int ie1_idiomas_actual(int voces) {
    cargar_lista();
    const char* v = std::getenv(voces ? "IE1_VOCES" : "IE1_TEXTOS");
    for (std::size_t i = 0; v && i < g_codigos.size(); ++i)
        if (g_codigos[i] == v) return static_cast<int>(i);
    return 0;
}
extern "C" void ie1_idiomas_guardar(int textos, int voces) {
    cargar_lista();
    auto cod = [](int i) { return (i >= 0 && i < int(g_codigos.size())) ? g_codigos[i] : std::string("en"); };
    std::ofstream f("idiomas.cfg");
    f << "textos=" << cod(textos) << "\nvoces=" << cod(voces) << "\n";
    std::fprintf(stderr, "[idiomas] guardado: textos=%s voces=%s (se aplica al reiniciar)\n",
                 cod(textos).c_str(), cod(voces).c_str());
}

// ---- Reiniciar el programa (opcion del menu System) -------------------------
// Al salir con normalidad (partida guardada en disco) se lanza otra vez el mismo
// ejecutable con los mismos argumentos y en la misma carpeta.
namespace {
void relanzar() {
#if defined(_WIN32)
    // El proceso nuevo espera a que este termine del todo (ventana, audio,
    // puerto de depuracion y archivo de guardado liberados) antes de arrancar.
    poner_env("IE1_ESPERAR_PID", std::to_string(GetCurrentProcessId()));
    std::wstring cmd = GetCommandLineW();
    STARTUPINFOW si{};
    si.cb = sizeof(si);
    // El proceso nuevo sigue escribiendo en el mismo registro (ultima_sesion.log)
    // y, si este no tenia consola (lanzado desde el lanzador), tampoco abre una.
    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE), err = GetStdHandle(STD_ERROR_HANDLE);
    BOOL heredar = FALSE;
    if (out && out != INVALID_HANDLE_VALUE && err && err != INVALID_HANDLE_VALUE) {
        SetHandleInformation(out, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
        SetHandleInformation(err, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
        si.dwFlags = STARTF_USESTDHANDLES;
        si.hStdOutput = out; si.hStdError = err; si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        heredar = TRUE;
    }
    const DWORD flags = GetConsoleWindow() ? 0 : CREATE_NO_WINDOW;
    std::fflush(stdout); std::fflush(stderr);
    PROCESS_INFORMATION pi{};
    if (CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, heredar, flags, nullptr, nullptr, &si, &pi)) {
        // aviso para el lanzador: este es el juego que sigue (lo espera en vez de reaparecer)
        if (std::FILE* f = std::fopen("reinicio.pid", "w")) { std::fprintf(f, "%lu\n", (unsigned long)pi.dwProcessId); std::fclose(f); }
        CloseHandle(pi.hThread);
        CloseHandle(pi.hProcess);
    } else {
        std::fprintf(stderr, "[menu] no se pudo reiniciar (error %lu)\n", (unsigned long)GetLastError());
    }
#endif
}
}  // namespace
extern "C" void ie1_reiniciar_programa() {
    static bool hecho = false;
    if (hecho) return;
    hecho = true;
    // Las variables que vinieron de idiomas.cfg se quitan, para que el proceso
    // nuevo vuelva a leer el archivo (por si el idioma se cambio en el menu).
    for (const char* v : g_desde_cfg) poner_env(v, "");
    std::atexit(relanzar);
    std::fprintf(stderr, "[menu] reiniciando el programa\n");
}

static void ie1_aplicar_idiomas(std::vector<uint8_t>& rom) {
    const char* textos = std::getenv("IE1_TEXTOS");
    const char* voces = std::getenv("IE1_VOCES");
    if (vacio_o_en(textos) && vacio_o_en(voces)) return;
    if (rom.size() < 0x200u || std::memcmp(rom.data() + 0x0C, "YEEP", 4) != 0) {
        std::fprintf(stderr, "[idiomas] la ROM base no es la inglesa (YEEP); se ignora\n");
        return;
    }
    const char* d = std::getenv("IE1_IDIOMAS_DIR");
    std::filesystem::path dir = (d && *d) ? std::filesystem::path(d) : std::filesystem::path("idiomas");
    std::error_code ec;
    if (!std::filesystem::is_directory(dir, ec) && std::filesystem::is_directory("../idiomas", ec))
        dir = "../idiomas";                       // se juega desde run/ y los paquetes estan al lado
    std::fprintf(stderr, "[idiomas] carpeta de paquetes: %s\n",
                 std::filesystem::absolute(dir, ec).string().c_str());
    const uint32_t fnt_off = rd32(rom, 0x40), fnt_size = rd32(rom, 0x44);
    const uint32_t fat_off = rd32(rom, 0x48), fat_size = rd32(rom, 0x4C);
    if (uint64_t{fnt_off} + fnt_size > rom.size() || uint64_t{fat_off} + fat_size > rom.size()) return;

    // Ruta -> numero de archivo, recorriendo la tabla de nombres (FNT).
    std::map<std::string, uint32_t> fids;
    std::function<void(uint32_t, const std::string&, int)> recorrer =
        [&](uint32_t dir_id, const std::string& ruta, int prof) {
        if (prof > 32) return;
        const std::size_t ent = fnt_off + std::size_t(dir_id & 0xFFFu) * 8u;
        if (ent + 8 > std::size_t(fnt_off) + fnt_size) return;
        std::size_t p = fnt_off + rd32(rom, ent);
        uint32_t fid = uint32_t{rom[ent + 4]} | uint32_t{rom[ent + 5]} << 8;
        while (p < std::size_t(fnt_off) + fnt_size) {
            const uint8_t n = rom[p++];
            if (n == 0) break;
            const std::string nombre(reinterpret_cast<const char*>(&rom[p]), n & 0x7Fu);
            p += n & 0x7Fu;
            if (n & 0x80u) {
                const uint32_t sid = uint32_t{rom[p]} | uint32_t{rom[p + 1]} << 8;
                p += 2;
                recorrer(sid, ruta + nombre + "/", prof + 1);
            } else {
                fids[ruta + nombre] = fid++;
            }
        }
    };
    recorrer(0xF000u, "/", 0);

    uint64_t fin = 0;
    for (uint32_t i = 0; i < fat_size / 8u; ++i) fin = std::max<uint64_t>(fin, rd32(rom, fat_off + i * 8u + 4u));
    fin = (fin + 0x1FFu) & ~uint64_t{0x1FFu};

    unsigned cambiados = 0, faltan = 0, sitio = 0, final = 0;
    uint64_t bytes = 0;
    std::vector<uint8_t> datos;
    for (const auto& [ruta, fid] : fids) {
        if (ruta.find("/en/") == std::string::npos) continue;
        const bool sonido = ruta.find("/sound/en/") != std::string::npos;
        const char* idioma = sonido ? voces : textos;
        if (vacio_o_en(idioma)) continue;
        const std::filesystem::path p = dir / idioma / ruta.substr(1);
        if (!leer(p, datos)) { ++faltan; continue; }
        const std::size_t e = fat_off + std::size_t(fid) * 8u;
        const uint32_t s0 = rd32(rom, e), e0 = rd32(rom, e + 4);
        if (datos.size() <= uint64_t{e0} - s0) {            // cabe en su sitio
            std::memcpy(rom.data() + s0, datos.data(), datos.size());
            wr32(rom, e + 4, s0 + uint32_t(datos.size()));
            ++sitio;
        } else {                                             // al final de la imagen
            uint64_t need = fin + datos.size();
            if (need > rom.size()) {
                std::size_t n = rom.size();
                while (n < need) n <<= 1;                    // siempre potencia de dos
                rom.resize(n, 0xFFu);
            }
            std::memcpy(rom.data() + fin, datos.data(), datos.size());
            wr32(rom, e, uint32_t(fin));
            wr32(rom, e + 4, uint32_t(fin + datos.size()));
            fin = (need + 0x1FFu) & ~uint64_t{0x1FFu};
            ++final;
        }
        ++cambiados;
        bytes += datos.size();
    }
    std::fprintf(stderr,
        "[idiomas] textos=%s voces=%s: %u archivos sustituidos (%.1f MB; %u en su sitio, %u al final), "
        "%u sin archivo en el paquete (iguales al ingles o no encontrados); imagen del cartucho %zu MB\n",
        vacio_o_en(textos) ? "en" : textos, vacio_o_en(voces) ? "en" : voces,
        cambiados, double(bytes) / 1048576.0, sitio, final, faltan, rom.size() >> 20);
}
// ---- Complemento de mods (ie1_mods.dll, opcional) ---------------------------
// Si ie1_mods.dll esta junto al ejecutable, se le deja aplicar los mods activos
// sobre la imagen del cartucho (despues del idioma). Si no esta, no hay mods.
struct Ie1ModsHost {
    uint32_t version;
    void* ctx;
    uint8_t* (*datos)(void* ctx);
    size_t (*tamano)(void* ctx);
    int (*redimensionar)(void* ctx, size_t minimo);
    void (*log)(const char* texto);
};
namespace {
uint8_t* host_datos(void* c) { return static_cast<std::vector<uint8_t>*>(c)->data(); }
size_t host_tamano(void* c) { return static_cast<std::vector<uint8_t>*>(c)->size(); }
int host_redimensionar(void* c, size_t minimo) {
    auto* v = static_cast<std::vector<uint8_t>*>(c);
    size_t n = v->size() ? v->size() : 1;
    while (n < minimo) n <<= 1;                  // siempre potencia de dos
    if (n > (size_t{1} << 30)) return 0;
    v->resize(n, 0xFFu);
    return 1;
}
void host_log(const char* t) { std::fprintf(stderr, "%s\n", t); }
constexpr int kMaxMods = 6;
bool g_mods_hay = false;
int g_mods_n = 0;
char g_mods_nombres[kMaxMods][64];
int g_mods_activos[kMaxMods];
using FnGuardar = void (*)(const char (*)[64], const int*, int);
FnGuardar g_mods_guardar = nullptr;
// Trucos (Action Replay) de los mods, una vez por fotograma
struct Ie1ModsMem {
    uint32_t version;   // 2: con copia rapida de memoria
    uint32_t (*r32)(uint32_t); uint16_t (*r16)(uint32_t); uint8_t (*r8)(uint32_t);
    void (*w32)(uint32_t, uint32_t); void (*w16)(uint32_t, uint16_t); void (*w8)(uint32_t, uint8_t);
    int (*copiar)(uint32_t, uint8_t*, uint32_t);   // copia un bloque de memoria del ARM9
};
using FnFotograma = void (*)(const Ie1ModsMem*);
FnFotograma g_mods_fotograma = nullptr;
// Menu propio de los mods dibujado sobre las pantallas (entrenamiento libre)
using FnInt = int (*)();
using FnVoid = void (*)();
using FnTeclas = void (*)(uint16_t);
using FnDibujar = int (*)(const uint32_t*, int, const uint32_t*, int, const uint32_t**, const uint32_t**);
FnInt g_ov_disponible = nullptr, g_ov_activo = nullptr;
FnVoid g_ov_alternar = nullptr;
FnTeclas g_ov_teclas = nullptr;
FnDibujar g_ov_dibujar = nullptr;
using FnToque = void (*)(int, int, int);
FnToque g_ov_toque = nullptr;
void ie1_mods_cargar(std::vector<uint8_t>& rom) {
#if defined(_WIN32)
    wchar_t exe[MAX_PATH];
    const DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return;
    const std::filesystem::path dll = std::filesystem::path(exe).parent_path() / L"ie1_mods.dll";
    std::error_code ec;
    if (!std::filesystem::exists(dll, ec)) return;           // sin complemento: sin mods
    HMODULE h = LoadLibraryW(dll.c_str());
    if (!h) { std::fprintf(stderr, "[mods] no se pudo cargar ie1_mods.dll\n"); return; }
    using Fn = int (*)(const Ie1ModsHost*);
    auto fn = reinterpret_cast<Fn>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_componer_v1")));
    if (!fn) { std::fprintf(stderr, "[mods] ie1_mods.dll no es compatible\n"); return; }
    const Ie1ModsHost host{1, &rom, host_datos, host_tamano, host_redimensionar, host_log};
    fn(&host);
    // Lista para el menu de Esc (seccion Mods)
    using FnLista = int (*)(char (*)[64], int*, int);
    if (auto lista = reinterpret_cast<FnLista>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_lista_v1")))) {
        g_mods_n = lista(g_mods_nombres, g_mods_activos, kMaxMods);
        g_mods_guardar = reinterpret_cast<FnGuardar>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_guardar_v1")));
        g_mods_hay = true;
    }
    g_ov_disponible = reinterpret_cast<FnInt>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_disponible_v1")));
    g_ov_activo = reinterpret_cast<FnInt>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_activo_v1")));
    g_ov_alternar = reinterpret_cast<FnVoid>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_alternar_v1")));
    g_ov_teclas = reinterpret_cast<FnTeclas>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_teclas_v1")));
    g_ov_dibujar = reinterpret_cast<FnDibujar>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_dibujar_v1")));
    g_ov_toque = reinterpret_cast<FnToque>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_toque_v1")));
    if (!(g_ov_disponible && g_ov_activo && g_ov_alternar && g_ov_teclas && g_ov_dibujar))
        g_ov_disponible = nullptr;
    // Se llama cada fotograma aunque no haya trucos: tambien da al complemento
    // el acceso a la memoria del juego que usa su menu (entrenamiento libre).
    g_mods_fotograma = reinterpret_cast<FnFotograma>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_fotograma_v1")));
#else
    (void)rom;
#endif
}
}  // namespace

void ie1_idiomas_componer(std::vector<uint8_t>& rom) {
    ie1_idiomas_cargar_cfg();
    ie1_aplicar_idiomas(rom);
    ie1_mods_cargar(rom);
}

// Trucos de los mods: el frontend lo llama una vez por fotograma (parche_trucos.py)
extern "C" void ie1_mods_fotograma() {
    if (!g_mods_fotograma) return;
    static const Ie1ModsMem mem{2,
        [](uint32_t a) -> uint32_t { return bus_read_u32(a); },
        [](uint32_t a) -> uint16_t { return bus_read_u16(a); },
        [](uint32_t a) -> uint8_t { return bus_read_u8(a); },
        [](uint32_t a, uint32_t v) { bus_write_u32(a, v); },
        [](uint32_t a, uint16_t v) { bus_write_u16(a, v); },
        [](uint32_t a, uint8_t v) { bus_write_u8(a, v); },
        [](uint32_t a, uint8_t* d, uint32_t n) -> int {   // copia por palabras (sin depender de otras APIs)
            for (uint32_t i = 0; i + 4 <= n; i += 4) {
                const uint32_t v = bus_read_u32(a + i);
                std::memcpy(d + i, &v, 4);
            }
            return 1;
        }};
    g_mods_fotograma(&mem);
}

// Menu propio de los mods (parche_overlay.py)
extern "C" int ie1_overlay_disponible() { return g_ov_disponible && g_ov_disponible() ? 1 : 0; }
extern "C" int ie1_overlay_activo() { return g_ov_disponible && g_ov_activo() ? 1 : 0; }
extern "C" void ie1_overlay_alternar() { if (ie1_overlay_disponible()) g_ov_alternar(); }
extern "C" void ie1_overlay_teclas(uint16_t pulsados) { if (g_ov_disponible) g_ov_teclas(pulsados); }
extern "C" void ie1_overlay_toque(int x, int y, int abajo) { if (g_ov_disponible && g_ov_toque) g_ov_toque(x, y, abajo); }
extern "C" int ie1_overlay_dibujar(const uint32_t* a, int aw, const uint32_t* b, int bw,
                                   const uint32_t** sa, const uint32_t** sb) {
    return g_ov_disponible ? g_ov_dibujar(a, aw, b, bw, sa, sb) : 0;
}

// API para el menu de Esc (parche_menu_mods.py)
extern "C" int ie1_mods_hay() { return g_mods_hay ? 1 : 0; }
extern "C" int ie1_mods_num() { return g_mods_n; }
extern "C" const char* ie1_mods_nombre(int i) { return (i >= 0 && i < g_mods_n) ? g_mods_nombres[i] : ""; }
extern "C" int ie1_mods_activo(int i) { return (i >= 0 && i < g_mods_n) ? g_mods_activos[i] : 0; }
extern "C" void ie1_mods_cambiar(int i, int activo) {
    if (i < 0 || i >= g_mods_n) return;
    g_mods_activos[i] = activo ? 1 : 0;
    if (g_mods_guardar) g_mods_guardar(g_mods_nombres, g_mods_activos, g_mods_n);
    std::fprintf(stderr, "[mods] '%s' %s (se aplica al reiniciar)\n", g_mods_nombres[i],
                 activo ? "activado" : "desactivado");
}

'''

def leer(p):
    s = open(p, encoding="utf-8", newline="").read()
    return s, ("\r\n" if "\r\n" in s else "\n")

def main():
    open(os.path.join(ROOT, "src", "ie1_idiomas.cpp"), "w", encoding="utf-8").write(FUENTE)
    print("escrito src/ie1_idiomas.cpp")
    p = os.path.join(ROOT, "src", "io.cpp")
    s, nl = leer(p)
    if "IE1_IDIOMAS" in s:
        print("io.cpp ya estaba modificado")
    else:
        a = "    g_card_rom.assign(rom, rom + rom_size);" + nl
        d = "bool nds_io_load_cartridge(const uint8_t* rom, uint32_t rom_size,"
        if s.count(a) != 1 or s.count(d) != 1:
            sys.exit("io.cpp no tiene la forma esperada; no toco nada.")
        s = s.replace(a, a + "    ie1_idiomas_componer(g_card_rom);  // IE1_IDIOMAS" + nl)
        s = s.replace(d, "void ie1_idiomas_componer(std::vector<uint8_t>& rom);  // IE1_IDIOMAS" + nl + d)
        open(p, "w", encoding="utf-8", newline="").write(s)
        print("modificado src/io.cpp")
    p = os.path.join(ROOT, "CMakeLists.txt")
    s, nl = leer(p)
    if "IE1_IDIOMAS" in s:
        print("CMakeLists.txt ya estaba modificado")
    else:
        a = 'message(STATUS "IE1 card implementation: ${NDS_IE1_CARD_IMPLEMENTATION}")'
        if s.count(a) != 1:
            sys.exit("CMakeLists.txt no tiene la opcion del HLE de Inazuma; ejecuta antes integrar_hle_cartucho.py")
        s = s.replace(a, a + nl + "target_sources(nds_runner PRIVATE src/ie1_idiomas.cpp)  # IE1_IDIOMAS")
        open(p, "w", encoding="utf-8", newline="").write(s)
        print("modificado CMakeLists.txt")
    print("Listo. Compila con: bash scripts/paso_mingw.sh")

if __name__ == "__main__":
    main()
