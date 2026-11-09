#!/usr/bin/env python3
"""
Vuelca una zona de punteros del ARM9 ingles y la zona equivalente del espanol,
mostrando el texto al que apunta cada palabra. Sirve para ver a mano como estan
organizadas las tablas de mensajes.

Uso (desde C:/dev/ie1recomp):
  python scripts/volcar_tabla.py "/c/ruta/rom_es.nds" 0x020B40E0 0x020B41E0 > run/tabla.txt
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(__file__))
from comparar_arm9 import arm9

BASE = 0x02000000


def texto(a9, v):
    o = v - BASE
    if not (0x4000 <= o < len(a9)):
        return ""
    j = a9.find(b"\0", o, o + 120)
    t = a9[o:j] if j > o else b""
    if len(t) >= 2 and sum(32 <= c < 127 or c >= 0x80 for c in t) >= 0.6 * len(t):
        return t.decode("latin-1")
    return ""


def volcar(nombre, a9, ini, fin):
    print(f"== {nombre} 0x{ini:08X}-0x{fin:08X}")
    for x in range(ini, fin, 4):
        v = struct.unpack_from("<I", a9, x - BASE)[0]
        print(f"  0x{x:08X}  0x{v:08X}  {texto(a9, v)!r}")


def main():
    en = open(os.path.join("images", "arm9.bin"), "rb").read()
    es, _, _ = arm9(sys.argv[1])
    ini, fin = int(sys.argv[2], 16), int(sys.argv[3], 16)
    volcar("ingles", en, ini, fin)
    volcar("espanol (+0x400..+0x480 alrededor)", es, ini + 0x400, fin + 0x480)


if __name__ == "__main__":
    main()
