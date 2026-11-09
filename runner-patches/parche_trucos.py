#!/usr/bin/env python3
"""
Frontend (runner/src/frontend.cpp): llama una vez por fotograma a los trucos
(codigos Action Replay de trucos.txt) de los mods activos.
Solo actua si el complemento ie1_mods.dll esta y algun mod activo trae trucos.
Requiere parche_menu_mods.py.
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_TRUCOS" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
a1 = 'extern "C" int ie1_mods_hay();'
a2 = "        // IE1_MENU: peticiones del menu de Esc" + nl
if s.count(a1) != 1 or s.count(a2) != 1:
    sys.exit("frontend.cpp no tiene la forma esperada (aplica antes parche_menu_mods.py).")
s = s.replace(a1, a1 + nl + 'extern "C" void ie1_mods_fotograma();  // IE1_TRUCOS')
s = s.replace(a2, "        ie1_mods_fotograma();  // IE1_TRUCOS: trucos de los mods" + nl + a2)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche de trucos aplicado en", PATH)
