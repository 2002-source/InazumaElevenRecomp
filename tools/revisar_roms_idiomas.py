#!/usr/bin/env python3
"""
Revisa ROMs de Inazuma Eleven 1 en otros idiomas antes de crear sus paquetes de idioma.
No cambia nada: solo mira y apunta. Para cada ROM dice:
  - codigo del juego y tamano del ARM9 (comparado con la ROM inglesa base)
  - que carpetas de idioma tiene (en, fr, ge, it, sp...) y cuantos archivos tiene cada una
  - cuantos archivos con la misma ruta que la ROM inglesa son distintos
  - el desplazamiento de la tabla de textos del ARM9 (en la espanola es 0x43C), que hace
    falta para traducir los menus que estan dentro del codigo

Uso (desde C:/dev/ie1recomp):
  python scripts/revisar_roms_idiomas.py games/ie1_fr.nds games/ie1_de.nds games/ie1_it.nds
  (se puede anadir la espanola para comprobar que sale 0x43C)
El informe se guarda tambien en run/revision_idiomas.txt
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comparar_arm9 import arm9            # noqa: E402
from listar_cambios_mod import archivos   # noqa: E402

BASE = 0x02000000
ZONA = (0x020B4000, 0x020B4A00)           # tablas de punteros a textos del ARM9 ingles
CARPETAS = {"en", "sp", "es", "fr", "ge", "de", "it", "gm", "nl", "ja", "jp"}
lineas = []


def decir(t=""):
    print(t)
    lineas.append(t)


def es_texto(a9, v):
    o = v - BASE
    if not (0 < o < len(a9)) or a9[o - 1] != 0:
        return False
    j = a9.find(b"\0", o, o + 200)
    if j <= o + 1:
        return False
    t = a9[o:j]
    return all(b >= 0x20 or b == 0x0A for b in t) and any(chr(b).isalpha() for b in t if b < 0x80)


def desplazamiento(en, a9):
    """El desplazamiento d con el que la zona de tablas del ARM9 cuadra mejor con la inglesa:
    donde la inglesa tiene un puntero a texto, aqui tambien (a su texto traducido), y donde
    tiene otro numero (indices, tamanos...), aqui el mismo numero."""
    pat = []
    for p in range(ZONA[0], ZONA[1], 4):
        v = struct.unpack_from("<I", en, p - BASE)[0]
        pat.append((p, "t" if es_texto(en, v) else (None if BASE <= v < 0x02400000 else v)))
    total = sum(1 for _, x in pat if x is not None)
    mejor = (0, 0)
    for d in range(-0x4000, 0x4001, 4):
        n = 0
        for p, x in pat:
            if x is None:
                continue
            o = p + d - BASE
            if not (0 <= o <= len(a9) - 4):
                continue
            v = struct.unpack_from("<I", a9, o)[0]
            n += (es_texto(a9, v) if x == "t" else v == x)
        if n > mejor[0]:
            mejor = (n, d)
    return mejor[1], mejor[0], total


def carpetas_idioma(fs):
    c = collections.Counter()
    for r in fs:
        for parte in r.strip("/").split("/")[:-1]:
            if parte.lower() in CARPETAS:
                c[parte.lower()] += 1
                break
    return c


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    base = os.path.join("games", "ie1_eur.nds")
    rom_en = open(base, "rb").read()
    en, _, _ = arm9(base)
    fs_en = archivos(rom_en)
    decir(f"Base: {base}  codigo {rom_en[0x0C:0x10].decode('latin-1')}  ARM9 {len(en):#x}  "
          f"archivos {len(fs_en)}  carpetas {dict(carpetas_idioma(fs_en))}")
    for ruta in sys.argv[1:]:
        decir()
        decir(f"=== {ruta}")
        if not os.path.isfile(ruta):
            decir("   no existe ese archivo")
            continue
        rom = open(ruta, "rb").read()
        if len(rom) < 0x200 or rom[0x15C:0x15E] != rom_en[0x15C:0x15E]:
            decir("   no parece una ROM de NDS")
            continue
        a9, _, _ = arm9(ruta)
        fs = archivos(rom)
        decir(f"   titulo {rom[0:12].decode('latin-1').strip(chr(0))!r}  codigo {rom[0x0C:0x10].decode('latin-1')}  "
              f"version {rom[0x1E]}  tamano {len(rom) // (1024 * 1024)} MB")
        decir(f"   ARM9 {len(a9):#x} (ingles {len(en):#x}, diferencia {len(a9) - len(en):+#x})")
        decir(f"   archivos {len(fs)}; carpetas de idioma {dict(carpetas_idioma(fs))}")
        solo_aqui = sorted(set(fs) - set(fs_en))
        solo_en = sorted(set(fs_en) - set(fs))
        distintos = sorted(r for r in set(fs) & set(fs_en) if fs[r] != fs_en[r])
        decir(f"   rutas que solo estan aqui: {len(solo_aqui)}; que solo estan en la inglesa: {len(solo_en)}; "
              f"misma ruta pero distintos: {len(distintos)}")
        for nombre, lista in (("solo aqui", solo_aqui), ("solo en la inglesa", solo_en), ("distintos", distintos)):
            if lista:
                decir(f"     ejemplos {nombre}: " + ", ".join(lista[:8]))
        d, n, n_en = desplazamiento(en, a9)
        decir(f"   tabla de textos del ARM9: desplazamiento {d:#x} (cuadran {n} de {n_en} datos"
              f"{'; POCOS, hay que mirarlo a mano' if n < n_en * 0.8 else ''})")
    os.makedirs("run", exist_ok=True)
    open(os.path.join("run", "revision_idiomas.txt"), "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    print("\nInforme guardado en run/revision_idiomas.txt")


if __name__ == "__main__":
    main()
