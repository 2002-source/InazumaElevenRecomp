#!/usr/bin/env python3
"""
Frontend (runner/src/frontend.cpp):
  1. Teclas configurables: si en la carpeta de trabajo (datos/run) hay un
     controles.cfg (lo escribe el lanzador), el teclado usa esas teclas para los
     botones de la DS. Formato:  A=Z  B=X  SELECT=Backspace  START=Return
     DERECHA=Right  IZQUIERDA=Left  ARRIBA=Up  ABAJO=Down  R=W  L=Q  X=S  Y=A
     (nombres de tecla de SDL). Sin el archivo, las teclas de siempre.
  2. VSync: con la variable IE1_VSYNC=1 (la pone el lanzador) el renderizador
     sincroniza con el monitor.
     python scripts/parche_controles_vsync.py  y despues  bash scripts/paso_mingw.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)
def rep(viejo, nuevo, nombre):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    if s.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)

aplicar1 = "IE1_CONTROLES" not in s
if aplicar1: rep('''uint16_t key_bit(SDL_Scancode key) {
    // KEYINPUT/EXTKEYIN are active-low. This layout follows the common DS
    // emulator convention: Z/X = A/B, A/S = Y/X, Q/W = L/R.
    switch (key) {''',
'''// IE1_CONTROLES: teclas de controles.cfg (las elige el lanzador)
const std::array<SDL_Scancode, 12>* ie1_controles() {
    static std::array<SDL_Scancode, 12> tabla{};
    static int estado = -1;            // -1 sin leer, 0 sin archivo, 1 cargado
    if (estado < 0) {
        estado = 0;
        static const char* kClaves[12] = {"A", "B", "SELECT", "START", "DERECHA", "IZQUIERDA",
                                          "ARRIBA", "ABAJO", "R", "L", "X", "Y"};
        std::FILE* f = std::fopen("controles.cfg", "r");
        if (f) {
            char linea[256];
            while (std::fgets(linea, sizeof linea, f)) {
                std::string l(linea);
                while (!l.empty() && (l.back() == '\\n' || l.back() == '\\r' || l.back() == ' ')) l.pop_back();
                const size_t e = l.find('=');
                if (l.empty() || l[0] == '#' || e == std::string::npos) continue;
                const std::string k = l.substr(0, e), v = l.substr(e + 1);
                for (int i = 0; i < 12; ++i)
                    if (k == kClaves[i]) {
                        const SDL_Scancode sc = SDL_GetScancodeFromName(v.c_str());
                        if (sc != SDL_SCANCODE_UNKNOWN) { tabla[size_t(i)] = sc; estado = 1; }
                    }
            }
            std::fclose(f);
            if (estado == 1) std::fprintf(stderr, "[controles] teclas de controles.cfg\\n");
        }
    }
    return estado == 1 ? &tabla : nullptr;
}

uint16_t key_bit(SDL_Scancode key) {
    if (const auto* t = ie1_controles()) {          // IE1_CONTROLES
        for (size_t i = 0; i < t->size(); ++i)
            if ((*t)[i] == key && key != SDL_SCANCODE_UNKNOWN) return uint16_t(1u << i);
        return 0;
    }
    // KEYINPUT/EXTKEYIN are active-low. This layout follows the common DS
    // emulator convention: Z/X = A/B, A/S = Y/X, Q/W = L/R.
    switch (key) {''', "key_bit")

if aplicar1: rep('''    if (!renderer)
        renderer = SDL_CreateRenderer(window, "software");
    if (renderer) {
        const char* name = SDL_GetRendererName(renderer);''',
'''    if (!renderer)
        renderer = SDL_CreateRenderer(window, "software");
    if (renderer) {   // IE1_VSYNC: sincronizar con el monitor si lo pide el lanzador
        const char* vs = std::getenv("IE1_VSYNC");
        if (vs && vs[0] == '1') {
            SDL_SetRenderVSync(renderer, 1);
            std::fprintf(stderr, "[sdl] vsync: on\\n");
        }
    }
    if (renderer) {
        const char* name = SDL_GetRendererName(renderer);''', "vsync")

if "#include <array>" not in s:
    s = N("#include <array>\n") + s

# ---- Etapa 2: menu Esc (VSync y controles) -------------------------------------
if "IE1_CONTROLES_MENU" not in s:
    # tabla global (siempre cargada: con controles.cfg o con las teclas de siempre)
    rep("""const std::array<SDL_Scancode, 12>* ie1_controles() {
    static std::array<SDL_Scancode, 12> tabla{};
    static int estado = -1;            // -1 sin leer, 0 sin archivo, 1 cargado
    if (estado < 0) {
        estado = 0;""",
"""// IE1_CONTROLES_MENU: la tabla tambien se cambia desde el menu Esc
std::array<SDL_Scancode, 12> g_ie1_tabla{SDL_SCANCODE_Z, SDL_SCANCODE_X, SDL_SCANCODE_BACKSPACE,
    SDL_SCANCODE_RETURN, SDL_SCANCODE_RIGHT, SDL_SCANCODE_LEFT, SDL_SCANCODE_UP, SDL_SCANCODE_DOWN,
    SDL_SCANCODE_W, SDL_SCANCODE_Q, SDL_SCANCODE_S, SDL_SCANCODE_A};
const std::array<SDL_Scancode, 12>* ie1_controles() {
    std::array<SDL_Scancode, 12>& tabla = g_ie1_tabla;
    static int estado = -1;            // -1 sin leer, 0 sin archivo, 1 cargado
    if (estado < 0) {
        estado = 0;""", "tabla global")
    rep("""    return estado == 1 ? &tabla : nullptr;
}""", """    return &tabla;                     // IE1_CONTROLES_MENU: siempre la tabla (por defecto, la de siempre)
}
void ie1_controles_guardar() {
    static const char* kClaves[12] = {"A", "B", "SELECT", "START", "DERECHA", "IZQUIERDA",
                                      "ARRIBA", "ABAJO", "R", "L", "X", "Y"};
    if (std::FILE* f = std::fopen("controles.cfg", "w")) {
        std::fprintf(f, "# Teclado -> botones de la DS (nombres de tecla de SDL)\\n");
        for (int i = 0; i < 12; ++i) std::fprintf(f, "%s=%s\\n", kClaves[i], SDL_GetScancodeName(g_ie1_tabla[size_t(i)]));
        std::fclose(f);
    }
}""", "guardar controles")
    # declaraciones y elementos del menu
    rep("""int ie1_menu_get(const RecompRuntimeUiItem* item, int* value) {""",
"""// IE1_CONTROLES_MENU: VSync y teclas en el menu Esc
const std::array<SDL_Scancode, 12>* ie1_controles();
void ie1_controles_guardar();
extern std::array<SDL_Scancode, 12> g_ie1_tabla;
int g_ie1_vsync = -1;
bool g_ie1_req_vsync = false;
constexpr const char* kIe1VsyncKey = "ie1.vsync";
const char* const kIe1VsyncChoices[] = {"No", "Si"};
const char* const kIe1CtlKeys[12] = {"ie1.ctl.0", "ie1.ctl.1", "ie1.ctl.2", "ie1.ctl.3", "ie1.ctl.4", "ie1.ctl.5",
                                     "ie1.ctl.6", "ie1.ctl.7", "ie1.ctl.8", "ie1.ctl.9", "ie1.ctl.10", "ie1.ctl.11"};
const char* const kIe1Teclas[] = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P",
    "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "Return", "Backspace", "Space", "Tab", "Up", "Down", "Left", "Right",
    "Keypad 0", "Keypad 1", "Keypad 2", "Keypad 3", "Keypad 4", "Keypad 5", "Keypad 6", "Keypad 7", "Keypad 8",
    "Keypad 9", "Keypad Enter", "Right Shift", "Right Ctrl", "Left Alt", "Home", "End", "PageUp", "PageDown",
    "Insert", "Delete"};
constexpr int kIe1NumTeclas = int(sizeof(kIe1Teclas) / sizeof(kIe1Teclas[0]));
int ie1_ctl_indice(const RecompRuntimeUiItem* item) {
    for (int i = 0; i < 12; ++i) if (ie1_key(item, kIe1CtlKeys[i])) return i;
    return -1;
}
int ie1_menu_get(const RecompRuntimeUiItem* item, int* value) {
    if (ie1_key(item, kIe1VsyncKey)) {
        if (g_ie1_vsync < 0) { const char* v = std::getenv("IE1_VSYNC"); g_ie1_vsync = (v && v[0] == '1') ? 1 : 0; }
        *value = g_ie1_vsync; return 1;
    }
    if (const int c = ie1_ctl_indice(item); c >= 0) {
        ie1_controles();
        const char* nom = SDL_GetScancodeName(g_ie1_tabla[size_t(c)]);
        *value = 0;
        for (int k = 0; k < kIe1NumTeclas; ++k) if (!std::strcmp(nom, kIe1Teclas[k])) *value = k;
        return 1;
    }""", "ie1_menu_get")
    rep("""int ie1_menu_set(const RecompRuntimeUiItem* item, int value) {""",
"""int ie1_menu_set(const RecompRuntimeUiItem* item, int value) {
    if (ie1_key(item, kIe1VsyncKey)) {  // IE1_CONTROLES_MENU
        g_ie1_vsync = value ? 1 : 0; g_ie1_req_vsync = true; return 1;
    }
    if (const int c = ie1_ctl_indice(item); c >= 0) {
        if (value < 0 || value >= kIe1NumTeclas) return 0;
        ie1_controles();
        const SDL_Scancode sc = SDL_GetScancodeFromName(kIe1Teclas[value]);
        if (sc == SDL_SCANCODE_UNKNOWN) return 0;
        g_ie1_tabla[size_t(c)] = sc;
        ie1_controles_guardar();
        return 1;
    }""", "ie1_menu_set")
    rep("""         "Llenar la ventana o escala entera sin deformar pixeles.",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1ScaleChoices, 2, nullptr},""",
"""         "Llenar la ventana o escala entera sin deformar pixeles.",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1ScaleChoices, 2, nullptr},
        {kIe1VsyncKey, "Pantalla", "VSync",  // IE1_CONTROLES_MENU
         "Sincroniza la imagen con el monitor (evita cortes en la imagen).",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1VsyncChoices, 2, nullptr},
        {kIe1CtlKeys[0], "Controles", "A", "Tecla del boton A.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[1], "Controles", "B", "Tecla del boton B.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[10], "Controles", "X", "Tecla del boton X.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[11], "Controles", "Y", "Tecla del boton Y.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[9], "Controles", "L", "Tecla del boton L.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[8], "Controles", "R", "Tecla del boton R.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[3], "Controles", "Start", "Tecla del boton Start.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[2], "Controles", "Select", "Tecla del boton Select.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[6], "Controles", "Arriba", "Tecla de la cruceta: arriba.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[7], "Controles", "Abajo", "Tecla de la cruceta: abajo.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[5], "Controles", "Izquierda", "Tecla de la cruceta: izquierda.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},
        {kIe1CtlKeys[4], "Controles", "Derecha", "Tecla de la cruceta: derecha.", RECOMP_RUNTIME_UI_CHOICE, 0, kIe1NumTeclas - 1, 1, kIe1Teclas, size_t(kIe1NumTeclas), nullptr},""", "elementos del menu")
    rep("""        // IE1_MENU: peticiones del menu de Esc
""", """        if (g_ie1_req_vsync) {  // IE1_CONTROLES_MENU
            g_ie1_req_vsync = false;
            for (int r = 0; r < 2; ++r)
                if (presentation.renderers[r]) SDL_SetRenderVSync(presentation.renderers[r], g_ie1_vsync);
            // recordarlo tambien para el lanzador (lanzador.cfg)
            std::string modo = "performance";
            if (std::FILE* f = std::fopen("lanzador.cfg", "r")) {
                char l[128];
                while (std::fgets(l, sizeof l, f))
                    if (!std::strncmp(l, "modo=", 5)) { modo = l + 5; while (!modo.empty() && (modo.back() == '\\n' || modo.back() == '\\r')) modo.pop_back(); }
                std::fclose(f);
            }
            if (std::FILE* f = std::fopen("lanzador.cfg", "w")) {
                std::fprintf(f, "# Ajustes del lanzador\\nmodo=%s\\nvsync=%d\\n", modo.c_str(), g_ie1_vsync);
                std::fclose(f);
            }
        }
        // IE1_MENU: peticiones del menu de Esc
""", "bucle principal")

if "#include <array>" not in s:
    s = N("#include <array>\n") + s
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado: controles.cfg, VSync y sus opciones en el menu Esc. Recompila con: bash scripts/paso_mingw.sh")
