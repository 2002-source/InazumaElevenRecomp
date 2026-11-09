// ============================================================================
//  Lanzador de Inazuma Eleven (port) - nucleo sin SDL
//  Dibuja las pantallas en un bufer ARGB de kAncho x kAlto y gestiona los menus:
//  Jugar / Mods / Opciones / Salir. La parte SDL (lanzador.cpp) solo sube el
//  bufer a una textura, pasa los eventos y lanza el juego.
// ============================================================================
#pragma once
#include <algorithm>
#include <array>
#include <sstream>
#include <cstdlib>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace lanz {
namespace fs = std::filesystem;

constexpr int kAncho = 400, kAlto = 225;   // 16:9, se escala sin suavizado

// ---------------------------------------------------------------- utilidades --
inline bool leer(const fs::path& p, std::vector<uint8_t>& v) {
    std::ifstream f(p, std::ios::binary);
    if (!f) return false;
    v.assign(std::istreambuf_iterator<char>(f), {});
    return true;
}
inline std::string recortar(std::string s) {
    while (!s.empty() && (s.back() == '\r' || s.back() == '\n' || s.back() == ' ' || s.back() == '\t')) s.pop_back();
    size_t i = 0;
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t')) ++i;
    return s.substr(i);
}
// archivo clave=valor
inline std::map<std::string, std::string> leer_cfg(const fs::path& p) {
    std::map<std::string, std::string> m;
    std::ifstream f(p);
    for (std::string l; std::getline(f, l);) {
        l = recortar(l);
        if (l.empty() || l[0] == '#' || l[0] == ';' || l[0] == '[') continue;
        const size_t e = l.find('=');
        if (e != std::string::npos) m[recortar(l.substr(0, e))] = recortar(l.substr(e + 1));
    }
    return m;
}
inline void guardar_cfg(const fs::path& p, const std::vector<std::pair<std::string, std::string>>& kv,
                        const char* cabecera) {
    std::ofstream f(p);
    if (cabecera) f << cabecera << "\n";
    for (const auto& e : kv) f << e.first << "=" << e.second << "\n";
}

// ------------------------------------------------------------- archivos ROM --
struct Rom {
    std::vector<uint8_t> d;          // cabecera, FNT y FAT (no hace falta la ROM entera)
    fs::path ruta_rom;               // para leer del disco los archivos que caen fuera de d
    // Carga solo la parte de la ROM con los indices de archivos
    bool abrir(const fs::path& p) {
        ruta_rom = p;
        std::ifstream f(p, std::ios::binary);
        if (!f) return false;
        d.resize(0x200);
        f.read(reinterpret_cast<char*>(d.data()), 0x200);
        if (f.gcount() != 0x200) return false;
        const uint64_t fin = std::max<uint64_t>(uint64_t(u32(0x40)) + u32(0x44), uint64_t(u32(0x48)) + u32(0x4C));
        if (fin > 64ull * 1024 * 1024) return false;
        d.resize(size_t(fin));
        f.seekg(0);
        f.read(reinterpret_cast<char*>(d.data()), std::streamsize(fin));
        return true;
    }
    uint32_t u32(size_t o) const { return o + 4 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8 | d[o + 2] << 16 | uint32_t(d[o + 3]) << 24) : 0; }
    uint32_t u16(size_t o) const { return o + 2 <= d.size() ? uint32_t(d[o] | d[o + 1] << 8) : 0; }
    // Devuelve el contenido de un archivo de la ROM por su ruta ("/data_iz/font/FONT12T.NFTR")
    bool archivo(const std::string& ruta, std::vector<uint8_t>& out) const {
        if (d.size() < 0x200) return false;
        const uint32_t fnt = u32(0x40), fat = u32(0x48);
        uint32_t dir = 0xF000;
        size_t pos = 1;
        while (true) {
            const size_t barra = ruta.find('/', pos);
            const std::string parte = ruta.substr(pos, barra == std::string::npos ? std::string::npos : barra - pos);
            const bool ultimo = barra == std::string::npos;
            const size_t ent = fnt + size_t(dir & 0xFFF) * 8;
            size_t p = fnt + u32(ent);
            uint32_t fid = u16(ent + 4);
            bool hallado = false;
            while (p < d.size()) {
                const uint8_t n = d[p++];
                if (!n) break;
                const std::string nom(reinterpret_cast<const char*>(&d[p]), n & 0x7F);
                p += n & 0x7F;
                if (n & 0x80) {
                    const uint32_t sid = u16(p); p += 2;
                    if (!ultimo && nom == parte) { dir = sid; hallado = true; break; }
                } else {
                    if (ultimo && nom == parte) {
                        const uint32_t s = u32(fat + size_t(fid) * 8), e = u32(fat + size_t(fid) * 8 + 4);
                        if (e < s) return false;
                        if (e <= d.size()) { out.assign(d.begin() + s, d.begin() + e); return true; }
                        std::ifstream f(ruta_rom, std::ios::binary);
                        if (!f) return false;
                        out.resize(e - s);
                        f.seekg(s);
                        f.read(reinterpret_cast<char*>(out.data()), std::streamsize(out.size()));
                        return f.gcount() == std::streamsize(out.size());
                    }
                    ++fid;
                }
            }
            if (!hallado) return false;
            pos = barra + 1;
        }
    }
};

// ------------------------------------------------------- fuente del juego --
struct Fuente {
    std::vector<uint8_t> v;
    int cw = 0, ch = 0, bpg = 0, bpp = 1, gl = 0, wfirst = 0, wlast = -1, wd = 0;
    std::map<int, int> mapa;
    int u16(size_t o) const { return v[o] | v[o + 1] << 8; }
    uint32_t u32(size_t o) const { return v[o] | v[o + 1] << 8 | v[o + 2] << 16 | uint32_t(v[o + 3]) << 24; }
    bool ok() const { return cw > 0; }
    void cargar(std::vector<uint8_t> datos) {
        v = std::move(datos); cw = 0; mapa.clear();
        if (v.size() < 0x20 || std::memcmp(v.data(), "RTFN", 4)) return;
        for (size_t o = 0x10; o + 8 <= v.size();) {
            const uint32_t sz = u32(o + 4);
            if (!std::memcmp(&v[o], "PLGC", 4)) { cw = v[o + 8]; ch = v[o + 9]; bpg = u16(o + 10); bpp = v[o + 14]; gl = int(o + 16); }
            else if (!std::memcmp(&v[o], "HDWC", 4)) { wfirst = u16(o + 8); wlast = u16(o + 10); wd = int(o + 16); }
            else if (!std::memcmp(&v[o], "PAMC", 4)) {
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
    void ancho(int g, int& iz, int& av) const {
        if (g >= wfirst && g <= wlast) { const size_t o = size_t(wd) + 3 * size_t(g - wfirst); iz = int8_t(v[o]); av = v[o + 2]; }
        else { iz = 0; av = cw; }
    }
    int pixel(int g, int x, int y) const {
        const size_t bit = size_t(y * cw + x) * size_t(bpp), o = size_t(gl) + size_t(g) * size_t(bpg) + bit / 8;
        return o < v.size() ? (v[o] >> (8 - bpp - int(bit % 8))) & ((1 << bpp) - 1) : 0;
    }
};

// Texto propio (UTF-8) -> codificacion del juego (tabla 0xA1-0xDF de sus fuentes)
inline std::string juego(const std::string& utf8) {
    static const struct { const char* u; char g; } k[] = {
        {"\xC3\xA1", '\xB2'}, {"\xC3\xA9", '\xBA'}, {"\xC3\xAD", '\xBE'}, {"\xC3\xB3", '\xC4'},
        {"\xC3\xBA", '\xCA'}, {"\xC3\xB1", '\xC2'}, {"\xC3\x91", '\xA9'}, {"\xC3\xBC", '\xCC'},
        {"\xC3\x81", '\xD1'}, {"\xC3\x89", '\xD9'}, {"\xC3\x8D", '\xA6'}, {"\xC3\x93", '\xAB'},
        {"\xC3\x9A", '\xA2'}, {"\xC2\xBF", '\xA5'}, {"\xC2\xA1", '\xDF'}};
    std::string r;
    for (size_t i = 0; i < utf8.size();) {
        bool hecho = false;
        for (const auto& e : k)
            if (!utf8.compare(i, 2, e.u)) { r += e.g; i += 2; hecho = true; break; }
        if (hecho) continue;
        if ((unsigned char)utf8[i] >= 0x80) { ++i; continue; }
        r += utf8[i++];
    }
    return r;
}

// ----------------------------------------------------------------- textos --
struct Textos {
    std::string jugar, mods, opciones, salir, volver, modo, rendimiento, normal, vsync, si, no,
        controles, pulsa_tecla, sin_mods, cambios_al_jugar, guardado, por_defecto, idioma,
        voces, pantalla, ventana, completa, tamano, disposicion, vertical, horizontal, escalado, llenar, entero,
        ayuda_info, sin_info, cerrar_info, activar, desactivar, activo_si, activo_no,
        jugar_red, rol, anfitrion, invitado, ip_rival, sin_ip, puerto, conectar, ayuda_red, escribe_ip, falta_ip;
    std::vector<std::string> botones_ds;
};
inline Textos textos_para(const std::string& lang) {
    Textos t;
    if (lang == "es") {
        t = {"Jugar", "Mods", "Opciones", "Salir", "Volver", "Modo", "Rendimiento", "Normal", "VSync", "Sí", "No",
             "Controles", "Pulsa una tecla... (Esc: cancelar)", "No hay mods en la carpeta mods",
             "Los cambios se aplican al jugar", "Guardado", "Restablecer controles", "Idioma",
             "Voces", "Pantalla", "Ventana", "Completa", "Tamaño", "Disposición", "Vertical", "Horizontal",
             "Escalado", "Llenar", "Entero",
             "Intro o clic: información del mod", "Este mod no tiene descripción.", "Pulsa cualquier tecla para cerrar",
             "Activar", "Desactivar", "Estado: activado", "Estado: desactivado",
             "Jugar en red", "Jugador", "1 (anfitrión)", "2 (invitado)", "IP del otro PC", "sin poner",
             "Puerto", "Conectar y jugar", "Misma red o Radmin VPN / ZeroTier. Cortafuegos: Permitir",
             "Escribe la IP y pulsa Intro", "Falta la IP del otro PC"};
        t.botones_ds = {"A", "B", "Select", "Start", "Derecha", "Izquierda", "Arriba", "Abajo", "R", "L", "X", "Y"};
    } else {
        t = {"Play", "Mods", "Options", "Quit", "Back", "Mode", "Performance", "Normal", "VSync", "On", "Off",
             "Controls", "Press a key... (Esc: cancel)", "No mods in the mods folder",
             "Changes apply when you play", "Saved", "Reset controls", "Language",
             "Voices", "Screen", "Window", "Fullscreen", "Size", "Layout", "Vertical", "Horizontal",
             "Scaling", "Fill", "Integer",
             "Enter or click: mod information", "This mod has no description.", "Press any key to close",
             "Turn on", "Turn off", "Status: on", "Status: off",
             "Play over network", "Player", "1 (host)", "2 (guest)", "Other PC's IP", "not set",
             "Port", "Connect and play", "Same network or Radmin VPN / ZeroTier. Firewall: Allow",
             "Type the IP and press Enter", "The other PC's IP is missing"};
        t.botones_ds = {"A", "B", "Select", "Start", "Right", "Left", "Up", "Down", "R", "L", "X", "Y"};
    }
    return t;
}
inline std::string nombre_idioma(const std::string& c, const std::string& ui) {
    static const std::map<std::string, std::pair<const char*, const char*>> k = {
        {"en", {"Inglés", "English"}}, {"es", {"Español", "Spanish"}}, {"fr", {"Francés", "French"}},
        {"ge", {"Alemán", "German"}}, {"de", {"Alemán", "German"}}, {"it", {"Italiano", "Italian"}},
        {"jp", {"Japonés", "Japanese"}}, {"ja", {"Japonés", "Japanese"}}};
    const auto it = k.find(c);
    if (it == k.end()) return c;
    return ui == "es" ? it->second.first : it->second.second;
}
// claves de controles.cfg (las lee el runner) y teclas por defecto (nombres SDL)
inline const std::vector<std::string>& claves_ds() {
    static const std::vector<std::string> k = {"A", "B", "SELECT", "START", "DERECHA", "IZQUIERDA", "ARRIBA", "ABAJO", "R", "L", "X", "Y"};
    return k;
}
inline const std::vector<std::string>& teclas_defecto() {
    static const std::vector<std::string> k = {"Z", "X", "Backspace", "Return", "Right", "Left", "Up", "Down", "W", "Q", "S", "A"};
    return k;
}

// ------------------------------------------------------------------- UI --
enum class Accion { Nada, Jugar, JugarRed, Salir };
enum class Tecla { Arriba, Abajo, Izquierda, Derecha, Aceptar, Atras, Info };

struct Mod { std::string carpeta, nombre, info; bool activo = false; };

class Lanzador {
public:
    uint32_t px[kAncho * kAlto] = {};
    // configuracion (rutas resueltas por la parte SDL)
    fs::path datos, mods_dir;
    std::string idioma = "en";
    std::string modo = "performance";
    bool vsync = false;
    // juego en red (Wi-Fi local entre PC): 0 = jugador 1 (anfitrion), 1 = jugador 2
    int red_rol = 0, red_puerto = 7030;
    std::string red_ip;
    bool editando_ip = false;
    std::vector<std::string> teclas;               // una por boton DS
    bool capturando = false;                       // esperando una tecla para remapear
    fs::path idiomas_dir;                          // paquetes de idioma (subcarpetas)
    std::vector<std::string> idiomas_disp;         // "en" + paquetes instalados
    std::string voces = "en";
    // pantalla (ie1_menu.cfg, el mismo archivo que el menu Esc del juego)
    int pant_completa = 0, tamano = 1, horizontal = 0, llenar = 1, ranura = 1;

    void iniciar(const Rom& rom) {
        std::vector<uint8_t> f;
        if (rom.archivo("/data_iz/font/FONT12T.NFTR", f)) fuente_.cargar(std::move(f));
        const auto idi = leer_cfg(datos / "idiomas.cfg");
        if (idi.count("textos")) idioma = idi.at("textos");
        if (idi.count("voces")) voces = idi.at("voces");
        t_ = textos_para(idioma);
        idiomas_disp = {"en"};
        std::error_code ec;
        for (const auto& e : fs::directory_iterator(idiomas_dir, ec))
            if (e.is_directory() && e.path().filename().string() != "en") idiomas_disp.push_back(e.path().filename().string());
        std::sort(idiomas_disp.begin() + 1, idiomas_disp.end());
        for (const std::string* c : {&idioma, &voces})
            if (std::find(idiomas_disp.begin(), idiomas_disp.end(), *c) == idiomas_disp.end()) idiomas_disp.push_back(*c);
        const auto pan = leer_cfg(datos / "ie1_menu.cfg");
        auto ent = [&](const char* k, int& v) { if (pan.count(k)) v = std::atoi(pan.at(k).c_str()); };
        ent("pantalla_completa", pant_completa); ent("tamano", tamano); ent("horizontal", horizontal);
        ent("llenar", llenar); ent("ranura", ranura);
        const auto cfg = leer_cfg(datos / "lanzador.cfg");
        if (cfg.count("modo")) modo = cfg.at("modo");
        if (cfg.count("vsync")) vsync = cfg.at("vsync") == "1";
        if (cfg.count("red_rol")) red_rol = std::atoi(cfg.at("red_rol").c_str()) ? 1 : 0;
        if (cfg.count("red_ip")) red_ip = cfg.at("red_ip");
        if (cfg.count("red_puerto")) red_puerto = std::clamp(std::atoi(cfg.at("red_puerto").c_str()), 1024, 65000);
        teclas = teclas_defecto();
        const auto ctl = leer_cfg(datos / "controles.cfg");
        for (size_t i = 0; i < claves_ds().size(); ++i)
            if (ctl.count(claves_ds()[i])) teclas[i] = ctl.at(claves_ds()[i]);
        cargar_mods();
    }
    Accion tecla(Tecla k) {
        if (capturando) { if (k == Tecla::Atras) capturando = false; return Accion::Nada; }
        if (!info_.empty()) { info_.clear(); return Accion::Nada; }       // cerrar la informacion
        if (k == Tecla::Info) {                       // Tab o I: ficha del mod (igual que Intro)
            if (pantalla_ == P::Mods && sel_ < int(mods_.size())) return aceptar();
            return Accion::Nada;
        }
        const int n = int(opciones_actuales().size());
        if (pantalla_ == P::ModInfo && (k == Tecla::Arriba || k == Tecla::Abajo)) {   // leer el texto largo
            info_scroll_ = std::clamp(info_scroll_ + (k == Tecla::Abajo ? 1 : -1), 0, info_max_);
            return Accion::Nada;
        }
        switch (k) {
            case Tecla::Arriba: sel_ = (sel_ + n - 1) % n; break;
            case Tecla::Abajo: sel_ = (sel_ + 1) % n; break;
            case Tecla::Info: break;
            case Tecla::Izquierda: case Tecla::Derecha:
                if (pantalla_ == P::ModInfo) sel_ = (sel_ + 1) % n;   // botones en fila
                else cambiar(k == Tecla::Derecha ? 1 : -1);
                break;
            case Tecla::Aceptar: return aceptar();
            case Tecla::Atras:
                if (pantalla_ != P::Principal) { volver(); } else return Accion::Salir;
                break;
        }
        return Accion::Nada;
    }
    Accion clic(int x, int y) {
        if (capturando) return Accion::Nada;
        if (!info_.empty()) { info_.clear(); return Accion::Nada; }
        const auto ops = opciones_actuales();
        for (int i = 0; i < int(ops.size()); ++i) {
            const auto r = caja(i, int(ops.size()));
            if (x >= r[0] && x < r[0] + r[2] && y >= r[1] && y < r[1] + r[3]) { sel_ = i; return aceptar(); }
        }
        return Accion::Nada;
    }
    // clic derecho: en la lista de mods abre su informacion; en lo demas, "volver"
    Accion clic_derecho(int x, int y) {
        if (capturando) return Accion::Nada;
        if (!info_.empty()) { info_.clear(); return Accion::Nada; }
        if (pantalla_ == P::Mods) {
            const auto ops = opciones_actuales();
            for (int i = 0; i < int(ops.size()) && i < int(mods_.size()); ++i) {
                const auto r = caja(i, int(ops.size()));
                if (x >= r[0] && x < r[0] + r[2] && y >= r[1] && y < r[1] + r[3]) { sel_ = i; return aceptar(); }
            }
        }
        return tecla(Tecla::Atras);
    }
    void rueda(int pasos) {             // rueda del raton: en la ficha, desplaza el texto
        if (pantalla_ == P::ModInfo) info_scroll_ = std::clamp(info_scroll_ - pasos, 0, info_max_);
    }
    void raton(int x, int y) {          // resaltar al pasar por encima
        if (capturando || !info_.empty()) return;
        const auto ops = opciones_actuales();
        for (int i = 0; i < int(ops.size()); ++i) {
            const auto r = caja(i, int(ops.size()));
            if (x >= r[0] && x < r[0] + r[2] && y >= r[1] && y < r[1] + r[3]) sel_ = i;
        }
    }
    // tecla capturada para remapear (nombre SDL); devuelve true si se uso
    bool capturar(const std::string& nombre) {
        if (!capturando) return false;
        capturando = false;
        if (cap_idx_ >= 0 && cap_idx_ < int(teclas.size()) && !nombre.empty()) { teclas[size_t(cap_idx_)] = nombre; guardar(); }
        return true;
    }
    void dibujar();
    void guardar() {
        guardar_cfg(datos / "lanzador.cfg", {{"modo", modo}, {"vsync", vsync ? "1" : "0"},
                    {"red_rol", std::to_string(red_rol)}, {"red_ip", red_ip},
                    {"red_puerto", std::to_string(red_puerto)}}, "# Ajustes del lanzador");
        std::vector<std::pair<std::string, std::string>> kv;
        for (size_t i = 0; i < claves_ds().size(); ++i) kv.push_back({claves_ds()[i], teclas[i]});
        guardar_cfg(datos / "controles.cfg", kv, "# Teclado -> botones de la DS (nombres de tecla de SDL). Lo lee el juego.");
        guardar_cfg(datos / "idiomas.cfg", {{"textos", idioma}, {"voces", voces}}, nullptr);
        guardar_cfg(datos / "ie1_menu.cfg", {{"pantalla_completa", std::to_string(pant_completa)},
                    {"tamano", std::to_string(tamano)}, {"horizontal", std::to_string(horizontal)},
                    {"llenar", std::to_string(llenar)}, {"ranura", std::to_string(ranura)}}, nullptr);
        aviso_ = 90; aviso_texto_.clear();
    }
    std::string titulo_ventana() const { return "Inazuma Eleven"; }

private:
    enum class P { Principal, Mods, Opciones, Controles, ModInfo, Red } pantalla_ = P::Principal;
    int sel_ = 0, cap_idx_ = -1, aviso_ = 0, desplaz_ = 0, mod_sel_ = 0;
    std::string aviso_texto_;          // aviso del pie (vacio = "Guardado")
    int info_scroll_ = 0, info_max_ = 0;   // desplazamiento del texto de la ficha (lineas)
    Fuente fuente_;
    Textos t_ = textos_para("en");
    std::vector<Mod> mods_;
    std::string info_;                  // cuadro de informacion del mod (vacio = cerrado)

    void volver() {
        if (pantalla_ == P::ModInfo) { pantalla_ = P::Mods; sel_ = mod_sel_; return; }   // de la ficha del mod a la lista
        const P antes = pantalla_;
        pantalla_ = (pantalla_ == P::Controles) ? P::Opciones : P::Principal;
        sel_ = antes == P::Red ? 1 : antes == P::Mods ? 2 : antes == P::Opciones ? 3 : antes == P::Controles ? 8 : 0;
        editando_ip = false;
        desplaz_ = 0;
    }
    void cargar_mods() {
        mods_.clear();
        std::vector<std::string> activos;
        {
            std::ifstream f(mods_dir / "mods.cfg");
            for (std::string l; std::getline(f, l);) { l = recortar(l); if (!l.empty() && l[0] != '#') activos.push_back(l); }
        }
        std::error_code ec;
        for (const auto& e : fs::directory_iterator(mods_dir, ec)) {
            if (!e.is_directory()) continue;
            Mod m; m.carpeta = e.path().filename().string(); m.nombre = m.carpeta;
            const auto info = leer_cfg(e.path() / "mod.txt");
            // mod.txt: nombre, descripcion y desbloqueo (en espanol) y sus versiones _en
            const bool es = idioma == "es";
            auto campo = [&](const std::string& k) {
                if (!es && info.count(k + "_en")) return info.at(k + "_en");
                return info.count(k) ? info.at(k) : std::string();
            };
            if (!campo("nombre").empty()) m.nombre = campo("nombre");
            m.info = campo("descripcion");
            const std::string desb = campo("desbloqueo");
            if (!desb.empty()) m.info += (m.info.empty() ? "" : "\n\n") + std::string(es ? "Cómo se consigue: " : "How to get it: ") + desb;
            m.activo = std::find(activos.begin(), activos.end(), m.carpeta) != activos.end();
            mods_.push_back(m);
        }
        std::sort(mods_.begin(), mods_.end(), [&](const Mod& a, const Mod& b) {
            const auto ia = std::find(activos.begin(), activos.end(), a.carpeta), ib = std::find(activos.begin(), activos.end(), b.carpeta);
            if (ia != ib) return ia < ib;
            return a.carpeta < b.carpeta;
        });
    }
    void guardar_mods() {
        std::ofstream f(mods_dir / "mods.cfg");
        f << "# Un mod activo por linea, en orden (el ultimo gana)\n";
        for (const auto& m : mods_) if (m.activo) f << m.carpeta << "\n";
        aviso_ = 90; aviso_texto_.clear();
    }
    std::vector<std::string> opciones_actuales() const {
        switch (pantalla_) {
            case P::Principal: return {t_.jugar, t_.jugar_red, t_.mods, t_.opciones, t_.salir};
            case P::Red:
                return {t_.rol + ": " + (red_rol ? t_.invitado : t_.anfitrion),
                        t_.ip_rival + ": " + (editando_ip ? red_ip + "_" : (red_ip.empty() ? t_.sin_ip : red_ip)),
                        t_.puerto + ": " + std::to_string(red_puerto) + (red_rol ? " / " + std::to_string(red_puerto + 1) : ""),
                        t_.conectar, t_.volver};
            case P::Mods: {
                std::vector<std::string> v;
                for (const auto& m : mods_) v.push_back((m.activo ? "[x] " : "[ ] ") + m.nombre);
                v.push_back(t_.volver);
                return v;
            }
            case P::Opciones: {
                static const char* kTam[] = {"480p", "720p", "1080p"};
                return {t_.idioma + ": " + nombre_idioma(idioma, idioma),
                        t_.voces + ": " + nombre_idioma(voces, idioma),
                        t_.pantalla + ": " + (pant_completa ? t_.completa : t_.ventana),
                        t_.tamano + ": " + kTam[std::clamp(tamano, 0, 2)],
                        t_.disposicion + ": " + (horizontal ? t_.horizontal : t_.vertical),
                        t_.escalado + ": " + (llenar ? t_.llenar : t_.entero),
                        t_.modo + ": " + (modo == "performance" ? t_.rendimiento : t_.normal),
                        t_.vsync + ": " + (vsync ? t_.si : t_.no), t_.controles, t_.volver};
            }
            case P::ModInfo:
                if (mod_sel_ >= int(mods_.size())) return {t_.volver};
                return {mods_[size_t(mod_sel_)].activo ? t_.desactivar : t_.activar, t_.volver};
            case P::Controles: {
                std::vector<std::string> v;
                for (size_t i = 0; i < t_.botones_ds.size(); ++i) v.push_back(t_.botones_ds[i] + ": " + teclas[i]);
                v.push_back(t_.por_defecto);
                v.push_back(t_.volver);
                return v;
            }
        }
        return {};
    }
public:
    // escribir la IP (solo con "IP del otro PC" en modo edicion)
    bool escribiendo() const { return pantalla_ == P::Red && editando_ip; }
    void escribir(char c) {
        if (!escribiendo()) return;
        if (((c >= '0' && c <= '9') || c == '.') && red_ip.size() < 15) red_ip += c;
    }
    void borrar() { if (escribiendo() && !red_ip.empty()) red_ip.pop_back(); }
private:
    void cambiar(int dir) {
        if (pantalla_ == P::Red) {
            if (sel_ == 0) { red_rol = 1 - red_rol; guardar(); }
            if (sel_ == 2) { red_puerto = std::clamp(red_puerto + dir * 10, 1024, 65000); guardar(); }
            return;
        }
        if (pantalla_ == P::Opciones) {
            auto ciclo = [&](std::string& v) {
                auto it = std::find(idiomas_disp.begin(), idiomas_disp.end(), v);
                const int n = int(idiomas_disp.size()), i = it == idiomas_disp.end() ? 0 : int(it - idiomas_disp.begin());
                v = idiomas_disp[size_t((i + dir + n) % n)];
            };
            switch (sel_) {
                case 0: ciclo(idioma); t_ = textos_para(idioma); cargar_mods(); break;   // el lanzador tambien cambia de idioma
                case 1: ciclo(voces); break;
                case 2: pant_completa = !pant_completa; break;
                case 3: tamano = (tamano + dir + 3) % 3; break;
                case 4: horizontal = !horizontal; break;
                case 5: llenar = !llenar; break;
                case 6: modo = modo == "performance" ? "normal" : "performance"; break;
                case 7: vsync = !vsync; break;
                default: return;
            }
            guardar();
        } else if (pantalla_ == P::Mods && sel_ < int(mods_.size())) {
            mods_[size_t(sel_)].activo = dir > 0; guardar_mods();
        }
    }
    Accion aceptar() {
        switch (pantalla_) {
            case P::Principal:
                if (sel_ == 0) return Accion::Jugar;
                if (sel_ == 1) { pantalla_ = P::Red; sel_ = 0; }
                if (sel_ == 2) { cargar_mods(); pantalla_ = P::Mods; sel_ = 0; desplaz_ = 0; }
                if (sel_ == 3) { pantalla_ = P::Opciones; sel_ = 0; }
                if (sel_ == 4) return Accion::Salir;
                break;
            case P::Red:
                if (sel_ == 0) { red_rol = 1 - red_rol; guardar(); }
                else if (sel_ == 1) { editando_ip = !editando_ip; if (!editando_ip) guardar(); }
                else if (sel_ == 2) { red_puerto = red_puerto >= 65000 ? 1024 : red_puerto + 10; guardar(); }
                else if (sel_ == 3) {
                    if (red_ip.empty()) { aviso_ = 120; aviso_texto_ = t_.falta_ip; break; }
                    guardar(); return Accion::JugarRed;
                } else volver();
                break;
            case P::Mods:
                if (sel_ < int(mods_.size())) { mod_sel_ = sel_; pantalla_ = P::ModInfo; sel_ = 0; info_scroll_ = 0; }   // ficha del mod
                else volver();
                break;
            case P::ModInfo:
                if (sel_ == 0 && mod_sel_ < int(mods_.size())) {
                    mods_[size_t(mod_sel_)].activo = !mods_[size_t(mod_sel_)].activo; guardar_mods();
                } else volver();
                break;
            case P::Opciones:
                if (sel_ <= 7) cambiar(1);
                else if (sel_ == 8) { pantalla_ = P::Controles; sel_ = 0; desplaz_ = 0; }
                else volver();
                break;
            case P::Controles: {
                const int n = int(t_.botones_ds.size());
                if (sel_ < n) { capturando = true; cap_idx_ = sel_; }
                else if (sel_ == n) { teclas = teclas_defecto(); guardar(); }
                else volver();
                break;
            }
        }
        return Accion::Nada;
    }
    // ---- dibujo ----
    void pix(int x, int y, uint32_t c) { if (x >= 0 && y >= 0 && x < kAncho && y < kAlto) px[y * kAncho + x] = c; }
    void rect(int x0, int y0, int w, int h, uint32_t c) { for (int y = y0; y < y0 + h; ++y) for (int x = x0; x < x0 + w; ++x) pix(x, y, c); }
    int ancho(const std::string& t, int esc = 1) const {
        if (!fuente_.ok()) return int(t.size()) * 6 * esc;
        int w = 0;
        for (unsigned char c : t) { const auto it = fuente_.mapa.find(c); if (it == fuente_.mapa.end()) { w += 4; continue; } int iz, av; fuente_.ancho(it->second, iz, av); w += av; }
        return w * esc;
    }
    void texto(int x, int y, const std::string& t, uint32_t c1, uint32_t c2, int esc = 1, uint32_t sombra = 0xFF101830) {
        if (!fuente_.ok()) return;
        int cx = x;
        for (unsigned char c : t) {
            const auto it = fuente_.mapa.find(c);
            if (it == fuente_.mapa.end()) { cx += 4 * esc; continue; }
            int iz, av; fuente_.ancho(it->second, iz, av);
            for (int r = 0; r < fuente_.ch; ++r)
                for (int k = 0; k < fuente_.cw; ++k) {
                    const int v = fuente_.pixel(it->second, k, r);
                    if (!v) continue;
                    uint32_t col = v == 2 ? sombra : (r < fuente_.ch / 2 ? c1 : c2);
                    for (int sy = 0; sy < esc; ++sy) for (int sx = 0; sx < esc; ++sx) pix(cx + (iz + k) * esc + sx, y + r * esc + sy, col);
                }
            cx += av * esc;
        }
    }
public:
    std::array<int, 4> caja(int i, int n) const;
};

inline std::array<int, 4> Lanzador::caja(int i, int n) const {
    if (pantalla_ == P::ModInfo) {                       // ficha del mod: botones abajo, en fila
        const int w = 150, h = 20, gap = 12, total = n * w + (n - 1) * gap;
        return {(kAncho - total) / 2 + i * (w + gap), kAlto - 16 - 4 - h - 6, w, h};
    }
    // botones centrados; en listas largas, dos columnas
    const bool lista = n > 6;
    const int w = lista ? 180 : 170, h = lista ? 14 : (n >= 5 ? 18 : 22), gap = lista ? 2 : (n >= 5 ? 5 : 6);
    if (!lista) {   // entre el subtitulo (y ~70) y el pie (16 px abajo)
        const int arriba = n >= 5 ? 72 : 90;
        const int total = n * h + (n - 1) * gap, y0 = arriba + (kAlto - arriba - 18 - total) / 2;
        return {(kAncho - w) / 2, y0 + i * (h + gap), w, h};
    }
    const int col = i < (n + 1) / 2 ? 0 : 1, fila = col ? i - (n + 1) / 2 : i;
    return {12 + col * (w + 16), 70 + fila * (h + gap), w, h};
}

inline void Lanzador::dibujar() {
    // fondo: degradado azul oscuro con franjas, como los menus del juego
    for (int y = 0; y < kAlto; ++y) {
        const int k = y * 255 / kAlto;
        const uint32_t c = 0xFF000000u | uint32_t(16 + k / 12) << 16 | uint32_t(32 + k / 7) << 8 | uint32_t(78 + k / 5);
        for (int x = 0; x < kAncho; ++x) px[y * kAncho + x] = ((x + y) / 6) % 2 ? c : c + 0x00030305;
    }
    // titulo
    const std::string tit = "INAZUMA ELEVEN";
    const int tw = ancho(tit, 2);
    rect(0, 14, kAncho, 40, 0xFF0C1A40);
    rect(0, 14, kAncho, 2, 0xFFF89838); rect(0, 52, kAncho, 2, 0xFFF89838);
    texto((kAncho - tw) / 2, 20, tit, 0xFFFFF070, 0xFFF0A020, 2, 0xFF5A2408);
    std::string sub;
    if (pantalla_ == P::Mods) sub = t_.mods;
    else if (pantalla_ == P::Red) sub = t_.jugar_red;
    else if (pantalla_ == P::ModInfo && mod_sel_ < int(mods_.size())) sub = mods_[size_t(mod_sel_)].nombre;
    else if (pantalla_ == P::Opciones) sub = t_.opciones;
    else if (pantalla_ == P::Controles) sub = t_.controles;
    if (!sub.empty()) { const std::string s = juego(sub); texto((kAncho - ancho(s)) / 2, 58, s, 0xFFB4E6FF, 0xFF64B4E6); }
    // ficha del mod: su informacion y su estado, encima de los botones
    if (pantalla_ == P::ModInfo && mod_sel_ < int(mods_.size())) {
        const Mod& m = mods_[size_t(mod_sel_)];
        const int bx = 16, by = 70, bw = kAncho - 32, bh = kAlto - 70 - 52;
        rect(bx - 1, by - 1, bw + 2, bh + 2, 0xFFF89838);
        rect(bx, by, bw, bh, 0xE0101830);
        std::vector<std::string> lineas;
        std::string parrafo;
        std::istringstream todo(juego(m.info.empty() ? t_.sin_info : m.info));
        while (std::getline(todo, parrafo)) {
            std::string linea, palabra;
            std::istringstream ps(parrafo);
            while (ps >> palabra) {
                const std::string prueba = linea.empty() ? palabra : linea + " " + palabra;
                if (ancho(prueba) > bw - 22 && !linea.empty()) { lineas.push_back(linea); linea = palabra; }
                else linea = prueba;
            }
            lineas.push_back(linea);
        }
        const int alto_linea = 12, caben = (bh - 6 - 16) / alto_linea;   // la ultima fila es para el estado
        info_max_ = std::max(0, int(lineas.size()) - caben);
        info_scroll_ = std::clamp(info_scroll_, 0, info_max_);
        int y = by + 4;
        for (int i = info_scroll_; i < int(lineas.size()) && i < info_scroll_ + caben; ++i, y += alto_linea)
            texto(bx + 6, y, lineas[size_t(i)], 0xFFF8F8F8, 0xFFD0D0E0);
        // flechas si hay mas texto arriba o abajo (se mueve con arriba/abajo o la rueda)
        if (info_scroll_ > 0) texto(bx + bw - 12, by + 3, "^", 0xFFFFF070, 0xFFF0C040);
        if (info_scroll_ < info_max_) texto(bx + bw - 12, by + bh - 30, "v", 0xFFFFF070, 0xFFF0C040);
        const std::string est = juego(m.activo ? t_.activo_si : t_.activo_no);
        texto(bx + 6, by + bh - 15, est, m.activo ? 0xFF90FF90 : 0xFFFFB0A0, m.activo ? 0xFF50D050 : 0xFFE07060);
    }
    // botones
    const auto ops = opciones_actuales();
    if (pantalla_ == P::Mods && mods_.empty()) {
        const std::string s = juego(t_.sin_mods);
        texto((kAncho - ancho(s)) / 2, 80, s, 0xFFF8F8F8, 0xFFD0D0E0);
    }
    for (int i = 0; i < int(ops.size()); ++i) {
        const auto r = caja(i, int(ops.size()));
        const bool s = i == sel_;
        rect(r[0] - 1, r[1] - 1, r[2] + 2, r[3] + 2, s ? 0xFFFFFFFF : 0xFF5A2408);
        rect(r[0], r[1], r[2], r[3], s ? 0xFFF89838 : 0xFFD86810);
        rect(r[0], r[1], r[2], r[3] / 2, s ? 0xFFFFB050 : 0xFFE88020);
        const std::string t = juego(ops[size_t(i)]);
        const int esc = 1;
        texto(r[0] + (r[2] - ancho(t, esc)) / 2, r[1] + (r[3] - 12 * esc) / 2 + 1, t, 0xFFFFFFFF, 0xFFFFF0D8, esc, 0xFF5A2408);
    }
    // pie
    std::string pie;
    if (capturando) pie = t_.pulsa_tecla;
    else if (aviso_ > 0) { --aviso_; pie = aviso_texto_.empty() ? t_.guardado : aviso_texto_; }
    else if (pantalla_ == P::Mods && !mods_.empty()) pie = t_.ayuda_info;
    else if (pantalla_ == P::Red) pie = editando_ip ? t_.escribe_ip : t_.ayuda_red;
    else if (pantalla_ != P::Principal) pie = t_.cambios_al_jugar;
    if (!pie.empty()) {
        const std::string s = juego(pie);
        rect(0, kAlto - 16, kAncho, 16, 0xC0101830);
        texto((kAncho - ancho(s)) / 2, kAlto - 14, s, 0xFFFFF070, 0xFFF0C040);
    }
    // cuadro de informacion del mod
    if (!info_.empty()) {
        const int bx = 24, by = 26, bw = kAncho - 48, bh = kAlto - 52;
        rect(bx - 2, by - 2, bw + 4, bh + 4, 0xFFF89838);
        rect(bx, by, bw, bh, 0xF0101830);
        // partir en lineas por palabras
        std::vector<std::string> lineas;
        std::string parrafo;
        std::istringstream todo(juego(info_));
        while (std::getline(todo, parrafo)) {
            std::string linea, palabra;
            std::istringstream ps(parrafo);
            while (ps >> palabra) {
                const std::string prueba = linea.empty() ? palabra : linea + " " + palabra;
                if (ancho(prueba) > bw - 16 && !linea.empty()) { lineas.push_back(linea); linea = palabra; }
                else linea = prueba;
            }
            lineas.push_back(linea);
        }
        int y = by + 8;
        for (size_t i = 0; i < lineas.size() && y < by + bh - 30; ++i, y += 14)
            texto(bx + 8, y, lineas[i], i == 0 ? 0xFFFFF070 : 0xFFF8F8F8, i == 0 ? 0xFFF0C040 : 0xFFD0D0E0);
        const std::string c = juego(t_.cerrar_info);
        texto(bx + (bw - ancho(c)) / 2, by + bh - 18, c, 0xFFB4E6FF, 0xFF64B4E6);
    }
}

}  // namespace lanz
