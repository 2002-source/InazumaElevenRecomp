#!/usr/bin/env python3
"""
Descomprime el ARM9 de dos ROMs y muestra en que direcciones difieren.
Sirve para saber si el CODIGO del ARM9 es el mismo y solo cambian datos
(textos, tablas) al final.

Uso (desde C:/dev/ie1recomp):
  python scripts/comparar_arm9.py games/ie1_eur.nds "/c/ruta/rom_es.nds"
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(__file__))
from comparar_codigo import blz


def arm9(path):
    rom = open(path, "rb").read()
    off, entry, ram, size = struct.unpack_from("<IIII", rom, 0x20)
    a9 = bytearray(rom[off:off + size])
    i = a9.find(struct.pack("<II", 0xDEC00621, 0x2106C0DE))
    if i < 0:
        return bytes(a9), ram, None
    params = struct.unpack_from("<7I", a9, i - 0x1C)
    comp_end = params[5]
    if comp_end:
        n = comp_end - ram
        dec = blz(bytes(a9[:n]))
        a9 = bytearray(dec) + a9[n:]
    return bytes(a9), ram, params


def main():
    A, ra, pa = arm9(sys.argv[1])
    B, rb, pb = arm9(sys.argv[2])
    print(f"ARM9 descomprimido: {len(A)} vs {len(B)} bytes (carga en 0x{ra:08X} / 0x{rb:08X})")
    if pa and pb:
        nombres = ["autoload_inicio", "autoload_fin", "autoload_datos", "bss_inicio", "bss_fin"]
        for n, x, y in zip(nombres, pa, pb):
            print(f"  {n:16s} 0x{x:08X}  0x{y:08X}  {'(igual)' if x == y else f'(+0x{y - x:X})'}")
    n = min(len(A), len(B))
    # Los primeros 0x4000 bytes son el "area segura" (cifrada, distinta en cada ROM): se omiten.
    tramos, i = [], 0x4000
    while i < n:
        if A[i] != B[i]:
            j = i
            while j < n and (A[j] != B[j] or (j + 16 < n and A[j:j + 16] != B[j:j + 16])):
                j += 1
            tramos.append((i, j))
            i = j
        else:
            i += 1
    if not tramos:
        print("Identicos (salvo el area segura) en la parte comun.")
        return
    print(f"Primera diferencia real: 0x{ra + tramos[0][0]:08X}; "
          f"{(tramos[0][0] - 0x4000) / (n - 0x4000) * 100:.1f} % del ARM9 (tras el area segura) es identico antes")
    print(f"Tramos distintos: {len(tramos)}  (primeros 15):")
    for a, b in tramos[:15]:
        print(f"  0x{ra + a:08X}-0x{ra + b:08X} ({b - a} bytes)  {A[a:a + 24]!r}")
        print(f"  {'':23s}  {B[a:a + 24]!r}")

if __name__ == "__main__":
    main()
