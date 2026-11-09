#!/usr/bin/env python3
"""
Lista los archivos internos (NitroFS) de una ROM de DS: ruta, tamano y una
huella corta de su contenido. Sirve para comparar versiones (ingles, espanol,
japones...) y ver que archivos cambian entre idiomas.

Uso (desde C:/dev/ie1recomp):
  python scripts/listar_archivos.py games/ie1_eur.nds > run/archivos_en.txt
  python scripts/listar_archivos.py /c/ruta/rom_es.nds > run/archivos_es.txt
  python scripts/listar_archivos.py --comparar run/archivos_en.txt run/archivos_es.txt

La salida contiene solo nombres, tamanos y huellas, no el contenido.
"""
import hashlib, struct, sys


def leer_fnt(rom):
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

    recorrer(0xF000, "/")
    return nombres


def listar(path):
    rom = open(path, "rb").read()
    fat_off, fat_size = struct.unpack_from("<II", rom, 0x48)
    nombres = leer_fnt(rom)
    titulo = rom[0:12].decode(errors="ignore").strip("\0 ")
    codigo = rom[0x0C:0x10].decode(errors="ignore")
    print(f"# ROM {titulo} {codigo} sha1={hashlib.sha1(rom).hexdigest()} archivos={len(nombres)}")
    for fid in sorted(nombres):
        s, e = struct.unpack_from("<II", rom, fat_off + fid * 8)
        h = hashlib.sha1(rom[s:e]).hexdigest()[:12]
        print(f"{fid}\t{e - s}\t{h}\t{nombres[fid]}")


def comparar(a, b):
    def carga(p):
        d = {}
        for line in open(p, encoding="utf-8", errors="ignore"):
            if line.startswith("#") or not line.strip():
                continue
            fid, size, h, ruta = line.rstrip("\n").split("\t", 3)
            d[ruta] = (int(size), h)
        return d
    A, B = carga(a), carga(b)
    iguales = [r for r in A if r in B and A[r][1] == B[r][1]]
    distintos = [r for r in A if r in B and A[r][1] != B[r][1]]
    solo_a = [r for r in A if r not in B]
    solo_b = [r for r in B if r not in A]
    print(f"Archivos: {len(A)} vs {len(B)}")
    print(f"  identicos: {len(iguales)}   distintos: {len(distintos)}   "
          f"solo en el 1o: {len(solo_a)}   solo en el 2o: {len(solo_b)}")
    carpetas = {}
    for r in distintos:
        c = r.rsplit("/", 1)[0] + "/"
        carpetas.setdefault(c, [0, 0, 0])
        carpetas[c][0] += 1
        carpetas[c][1] += A[r][0]
        carpetas[c][2] += B[r][0]
    print("\nCarpetas con archivos distintos (n, tamano 1o, tamano 2o):")
    for c, (n, sa, sb) in sorted(carpetas.items(), key=lambda kv: -kv[1][0]):
        print(f"  {n:5d}  {sa:>11,}  {sb:>11,}  {c}")
    for titulo, lista in (("Solo en el 1o", solo_a), ("Solo en el 2o", solo_b)):
        if lista:
            print(f"\n{titulo} (primeros 30):")
            for r in lista[:30]:
                print("  ", r)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--comparar":
        comparar(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2:
        listar(sys.argv[1])
    else:
        print(__doc__)
