#!/usr/bin/env python3
"""
Crea un PAQUETE DE IDIOMA a partir de una ROM de Inazuma Eleven 1 (tuya):
copia los archivos de su carpeta de idioma (textos, imagenes con texto y
sonido/voces) a  idiomas/<idioma>/  con las rutas de la version inglesa,
que es la base del recomp. Despues la ROM de ese idioma ya no hace falta.

Uso (desde C:/dev/ie1recomp):
  python scripts/crear_paquete_idioma.py "/c/ruta/rom_es.nds" es
  python scripts/crear_paquete_idioma.py "/c/ruta/rom_fr.nds" fr --base games/ie1_eur.nds
  python scripts/crear_paquete_idioma.py "/c/ruta/rom_jp.nds" jp --base games/ie1_eur.nds --solo-sonido

Con --base solo se copian los archivos que cambian respecto a la ROM base.
El paquete es contenido del juego: es para tu uso, no lo distribuyas.
"""
import argparse, hashlib, os, struct

CARPETAS_IDIOMA = {"en", "sp", "fr", "ge", "it", "gm", "nl", "ja", "jp", "es", "de"}


def archivos(path):
    rom = open(path, "rb").read()
    fnt_off, fnt_size = struct.unpack_from("<II", rom, 0x40)
    fat_off = struct.unpack_from("<I", rom, 0x48)[0]
    fnt = rom[fnt_off:fnt_off + fnt_size]
    res = {}

    def recorrer(dir_id, ruta):
        sub, first, _ = struct.unpack_from("<IHH", fnt, (dir_id & 0xFFF) * 8)
        p, fid = sub, first
        while True:
            n = fnt[p]; p += 1
            if n == 0:
                break
            es_dir, largo = n & 0x80, n & 0x7F
            nombre = fnt[p:p + largo].decode("latin-1"); p += largo
            if es_dir:
                sid = struct.unpack_from("<H", fnt, p)[0]; p += 2
                recorrer(sid, ruta + nombre + "/")
            else:
                s, e = struct.unpack_from("<II", rom, fat_off + fid * 8)
                res[ruta + nombre] = rom[s:e]
                fid += 1

    recorrer(0xF000, "/")
    return rom, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("idioma")
    ap.add_argument("--base")
    ap.add_argument("--salida", default="idiomas")
    ap.add_argument("--solo-sonido", action="store_true",
                    help="solo los archivos de sonido; sirve para versiones sin carpetas de "
                         "idioma (p. ej. la japonesa): se emparejan por nombre con sound/en")
    a = ap.parse_args()
    rom, fs = archivos(a.rom)
    base = archivos(a.base)[1] if a.base else None
    destino = os.path.join(a.salida, a.idioma)
    n = tam = omitidos = 0
    for ruta, datos in fs.items():
        partes = ruta.split("/")
        if a.solo_sonido and "/sound/" not in ruta:
            continue
        idx = [i for i, x in enumerate(partes[:-1]) if x in CARPETAS_IDIOMA]
        if idx:
            partes[idx[-1]] = "en"                 # ruta equivalente en la base inglesa
            ruta_en = "/".join(partes)
        elif a.solo_sonido and ruta.startswith("/data_iz/sound/"):
            # Version sin carpetas de idioma: mismo nombre dentro de sound/en
            ruta_en = "/data_iz/sound/en/" + partes[-1]
        else:
            continue
        if base is not None:
            if ruta_en not in base:
                omitidos += 1
                continue
            if hashlib.sha1(base[ruta_en]).digest() == hashlib.sha1(datos).digest():
                continue
        out = os.path.join(destino, ruta_en.lstrip("/"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(datos)
        n += 1
        tam += len(datos)
    print(f"Paquete '{a.idioma}': {n} archivos, {tam / 1048576:.1f} MB en {destino}")
    if omitidos:
        print(f"  ({omitidos} archivos sin equivalente en la base; omitidos)")


if __name__ == "__main__":
    main()
