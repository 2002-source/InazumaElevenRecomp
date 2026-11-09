#!/usr/bin/env python3
"""
Anade al menu de Esc la seccion "Idioma" (runner/src/frontend.cpp):
  Textos  idioma de textos y menus
  Voces   idioma de las voces
Las opciones son "Ingles (original)" mas los paquetes que haya en idiomas/.
La eleccion se guarda en run/idiomas.cfg y se aplica AL REINICIAR el juego
(el juego lee la tabla de archivos del cartucho al arrancar).
Las variables IE1_TEXTOS / IE1_VOCES, si se usan, tienen prioridad.
Requiere parche_menu.py e integrar_idiomas.py (version con idiomas.cfg).
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/frontend.cpp
          (y vuelve a aplicar parche_menu.py y parche_turbo.py)
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
src = open(PATH, encoding="utf-8", newline="").read()
if "IE1_IDIOMAS_MENU" in src:
    # Correccion de la primera version: el numero de opciones debe ser size_t
    viejo = "ie1_lang_nombres(), ie1_lang_count(), nullptr}"
    if viejo in src:
        src = src.replace(viejo, "ie1_lang_nombres(), static_cast<size_t>(ie1_lang_count()), nullptr}")
        open(PATH, "w", encoding="utf-8", newline="").write(src)
        print("Corregido el tipo del numero de opciones (size_t).")
    else:
        print("El parche ya estaba aplicado.")
    sys.exit(0)
if "IE1_MENU" not in src:
    sys.exit("Aplica antes parche_menu.py.")
nl = "\r\n" if "\r\n" in src else "\n"
def N(t): return t.replace("\n", nl)
def reemplazar(viejo, nuevo, nombre):
    global src
    viejo, nuevo = N(viejo), N(nuevo)
    if src.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    src = src.replace(viejo, nuevo)

reemplazar('''bool g_ie1_fill_scale = true;''', '''// IE1_IDIOMAS_MENU: seccion Idioma del menu (parche_menu_idiomas.py)
extern "C" int ie1_idiomas_lista(const char* const** nombres);
extern "C" int ie1_idiomas_actual(int voces);
extern "C" void ie1_idiomas_guardar(int textos, int voces);
int g_ie1_lang_txt = -1, g_ie1_lang_voz = -1;
bool g_ie1_req_lang = false;
constexpr const char* kIe1TxtKey = "ie1.lang_text";
constexpr const char* kIe1VozKey = "ie1.lang_voice";
const char* const* ie1_lang_nombres() { const char* const* n = nullptr; ie1_idiomas_lista(&n); return n; }
int ie1_lang_count() { const char* const* n = nullptr; return ie1_idiomas_lista(&n); }
void ie1_lang_init() {
    if (g_ie1_lang_txt < 0) { g_ie1_lang_txt = ie1_idiomas_actual(0); g_ie1_lang_voz = ie1_idiomas_actual(1); }
}
bool g_ie1_fill_scale = true;''', "inicio del bloque IE1_MENU")

reemplazar('''    if (ie1_key(item, kIe1SlotKey)) { *value = g_ie1_state_slot; return 1; }''',
'''    if (ie1_key(item, kIe1TxtKey)) { ie1_lang_init(); *value = g_ie1_lang_txt; return 1; }  // IE1_IDIOMAS_MENU
    if (ie1_key(item, kIe1VozKey)) { ie1_lang_init(); *value = g_ie1_lang_voz; return 1; }
    if (ie1_key(item, kIe1SlotKey)) { *value = g_ie1_state_slot; return 1; }''', "ie1_menu_get")

reemplazar('''    if (ie1_key(item, kIe1SlotKey)) {
        if (value < 1 || value > 10) return 0;''', '''    if (ie1_key(item, kIe1TxtKey) || ie1_key(item, kIe1VozKey)) {  // IE1_IDIOMAS_MENU
        ie1_lang_init();
        if (value < 0 || value >= ie1_lang_count()) return 0;
        (ie1_key(item, kIe1TxtKey) ? g_ie1_lang_txt : g_ie1_lang_voz) = value;
        ie1_idiomas_guardar(g_ie1_lang_txt, g_ie1_lang_voz);
        g_ie1_req_lang = true;
        return 1;
    }
    if (ie1_key(item, kIe1SlotKey)) {
        if (value < 1 || value > 10) return 0;''', "ie1_menu_set")

reemplazar('''        // IE1_MENU
        {kIe1SlotKey, "Estados", "Ranura",''', '''        // IE1_MENU
        {kIe1TxtKey, "Idioma", "Textos",  // IE1_IDIOMAS_MENU
         "Idioma de textos y menus. Se aplica al reiniciar el juego.",
         RECOMP_RUNTIME_UI_CHOICE, 0, ie1_lang_count() - 1, 1, ie1_lang_nombres(), static_cast<size_t>(ie1_lang_count()), nullptr},
        {kIe1VozKey, "Idioma", "Voces",
         "Idioma de las voces. Se aplica al reiniciar el juego.",
         RECOMP_RUNTIME_UI_CHOICE, 0, ie1_lang_count() - 1, 1, ie1_lang_nombres(), static_cast<size_t>(ie1_lang_count()), nullptr},
        {kIe1SlotKey, "Estados", "Ranura",''', "elementos del menu")

reemplazar('''        // IE1_MENU: peticiones del menu de Esc
''', '''        if (g_ie1_req_lang) {  // IE1_IDIOMAS_MENU
            g_ie1_req_lang = false;
            savestate_notice = "Idioma guardado: reinicia el juego para aplicarlo";
            savestate_notice_until = SDL_GetPerformanceCounter() + frequency * 4u;
        }
        // IE1_MENU: peticiones del menu de Esc
''', "bucle principal")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche del menu de idiomas aplicado en", PATH)
