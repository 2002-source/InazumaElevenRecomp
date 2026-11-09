#!/usr/bin/env python3
"""
Frontend (runner/src/frontend.cpp): mientras el menu de los mods esta abierto,
el raton / tactil de la pantalla inferior va al menu y NO al juego.
Requiere parche_overlay.py.
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_OVERLAY_TACTIL" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
if "IE1_OVERLAY" not in s:
    sys.exit("Aplica antes parche_overlay.py.")
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)
def rep(viejo, nuevo, nombre):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    if s.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)
rep('''extern "C" void ie1_overlay_teclas(uint16_t pulsados);''',
'''extern "C" void ie1_overlay_teclas(uint16_t pulsados);
extern "C" void ie1_overlay_toque(int x, int y, int abajo);  // IE1_OVERLAY_TACTIL''', "declaracion")
rep('''    if (!down || x < left || x >= left + kScreenWidth ||
        y < bottom_origin || y >= bottom_origin + kScreenHeight) {
        nds_set_touch(0, 0, false);
        return;
    }''',
'''    if (!down || x < left || x >= left + kScreenWidth ||
        y < bottom_origin || y >= bottom_origin + kScreenHeight) {
        if (ie1_overlay_activo()) ie1_overlay_toque(0, 0, 0);  // IE1_OVERLAY_TACTIL
        nds_set_touch(0, 0, false);
        return;
    }''', "toque fuera / soltar")
rep('''    nds_set_touch(touch_x, touch_y, true);
}''',
'''    if (ie1_overlay_activo()) {  // IE1_OVERLAY_TACTIL: el toque es para el menu, no para el juego
        ie1_overlay_toque(touch_x, touch_y, 1);
        nds_set_touch(0, 0, false);
        return;
    }
    nds_set_touch(touch_x, touch_y, true);
}''', "toque dentro")
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Tactil del menu conectado en", PATH)
