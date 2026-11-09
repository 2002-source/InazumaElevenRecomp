#!/usr/bin/env python3
"""
Menu de Esc en el idioma de los textos del juego (idiomas.cfg / IE1_TEXTOS):
espanol con "es"; ingles con cualquier otro. Traduce secciones, nombres,
descripciones y opciones (los del runner, en ingles, y los nuestros, en
espanol). Lo que no este en la tabla se queda como esta.
   python scripts/parche_menu_traduccion.py   y despues   bash scripts/paso_mingw.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_MENU_TRADUCCION" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)

# texto original -> (espanol, ingles)
T = [
    ("Mods", "Mods", "Mods"),
    ("Activa o desactiva el mod. Se aplica al reiniciar (System > Reiniciar).",
     "Activa o desactiva el mod. Se aplica al reiniciar (Sistema > Reiniciar).",
     "Turns the mod on or off. Applied on restart (System > Restart)."),
    ("System", "Sistema", "System"),
    ("Reiniciar", "Reiniciar", "Restart"),
    ("Cierra y vuelve a abrir el juego (por ejemplo, para aplicar el idioma).",
     "Cierra y vuelve a abrir el juego (por ejemplo, para aplicar el idioma).",
     "Closes and reopens the game (for example, to apply the language)."),
    ("Idioma", "Idioma", "Language"),
    ("Textos", "Textos", "Text"),
    ("Idioma de textos y menus. Se aplica al reiniciar el juego.",
     "Idioma de textos y menus. Se aplica al reiniciar el juego.",
     "Language of texts and menus. Applied when the game restarts."),
    ("Voces", "Voces", "Voices"),
    ("Idioma de las voces. Se aplica al reiniciar el juego.",
     "Idioma de las voces. Se aplica al reiniciar el juego.",
     "Language of the voices. Applied when the game restarts."),
    ("Estados", "Estados", "Save states"),
    ("Ranura", "Ranura", "Slot"),
    ("Ranura que usan Guardar y Cargar estado.", "Ranura que usan Guardar y Cargar estado.",
     "Slot used by Save and Load state."),
    ("Guardar estado", "Guardar estado", "Save state"),
    ("Guarda la partida en la ranura elegida.", "Guarda la partida en la ranura elegida.",
     "Saves the game to the selected slot."),
    ("Cargar estado", "Cargar estado", "Load state"),
    ("Carga la partida de la ranura elegida.", "Carga la partida de la ranura elegida.",
     "Loads the game from the selected slot."),
    ("Pantalla", "Pantalla", "Display"),
    ("Modo", "Modo", "Mode"),
    ("Ventana o pantalla completa.", "Ventana o pantalla completa.", "Window or fullscreen."),
    ("Tamano de ventana", "Tamano de ventana", "Window size"),
    ("Tamano de la ventana en modo ventana.", "Tamano de la ventana en modo ventana.",
     "Size of the window in windowed mode."),
    ("Disposicion", "Disposicion", "Layout"),
    ("Pantallas una encima de otra o lado a lado.", "Pantallas una encima de otra o lado a lado.",
     "Screens stacked or side by side."),
    ("Escalado", "Escalado", "Scaling"),
    ("Llenar la ventana o escala entera sin deformar pixeles.",
     "Llenar la ventana o escala entera sin deformar pixeles.",
     "Fill the window, or integer scaling without distorting pixels."),
    ("VSync", "VSync", "VSync"),
    ("Sincroniza la imagen con el monitor (evita cortes en la imagen).",
     "Sincroniza la imagen con el monitor (evita cortes en la imagen).",
     "Syncs the picture with the monitor (avoids tearing)."),
    ("Controles", "Controles", "Controls"),
    ("Arriba", "Arriba", "Up"), ("Abajo", "Abajo", "Down"),
    ("Izquierda", "Izquierda", "Left"), ("Derecha", "Derecha", "Right"),
    ("Tecla del boton A.", "Tecla del boton A.", "Key for the A button."),
    ("Tecla del boton B.", "Tecla del boton B.", "Key for the B button."),
    ("Tecla del boton X.", "Tecla del boton X.", "Key for the X button."),
    ("Tecla del boton Y.", "Tecla del boton Y.", "Key for the Y button."),
    ("Tecla del boton L.", "Tecla del boton L.", "Key for the L button."),
    ("Tecla del boton R.", "Tecla del boton R.", "Key for the R button."),
    ("Tecla del boton Start.", "Tecla del boton Start.", "Key for the Start button."),
    ("Tecla del boton Select.", "Tecla del boton Select.", "Key for the Select button."),
    ("Tecla de la cruceta: arriba.", "Tecla de la cruceta: arriba.", "Key for D-pad up."),
    ("Tecla de la cruceta: abajo.", "Tecla de la cruceta: abajo.", "Key for D-pad down."),
    ("Tecla de la cruceta: izquierda.", "Tecla de la cruceta: izquierda.", "Key for D-pad left."),
    ("Tecla de la cruceta: derecha.", "Tecla de la cruceta: derecha.", "Key for D-pad right."),
    ("Input", "Entrada", "Input"),
    ("Resume game", "Volver al juego", "Resume game"),
    ("Close settings and return to the game.", "Cierra el menu y vuelve al juego.",
     "Close settings and return to the game."),
    ("Quit", "Salir", "Quit"),
    ("Close the runner.", "Cierra el juego.", "Close the game."),
    ("Audio", "Audio", "Audio"), ("Volume", "Volumen", "Volume"),
    # opciones
    ("Desactivado", "Desactivado", "Off"), ("Activado", "Activado", "On"),
    ("Ventana", "Ventana", "Window"), ("Pantalla completa", "Pantalla completa", "Fullscreen"),
    ("Vertical", "Vertical", "Vertical"), ("Horizontal", "Horizontal", "Horizontal"),
    ("Llenar", "Llenar", "Fill"), ("Entero (nitido)", "Entero (nitido)", "Integer (sharp)"),
    ("No", "No", "Off"), ("Si", "Si", "On"),
    ("Espanol", "Espanol", "Spanish"), ("Ingles", "Ingles", "English"), ("Japones", "Japones", "Japanese"),
    ("Frances", "Frances", "French"), ("Aleman", "Aleman", "German"), ("Italiano", "Italiano", "Italian"),
    # cabecera
    ("Runtime Settings", "Ajustes", "Settings"),
    ("A / Enter", "A / Intro", "A / Enter"), ("B / Backspace", "B / Retroceso", "B / Backspace"),
]

def c(t): return t.replace("\\", "\\\\").replace('"', '\\"')
tabla = "".join(f'        {{"{c(o)}", "{c(e)}", "{c(i)}"}},\n' for o, e, i in T)

funcion = '''// IE1_MENU_TRADUCCION: menu de Esc en el idioma de los textos (es / resto en ingles)
struct Ie1Traduccion { const char* original; const char* es; const char* en; };
const Ie1Traduccion kIe1Traducciones[] = {
''' + tabla + '''};
bool ie1_menu_en_espanol() {
    static int es = -1;
    if (es < 0) {
        std::string idioma = "en";
        if (const char* e = std::getenv("IE1_TEXTOS"); e && *e) idioma = e;
        else if (std::FILE* f = std::fopen("idiomas.cfg", "r")) {
            char l[128];
            while (std::fgets(l, sizeof l, f))
                if (!std::strncmp(l, "textos=", 7)) {
                    idioma = l + 7;
                    while (!idioma.empty() && (idioma.back() == '\\n' || idioma.back() == '\\r' || idioma.back() == ' ')) idioma.pop_back();
                }
            std::fclose(f);
        }
        es = idioma == "es" ? 1 : 0;
    }
    return es == 1;
}
const char* ie1_tr(const char* t) {
    if (!t) return t;
    const bool es = ie1_menu_en_espanol();
    for (const auto& x : kIe1Traducciones)
        if (!std::strcmp(t, x.original)) return es ? x.es : x.en;
    return t;
}
const RecompRuntimeUiItem* ie1_traducir_menu(const RecompRuntimeUiItem* items, size_t n) {
    static std::vector<RecompRuntimeUiItem> trad;
    static std::vector<std::vector<const char*>> opciones;
    trad.assign(items, items + n);
    opciones.assign(n, {});
    for (size_t i = 0; i < n; ++i) {
        trad[i].section = ie1_tr(trad[i].section);
        trad[i].label = ie1_tr(trad[i].label);
        trad[i].description = ie1_tr(trad[i].description);
        if (trad[i].choices && trad[i].choice_count) {
            for (size_t k = 0; k < trad[i].choice_count; ++k) opciones[i].push_back(ie1_tr(trad[i].choices[k]));
            trad[i].choices = opciones[i].data();
        }
    }
    return trad.data();
}

'''

def rep(viejo, nuevo, nombre):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    if s.count(viejo) != 1: sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)

rep("int ie1_menu_get(const RecompRuntimeUiItem* item, int* value) {",
    funcion + "int ie1_menu_get(const RecompRuntimeUiItem* item, int* value) {", "funciones")
rep("""    runtime_menu_config.subtitle = "Runtime Settings";
    runtime_menu_config.items = runtime_menu_items;""",
    """    runtime_menu_config.subtitle = ie1_tr("Runtime Settings");   // IE1_MENU_TRADUCCION
    runtime_menu_config.items = ie1_traducir_menu(runtime_menu_items,
        sizeof(runtime_menu_items) / sizeof(runtime_menu_items[0]));""", "items")
rep("""    runtime_menu_config.accept_label = "A / Enter";
    runtime_menu_config.back_label = "B / Backspace";""",
    """    runtime_menu_config.accept_label = ie1_tr("A / Enter");
    runtime_menu_config.back_label = ie1_tr("B / Backspace");""", "botones")
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado: menu de Esc en espanol o ingles segun el idioma de los textos.")
print("Recompila con: bash scripts/paso_mingw.sh")
