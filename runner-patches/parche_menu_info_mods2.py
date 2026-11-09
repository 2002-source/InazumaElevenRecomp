#!/usr/bin/env python3
"""
Menu de Esc, seccion Mods: la barra de ayuda solo muestra UNA linea, asi que la
descripcion larga de cada mod se corta. Se cambia por un texto corto que si
cabe; la informacion completa queda en el lanzador (Tab o clic derecho).
Requiere parche_menu_info_mods.py. Se puede ejecutar varias veces.
   python scripts/parche_menu_info_mods2.py   y despues   bash scripts/paso_mingw.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_MENU_INFO_MODS2" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
if "IE1_MENU_INFO_MODS" not in s:
    sys.exit("Aplica antes parche_menu_info_mods.py.")
nl = "\r\n" if "\r\n" in s else "\n"
a = s.find("const char* ie1_mod_descripcion(int i) {")
if a < 0:
    sys.exit("No encontre ie1_mod_descripcion. No toco nada.")
b = s.find(nl + "}" + nl, a)
nuevo = ("const char* ie1_mod_descripcion(int i) {   // IE1_MENU_INFO_MODS2: una sola linea" + nl +
         "    (void)i;" + nl +
         "    return ie1_menu_en_espanol() ? \"Activar o desactivar (al reiniciar). Info: lanzador, Tab.\"" + nl +
         "                                 : \"Turn on or off (on restart). Info: launcher, Tab.\";" + nl +
         "}")
s = s[:a] + nuevo + s[b + len(nl) + 1:]
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado: descripcion corta de los mods en el menu de Esc.")
print("Recompila con: bash scripts/paso_mingw.sh")
