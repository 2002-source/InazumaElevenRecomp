#!/usr/bin/env python3
"""
Mod "Tiro del IE2": boton de tiro con la letra de cada idioma.

El grafico del boton (pic3d/en/gmdn_c02.pac_) trae una "S" (Shoot) en todas las versiones
del IE1 (inglesa, francesa, alemana e italiana: el mismo archivo). Este script dibuja una
"T" con el mismo estilo (contorno, brillo y sombra de la S) en los 11 dibujos del boton
(el normal y los del contador 0-9) y la guarda como archivo de idioma del mod:
   mods/tiro_ie2/idioma/es/data_iz/pic3d/en/gmdn_c02.pac_   (Tiro)
   mods/tiro_ie2/idioma/fr/...                               (Tir)
   mods/tiro_ie2/idioma/it/...                               (Tiro)
En ingles (Shoot) y aleman (Schuss) se queda la S del juego.

Uso (desde C:/dev/ie1recomp):
   python scripts/crear_mod_tiro.py games/ie1_eur.nds
   (opcional: --mods RUTA/mods, por defecto C:/dev/ie1recomp/mods; --png para ver el resultado)
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crear_npc_entrenador as C   # noqa: E402  (archivo_rom, lz10_des, lz10_com)

RUTA = "/data_iz/pic3d/en/gmdn_c02.pac_"
IDIOMAS_T = ("es", "fr", "it")

# La "T" en la zona de la S (columnas 5..17 y sombra en la 18, filas 5..18 de cada dibujo de 24x24).
# Mismos colores que la S: 6 contorno, 7 azul oscuro, 9 azul claro, F blanco (brillo),
# E celeste (mitad de abajo), 1 sombra. "." = transparente.
T = [
    "6666666666666.",   # fila 5
    "67FFFFFFFFF961",   # fila 6
    "699999FF999761",   # fila 7
    "666669FF966661",   # fila 8
    ".11169FF961111",   # fila 9
    "....69FF961...",   # fila 10
    "....69FF961...",   # fila 11
    "....6E99E61...",   # fila 12
    "....6E99E61...",   # fila 13
    "....6E99E61...",   # fila 14
    "....6E99E61...",   # fila 15
    "....6EEE761...",   # fila 16
    "....666661....",   # fila 17
    ".....11111....",   # fila 18
]
X0, Y0 = 5, 5


def secciones(d):
    k = struct.unpack_from("<I", d, 0)[0]
    return [struct.unpack_from("<2I", d, 4 + 8 * i) for i in range(k)]


def con_t(pac):
    d = bytearray(C.lz10_des(pac))
    s = secciones(d)
    (po, pl), (_, _), (do, dl) = s[0], s[1], s[2]
    n, wl = struct.unpack_from("<HB", d, do)
    w = 8 << wl
    frames = [struct.unpack_from("<4H", d, do + 8 + 8 * i) for i in range(n)]

    def ci(x, y):
        b = d[po + (y * w + x) // 2]
        return b & 15 if x % 2 == 0 else b >> 4

    def pon(x, y, v):
        o = po + (y * w + x) // 2
        d[o] = (d[o] & 0xF0) | v if x % 2 == 0 else (d[o] & 0x0F) | (v << 4)

    fx, fy, fw, fh = frames[0]
    if (fw, fh) != (24, 24) or n < 11:
        raise SystemExit(f"{RUTA}: no tiene el formato esperado ({n} dibujos de {fw}x{fh})")
    # la S del dibujo 0 (lo que hay que borrar en todos los dibujos)
    zona = [(x, y) for y in range(24) for x in range(19)]
    s_pix = {(x, y): ci(fx + x, fy + y) for x, y in zona}
    if sum(1 for v in s_pix.values() if v) < 100:
        raise SystemExit(f"{RUTA}: el dibujo 0 no parece el boton S")
    cambiados = 0
    for fx2, fy2, _, _ in frames:
        for x, y in zona:
            actual = ci(fx2 + x, fy2 + y)
            if actual != s_pix[(x, y)]:
                continue            # es parte del numero del contador: no se toca
            nuevo = 0
            if Y0 <= y < Y0 + len(T) and X0 <= x < X0 + len(T[0]):
                c = T[y - Y0][x - X0]
                nuevo = 0 if c == "." else int(c, 16)
            if nuevo != actual:
                pon(fx2 + x, fy2 + y, nuevo)
                cambiados += 1
    return bytes(d), C.lz10_com(bytes(d)), cambiados, (po, w, frames, s[1])


def png(d, info, salida):
    from PIL import Image
    po, w, frames, (qo, ql) = info
    pal = []
    for i in range(ql // 2):
        c = d[qo + 2 * i] | d[qo + 2 * i + 1] << 8
        pal.append(((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31, 255))
    im = Image.new("RGBA", (24 * len(frames), 24), (40, 40, 40, 255))
    p = im.load()
    for k, (fx, fy, _, _) in enumerate(frames):
        for y in range(24):
            for x in range(24):
                b = d[po + ((fy + y) * w + fx + x) // 2]
                v = b & 15 if (fx + x) % 2 == 0 else b >> 4
                if v:
                    p[24 * k + x, y] = pal[v]
    im.resize((im.width * 4, im.height * 4), Image.NEAREST).save(salida)
    print(f"Vista previa: {salida}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--mods", default="C:/dev/ie1recomp/mods")
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    pac = C.archivo_rom(rom, RUTA)
    d, comprimido, n, info = con_t(pac)
    if C.lz10_des(comprimido) != d:
        raise SystemExit("Error al comprimir el grafico (no se ha escrito nada)")
    for lang in IDIOMAS_T:
        dest = os.path.join(a.mods, "tiro_ie2", "idioma", lang, RUTA.strip("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(comprimido)
        print(f"Escrito {dest}")
    print(f"Boton T listo ({n} pixeles cambiados en 11 dibujos). En ingles y aleman se queda la S.")
    if a.png:
        png(d, info, os.path.join("run", "boton_tiro_T.png"))


if __name__ == "__main__":
    main()
