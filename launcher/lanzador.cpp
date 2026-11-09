// ============================================================================
//  Lanzador de Inazuma Eleven (port): Jugar / Mods / Opciones / Salir
//  Lee lanzador.ini junto al ejecutable (rutas del runner, ROM, datos...).
//  Ajustes que guarda (en la carpeta de datos):
//    lanzador.cfg   modo=performance|normal, vsync=0|1
//    controles.cfg  teclado -> botones de la DS (lo lee el juego al arrancar)
//    mods.cfg       (carpeta de mods) mods activos
// ============================================================================
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>

#include "lanzador_ui.hpp"
#include <cstdlib>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

using namespace lanz;

namespace {

struct Rutas {
    fs::path base, runner, bios, datos, rom, idiomas, mods;
    std::string extra, dlls;   // dlls: carpetas extra con DLL del juego (separadas por ;)
};

Rutas leer_rutas() {
    Rutas r;
    const char* bp = SDL_GetBasePath();
    r.base = bp ? fs::path(bp) : fs::current_path();
    const auto ini = leer_cfg(r.base / "lanzador.ini");
    auto ruta = [&](const char* clave, const char* defecto) {
        const auto it = ini.find(clave);
        fs::path p = it != ini.end() ? fs::path(it->second) : fs::path(defecto);
        return p.is_absolute() ? p : r.base / p;
    };
    // valores por defecto: estructura de la carpeta del port
    r.runner = ruta("runner", "bin/nds_runner.exe");
    r.bios = ruta("bios", "bios");
    r.datos = ruta("datos", "datos");
    r.rom = ruta("rom", "rom/ie1_eur.nds");
    r.idiomas = ruta("idiomas", "idiomas");
    r.mods = ruta("mods", "mods");
    if (ini.count("extra")) r.extra = ini.at("extra");
    if (ini.count("dlls")) r.dlls = ini.at("dlls");
    return r;
}

std::string comillas(const fs::path& p) { return "\"" + p.string() + "\""; }

// Lanza el juego y espera a que termine. Devuelve el codigo de salida.
int jugar(const Rutas& r, const Lanzador& L, bool en_red = false) {
    std::error_code ec;
    fs::create_directories(r.datos / "estados", ec);
    std::string cmd = comillas(r.runner) + " " + comillas(r.bios) +
        " --interactive --freebios --generated-firmware --boot direct"
        " --firmware-state-path firmware_state.bin --save-path ie1_eur.sav --savestate-dir estados"
        " --virtual-stylus off --config game.toml --performance-governor stage1";
    if (L.modo == "performance") cmd += " --execution-model performance";
    cmd += " --diagnostics off --no-coverage-manifest --rom " + comillas(r.rom);
    if (!r.extra.empty()) cmd += " " + r.extra;
    // juego en red (Wi-Fi local entre PC): cada jugador su instancia y su puerto,
    // y la direccion del otro en IE1_WIFI_PEERS (la usa el runner)
    std::string pares;
    if (en_red) {
        const int yo = L.red_rol, otro = 1 - L.red_rol;
        cmd += " --instance-index " + std::to_string(yo) + " --local-wireless on --local-wireless-port " +
               std::to_string(L.red_puerto);
        pares = L.red_ip + ":" + std::to_string(L.red_puerto + otro);
    }

    // entorno del juego
#if !defined(_WIN32)
    setenv("NDS_FAST_CARD", "1", 1);
    setenv("IE1_IDIOMAS_DIR", r.idiomas.string().c_str(), 1);
    setenv("IE1_MODS_DIR", r.mods.string().c_str(), 1);
    setenv("IE1_VSYNC", L.vsync ? "1" : "0", 1);
    setenv("IE1_WIFI_PEERS", pares.c_str(), 1);
#endif
#if defined(_WIN32)
    {   // las DLL del juego estan junto a su ejecutable
        // carpeta del juego, carpetas extra del ini y la del propio lanzador (lleva SDL3, libc++...)
        const std::string bin = r.runner.parent_path().string();
        static char viejo[32767]; const DWORD n = GetEnvironmentVariableA("PATH", viejo, sizeof viejo);
        std::string nuevo = bin + ";";
        if (!r.dlls.empty()) nuevo += r.dlls + ";";
        nuevo += r.base.string() + ";" + (n ? std::string(viejo, n) : std::string());
        SetEnvironmentVariableA("PATH", nuevo.c_str());
        SetEnvironmentVariableA("NDS_FAST_CARD", "1");
        SetEnvironmentVariableA("IE1_IDIOMAS_DIR", r.idiomas.string().c_str());
        SetEnvironmentVariableA("IE1_MODS_DIR", r.mods.string().c_str());
        SetEnvironmentVariableA("IE1_VSYNC", L.vsync ? "1" : "0");
        SetEnvironmentVariableA("IE1_WIFI_PEERS", pares.empty() ? nullptr : pares.c_str());
    }
    fs::remove(r.datos / "reinicio.pid", ec);
    SECURITY_ATTRIBUTES sa{sizeof sa, nullptr, TRUE};
    const std::string log = (r.datos / "ultima_sesion.log").string();
    HANDLE hlog = CreateFileA(log.c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    STARTUPINFOA si{}; si.cb = sizeof si;
    if (hlog != INVALID_HANDLE_VALUE) { si.dwFlags = STARTF_USESTDHANDLES; si.hStdOutput = hlog; si.hStdError = hlog; si.hStdInput = GetStdHandle(STD_INPUT_HANDLE); }
    PROCESS_INFORMATION pi{};
    std::vector<char> linea(cmd.begin(), cmd.end()); linea.push_back(0);
    const std::string cwd = r.datos.string();
    if (!CreateProcessA(nullptr, linea.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW, nullptr, cwd.c_str(), &si, &pi)) {
        if (hlog != INVALID_HANDLE_VALUE) CloseHandle(hlog);
        return -1;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD codigo = 0; GetExitCodeProcess(pi.hProcess, &codigo);
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    // Si el juego se reinicio (Esc > Sistema > Reiniciar), el proceso nuevo deja su
    // numero en datos/reinicio.pid: se espera tambien a ese (y a los siguientes),
    // para que el lanzador no vuelva a aparecer con el juego abierto.
    for (int vueltas = 0; vueltas < 1000; ++vueltas) {
        const fs::path marca = r.datos / "reinicio.pid";
        DWORD pid = 0;
        for (int intento = 0; intento < 20 && !pid; ++intento) {      // el aviso llega justo al salir
            std::ifstream f(marca);
            if (f) f >> pid;
            if (!pid) Sleep(50);
        }
        if (!pid) break;
        std::error_code ec2; fs::remove(marca, ec2);
        HANDLE h = OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
        if (!h) break;
        WaitForSingleObject(h, INFINITE);
        GetExitCodeProcess(h, &codigo);
        CloseHandle(h);
    }
    if (hlog != INVALID_HANDLE_VALUE) CloseHandle(hlog);
    return int(codigo);
#else
    const std::string completo = "cd " + comillas(r.datos) + " && " + cmd + " > ultima_sesion.log 2>&1";
    return std::system(completo.c_str());
#endif
}

}  // namespace

int main(int, char**) {
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMEPAD)) return 1;
    const Rutas rutas = leer_rutas();
    Rom rom;
    rom.abrir(rutas.rom);                 // solo la fuente del juego; sin ROM el menu funciona igual
    static Lanzador L;
    L.datos = rutas.datos;
    L.mods_dir = rutas.mods;
    L.idiomas_dir = rutas.idiomas;
    std::error_code ec;
    fs::create_directories(rutas.datos, ec);
    L.iniciar(rom);

    SDL_Window* win = SDL_CreateWindow("Inazuma Eleven", kAncho * 3, kAlto * 3, SDL_WINDOW_RESIZABLE);
    SDL_Renderer* ren = win ? SDL_CreateRenderer(win, nullptr) : nullptr;
    if (!ren) { SDL_Quit(); return 1; }
    SDL_SetRenderVSync(ren, 1);
    SDL_SetRenderLogicalPresentation(ren, kAncho, kAlto, SDL_LOGICAL_PRESENTATION_LETTERBOX);
    SDL_Texture* tex = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, kAncho, kAlto);
    SDL_SetTextureScaleMode(tex, SDL_SCALEMODE_NEAREST);
    SDL_Gamepad* mando = nullptr;

    bool seguir = true;
    while (seguir) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            Accion a = Accion::Nada;
            switch (e.type) {
                case SDL_EVENT_QUIT: seguir = false; break;
                case SDL_EVENT_GAMEPAD_ADDED: if (!mando) mando = SDL_OpenGamepad(e.gdevice.which); break;
                case SDL_EVENT_KEY_DOWN: {
                    const SDL_Scancode sc = e.key.scancode;
                    if (L.capturando) {
                        if (sc == SDL_SCANCODE_ESCAPE) L.tecla(Tecla::Atras);
                        else L.capturar(SDL_GetScancodeName(sc));
                        break;
                    }
                    if (L.escribiendo()) {               // escribiendo la IP del otro PC
                        if (sc >= SDL_SCANCODE_1 && sc <= SDL_SCANCODE_9) L.escribir(char('1' + (sc - SDL_SCANCODE_1)));
                        else if (sc == SDL_SCANCODE_0) L.escribir('0');
                        else if (sc >= SDL_SCANCODE_KP_1 && sc <= SDL_SCANCODE_KP_9) L.escribir(char('1' + (sc - SDL_SCANCODE_KP_1)));
                        else if (sc == SDL_SCANCODE_KP_0) L.escribir('0');
                        else if (sc == SDL_SCANCODE_PERIOD || sc == SDL_SCANCODE_KP_PERIOD) L.escribir('.');
                        else if (sc == SDL_SCANCODE_BACKSPACE) L.borrar();
                        else if (sc == SDL_SCANCODE_RETURN || sc == SDL_SCANCODE_KP_ENTER || sc == SDL_SCANCODE_ESCAPE)
                            a = L.tecla(Tecla::Aceptar);
                        break;
                    }
                    if (sc == SDL_SCANCODE_UP) a = L.tecla(Tecla::Arriba);
                    else if (sc == SDL_SCANCODE_DOWN) a = L.tecla(Tecla::Abajo);
                    else if (sc == SDL_SCANCODE_LEFT) a = L.tecla(Tecla::Izquierda);
                    else if (sc == SDL_SCANCODE_RIGHT) a = L.tecla(Tecla::Derecha);
                    else if (sc == SDL_SCANCODE_RETURN || sc == SDL_SCANCODE_KP_ENTER || sc == SDL_SCANCODE_SPACE || sc == SDL_SCANCODE_Z)
                        a = L.tecla(Tecla::Aceptar);
                    else if (sc == SDL_SCANCODE_ESCAPE || sc == SDL_SCANCODE_BACKSPACE || sc == SDL_SCANCODE_X)
                        a = L.tecla(Tecla::Atras);
                    else if (sc == SDL_SCANCODE_TAB || sc == SDL_SCANCODE_I)
                        a = L.tecla(Tecla::Info);
                    break;
                }
                case SDL_EVENT_GAMEPAD_BUTTON_DOWN:
                    if (L.capturando) { if (e.gbutton.button == SDL_GAMEPAD_BUTTON_EAST) L.tecla(Tecla::Atras); break; }
                    switch (e.gbutton.button) {
                        case SDL_GAMEPAD_BUTTON_DPAD_UP: a = L.tecla(Tecla::Arriba); break;
                        case SDL_GAMEPAD_BUTTON_DPAD_DOWN: a = L.tecla(Tecla::Abajo); break;
                        case SDL_GAMEPAD_BUTTON_DPAD_LEFT: a = L.tecla(Tecla::Izquierda); break;
                        case SDL_GAMEPAD_BUTTON_DPAD_RIGHT: a = L.tecla(Tecla::Derecha); break;
                        case SDL_GAMEPAD_BUTTON_SOUTH: case SDL_GAMEPAD_BUTTON_START: a = L.tecla(Tecla::Aceptar); break;
                        case SDL_GAMEPAD_BUTTON_EAST: a = L.tecla(Tecla::Atras); break;
                        case SDL_GAMEPAD_BUTTON_NORTH: case SDL_GAMEPAD_BUTTON_BACK: a = L.tecla(Tecla::Info); break;
                        default: break;
                    }
                    break;
                case SDL_EVENT_MOUSE_WHEEL:
                    L.rueda(e.wheel.y > 0 ? 1 : e.wheel.y < 0 ? -1 : 0);
                    break;
                case SDL_EVENT_MOUSE_MOTION: case SDL_EVENT_MOUSE_BUTTON_DOWN: {
                    SDL_ConvertEventToRenderCoordinates(ren, &e);
                    const int x = e.type == SDL_EVENT_MOUSE_MOTION ? int(e.motion.x) : int(e.button.x);
                    const int y = e.type == SDL_EVENT_MOUSE_MOTION ? int(e.motion.y) : int(e.button.y);
                    if (e.type == SDL_EVENT_MOUSE_MOTION) L.raton(x, y);
                    else if (e.button.button == SDL_BUTTON_LEFT) a = L.clic(x, y);
                    else if (e.button.button == SDL_BUTTON_RIGHT) a = L.clic_derecho(x, y);
                    break;
                }
                default: break;
            }
            if (a == Accion::Salir) seguir = false;
            if (a == Accion::Jugar || a == Accion::JugarRed) {
                L.guardar();
                SDL_HideWindow(win);
                SDL_PumpEvents();
                jugar(rutas, L, a == Accion::JugarRed);
                SDL_ShowWindow(win);
                SDL_RaiseWindow(win);
                SDL_FlushEvents(SDL_EVENT_FIRST, SDL_EVENT_LAST);   // lo pulsado durante la partida no cuenta
            }
        }
        L.dibujar();
        SDL_UpdateTexture(tex, nullptr, L.px, kAncho * 4);
        SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
        SDL_RenderClear(ren);
        SDL_RenderTexture(ren, tex, nullptr, nullptr);
        SDL_RenderPresent(ren);
    }
    if (mando) SDL_CloseGamepad(mando);
    SDL_DestroyTexture(tex);
    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
