#!/usr/bin/env python3
"""
Compara las paginas de codigo que el runner vio en RAM (archivo de cobertura,
con un SHA-1 por pagina de 4 KB) con los binarios extraidos de la ROM.

Sirve para dos cosas:
  1. Comprobar que nuestros binarios (arm9.bin, arm7.bin, overlays) son
     identicos byte a byte a lo que el juego tiene en RAM. Si no coinciden,
     la validacion de bytes nunca dara por buenas esas funciones.
  2. Averiguar a que overlay pertenece cada pagina ejecutada.

Uso (desde C:\\dev\\ie1recomp):
  python scripts/verificar_paginas.py run/ie1_eur-coverage-XXXX-part00.json
"""
import hashlib, json, os, sys
from collections import defaultdict

PAGE = 0x1000
IMG = "images"


def load(path):
    with open(path, "rb") as f:
        return f.read()


def main():
    cov = json.load(open(sys.argv[1], encoding="utf-8"))
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))

    # Imagenes candidatas: (nombre, cpu, direccion_runtime, bytes)
    imgs = []
    arm9 = load(os.path.join(IMG, "arm9.bin"))
    ram9 = int(info["arm9"]["ram_address"], 16)
    imgs.append(("arm9", 9, ram9, arm9))
    for a in info["autoloads"]:
        off, size = int(a["origen_en_arm9"], 16), a["tamano"]
        imgs.append((f"autoload@{a['destino']}", 9, int(a["destino"], 16), arm9[off:off + size]))
    arm7 = load(os.path.join(IMG, "arm7.bin"))
    ram7 = int(info["arm7"]["ram_address"], 16)
    imgs.append(("arm7", 7, ram7, arm7))
    # Copia de codigo del ARM7 a su WRAM detectada por el reloc-scan
    imgs.append(("arm7->WRAM", 7, 0x037F8000, arm7[0x2E4:0x2E4 + 0xFCA8]))
    for ov in info["overlays_arm9"]:
        p = os.path.join(IMG, "overlays", f"ov9_{ov['id']:03d}.bin")
        imgs.append((f"ov{ov['id']:03d}", 9, int(ov["ram_address"], 16), load(p)))

    stats = defaultdict(lambda: [0, 0, 0])   # nombre -> [paginas, coinciden, ejecuciones]
    owners = defaultdict(list)               # overlay -> paginas que coinciden
    unmatched = []
    for page in cov["pages"]["entries"]:
        addr, cpu, want = int(page["addr"], 16), page["cpu"], page["sha1"]
        cands = []
        for name, icpu, base, data in imgs:
            if icpu != cpu or not (base <= addr and addr + PAGE <= base + len(data)):
                continue
            off = addr - base
            ok = hashlib.sha1(data[off:off + PAGE]).hexdigest() == want
            cands.append((name, ok))
        if not cands:
            unmatched.append((addr, cpu, page["executions"], "pagina no cubierta entera por ninguna imagen"))
            continue
        hit = [n for n, ok in cands if ok]
        group = "overlays" if cands[0][0].startswith("ov") else cands[0][0]
        s = stats[group]
        s[0] += 1
        s[2] += page["executions"]
        if hit:
            s[1] += 1
            for n in hit:
                owners[n].append(addr)
        else:
            unmatched.append((addr, cpu, page["executions"], "ninguna imagen coincide"))

    print("Region            paginas  coinciden  ejecuciones")
    for g, (n, ok, ex) in sorted(stats.items()):
        print(f"{g:16s} {n:8d} {ok:10d} {ex:12d}")
    print("\nOverlays identificados por contenido:")
    for n in sorted(k for k in owners if k.startswith("ov")):
        print(f"  {n}: {len(owners[n])} paginas")
    print(f"\nPaginas sin coincidencia: {len(unmatched)} (las 15 con mas ejecuciones)")
    for addr, cpu, ex, why in sorted(unmatched, key=lambda u: -u[2])[:15]:
        print(f"  ARM{cpu} 0x{addr:08X} ejec={ex:9d}  {why}")


if __name__ == "__main__":
    main()
