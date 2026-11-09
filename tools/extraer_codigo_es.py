#!/usr/bin/env python3
"""
Extrae el codigo de la ROM espanola (ARM9 + overlays, descomprimidos) a un zip
pequeno, para compararlo con el de la version inglesa.

  python scripts/extraer_codigo_es.py "D:/ruta/ie1_eur_es.nds"

Resultado: C:/dev/ie1recomp/run/codigo_es.zip
(arm9.bin, overlays/ovNNN.bin, overlays.csv y run/cadenas_es.json si existe)
"""
import csv, io, os, struct, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extraer_recursos import blz_descomprimir   # misma descompresion que para la ROM inglesa


def u32(b, o): return struct.unpack_from("<I", b, o)[0]


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python scripts/extraer_codigo_es.py <rom_espanola.nds>")
    rom = open(sys.argv[1], "rb").read()
    dest = "C:/dev/ie1recomp/run/codigo_es.zip"
    a9o, a9s = u32(rom, 0x20), u32(rom, 0x2C)
    fat_o = u32(rom, 0x48)
    y9o, y9s = u32(rom, 0x50), u32(rom, 0x54)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("arm9.bin", blz_descomprimir(rom[a9o:a9o + a9s]))
        tabla = io.StringIO()
        w = csv.writer(tabla)
        w.writerow(["overlay", "direccion_carga", "tamano_en_ram", "bss", "id_archivo", "comprimido", "tamano_descomprimido"])
        for k in range(y9s // 32):
            e = y9o + 32 * k
            ov, ram, rsize, bss, fid, flags = (u32(rom, e), u32(rom, e + 4), u32(rom, e + 8),
                                              u32(rom, e + 12), u32(rom, e + 24), u32(rom, e + 28))
            s0, e0 = u32(rom, fat_o + 8 * fid), u32(rom, fat_o + 8 * fid + 4)
            comp = bool(flags & 0x01000000)
            dd = blz_descomprimir(rom[s0:e0]) if comp else rom[s0:e0]
            z.writestr(f"overlays/ov{ov:03d}.bin", dd)
            w.writerow([f"{ov:03d}", f"0x{ram:08X}", rsize, bss, fid, "si" if comp else "no", len(dd)])
        z.writestr("overlays.csv", tabla.getvalue())
        cj = "C:/dev/ie1recomp/run/cadenas_es.json"
        if os.path.exists(cj):
            z.write(cj, "cadenas_es.json")
    print("Creado:", dest, f"({os.path.getsize(dest) // 1024} KB)")


if __name__ == "__main__":
    main()
