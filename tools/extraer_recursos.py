#!/usr/bin/env python3
"""
Extrae TODO el contenido interno de la ROM a una carpeta, ordenado y documentado:

  <destino>/
    codigo/arm9.bin            ARM9 ya descomprimido (el programa principal)
    codigo/arm7.bin            ARM7
    codigo/overlays/ovNNN.bin  overlays ya descomprimidos
    codigo/overlays.csv        tabla de overlays (direccion de carga, tamano...)
    archivos/...               el sistema de archivos completo de la ROM
    indice.csv                 cada archivo: ruta, tamano, tipo detectado, SHA-1
    LEEME.txt                  que es cada carpeta
    para_claude.zip            paquete pequeno para analizar: codigo + datos de
                               logica + indice (sin musica, voces, video ni imagenes)

Uso:
  python scripts/extraer_recursos.py games/ie1_eur.nds "D:/Inazuma Eleven 1 Port/Recursos"
Opcional:  --limite-mb 28   (tamano maximo de para_claude.zip; por defecto 28 MB)
"""
import argparse, csv, hashlib, os, struct, sys, zipfile

def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u16(b, o): return struct.unpack_from("<H", b, o)[0]

def blz_descomprimir(data):
    """Descompresion 'backward LZ' de Nintendo (ARM9 y overlays)."""
    if len(data) < 8:
        return bytes(data)
    info, inc = u32(data, len(data) - 8), u32(data, len(data) - 4)
    if inc == 0:
        return bytes(data)
    enc_len, hdr_len = info & 0xFFFFFF, info >> 24
    if hdr_len < 8 or enc_len > len(data) or hdr_len > enc_len:
        return bytes(data)
    out = bytearray(data) + bytearray(inc)
    src, dst, fin = len(data) - hdr_len, len(out), len(data) - enc_len
    while src > fin:
        src -= 1
        flags = out[src]
        for _ in range(8):
            if src <= fin:
                break
            if flags & 0x80:
                src -= 2
                b1, b2 = out[src + 1], out[src]
                disp = (((b1 << 8) | b2) & 0x0FFF) + 3
                n = (b1 >> 4) + 3
                for _ in range(n):
                    dst -= 1
                    out[dst] = out[dst + disp]
            else:
                src -= 1
                dst -= 1
                out[dst] = out[src]
            flags = (flags << 1) & 0xFF
    return bytes(out)

def tipo(datos, ruta):
    ext = os.path.splitext(ruta)[1].lower()
    cab = datos[:4]
    if cab[:1] == b"\x10" and len(datos) >= 4: t = "LZ10 (comprimido)"
    elif cab[:1] == b"\x11" and len(datos) >= 4: t = "LZ11 (comprimido)"
    elif cab in (b"SDAT", b"NARC", b"RLCN", b"RGCN", b"RNCL", b"RCSN", b"BMD0", b"BTX0", b"BCA0"): t = cab.decode()
    elif cab.isascii() and cab.isalnum(): t = "cabecera " + cab.decode()
    else: t = "binario"
    return (ext[1:] if ext else "-"), t

GRANDES = ("/sound/", "/movie/", "/mov/", "/video/")
IMAGEN = (".nclr", ".ncgr", ".nscr", ".ncer", ".nanr", ".nbfp", ".nbfc", ".nbfs", ".bmd", ".btx", ".bca", ".nsbmd", ".nsbtx")
SONIDO = (".sad", ".sdat", ".swd", ".sed", ".smd", ".pb", ".ph", ".mods", ".bnk")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("destino")
    ap.add_argument("--limite-mb", type=float, default=28.0)
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    dest = a.destino
    os.makedirs(os.path.join(dest, "codigo", "overlays"), exist_ok=True)

    titulo = rom[0:12].decode("ascii", "replace").strip("\0")
    codigo_juego = rom[12:16].decode("ascii", "replace")
    print(f"ROM: {titulo} ({codigo_juego}), {len(rom) / 1048576:.0f} MB, SHA-1 {hashlib.sha1(rom).hexdigest()}")

    # --- ARM9 / ARM7 -----------------------------------------------------------
    a9o, a9ram, a9s = u32(rom, 0x20), u32(rom, 0x28), u32(rom, 0x2C)
    a7o, a7ram, a7s = u32(rom, 0x30), u32(rom, 0x38), u32(rom, 0x3C)
    arm9 = rom[a9o:a9o + a9s]
    arm9d = blz_descomprimir(arm9)
    open(os.path.join(dest, "codigo", "arm9_comprimido.bin"), "wb").write(arm9)
    open(os.path.join(dest, "codigo", "arm9.bin"), "wb").write(arm9d)
    open(os.path.join(dest, "codigo", "arm7.bin"), "wb").write(rom[a7o:a7o + a7s])
    print(f"ARM9: {a9s} -> {len(arm9d)} bytes (carga en 0x{a9ram:08X});  ARM7: {a7s} bytes (0x{a7ram:08X})")

    # --- Tabla de archivos -------------------------------------------------------
    fnt_o, fnt_s, fat_o, fat_s = u32(rom, 0x40), u32(rom, 0x44), u32(rom, 0x48), u32(rom, 0x4C)
    def fat(i): return u32(rom, fat_o + 8 * i), u32(rom, fat_o + 8 * i + 4)
    rutas = {}
    def recorrer(did, ruta, prof=0):
        if prof > 32: return
        ent = fnt_o + (did & 0xFFF) * 8
        p = fnt_o + u32(rom, ent)
        fid = u16(rom, ent + 4)
        while True:
            n = rom[p]; p += 1
            if n == 0: break
            nombre = rom[p:p + (n & 0x7F)].decode("latin-1"); p += n & 0x7F
            if n & 0x80:
                sid = u16(rom, p); p += 2
                recorrer(sid, ruta + nombre + "/", prof + 1)
            else:
                rutas[fid] = ruta + nombre; fid += 1
    recorrer(0xF000, "/")

    # --- Overlays ------------------------------------------------------------------
    y9o, y9s = u32(rom, 0x50), u32(rom, 0x54)
    with open(os.path.join(dest, "codigo", "overlays.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["overlay", "direccion_carga", "tamano_en_ram", "bss", "id_archivo", "comprimido", "tamano_descomprimido"])
        for k in range(y9s // 32):
            e = y9o + 32 * k
            ov, ram, rsize, bss, fid, flags = u32(rom, e), u32(rom, e + 4), u32(rom, e + 8), u32(rom, e + 12), u32(rom, e + 24), u32(rom, e + 28)
            s0, e0 = fat(fid)
            datos = rom[s0:e0]
            comp = bool(flags & 0x01000000)
            dd = blz_descomprimir(datos) if comp else datos
            open(os.path.join(dest, "codigo", "overlays", f"ov{ov:03d}.bin"), "wb").write(dd)
            rutas.setdefault(fid, f"/overlays/ov{ov:03d}.bin")
            w.writerow([f"{ov:03d}", f"0x{ram:08X}", rsize, bss, fid, "si" if comp else "no", len(dd)])
    print(f"Overlays: {y9s // 32} (descomprimidos en codigo/overlays/)")

    # --- Sistema de archivos ---------------------------------------------------------
    filas = []
    for fid in range(fat_s // 8):
        ruta = rutas.get(fid)
        if not ruta or ruta.startswith("/overlays/"): continue
        s0, e0 = fat(fid)
        datos = rom[s0:e0]
        destino = os.path.join(dest, "archivos", *ruta.strip("/").split("/"))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        open(destino, "wb").write(datos)
        ext, t = tipo(datos, ruta)
        filas.append([ruta, len(datos), ext, t, hashlib.sha1(datos).hexdigest()])
    with open(os.path.join(dest, "indice.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ruta", "tamano", "extension", "tipo_detectado", "sha1"])
        w.writerows(sorted(filas))
    total = sum(r[1] for r in filas)
    print(f"Archivos: {len(filas)} ({total / 1048576:.1f} MB) en archivos/")

    # Resumen por carpeta y extension
    from collections import Counter
    carpetas, exts = Counter(), Counter()
    for r in filas:
        carpetas["/".join(r[0].split("/")[:4])] += r[1]
        exts[r[2]] += r[1]

    with open(os.path.join(dest, "LEEME.txt"), "w", encoding="utf-8") as f:
        f.write(f"Contenido interno de {titulo} ({codigo_juego})\nSHA-1 ROM {hashlib.sha1(rom).hexdigest()}\n\n")
        f.write("codigo/      ARM9 y overlays YA descomprimidos (se cargan en RAM en la direccion de overlays.csv)\n")
        f.write("archivos/    sistema de archivos de la ROM tal cual\n")
        f.write("indice.csv   lista de todos los archivos con tipo y SHA-1\n\n")
        f.write("Tamano por carpeta:\n")
        for k, v in carpetas.most_common(): f.write(f"  {v / 1048576:9.2f} MB  {k}\n")
        f.write("\nTamano por extension:\n")
        for k, v in exts.most_common(): f.write(f"  {v / 1048576:9.2f} MB  .{k}\n")

    # --- Paquete pequeno para analizar ---------------------------------------------------
    limite = int(a.limite_mb * 1048576)
    zpath = os.path.join(dest, "para_claude.zip")
    usados, omitidos = 0, 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for extra in ("LEEME.txt", "indice.csv"):
            z.write(os.path.join(dest, extra), extra)
        for nombre in ["arm9.bin", "arm7.bin", "overlays.csv"]:
            z.write(os.path.join(dest, "codigo", nombre), "codigo/" + nombre)
        for nombre in sorted(os.listdir(os.path.join(dest, "codigo", "overlays"))):
            z.write(os.path.join(dest, "codigo", "overlays", nombre), "codigo/overlays/" + nombre)
        # Datos: primero los de logica/textos (lo mas util), luego el resto pequeno
        def prioridad(r):
            ruta = r[0].lower()
            return (0 if "/logic/" in ruta else 1 if "/text/" in ruta or "/msg/" in ruta else 2, r[1])
        for r in sorted(filas, key=prioridad):
            ruta = r[0].lower()
            if any(g in ruta for g in GRANDES) or ruta.endswith(SONIDO) or ruta.endswith(IMAGEN):
                continue
            if r[1] > 2 * 1048576:
                continue
            z.fp.flush()
            if os.path.getsize(zpath) + r[1] > limite:   # estimacion prudente (sin contar la compresion)
                omitidos += 1
                continue
            z.write(os.path.join(dest, "archivos", *r[0].strip("/").split("/")), "archivos" + r[0])
            usados += 1
    print(f"Paquete para analizar: {zpath} ({os.path.getsize(zpath) / 1048576:.1f} MB, {usados} archivos de datos)")
    if omitidos:
        print("  (se alcanzo el limite de tamano; los datos menos prioritarios quedaron fuera)")
    print("Listo.")

if __name__ == "__main__":
    main()
