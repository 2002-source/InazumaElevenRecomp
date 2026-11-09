#!/usr/bin/env python3
"""
Busca en que parte de la ROM esta un texto: en el codigo (ARM9 u overlays,
ya descomprimidos) o en los archivos internos (sin comprimir o LZ).

Uso (desde C:/dev/ie1recomp):
  python scripts/buscar_texto.py games/ie1_eur.nds "Inventory" "Special Moves" "Main Bldg"
"""
import struct, sys, os

sys.path.insert(0, os.path.dirname(__file__))
from comparar_codigo import blz            # descompresion de overlays
from crear_paquete_idioma import archivos  # archivos internos por ruta


def lz(data):
    """Descompresion LZ10/LZ11 de los archivos (cabecera 0x10 / 0x11)."""
    if len(data) < 4 or data[0] not in (0x10, 0x11):
        return None
    size = struct.unpack_from("<I", data, 0)[0] >> 8
    if size == 0 or size > 16 * 1024 * 1024:
        return None
    out, p, ext = bytearray(), 4, data[0] == 0x11
    try:
        while len(out) < size:
            flags = data[p]; p += 1
            for _ in range(8):
                if len(out) >= size:
                    break
                if not flags & 0x80:
                    out.append(data[p]); p += 1
                else:
                    b0 = data[p]
                    if not ext:
                        n = (b0 >> 4) + 3; disp = ((b0 & 0xF) << 8 | data[p + 1]) + 1; p += 2
                    else:
                        hi = b0 >> 4
                        if hi == 0:
                            n = (((b0 & 0xF) << 4) | (data[p + 1] >> 4)) + 0x11
                            disp = ((data[p + 1] & 0xF) << 8 | data[p + 2]) + 1; p += 3
                        elif hi == 1:
                            n = (((b0 & 0xF) << 12) | (data[p + 1] << 4) | (data[p + 2] >> 4)) + 0x111
                            disp = ((data[p + 2] & 0xF) << 8 | data[p + 3]) + 1; p += 4
                        else:
                            n = hi + 1; disp = ((b0 & 0xF) << 8 | data[p + 1]) + 1; p += 2
                    for _ in range(n):
                        out.append(out[-disp])
                flags <<= 1
    except IndexError:
        return None
    return bytes(out[:size])


def main():
    rom_path, textos = sys.argv[1], sys.argv[2:]
    rom, fs = archivos(rom_path)
    zonas = {}
    a9o, _, _, a9s = struct.unpack_from("<IIII", rom, 0x20)
    zonas["arm9 (comprimido; puede no verse el texto)"] = rom[a9o:a9o + a9s]
    if os.path.exists("images/arm9.bin"):
        zonas["arm9 (descomprimido, images/arm9.bin)"] = open("images/arm9.bin", "rb").read()
    fat_off = struct.unpack_from("<I", rom, 0x48)[0]
    ovt_off, ovt_size = struct.unpack_from("<II", rom, 0x50)
    if ovt_off + ovt_size > len(rom):
        ovt_size = 0
    for i in range(ovt_size // 32):
        ov_id, ram, size, bss, si, se, fid, flags = struct.unpack_from("<8I", rom, ovt_off + i * 32)
        s, e = struct.unpack_from("<II", rom, fat_off + fid * 8)
        zonas[f"overlay {ov_id}"] = blz(rom[s:e]) if (flags >> 24) & 1 else rom[s:e]
    for ruta, d in fs.items():
        zonas[ruta] = d
        dd = lz(d)
        if dd:
            zonas[ruta + " (LZ)"] = dd
    for t in textos:
        print(f"== '{t}'")
        variantes = {"ascii": t.encode("latin-1"), "utf16": t.encode("utf-16-le")}
        hallado = False
        for nombre, datos in zonas.items():
            for tipo, v in variantes.items():
                i = datos.find(v)
                veces = 0
                while i >= 0 and veces < 5:
                    print(f"   {nombre}  +0x{i:X}  ({tipo})")
                    hallado = True
                    veces += 1
                    i = datos.find(v, i + 1)
        if not hallado:
            print("   no encontrado (puede estar comprimido de otra forma o codificado)")


if __name__ == "__main__":
    main()
