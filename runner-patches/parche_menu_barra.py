#!/usr/bin/env python3
"""
Menu de Esc: traduce tambien los textos fijos que dibuja la propia biblioteca del
menu (C:/dev/recomp-ui/src/common/recomp_runtime_ui.c):
  - la barra de ayuda de abajo ("UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT",
    "ENTER OPEN  ESC BACK");
  - el aviso "Press again to confirm";
  - los valores On / Off y el titulo por defecto "Settings".
La biblioteca gana un "traductor" opcional (un puntero a funcion, vacio por
defecto: sin el, todo sale como siempre) y el runner le pasa la tabla de
traducciones del menu (parche_menu_traduccion.py), con el mismo idioma.
Se puede ejecutar varias veces.
   python scripts/parche_menu_barra.py   y despues   bash scripts/paso_mingw.sh
"""
import re, sys
UI = "C:/dev/recomp-ui/src/common/recomp_runtime_ui.c"
FRONT = "C:/dev/ndsrecomp/runner/src/frontend.cpp"


def leer(p):
    s = open(p, encoding="utf-8", newline="").read()
    return s, ("\r\n" if "\r\n" in s else "\n")


# ---- 1. La biblioteca: traductor opcional ---------------------------------------
s, nl = leer(UI)
if "recomp_runtime_ui_translate" not in s:
    TEXTOS = ['"UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT"', '"ENTER OPEN  ESC BACK"',
              '"Press again to confirm"', 'value ? "On" : "Off"']
    for t in TEXTOS:
        if t not in s:
            sys.exit(f"No encontre {t} en recomp_runtime_ui.c. No toco nada.")
    s = s.replace('"UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT"', 'ui_tr("UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT")')
    s = s.replace('"ENTER OPEN  ESC BACK"', 'ui_tr("ENTER OPEN  ESC BACK")')
    s = s.replace('"Press again to confirm"', 'ui_tr("Press again to confirm")')
    s = s.replace('value ? "On" : "Off"', 'value ? ui_tr("On") : ui_tr("Off")')
    s = s.replace('ui->config.title : "Settings"', 'ui->config.title : ui_tr("Settings")')
    s = s.replace('item->section : "Settings"', 'item->section : ui_tr("Settings")')
    # el traductor, despues del ultimo #include
    incs = list(re.finditer(r'^#include[^\r\n]*\r?\n', s, re.M))
    if not incs:
        sys.exit("No encontre los #include de recomp_runtime_ui.c. No toco nada.")
    pos = incs[-1].end()
    bloque = (nl + "/* Traductor opcional de los textos fijos del menu (lo pone el programa que" + nl +
              " * usa la biblioteca; vacio = textos tal cual). */" + nl +
              "const char *(*recomp_runtime_ui_translate)(const char *text) = 0;" + nl +
              "static const char *ui_tr(const char *text) {" + nl +
              "    return recomp_runtime_ui_translate ? recomp_runtime_ui_translate(text) : text;" + nl +
              "}" + nl)
    s = s[:pos] + bloque + s[pos:]
    open(UI, "w", encoding="utf-8", newline="").write(s)
    print("recomp_runtime_ui.c: textos fijos con traductor opcional.")
else:
    print("recomp_runtime_ui.c: ya tenia el traductor.")

# ---- 2. El runner: le pasa la tabla de traducciones -------------------------------
f, nl = leer(FRONT)
if "IE1_MENU_TRADUCCION" not in f:
    sys.exit("Aplica antes parche_menu_traduccion.py.")
if "IE1_MENU_BARRA" not in f:
    # declaraciones al principio (enlace C, fuera de cualquier espacio de nombres)
    decl = ("// IE1_MENU_BARRA: traductor para los textos fijos de la biblioteca del menu" + nl +
            'extern "C" { extern const char *(*recomp_runtime_ui_translate)(const char *); const char *ie1_tr_c(const char *); }' + nl)
    m = re.search(r'^#include[^\r\n]*\r?\n', f, re.M)
    f = f[:m.start()] + decl + f[m.start():]
    # la funcion, al final del archivo (ve a ie1_tr, que esta en el espacio sin nombre)
    f = f.rstrip("\r\n") + nl + nl + "// IE1_MENU_BARRA" + nl + 'extern "C" const char *ie1_tr_c(const char *t) { return ie1_tr(t); }' + nl
    viejo = '    runtime_menu_config.subtitle = ie1_tr("Runtime Settings");   // IE1_MENU_TRADUCCION'
    if f.count(viejo) != 1:
        sys.exit("No encontre donde se configura el menu en frontend.cpp. No toco nada.")
    f = f.replace(viejo, "    recomp_runtime_ui_translate = ie1_tr_c;   // IE1_MENU_BARRA" + nl + viejo)
    # sus textos en la tabla
    nuevas = [
        ("UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT",
         "ARRIBA/ABAJO ELEGIR  IZQ/DER CAMBIAR  INTRO ACEPTAR", "UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT"),
        ("ENTER OPEN  ESC BACK", "INTRO ABRIR  ESC VOLVER", "ENTER OPEN  ESC BACK"),
        ("Press again to confirm", "Pulsa otra vez para confirmar", "Press again to confirm"),
        ("On", "Si", "On"), ("Off", "No", "Off"),
    ]
    marca = "const Ie1Traduccion kIe1Traducciones[] = {" + nl
    lineas = "".join(f'        {{"{o}", "{e}", "{i}"}},{nl}' for o, e, i in nuevas if f'{{"{o}", ' not in f)
    f = f.replace(marca, marca + lineas, 1)
    open(FRONT, "w", encoding="utf-8", newline="").write(f)
    print("frontend.cpp: la barra de ayuda y los avisos siguen el idioma del menu.")
else:
    print("frontend.cpp: ya estaba.")
print("Recompila con: bash scripts/paso_mingw.sh")
