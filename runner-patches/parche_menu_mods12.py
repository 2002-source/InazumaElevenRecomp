#!/usr/bin/env python3
"""
Menu de Esc, seccion Mods: hasta ahora solo cabian 6 mods (los demas no salian en la
lista, aunque se aplicaban si estaban en mods.cfg). Este parche sube el limite a 12,
en el menu (frontend.cpp) y en la lista que el runner lee de la carpeta mods
(ie1_idiomas.cpp). Se puede ejecutar varias veces.
   python scripts/parche_menu_mods12.py   y despues   bash scripts/paso_mingw.sh
"""
import re
import sys

N = 12
FRONT = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
IDIOMAS = "C:/dev/ndsrecomp/runner/src/ie1_idiomas.cpp"


def leer(p):
    return open(p, encoding="utf-8", newline="").read()


def guardar(p, s):
    open(p, "w", encoding="utf-8", newline="").write(s)


# 1) lista de mods del runner
s = leer(IDIOMAS)
if "constexpr int kMaxMods = %d;" % N in s:
    print("ie1_idiomas.cpp: ya admitia %d mods." % N)
elif "constexpr int kMaxMods = 6;" in s:
    guardar(IDIOMAS, s.replace("constexpr int kMaxMods = 6;", "constexpr int kMaxMods = %d;  // IE1_MODS12" % N))
    print("ie1_idiomas.cpp: limite de mods 6 -> %d." % N)
else:
    sys.exit("No encontre kMaxMods en ie1_idiomas.cpp. No toco nada.")

# 2) menu de Esc
s = leer(FRONT)
if "IE1_MODS12" in s:
    print("frontend.cpp: el parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
if "constexpr int kIe1ModSlots = 6;" not in s:
    sys.exit("No encontre kIe1ModSlots en frontend.cpp (aplica antes parche_menu_mods.py). No toco nada.")
s = s.replace("constexpr int kIe1ModSlots = 6;", "constexpr int kIe1ModSlots = %d;  // IE1_MODS12" % N)
# claves ie1.mod0..ie1.mod11
m = re.search(r"const char\* const kIe1ModKeys\[kIe1ModSlots\] = \{[^}]*\};", s)
if not m:
    sys.exit("No encontre la lista kIe1ModKeys. No toco nada.")
claves = ", ".join('"ie1.mod%d"' % i for i in range(N))
s = s[:m.start()] + "const char* const kIe1ModKeys[kIe1ModSlots] = {" + claves + "};" + s[m.end():]
# casillas del menu: copiar la del mod 5 para los mods 6..11
a = s.find("{kIe1ModKeys[5],")
if a < 0:
    sys.exit("No encontre la casilla del mod 5 en el menu. No toco nada.")
a = s.rfind(nl, 0, a) + len(nl)                     # principio de la linea
b = s.find("nullptr}," , a)
if b < 0:
    sys.exit("No encontre el final de la casilla del mod 5. No toco nada.")
b = s.find(nl, b) + len(nl)                         # final de la linea
casilla = s[a:b]
nuevas = ""
for i in range(6, N):
    nuevas += casilla.replace("[5]", "[%d]" % i).replace("(5)", "(%d)" % i).replace("(5,", "(%d," % i)
s = s[:b] + nuevas + s[b:]
# nombres de las casillas (parche_menu_info_mods.py): bufer de 8 -> 16
s = s.replace("static std::string nombres[8];", "static std::string nombres[16];")
s = s.replace("if (i < 0 || i >= 8) return respaldo;", "if (i < 0 || i >= 16) return respaldo;")
guardar(FRONT, s)
print("frontend.cpp: menu de Esc con %d casillas de mods." % N)
print("Recompila con: bash scripts/paso_mingw.sh")
