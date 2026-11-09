#!/usr/bin/env python3
"""
Compara el CODIGO de dos ROMs de DS (ARM9, ARM7 y overlays), no sus datos.
Indica si son identicos y, si no, cuantos bytes cambian en cada parte.

Uso (desde C:/dev/ie1recomp):
  python scripts/comparar_codigo.py games/ie1_eur.nds "/c/ruta/rom_es.nds"
"""
import hashlib, struct, sys


def blz(data):
    """Descompresion BLZ (la de los overlays/ARM9 de la DS)."""
    if len(data) < 8:
        return data
    enc_len, hdr_len = struct.unpack_from("<I", data, len(data) - 8)[0] & 0xFFFFFF, data[-5]
    inc = struct.unpack_from("<I", data, len(data) - 4)[0]
    if hdr_len < 8 or enc_len > len(data) or inc == 0:
        return data
    out = bytearray(data) + bytearray(inc)
    in_pos, end_in = len(data) - hdr_len, len(data) - enc_len
    out_pos = len(out)
    while in_pos > end_in:
        in_pos -= 1
        flags = out[in_pos]
        for _ in range(8):
            if in_pos <= end_in:
                break
            if flags & 0x80:
                in_pos -= 2
                v = out[in_pos] | (out[in_pos + 1] << 8)
                n, disp = (v >> 12) + 3, (v & 0xFFF) + 3
                for _ in range(n):
                    out_pos -= 1
                    out[out_pos] = out[out_pos + disp]
            else:
                in_pos -= 1
                out_pos -= 1
                out[out_pos] = out[in_pos]
            flags <<= 1
    return bytes(out)


def partes(rom):
    p = {}
    a9o, a9e, a9r, a9s = struct.unpack_from("<IIII", rom, 0x20)
    a7o, a7e, a7r, a7s = struct.unpack_from("<IIII", rom, 0x30)
    p["arm9"] = rom[a9o:a9o + a9s]   # (comprimido; se compara aparte)
    p["arm7"] = rom[a7o:a7o + a7s]
    fat_off = struct.unpack_from("<I", rom, 0x48)[0]
    ovt_off, ovt_size = struct.unpack_from("<II", rom, 0x50)
    for i in range(ovt_size // 32):
        ent = rom[ovt_off + i * 32: ovt_off + i * 32 + 32]
        ov_id, ram, size, bss, si, se, fid, flags = struct.unpack("<8I", ent)
        s, e = struct.unpack_from("<II", rom, fat_off + fid * 8)
        raw = rom[s:e]
        p[f"ov9_{ov_id:03d}"] = blz(raw) if (flags >> 24) & 1 else raw
        p[f"ov9_{ov_id:03d}_tabla"] = ent
    p["cabecera_codigos"] = rom[0x20:0x40]
    return p


def difiere(a, b):
    n = sum(1 for x, y in zip(a, b) if x != y)
    tramos, dentro = [], False
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y and not dentro:
            tramos.append([i, i]); dentro = True
        elif x != y:
            tramos[-1][1] = i
        elif dentro and i - tramos[-1][1] > 8:
            dentro = False
    txt = f"{n} bytes distintos en {len(tramos)} tramos"
    if len(a) != len(b):
        txt = f"tamano {len(a)} vs {len(b)}; " + txt + " (tras el cambio de tamano todo se desplaza)"
    muestra = []
    for t0, t1 in tramos[:3]:
        aa, bb = a[t0:t1 + 1][:24], b[t0:t1 + 1][:24]
        muestra.append(f"+0x{t0:X}: {aa!r} -> {bb!r}")
    return txt + ("\n      " + "\n      ".join(muestra) if muestra else "")


def main():
    A = open(sys.argv[1], "rb").read()
    B = open(sys.argv[2], "rb").read()
    print("codigo de juego:", A[0xC:0x10].decode(errors="ignore"), "vs", B[0xC:0x10].decode(errors="ignore"))
    pa, pb = partes(A), partes(B)
    iguales = 0
    for k in sorted(set(pa) | set(pb)):
        if k not in pa or k not in pb:
            print(f"  {k}: solo en una ROM")
            continue
        if pa[k] == pb[k]:
            iguales += 1
            continue
        print(f"  {k}: {difiere(pa[k], pb[k])}  (sha1 {hashlib.sha1(pa[k]).hexdigest()[:10]} vs {hashlib.sha1(pb[k]).hexdigest()[:10]})")
    print(f"Partes identicas: {iguales} de {len(set(pa) | set(pb))}")


if __name__ == "__main__":
    main()
