#!/usr/bin/env python3
"""
Overlay de los mods (menu de entrenamiento, panel de "Valor"): con el renderizador
compute, la pantalla de arriba se dibuja por el camino directo de la tarjeta
grafica. Hasta ahora, en cuanto el complemento dibujaba algo (en cualquier
pantalla), ese camino se apagaba y la de arriba pasaba por la CPU (mas lento).
Con este parche solo se apaga si el complemento ha cambiado de verdad la imagen
de ARRIBA; si solo cambia la de abajo (el panel de valor), sigue el camino directo.
   python scripts/parche_overlay_directo.py   y despues   bash scripts/paso_mingw.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_OVERLAY_DIRECTO" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
a = "    const uint32_t* ie1_arriba = top_pixels;"
b = "        const bool direct = !ie1_ov && nds_gpu2d_direct_frame(&direct_frame);  // IE1_OVERLAY"
if s.count(a) != 1 or s.count(b) != 1:
    sys.exit("No encontre el codigo del overlay en frontend.cpp (aplica antes parche_overlay.py). No toco nada.")
s = s.replace(a, "    const uint32_t* const ie1_arriba_orig = top_pixels;   // IE1_OVERLAY_DIRECTO" + nl + a)
s = s.replace(b, "        const bool direct = !(ie1_ov && ie1_arriba != ie1_arriba_orig) &&   // IE1_OVERLAY_DIRECTO" + nl +
                 "                            nds_gpu2d_direct_frame(&direct_frame);")
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado: el camino directo solo se apaga si el overlay cambia la pantalla de arriba.")
print("Recompila con: bash scripts/paso_mingw.sh")
