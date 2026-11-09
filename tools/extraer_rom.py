#!/usr/bin/env python3
"""
Extrae de una ROM de Nintendo DS todo lo que necesita ndsrecomp:
  - arm9.bin          ARM9 principal DESCOMPRIMIDO (tal como queda en RAM)
  - arm7.bin          ARM7 principal
  - overlays/ov9_XXX.bin   overlays ARM9 descomprimidos
  - overlays/ov7_XXX.bin   overlays ARM7 (si hay)
  - rom_info.json     direcciones de carga, entry points, autoloads (ITCM/DTCM)
                      y la tabla completa de overlays
Sin dependencias: solo Python 3.

Uso:
  python extraer_rom.py "ruta\\a\\la\\rom.nds" carpeta_salida
"""
import hashlib, json, os, struct, sys, zlib

CRC_ESPERADO = 0xC18C1468  # Inazuma Eleven (Europe), No-Intro (Decrypted)


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def blz_decompress(data: bytes) -> bytes:
    """Descompresion 'backwards LZ' usada por el SDK de Nintendo (arm9 y overlays)."""
    footer = u32(data, len(data) - 8)
    inc_len = u32(data, len(data) - 4)
    if inc_len == 0:
        return bytes(data)
    header_len = footer >> 24
    enc_len = footer & 0xFFFFFF
    out = bytearray(data) + bytearray(inc_len)
    in_pos = len(data) - header_len
    out_pos = len(out)
    end_in = len(data) - enc_len
    while in_pos > end_in:
        in_pos -= 1
        flags = out[in_pos]
        for _ in range(8):
            if in_pos <= end_in:
                break
            if flags & 0x80:
                in_pos -= 2
                v = (out[in_pos + 1] << 8) | out[in_pos]
                disp = (v & 0x0FFF) + 3
                length = (v >> 12) + 3
                for _ in range(length):
                    out_pos -= 1
                    out[out_pos] = out[out_pos + disp]
            else:
                in_pos -= 1
                out_pos -= 1
                out[out_pos] = out[in_pos]
            flags = (flags << 1) & 0xFF
    return bytes(out)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    rom_path, out_dir = sys.argv[1], sys.argv[2]
    rom = open(rom_path, "rb").read()
    os.makedirs(os.path.join(out_dir, "overlays"), exist_ok=True)

    crc = zlib.crc32(rom) & 0xFFFFFFFF
    sha1 = hashlib.sha1(rom).hexdigest()
    print(f"CRC32: {crc:08X}  ({'OK, coincide con No-Intro' if crc == CRC_ESPERADO else 'NO COINCIDE con la ROM esperada'})")
    print(f"SHA-1: {sha1}")

    title = rom[0:12].rstrip(b"\0").decode("ascii", "replace")
    code = rom[0x0C:0x10].decode("ascii", "replace")
    print(f"Titulo: {title}  Codigo: {code}  Revision: {rom[0x1E]}")

    a9_off, a9_entry, a9_ram, a9_size = struct.unpack_from("<IIII", rom, 0x20)
    a7_off, a7_entry, a7_ram, a7_size = struct.unpack_from("<IIII", rom, 0x30)
    fat_off, fat_size = struct.unpack_from("<II", rom, 0x48)
    ov9_off, ov9_size, ov7_off, ov7_size = struct.unpack_from("<IIII", rom, 0x50)
    fat = [struct.unpack_from("<II", rom, fat_off + i * 8) for i in range(fat_size // 8)]

    # ---------- ARM9 ----------
    arm9 = rom[a9_off:a9_off + a9_size]
    magic = struct.pack("<II", 0xDEC00621, 0x2106C0DE)
    idx = arm9.find(magic)
    info_arm9 = {"rom_offset": hex(a9_off), "ram_address": hex(a9_ram),
                 "entry": hex(a9_entry), "size_en_rom": a9_size}
    autoloads = []
    if idx < 0:
        print("AVISO: no se encontraron los module params del ARM9; se guarda tal cual.")
        arm9_dec = arm9
    else:
        mp = idx - 0x1C
        al_start, al_end, al_data, bss_start, bss_end, comp_end = struct.unpack_from("<IIIIII", arm9, mp)
        if comp_end:
            clen = comp_end - a9_ram
            arm9_dec = blz_decompress(arm9[:clen]) + arm9[clen:]
            # No se toca compressed_static_end: la cobertura demostro que la
            # pagina 0x02000000 en RAM no coincide si se pone a 0, y la
            # validacion por bytes necesita la imagen identica a la RAM.
            print(f"ARM9 comprimido: {len(arm9)} -> {len(arm9_dec)} bytes")
        else:
            arm9_dec = arm9
            print("ARM9 sin comprimir.")
        # Autoloads (bloques que el arranque copia a ITCM/DTCM u otras zonas)
        n = (al_end - al_start) // 12
        data_ptr = al_data
        for i in range(n):
            dest, size, bss = struct.unpack_from("<III", arm9_dec, al_start - a9_ram + i * 12)
            autoloads.append({"destino": hex(dest), "tamano": size, "bss": bss,
                              "origen_en_arm9": hex(data_ptr - a9_ram)})
            data_ptr += size
        # Comprobacion: los datos de autoload deben terminar justo al final del ARM9
        # (en muchos juegos la propia tabla de autoloads va justo despues de los datos)
        fin = data_ptr - a9_ram
        if fin == al_start - a9_ram:
            fin = al_end - a9_ram
        ok = fin == len(arm9_dec)
        print(f"Comprobacion ARM9: {'OK' if ok else 'FALLO'} (fin autoloads {fin:#x}, tamano {len(arm9_dec):#x}, {n} autoloads)")
        info_arm9.update({"module_params": hex(a9_ram + mp), "bss_start": hex(bss_start),
                          "bss_end": hex(bss_end), "tamano_descomprimido": len(arm9_dec),
                          "comprobacion": "OK" if ok else "FALLO"})
    open(os.path.join(out_dir, "arm9.bin"), "wb").write(arm9_dec)

    # ---------- ARM7 ----------
    arm7 = rom[a7_off:a7_off + a7_size]
    open(os.path.join(out_dir, "arm7.bin"), "wb").write(arm7)
    print(f"ARM7: {len(arm7)} bytes en {a7_ram:#x}")

    # ---------- Overlays ----------
    def overlays(tab_off, tab_size, cpu):
        lista, fallos = [], 0
        for i in range(tab_size // 32):
            oid, ram, rsize, bss, si_s, si_e, fid, flags = struct.unpack_from("<8I", rom, tab_off + i * 32)
            s, e = fat[fid]
            raw = rom[s:e]
            comp = (flags >> 24) & 1
            data = blz_decompress(raw[:flags & 0xFFFFFF]) if comp else raw
            ok = len(data) == rsize
            fallos += not ok
            open(os.path.join(out_dir, "overlays", f"ov{cpu}_{oid:03d}.bin"), "wb").write(data)
            lista.append({"id": oid, "ram_address": hex(ram), "ram_size": rsize, "bss_size": bss,
                          "sinit_start": hex(si_s), "sinit_end": hex(si_e), "file_id": fid,
                          "comprimido": bool(comp), "comprobacion": "OK" if ok else "FALLO"})
        print(f"Overlays ARM{cpu}: {len(lista)} extraidos, {fallos} con fallo de tamano")
        return lista

    ov9 = overlays(ov9_off, ov9_size, 9)
    ov7 = overlays(ov7_off, ov7_size, 7)

    info = {"titulo": title, "codigo": code, "revision": rom[0x1E], "crc32": f"{crc:08x}",
            "sha1": sha1, "arm9": info_arm9, "autoloads": autoloads,
            "arm7": {"rom_offset": hex(a7_off), "ram_address": hex(a7_ram), "entry": hex(a7_entry),
                     "size": a7_size},
            "overlays_arm9": ov9, "overlays_arm7": ov7}
    with open(os.path.join(out_dir, "rom_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    print(f"Listo. Todo en: {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
