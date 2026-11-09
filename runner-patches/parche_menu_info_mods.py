#!/usr/bin/env python3
"""
Menu de Esc, seccion Mods: cada mod con su NOMBRE y su DESCRIPCION (que hace y
como se consigue o donde aparece) en el idioma de los textos, sacados de su
mod.txt:
    nombre=...        nombre_en=...
    descripcion=...   descripcion_en=...
    desbloqueo=...    desbloqueo_en=...
La descripcion sale abajo, en el recuadro de ayuda, al seleccionar el mod.
Ademas apunta en el registro (una vez) cada texto del menu que no tenga
traduccion, para completarlas: busca "[menu] sin traducir".
Requiere parche_menu_traduccion.py.
   python scripts/parche_menu_info_mods.py   y despues   bash scripts/paso_mingw.sh
"""
import re, sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_MENU_INFO_MODS" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
if "IE1_MENU_TRADUCCION" not in s:
    sys.exit("Aplica antes parche_menu_traduccion.py.")
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)

funciones = r'''// IE1_MENU_INFO_MODS: nombre y descripcion de cada mod (mod.txt), en su idioma
std::string ie1_mod_campo(int i, const char* clave) {
    const char* carpeta = ie1_mods_nombre(i);
    if (!carpeta || !*carpeta) return {};
    std::vector<std::string> dirs;
    if (const char* e = std::getenv("IE1_MODS_DIR"); e && *e) dirs.push_back(e);
    dirs.push_back("../mods"); dirs.push_back("mods");
    for (const auto& d : dirs) {
        std::FILE* f = std::fopen((d + "/" + carpeta + "/mod.txt").c_str(), "r");
        if (!f) continue;
        std::string base, en, l;
        char linea[1024];
        const std::string k = clave, ken = k + "_en";
        while (std::fgets(linea, sizeof linea, f)) {
            l = linea;
            while (!l.empty() && (l.back() == '\n' || l.back() == '\r')) l.pop_back();
            const size_t eq = l.find('=');
            if (eq == std::string::npos) continue;
            if (l.compare(0, eq, k) == 0 && eq == k.size()) base = l.substr(eq + 1);
            if (l.compare(0, eq, ken) == 0 && eq == ken.size()) en = l.substr(eq + 1);
        }
        std::fclose(f);
        return (!ie1_menu_en_espanol() && !en.empty()) ? en : base;
    }
    return {};
}
const char* ie1_mod_nombre_ui(int i, const char* respaldo) {
    static std::string nombres[8];
    if (i < 0 || i >= 8) return respaldo;
    nombres[i] = ie1_mod_campo(i, "nombre");
    return nombres[i].empty() ? respaldo : nombres[i].c_str();
}
const char* ie1_mod_descripcion(int i) {
    static std::string textos[8];
    if (i < 0 || i >= 8) return "";
    const bool es = ie1_menu_en_espanol();
    std::string t = ie1_mod_campo(i, "descripcion");
    const std::string d = ie1_mod_campo(i, "desbloqueo");
    if (!d.empty()) t += (t.empty() ? "" : " ") + std::string(es ? "Como se consigue: " : "How to get it: ") + d;
    t += es ? " (Se aplica al reiniciar: Sistema > Reiniciar.)" : " (Applied on restart: System > Restart.)";
    textos[i] = t;
    return textos[i].c_str();
}

'''

def rep(viejo, nuevo, nombre, todas=False):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    n = s.count(viejo)
    if n == 0 or (n != 1 and not todas): sys.exit(f"No encontre {nombre} ({n} veces). No toco nada.")
    s = s.replace(viejo, nuevo)

rep("const RecompRuntimeUiItem* ie1_traducir_menu(const RecompRuntimeUiItem* items, size_t n) {",
    funciones + "const RecompRuntimeUiItem* ie1_traducir_menu(const RecompRuntimeUiItem* items, size_t n) {",
    "traducir_menu")
# textos sin traduccion: avisar una vez
rep('''    for (const auto& x : kIe1Traducciones)
        if (!std::strcmp(t, x.original)) return es ? x.es : x.en;
    return t;''',
    '''    for (const auto& x : kIe1Traducciones)
        if (!std::strcmp(t, x.original)) return es ? x.es : x.en;
    static std::vector<std::string> avisados;
    if (*t && std::find(avisados.begin(), avisados.end(), t) == avisados.end()) {
        avisados.push_back(t);
        std::fprintf(stderr, "[menu] sin traducir: \\"%s\\"\\n", t);
    }
    return t;''', "ie1_tr")

# los elementos de los mods traen su propio texto: no se buscan en la tabla
rep('''        trad[i].label = ie1_tr(trad[i].label);
        trad[i].description = ie1_tr(trad[i].description);''',
    '''        const bool de_mod = trad[i].section && !std::strcmp(items[i].section, "Mods");
        if (!de_mod) {
            trad[i].label = ie1_tr(trad[i].label);
            trad[i].description = ie1_tr(trad[i].description);
        }''', "traduccion de elementos")
# elementos de los mods: nombre y descripcion propios (no se pasan por la tabla)
patron = re.compile(r'\{kIe1ModKeys\[(\d)\], "Mods", ie1_mod_label\(\1\),(\r?\n)(\s*)"Activa o desactiva el mod\. Se aplica al reiniciar \(System > Reiniciar\)\.",')
s, n = patron.subn(lambda m: f'{{kIe1ModKeys[{m.group(1)}], "Mods", ie1_mod_nombre_ui({m.group(1)}, ie1_mod_label({m.group(1)})),'
                             f'{m.group(2)}{m.group(3)}ie1_mod_descripcion({m.group(1)}),  // IE1_MENU_INFO_MODS', s)
if n == 0:
    sys.exit("No encontre los elementos de los mods en el menu. No toco nada.")
open(PATH, "w", encoding="utf-8", newline="").write(s)
print(f"Parche aplicado: {n} mods con nombre y descripcion en el menu de Esc.")
print("Recompila con: bash scripts/paso_mingw.sh")
