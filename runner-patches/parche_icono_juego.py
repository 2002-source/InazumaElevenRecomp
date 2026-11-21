#!/usr/bin/env python3
"""
Icono del ejecutable del juego (nds_runner.exe, en el port bin/nds_runner.exe):
el mismo que el lanzador, el icono de la ROM (el que sale en el menu de la DS).
Windows lo usa tambien para la ventana y la barra de tareas.

1. Saca el icono de la ROM (banner +0x20 dibujo 32x32 de 4 bits, +0x220 paleta)
   y lo guarda como runner/src/ie1_icono.ico (32, 64, 128 y 256 px).
2. Escribe runner/src/ie1_icono.rc.
3. Anade el .rc al ejecutable en runner/CMakeLists.txt (una sola vez).

Uso:      python scripts/parche_icono_juego.py [ruta de la ROM]
          (por defecto C:/dev/ie1recomp/games/ie1_eur.nds)
Despues:  bash scripts/paso_mingw.sh
Se puede ejecutar varias veces (rehace el icono; el CMakeLists solo se toca una vez).
"""
import os, struct, sys

RUNNER = "C:/dev/ndsrecomp/runner"
ROM = "C:/dev/ie1recomp/games/ie1_eur.nds"
MARCA = "IE1_ICONO"


def icono_de_rom(rom):
    if len(rom) < 0x200:
        sys.exit("La ROM es demasiado pequena.")
    b = struct.unpack_from("<I", rom, 0x68)[0]
    if b == 0 or b + 0x240 > len(rom):
        sys.exit("La ROM no tiene banner (icono).")
    pal = []
    for i in range(16):
        c = struct.unpack_from("<H", rom, b + 0x220 + 2 * i)[0]
        pal.append(((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31))
    px = [[None] * 32 for _ in range(32)]
    for t in range(16):
        for i in range(32):
            v = rom[b + 0x20 + t * 32 + i]
            for k, c in enumerate((v & 15, v >> 4)):
                x = (t % 4) * 8 + (i % 4) * 2 + k
                y = (t // 4) * 8 + i // 4
                px[y][x] = pal[c] if c else None
    return px


def crear_ico(px):
    tams = (32, 64, 128, 256)
    imgs = []
    for s in tams:
        d = bytearray(struct.pack("<IiiHHIIiiII", 40, s, s * 2, 1, 32, 0, 0, 0, 0, 0, 0))
        for y in range(s - 1, -1, -1):              # de abajo arriba, BGRA
            for x in range(s):
                c = px[y * 32 // s][x * 32 // s]
                d += bytes((c[2], c[1], c[0], 255)) if c else b"\0\0\0\0"
        fila = ((s + 31) // 32) * 4                 # mascara (1 bit por pixel, 1 = transparente)
        for y in range(s - 1, -1, -1):
            m = bytearray(fila)
            for x in range(s):
                if px[y * 32 // s][x * 32 // s] is None:
                    m[x // 8] |= 0x80 >> (x % 8)
            d += m
        imgs.append(bytes(d))
    ico = bytearray(struct.pack("<HHH", 0, 1, len(imgs)))
    pos = 6 + 16 * len(imgs)
    for s, d in zip(tams, imgs):
        ico += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(d), pos)
        pos += len(d)
    for d in imgs:
        ico += d
    return bytes(ico)


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else ROM
    try:
        rom = open(rom_path, "rb").read()
    except OSError:
        sys.exit("No encuentro la ROM: %s" % rom_path)
    src = os.path.join(RUNNER, "src")
    cm = os.path.join(RUNNER, "CMakeLists.txt")
    if not os.path.isdir(src) or not os.path.isfile(cm):
        sys.exit("No encuentro el runner en %s. No toco nada." % RUNNER)

    ico = os.path.join(src, "ie1_icono.ico")
    open(ico, "wb").write(crear_ico(icono_de_rom(rom)))
    print("escrito %s (32, 64, 128 y 256 px)" % ico)

    ruta_ico = os.path.abspath(ico).replace("\\", "/")
    open(os.path.join(src, "ie1_icono.rc"), "w", encoding="ascii").write(
        "// Icono del juego (parche_icono_juego.py): el de la ROM\n"
        "1 ICON \"%s\"\n" % ruta_ico)
    print("escrito %s" % os.path.join(src, "ie1_icono.rc"))

    s = open(cm, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in s else "\n"
    if MARCA in s:
        print("CMakeLists.txt ya llevaba el icono")
    else:
        ancla = "target_sources(nds_runner PRIVATE src/ie1_idiomas.cpp)  # IE1_IDIOMAS"
        if s.count(ancla) != 1:
            sys.exit("CMakeLists.txt no tiene la linea de ie1_idiomas.cpp (integrar_idiomas.py). No toco nada.")
        add = (nl + "if(WIN32)  # IE1_ICONO: icono del .exe (el de la ROM)" + nl +
               "    enable_language(RC)" + nl +
               "    target_sources(nds_runner PRIVATE src/ie1_icono.rc)" + nl +
               "endif()")
        s = s.replace(ancla, ancla + add)
        open(cm, "w", encoding="utf-8", newline="").write(s)
        print("modificado CMakeLists.txt")
    print("Compila el runner con: bash scripts/paso_mingw.sh")


if __name__ == "__main__":
    main()
