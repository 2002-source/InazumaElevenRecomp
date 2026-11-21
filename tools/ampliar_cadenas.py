#!/usr/bin/env python3
"""
Anade a run/cadenas_<idioma>.json los textos del ARM9 que analizar_cadenas.py no
emparejo (por ejemplo "Gym" en el mapa y "None" en el filtro del ojeo).

La zona de tablas de punteros a textos del ARM9 (0x020B4000-0x020B4A00) esta en el
ARM9 espanol desplazada exactamente 0x43C bytes (asi estan emparejadas las 475
traducciones que ya habia). Para cada puntero de esa zona que no tenga traduccion, se
lee el texto al que apunta el puntero equivalente del ARM9 espanol.

Se dejan en ingles: los textos japoneses (iguales en las dos versiones), los iguales,
y los grupos de letras de la busqueda por nombre (ABC, DEF...), porque el codigo que
agrupa las letras es el ingles.

El desplazamiento de cada version (0x43C en la espanola) se calcula solo.

Uso (desde C:/dev/ie1recomp):
  python scripts/ampliar_cadenas.py "/c/ruta/rom_es.nds" [es]
  python scripts/ampliar_cadenas.py games/ie1_fr.nds fr
  python scripts/crear_parche_textos.py es
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comparar_arm9 import arm9   # noqa: E402

BASE = 0x02000000
ZONA = (0x020B4000, 0x020B4A00)
DESPL = 0x43C
NO_TOCAR = {b"ABC", b"DEF", b"GHI", b"JKL", b"MNO", b"PQRS", b"TUV", b"WXYZ"}


def cadena(a9, addr, maximo=300):
    o = addr - BASE
    if not (0 <= o < len(a9)):
        return None
    j = a9.find(b"\0", o, o + maximo)
    return a9[o:j] if j > o else None


def es_texto(t):
    if not t or any(b < 0x20 and b not in (0x0A,) for b in t):
        return False
    ascii_letras = sum(1 for b in t if b < 0x80 and chr(b).isalpha())
    return ascii_letras >= 1 or t.startswith(b"%")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    idioma = sys.argv[2] if len(sys.argv) > 2 else "es"
    ruta = os.path.join("run", f"cadenas_{idioma}.json")
    datos = json.load(open(ruta))
    en = open(os.path.join("images", "arm9.bin"), "rb").read()
    global DESPL
    es, _, _ = arm9(sys.argv[1])
    from revisar_roms_idiomas import desplazamiento
    DESPL = desplazamiento(en, es)[0]
    con_punteros = {int(p, 16) for v in datos.values() for p in v["punteros"]}
    # comprobar el desplazamiento con las que ya estan
    ok = mal = 0
    for k, v in datos.items():
        for p in v["punteros"]:
            p = int(p, 16)
            if ZONA[0] <= p < ZONA[1]:
                b = struct.unpack_from("<I", es, p + DESPL - BASE)[0]
                if cadena(es, b) == bytes.fromhex(v["es"]):
                    ok += 1
                else:
                    mal += 1
    print(f"Comprobacion del desplazamiento {DESPL:#x}: {ok} coinciden, {mal} no")
    if ok < 100 or mal > ok // 10:
        sys.exit("El desplazamiento no cuadra con esta ROM espanola; no toco nada.")
    nuevas = 0
    for p in range(ZONA[0], ZONA[1], 4):
        if p in con_punteros:
            continue
        a = struct.unpack_from("<I", en, p - BASE)[0]
        if not (0x020A0000 <= a < ZONA[0]):
            continue
        t_en = cadena(en, a)
        if not es_texto(t_en) or t_en in NO_TOCAR:
            continue
        b = struct.unpack_from("<I", es, p + DESPL - BASE)[0]
        t_es = cadena(es, b)
        if not t_es or t_es == t_en or max(t_en) >= 0x81 and t_en == t_es:
            continue
        clave = f"0x{a:08X}"
        if clave in datos:
            if p not in [int(x, 16) for x in datos[clave]["punteros"]] and bytes.fromhex(datos[clave]["es"]) == t_es:
                datos[clave]["punteros"].append(f"0x{p:08X}")
            continue
        datos[clave] = {"en": t_en.hex(), "es": t_es.hex(), "punteros": [f"0x{p:08X}"], "fijo": False}
        nuevas += 1
        print(f"  {p:#010x}: {t_en.decode('latin-1')!r} -> {t_es.decode('latin-1')!r}")
    json.dump(datos, open(ruta, "w"), indent=1)
    print(f"{nuevas} textos nuevos anadidos a {ruta} (total {len(datos)}).")
    print("Ahora: python scripts/crear_parche_textos.py " + idioma)


if __name__ == "__main__":
    main()
