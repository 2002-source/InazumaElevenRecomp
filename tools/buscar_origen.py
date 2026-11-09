#!/usr/bin/env python3
"""
Busca de donde sale el codigo que habia en RAM en una direccion.

Toma de la cobertura el contenido real de la pagina, extrae 64 bytes a partir
de la direccion y los busca en:
  - arm9.bin, arm7.bin y los 91 overlays (en cualquier posicion)
  - la ROM completa; si aparece, dice en que archivo del sistema de archivos
    del cartucho (NitroFS) esta y en que posicion dentro de el.

Uso (desde C:\\dev\\ie1recomp):
  python scripts/buscar_origen.py run/ie1_eur-coverage-XXXX.json 0x021759AC
"""
import base64, glob, json, os, struct, sys

PAGE = 0x1000


def nombres_fnt(rom):
    fnt_off, fnt_size = struct.unpack_from("<II", rom, 0x40)
    fnt = rom[fnt_off:fnt_off + fnt_size]
    nombres = {}

    def recorrer(dir_id, ruta):
        sub, first, _ = struct.unpack_from("<IHH", fnt, (dir_id & 0xFFF) * 8)
        p, fid = sub, first
        while True:
            n = fnt[p]
            p += 1
            if n == 0:
                break
            es_dir, largo = n & 0x80, n & 0x7F
            nombre = fnt[p:p + largo].decode("latin-1")
            p += largo
            if es_dir:
                sub_id = struct.unpack_from("<H", fnt, p)[0]
                p += 2
                recorrer(sub_id, ruta + nombre + "/")
            else:
                nombres[fid] = ruta + nombre
                fid += 1

    try:
        recorrer(0xF000, "/")
    except Exception as e:
        print(f"(no pude leer la tabla de nombres: {e})")
    return nombres


def main():
    cov = json.load(open(sys.argv[1], encoding="utf-8"))
    addr = int(sys.argv[2], 16)
    page = addr & ~(PAGE - 1)
    off = addr - page
    muestras = []
    for p in cov["pages"]["entries"]:
        if p["cpu"] == 9 and int(p["addr"], 16) == page and p.get("data"):
            m = base64.b64decode(p["data"])[off:off + 64]
            if m not in muestras:
                muestras.append(m)
    print(f"{len(muestras)} contenido(s) distinto(s) en 0x{addr:08X}")

    imgs = {"arm9.bin": "images/arm9.bin", "arm7.bin": "images/arm7.bin"}
    for f in sorted(glob.glob("images/overlays/ov9_*.bin")):
        imgs[os.path.basename(f)] = f
    rom = open(glob.glob("games/*.nds")[0], "rb").read()
    fat_off, fat_size = struct.unpack_from("<II", rom, 0x48)
    fat = [struct.unpack_from("<II", rom, fat_off + i * 8) for i in range(fat_size // 8)]
    nombres = nombres_fnt(rom)

    for n, m in enumerate(muestras):
        print(f"\n--- contenido {n}: {m[:16].hex()}...")
        if m.count(0) > 48:
            print("    (casi todo ceros, se omite)")
            continue
        for nombre, path in imgs.items():
            data = open(path, "rb").read()
            i = data.find(m)
            while i >= 0:
                print(f"    en {nombre} +0x{i:X}")
                i = data.find(m, i + 1)
        i = rom.find(m)
        hits = 0
        while i >= 0 and hits < 10:
            dueño = [fid for fid, (s, e) in enumerate(fat) if s <= i < e]
            if dueño:
                fid = dueño[0]
                s, e = fat[fid]
                print(f"    en la ROM +0x{i:X}: archivo {fid} "
                      f"'{nombres.get(fid, '(overlay o sin nombre)')}' +0x{i - s:X} (tamano 0x{e - s:X})")
            else:
                print(f"    en la ROM +0x{i:X} (fuera de cualquier archivo)")
            hits += 1
            i = rom.find(m, i + 1)
        if hits == 0:
            print("    no aparece tal cual en la ROM (puede venir comprimido o generarse en tiempo de ejecucion)")


if __name__ == "__main__":
    main()
