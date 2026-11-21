#!/usr/bin/env python3
"""
Runner: con el menu propio de los mods CERRADO, pasa tambien los botones y el tactil al
complemento, que puede quedarselos (devuelve 1) para abrir su menu. Lo usan los filtros
de los cuadernos de supertecnicas: X (o tocar el boton "Filtros") abre la ventana.

Toca runner/src/ie1_idiomas.cpp y runner/src/frontend.cpp. Requiere parche_overlay.py y
parche_overlay_tactil.py. Se puede ejecutar varias veces.
   python scripts/parche_overlay_vigilar.py   y despues   bash scripts/paso_mingw.sh
"""
import sys

IDIOMAS = "C:/dev/ndsrecomp/runner/src/ie1_idiomas.cpp"
FRONT = "C:/dev/ndsrecomp/runner/src/frontend.cpp"


def parchear(path, cambios, marca):
    s = open(path, encoding="utf-8", newline="").read()
    if marca in s:
        print(f"{path}: ya estaba aplicado.")
        return
    nl = "\r\n" if "\r\n" in s else "\n"
    for viejo, nuevo, nombre in cambios:
        viejo, nuevo = viejo.replace("\n", nl), nuevo.replace("\n", nl)
        if s.count(viejo) != 1:
            sys.exit(f"{path}: no encontre exactamente una vez: {nombre}. No toco nada.")
        s = s.replace(viejo, nuevo)
    open(path, "w", encoding="utf-8", newline="").write(s)
    print(f"{path}: parcheado.")


parchear(IDIOMAS, [
    ('''FnToque g_ov_toque = nullptr;''',
     '''FnToque g_ov_toque = nullptr;
// IE1_OVERLAY_VIGILAR: botones y tactil con el menu cerrado (el complemento puede quedarselos)
using FnVigTeclas = int (*)(uint16_t);
using FnVigToque = int (*)(int, int, int);
FnVigTeclas g_ov_vig_teclas = nullptr;
FnVigToque g_ov_vig_toque = nullptr;''', "variables"),
    ('''    g_ov_toque = reinterpret_cast<FnToque>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_toque_v1")));''',
     '''    g_ov_toque = reinterpret_cast<FnToque>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_overlay_toque_v1")));
    g_ov_vig_teclas = reinterpret_cast<FnVigTeclas>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_vigilar_teclas_v1")));
    g_ov_vig_toque = reinterpret_cast<FnVigToque>(reinterpret_cast<void*>(GetProcAddress(h, "ie1_mods_vigilar_toque_v1")));''', "carga"),
    ('''extern "C" void ie1_overlay_toque(int x, int y, int abajo) { if (g_ov_disponible && g_ov_toque) g_ov_toque(x, y, abajo); }''',
     '''extern "C" void ie1_overlay_toque(int x, int y, int abajo) { if (g_ov_disponible && g_ov_toque) g_ov_toque(x, y, abajo); }
extern "C" int ie1_overlay_vigilar_teclas(uint16_t p) { return g_ov_vig_teclas ? g_ov_vig_teclas(p) : 0; }  // IE1_OVERLAY_VIGILAR
extern "C" int ie1_overlay_vigilar_toque(int x, int y, int abajo) { return g_ov_vig_toque ? g_ov_vig_toque(x, y, abajo) : 0; }''', "funciones"),
], "IE1_OVERLAY_VIGILAR")

parchear(FRONT, [
    ('''extern "C" void ie1_overlay_toque(int x, int y, int abajo);  // IE1_OVERLAY_TACTIL''',
     '''extern "C" void ie1_overlay_toque(int x, int y, int abajo);  // IE1_OVERLAY_TACTIL
extern "C" int ie1_overlay_vigilar_teclas(uint16_t pulsados);  // IE1_OVERLAY_VIGILAR
extern "C" int ie1_overlay_vigilar_toque(int x, int y, int abajo);''', "declaraciones"),
    ('''            nds_set_key_mask(0x0FFFu);
            return;
        }
        nds_set_key_mask(static_cast<uint16_t>(''',
     '''            nds_set_key_mask(0x0FFFu);
            return;
        }
        if (ie1_overlay_vigilar_teclas(static_cast<uint16_t>(  // IE1_OVERLAY_VIGILAR
                keyboard_pressed | controller_pressed | mouse_pressed |
                mph_prime_pressed | stick_pressed))) {
            nds_set_key_mask(0x0FFFu);
            return;
        }
        nds_set_key_mask(static_cast<uint16_t>(''', "publish_keys"),
    ('''        if (ie1_overlay_activo()) ie1_overlay_toque(0, 0, 0);  // IE1_OVERLAY_TACTIL''',
     '''        if (ie1_overlay_activo()) ie1_overlay_toque(0, 0, 0);  // IE1_OVERLAY_TACTIL
        else ie1_overlay_vigilar_toque(0, 0, 0);  // IE1_OVERLAY_VIGILAR''', "soltar"),
    ('''    if (ie1_overlay_activo()) {  // IE1_OVERLAY_TACTIL: el toque es para el menu, no para el juego''',
     '''    if (!ie1_overlay_activo() && ie1_overlay_vigilar_toque(touch_x, touch_y, 1)) {  // IE1_OVERLAY_VIGILAR
        nds_set_touch(0, 0, false);
        return;
    }
    if (ie1_overlay_activo()) {  // IE1_OVERLAY_TACTIL: el toque es para el menu, no para el juego''', "toque"),
], "IE1_OVERLAY_VIGILAR")
print("Recompila con: bash scripts/paso_mingw.sh")
