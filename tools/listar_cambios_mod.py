#!/usr/bin/env python3
"""
Compara una ROM limpia con la misma ROM modificada (por ejemplo, despues de
aplicar tus BPS con Flips) y dice QUE ha cambiado, archivo por archivo:
  - archivos de datos de NitroFS (tablas, graficos, modelos, guiones...)
  - codigo: ARM9, ARM7, tabla de overlays y cada overlay
Sirve para saber como pasar un mod de ROM al sistema de mods del port:
los cambios de DATOS se pueden llevar tal cual; los de CODIGO necesitan
otro tratamiento (el port ejecuta codigo ya recompilado).
No copia ni sube nada de las ROM: solo escribe un informe de texto.
   python scripts/listar_cambios_mod.py LIMPIA.nds MODIFICADA.nds [informe.txt]
"""
import hashlib, struct, sys


def u32(d, o): return struct.unpack_from("<I", d, o)[0]
def u16(d, o): return struct.unpack_from("<H", d, o)[0]


def archivos(rom):
    """{ruta: bytes} de todo NitroFS, mas el codigo como entradas especiales."""
    fnt, fat = u32(rom, 0x40), u32(rom, 0x48)
    sal = {}

    def tramo(fid):
        a, b = u32(rom, fat + 8 * fid), u32(rom, fat + 8 * fid + 4)
        return rom[a:b]

    def recorrer(did, ruta):
        ent = fnt + (did & 0xFFF) * 8
        p = fnt + u32(rom, ent)
        fid = u16(rom, ent + 4)
        while True:
            n = rom[p]; p += 1
            if not n:
                return
            nom = rom[p:p + (n & 0x7F)].decode("latin-1"); p += n & 0x7F
            if n & 0x80:
                sub = u16(rom, p); p += 2
                recorrer(sub, ruta + nom + "/")
            else:
                sal[ruta + nom] = tramo(fid)
                fid += 1

    recorrer(0xF000, "/")
    # codigo
    sal["[ARM9]"] = rom[u32(rom, 0x20):u32(rom, 0x20) + u32(rom, 0x2C)]
    sal["[ARM7]"] = rom[u32(rom, 0x30):u32(rom, 0x30) + u32(rom, 0x3C)]
    ovt, ovn = u32(rom, 0x50), u32(rom, 0x54)
    sal["[tabla de overlays ARM9]"] = rom[ovt:ovt + ovn]
    for k in range(ovn // 32):
        e = ovt + 32 * k
        oid, fid = u32(rom, e), u32(rom, e + 0x18)
        sal["[overlay %03d]" % oid] = tramo(fid)
    return sal


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    a = open(sys.argv[1], "rb").read()
    b = open(sys.argv[2], "rb").read()
    fa, fb = archivos(a), archivos(b)
    lineas = []
    def p(t=""):
        print(t); lineas.append(t)
    p("ROM limpia     : %s  (%s, codigo %s)" % (sys.argv[1], hashlib.sha1(a).hexdigest()[:12], a[0x0C:0x10].decode("latin-1")))
    p("ROM modificada : %s  (%s)" % (sys.argv[2], hashlib.sha1(b).hexdigest()[:12]))
    codigo, datos, nuevos, borrados = [], [], [], []
    for ruta in sorted(set(fa) | set(fb)):
        if ruta not in fa:
            nuevos.append(ruta); continue
        if ruta not in fb:
            borrados.append(ruta); continue
        if fa[ruta] == fb[ruta]:
            continue
        x, y = fa[ruta], fb[ruta]
        dif = sum(1 for i in range(min(len(x), len(y))) if x[i] != y[i]) + abs(len(x) - len(y))
        fila = "  %-48s %9d -> %9d bytes, %d bytes distintos" % (ruta, len(x), len(y), dif)
        (codigo if ruta.startswith("[") else datos).append(fila)
    p()
    p("=== CODIGO (necesita tratamiento aparte en el port): %d ===" % len(codigo))
    for f in codigo: p(f)
    p()
    p("=== DATOS (se pueden llevar como mod del port): %d ===" % len(datos))
    for f in datos: p(f)
    if nuevos:
        p(); p("=== ARCHIVOS NUEVOS: %d ===" % len(nuevos))
        for r in nuevos: p("  %-48s %9d bytes" % (r, len(fb[r])))
    if borrados:
        p(); p("=== ARCHIVOS QUE YA NO ESTAN: %d ===" % len(borrados))
        for r in borrados: p("  " + r)
    if len(sys.argv) > 3:
        open(sys.argv[3], "w", encoding="utf-8").write("\n".join(lineas) + "\n")
        print("\nInforme guardado en", sys.argv[3])


if __name__ == "__main__":
    main()
