#!/usr/bin/env python3
"""
Menu de Esc (runner/src/frontend.cpp):
  - System > Reiniciar: cierra el juego con normalidad (la partida se guarda en
    disco) y lo vuelve a abrir con los mismos argumentos. Util tras cambiar el
    idioma.
  - La configuracion de Pantalla (modo, tamano de ventana, disposicion,
    escalado) y la ranura de estados se RECUERDAN en run/ie1_menu.cfg y se
    aplican al arrancar.
Requiere parche_menu.py, parche_menu_idiomas.py e integrar_idiomas.py.
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/frontend.cpp
          (y vuelve a aplicar parche_menu.py, parche_turbo.py y parche_menu_idiomas.py)
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
src = open(PATH, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in src else "\n"
def N(t): return t.replace("\n", nl)
def reemplazar(viejo, nuevo, nombre):
    global src
    viejo, nuevo = N(viejo), N(nuevo)
    if src.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    src = src.replace(viejo, nuevo)
def ventana_v2():
    """v2: el tamano de ventana nunca supera el escritorio (si no cabe, se
    maximiza) y al salir de pantalla completa se recupera el tamano elegido."""
    global src
    if "IE1_VENTANA_V2" in src:
        return False
    reemplazar('''            if (!g_ie1_fullscreen) {
                SDL_SetWindowSize(presentation.windows[0],
                                  sizes[g_ie1_window_size][0], sizes[g_ie1_window_size][1]);
                SDL_SetWindowPosition(presentation.windows[0],
                                      SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
            }''', '''            if (!g_ie1_fullscreen) {  // IE1_VENTANA_V2
                int w = sizes[g_ie1_window_size][0], h = sizes[g_ie1_window_size][1];
                bool maximizar = false;
#if defined(NDS_HAVE_SDL3)
                SDL_Rect util{};
                if (SDL_GetDisplayUsableBounds(SDL_GetDisplayForWindow(presentation.windows[0]), &util) &&
                    (w > util.w || h > util.h - 40))
                    maximizar = true;              // no cabe con el marco: maximizar
#endif
                if (maximizar) {
                    SDL_MaximizeWindow(presentation.windows[0]);
                } else {
#if defined(NDS_HAVE_SDL3)
                    SDL_RestoreWindow(presentation.windows[0]);
#endif
                    SDL_SetWindowSize(presentation.windows[0], w, h);
                    SDL_SetWindowPosition(presentation.windows[0],
                                          SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
                }
            }''', "tamano de ventana")
    reemplazar('''            if (!set_window_fullscreen(presentation.windows[0], options.fullscreen))''',
'''            if (!g_ie1_fullscreen) g_ie1_req.size = true;  // IE1_VENTANA_V2: recuperar el tamano
            if (!set_window_fullscreen(presentation.windows[0], options.fullscreen))''', "salir de pantalla completa")
    return True

if "IE1_MENU_EXTRA" in src:
    if ventana_v2():
        open(PATH, "w", encoding="utf-8", newline="").write(src)
        print("Actualizado: tamano de ventana ajustado al escritorio (v2).")
    else:
        print("El parche ya estaba aplicado.")
    sys.exit(0)
if "IE1_IDIOMAS_MENU" not in src:
    sys.exit("Aplica antes parche_menu.py y parche_menu_idiomas.py.")

reemplazar('''bool g_ie1_fill_scale = true;''', '''// IE1_MENU_EXTRA: reiniciar y recordar la configuracion (parche_menu_extra.py)
extern "C" void ie1_reiniciar_programa();
bool g_ie1_req_restart = false;
constexpr const char* kIe1RestartKey = "ie1.restart";
void ie1_cfg_cargar();
void ie1_cfg_guardar_si_cambia();
bool g_ie1_fill_scale = true;''', "inicio del bloque IE1_MENU")

reemplazar('''    if (ie1_key(item, kIe1SaveKey)) { g_ie1_req.save = true; *close_requested = true; return 1; }''',
'''    if (ie1_key(item, kIe1RestartKey)) { g_ie1_req_restart = true; *close_requested = true; return 1; }  // IE1_MENU_EXTRA
    if (ie1_key(item, kIe1SaveKey)) { g_ie1_req.save = true; *close_requested = true; return 1; }''',
"ie1_menu_action")

reemplazar('''void set_touch_from_mouse(float x, float y, bool down,
''', '''// IE1_MENU_EXTRA: configuracion de pantalla recordada en ie1_menu.cfg
void ie1_cfg_cargar() {
    std::FILE* f = std::fopen("ie1_menu.cfg", "r");
    if (!f) return;
    int fs = g_ie1_fullscreen ? 1 : 0, size = g_ie1_window_size, hor = g_ie1_horizontal ? 1 : 0,
        fill = g_ie1_fill_scale ? 1 : 0, slot = g_ie1_state_slot;
    bool hay_tamano = false;
    char k[32];
    int v = 0;
    while (std::fscanf(f, " %31[^=]=%d", k, &v) == 2) {
        if (!std::strcmp(k, "pantalla_completa")) fs = v;
        else if (!std::strcmp(k, "tamano")) { size = v; hay_tamano = true; }
        else if (!std::strcmp(k, "horizontal")) hor = v;
        else if (!std::strcmp(k, "llenar")) fill = v;
        else if (!std::strcmp(k, "ranura")) slot = v;
    }
    std::fclose(f);
    if (hay_tamano && size >= 0 && size <= 2) { g_ie1_window_size = size; g_ie1_req.size = true; }
    if ((fs != 0) != g_ie1_fullscreen) { g_ie1_fullscreen = fs != 0; g_ie1_req.fullscreen = true; }
    if ((hor != 0) != g_ie1_horizontal || (fill != 0) != g_ie1_fill_scale) {
        g_ie1_horizontal = hor != 0; g_ie1_fill_scale = fill != 0; g_ie1_req.layout = true;
    }
    if (slot >= 1 && slot <= 10) g_ie1_state_slot = slot;
    std::fprintf(stderr, "[menu] configuracion de pantalla cargada de ie1_menu.cfg\\n");
}
void ie1_cfg_guardar_si_cambia() {
    static int ult[5] = {-1, -1, -1, -1, -1};
    const int cur[5] = {g_ie1_fullscreen ? 1 : 0, g_ie1_window_size, g_ie1_horizontal ? 1 : 0,
                        g_ie1_fill_scale ? 1 : 0, g_ie1_state_slot};
    if (std::memcmp(ult, cur, sizeof cur) == 0) return;
    const bool primera = ult[0] == -1;
    std::memcpy(ult, cur, sizeof cur);
    if (primera) return;                       // valores de arranque: no hace falta escribir
    if (std::FILE* f = std::fopen("ie1_menu.cfg", "w")) {
        std::fprintf(f, "pantalla_completa=%d\\ntamano=%d\\nhorizontal=%d\\nllenar=%d\\nranura=%d\\n",
                     cur[0], cur[1], cur[2], cur[3], cur[4]);
        std::fclose(f);
    }
}

void set_touch_from_mouse(float x, float y, bool down,
''', "set_touch_from_mouse")

reemplazar('''    g_ie1_fullscreen = options.fullscreen != NdsFullscreenMode::Off;
''', '''    g_ie1_fullscreen = options.fullscreen != NdsFullscreenMode::Off;
    ie1_cfg_cargar();  // IE1_MENU_EXTRA
''', "estado inicial")

reemplazar('''        // IE1_MENU: peticiones del menu de Esc
''', '''        ie1_cfg_guardar_si_cambia();  // IE1_MENU_EXTRA
        if (g_ie1_req_restart) {
            g_ie1_req_restart = false;
            ie1_reiniciar_programa();
            SDL_Event ie1_quit{};
#if defined(NDS_HAVE_SDL3)
            ie1_quit.type = SDL_EVENT_QUIT;
#else
            ie1_quit.type = SDL_QUIT;
#endif
            SDL_PushEvent(&ie1_quit);
        }
        // IE1_MENU: peticiones del menu de Esc
''', "bucle principal")

reemplazar('''        // IE1_MENU
        {kIe1TxtKey, "Idioma", "Textos",  // IE1_IDIOMAS_MENU''', '''        // IE1_MENU
        {kIe1RestartKey, "System", "Reiniciar",  // IE1_MENU_EXTRA
         "Cierra y vuelve a abrir el juego (por ejemplo, para aplicar el idioma).",
         RECOMP_RUNTIME_UI_ACTION, 0, 0, 0, nullptr, 0, nullptr},
        {kIe1TxtKey, "Idioma", "Textos",  // IE1_IDIOMAS_MENU''', "elementos del menu")

ventana_v2()
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche aplicado en", PATH)
