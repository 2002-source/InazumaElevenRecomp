#!/usr/bin/env python3
"""
Anade al menu de Esc la seccion "Mods" (runner/src/frontend.cpp): hasta 6 mods
de la carpeta mods\\, cada uno Activado/Desactivado. Solo funciona si el
complemento ie1_mods.dll esta junto al ejecutable; sin el, la seccion aparece
desactivada ("complemento no instalado"). Los cambios se aplican al reiniciar.
Requiere parche_menu.py, parche_menu_idiomas.py y parche_menu_extra.py,
e integrar_idiomas.py (version con mods).
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/frontend.cpp (y reaplicar los parches del menu)
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
if "IE1_MODS_MENU" in src:
    print("El parche ya estaba aplicado."); sys.exit(0)
if "IE1_MENU_EXTRA" not in src:
    sys.exit("Aplica antes parche_menu.py, parche_menu_idiomas.py y parche_menu_extra.py.")

reemplazar('''bool g_ie1_fill_scale = true;''', '''// IE1_MODS_MENU: seccion Mods (parche_menu_mods.py)
extern "C" int ie1_mods_hay();
extern "C" int ie1_mods_num();
extern "C" const char* ie1_mods_nombre(int i);
extern "C" int ie1_mods_activo(int i);
extern "C" void ie1_mods_cambiar(int i, int activo);
constexpr int kIe1ModSlots = 6;
const char* const kIe1ModKeys[kIe1ModSlots] = {"ie1.mod0", "ie1.mod1", "ie1.mod2",
                                               "ie1.mod3", "ie1.mod4", "ie1.mod5"};
const char* const kIe1OnOffChoices[] = {"Desactivado", "Activado"};
bool g_ie1_req_mods = false;
int ie1_mod_slot(const RecompRuntimeUiItem* item) {
    if (!item || !item->key) return -1;
    for (int i = 0; i < kIe1ModSlots; ++i)
        if (std::strcmp(item->key, kIe1ModKeys[i]) == 0) return i;
    return -1;
}
const char* ie1_mod_label(int i) {
    if (!ie1_mods_hay()) return i == 0 ? "Complemento no instalado" : "-";
    if (i < ie1_mods_num()) return ie1_mods_nombre(i);
    return (i == 0) ? "No hay mods en la carpeta mods" : "-";
}
bool g_ie1_fill_scale = true;''', "inicio del bloque IE1_MENU")

reemplazar('''    if (ie1_key(item, kIe1TxtKey)) { ie1_lang_init(); *value = g_ie1_lang_txt; return 1; }  // IE1_IDIOMAS_MENU''',
'''    if (const int m = ie1_mod_slot(item); m >= 0) { *value = ie1_mods_activo(m); return 1; }  // IE1_MODS_MENU
    if (ie1_key(item, kIe1TxtKey)) { ie1_lang_init(); *value = g_ie1_lang_txt; return 1; }  // IE1_IDIOMAS_MENU''',
"ie1_menu_get")

reemplazar('''    if (ie1_key(item, kIe1TxtKey) || ie1_key(item, kIe1VozKey)) {  // IE1_IDIOMAS_MENU''',
'''    if (const int m = ie1_mod_slot(item); m >= 0) {  // IE1_MODS_MENU
        if (m >= ie1_mods_num()) return 0;
        ie1_mods_cambiar(m, value != 0);
        g_ie1_req_mods = true;
        return 1;
    }
    if (ie1_key(item, kIe1TxtKey) || ie1_key(item, kIe1VozKey)) {  // IE1_IDIOMAS_MENU''',
"ie1_menu_set")

reemplazar('''    if (ie1_key(item, kIe1SizeKey)) return g_ie1_fullscreen ? 0 : 1;
    return -1;''', '''    if (ie1_key(item, kIe1SizeKey)) return g_ie1_fullscreen ? 0 : 1;
    if (const int m = ie1_mod_slot(item); m >= 0)  // IE1_MODS_MENU
        return (ie1_mods_hay() && m < ie1_mods_num()) ? 1 : 0;
    return -1;''', "ie1_menu_enabled")

slots = "".join(
    f'''        {{kIe1ModKeys[{i}], "Mods", ie1_mod_label({i}),
         "Activa o desactiva el mod. Se aplica al reiniciar (System > Reiniciar).",
         RECOMP_RUNTIME_UI_CHOICE, 0, 1, 1, kIe1OnOffChoices, 2, nullptr}},
''' for i in range(6))
reemplazar('''        {kIe1RestartKey, "System", "Reiniciar",  // IE1_MENU_EXTRA''',
'''        // IE1_MODS_MENU
''' + slots + '''        {kIe1RestartKey, "System", "Reiniciar",  // IE1_MENU_EXTRA''', "elementos del menu")

reemplazar('''        ie1_cfg_guardar_si_cambia();  // IE1_MENU_EXTRA
''', '''        ie1_cfg_guardar_si_cambia();  // IE1_MENU_EXTRA
        if (g_ie1_req_mods) {  // IE1_MODS_MENU
            g_ie1_req_mods = false;
            savestate_notice = "Mods guardados: usa System > Reiniciar para aplicarlos";
            savestate_notice_until = SDL_GetPerformanceCounter() + frequency * 4u;
        }
''', "bucle principal")

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Seccion Mods anadida en", PATH)
