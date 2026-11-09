#!/usr/bin/env python3
"""
Amplia la tabla de traducciones del menu de Esc (parche_menu_traduccion.py):
nombres de teclas (Return, Up, Backspace...), raton y otros textos que faltaban.
Solo cambia lo que se MUESTRA: la tecla elegida se sigue guardando con su
nombre de SDL. Se puede ejecutar varias veces (no repite entradas).
   python scripts/parche_menu_traduccion2.py   y despues   bash scripts/paso_mingw.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_MENU_TRADUCCION" not in s:
    sys.exit("Aplica antes parche_menu_traduccion.py.")
nl = "\r\n" if "\r\n" in s else "\n"

NUEVAS = [
    ("Mouse sensitivity", "Sensibilidad del raton", "Mouse sensitivity"),
    ("Prime Controls relative aim speed.", "Velocidad del raton.", "Mouse speed."),
    ("Mouse", "Raton", "Mouse"),
    ("Settings", "Ajustes", "Settings"),
    ("Return", "Intro", "Enter"), ("Backspace", "Retroceso", "Backspace"),
    ("Space", "Espacio", "Space"), ("Tab", "Tab", "Tab"),
    ("Up", "Arriba", "Up"), ("Down", "Abajo", "Down"), ("Left", "Izquierda", "Left"), ("Right", "Derecha", "Right"),
    ("Keypad Enter", "Intro (teclado num.)", "Keypad Enter"),
    ("Right Shift", "Mayus derecha", "Right Shift"), ("Right Ctrl", "Ctrl derecho", "Right Ctrl"),
    ("Left Alt", "Alt izquierdo", "Left Alt"), ("Home", "Inicio", "Home"), ("End", "Fin", "End"),
    ("PageUp", "Re Pag", "Page Up"), ("PageDown", "Av Pag", "Page Down"),
    ("Insert", "Insertar", "Insert"), ("Delete", "Suprimir", "Delete"),
] + [(f"Keypad {d}", f"{d} (teclado num.)", f"Keypad {d}") for d in range(10)]

def c(t): return t.replace("\\", "\\\\").replace('"', '\\"')
marca = "const Ie1Traduccion kIe1Traducciones[] = {" + nl
if marca not in s:
    sys.exit("No encontre la tabla de traducciones. No toco nada.")
nuevas = [x for x in NUEVAS if f'{{"{c(x[0])}", ' not in s]
if not nuevas:
    print("Ya estaban todas las traducciones."); sys.exit(0)
lineas = "".join(f'        {{"{c(o)}", "{c(e)}", "{c(i)}"}},{nl}' for o, e, i in nuevas)
s = s.replace(marca, marca + lineas, 1)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print(f"{len(nuevas)} traducciones anadidas. Recompila con: bash scripts/paso_mingw.sh")
