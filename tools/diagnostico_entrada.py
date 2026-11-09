#!/usr/bin/env python3
"""
Diagnostico de una entrada que sigue en el interprete.

Para una direccion dada:
  1. Busca en la cobertura todas las versiones de su pagina (el contenido real
     que habia en RAM) y las compara byte a byte con cada overlay que cubre esa
     direccion. Muestra que overlay coincide y DONDE difieren los bytes.
  2. Busca en los bancos generados la fila de validacion de esa funcion
     (direccion y tamano del rango que el runner exige identico).

Uso (desde C:\\dev\\ie1recomp):
  python scripts/diagnostico_entrada.py run/ie1_eur-coverage-XXXX.json 0x021759AC
"""
import base64, glob, json, os, re, sys

PAGE = 0x1000
IMG = "images"


def rangos_distintos(a, b, base):
    """Lista de (inicio, fin) donde a y b difieren, en direcciones absolutas."""
    out, start = [], None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            if start is None:
                start = i
        elif start is not None:
            out.append((base + start, base + i))
            start = None
    if start is not None:
        out.append((base + start, base + min(len(a), len(b))))
    return out


def main():
    cov = json.load(open(sys.argv[1], encoding="utf-8"))
    addr = int(sys.argv[2], 16)
    page = addr & ~(PAGE - 1)
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))

    ovs = []
    for ov in info["overlays_arm9"]:
        base = int(ov["ram_address"], 16)
        data = open(os.path.join(IMG, "overlays", f"ov9_{ov['id']:03d}.bin"), "rb").read()
        if base <= addr < base + len(data):
            ovs.append((ov["id"], base, data))
    print(f"Overlays que cubren 0x{addr:08X}: {[f'ov{o[0]:03d}' for o in ovs]}")

    versiones = [base64.b64decode(p["data"]) for p in cov["pages"]["entries"]
                 if p["cpu"] == 9 and int(p["addr"], 16) == page and p.get("data")]
    print(f"Versiones de la pagina 0x{page:08X} en la cobertura: {len(versiones)}\n")

    for n, pdata in enumerate(versiones):
        print(f"--- version {n}")
        for oid, base, data in ovs:
            lo = max(page, base)
            hi = min(page + PAGE, base + len(data))
            ram = pdata[lo - page:hi - page]
            rom = data[lo - base:hi - base]
            difs = rangos_distintos(ram, rom, lo)
            off = addr - page
            win_ok = pdata[off:off + 32] == data[addr - base:addr - base + 32]
            tot = sum(e - s for s, e in difs)
            print(f"  ov{oid:03d}: entrada {'COINCIDE' if win_ok else 'no coincide'}; "
                  f"{tot} bytes distintos en 0x{lo:08X}-0x{hi:08X}")
            if win_ok:
                for s, e in difs[:12]:
                    print(f"      difiere 0x{s:08X}-0x{e:08X} ({e - s} bytes)")

    print("\nFilas de validacion que contienen la direccion en los bancos generados:")
    fila = re.compile(r"NdsStaticValidation\s+(\w+)\s*=\s*\{0x([0-9A-Fa-f]+)u,\s*(\d+)u,\s*(\w+)")
    for f in sorted(glob.glob("generated/*_dispatch.c")):
        txt = None
        for line in open(f, encoding="utf-8", errors="ignore"):
            m = fila.search(line)
            if not m:
                continue
            a, sz, sym = int(m.group(2), 16), int(m.group(3)), m.group(4)
            if not (a <= addr < a + sz):
                continue
            print(f"  {os.path.basename(f)}: 0x{a:08X} + {sz} bytes (hasta 0x{a + sz:08X})")
            if txt is None:
                txt = open(f, encoding="utf-8", errors="ignore").read()
            mb = re.search(re.escape(sym) + r"\[\]\s*=\s*\{([^}]*)\}", txt)
            if not mb:
                print("      (no encontre los bytes esperados)")
                continue
            esperado = bytes(int(x.strip().rstrip("u"), 16) for x in mb.group(1).split(",") if x.strip())
            if a < page or a + sz > page + PAGE:
                print("      (el rango cruza el limite de pagina; solo comparo la parte de esta pagina)")
            for n, pdata in enumerate(versiones):
                lo, hi = max(a, page), min(a + sz, page + PAGE)
                ram = pdata[lo - page:hi - page]
                exp = esperado[lo - a:hi - a]
                difs = rangos_distintos(ram, exp, lo)
                if difs:
                    print(f"      version {n}: DIFIERE en {[(hex(x), hex(y)) for x, y in difs[:6]]}")
                else:
                    print(f"      version {n}: identico")


if __name__ == "__main__":
    main()
