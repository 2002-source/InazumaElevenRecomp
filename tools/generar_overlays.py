#!/usr/bin/env python3
"""
Genera bancos de overlays ARM9 para ndsrecomp a partir de la cobertura.

Para cada overlay que se ejecuto en alguna sesion (identificado comparando
los bytes que habia en RAM en cada punto de entrada con los de cada overlay,
porque varios overlays comparten direccion) crea:
  configs/overlays/ov9_XXX.toml   con semillas = entradas reales al interprete
                                  + punteros de su tabla de inicializacion
  configs/overlays/recompilar.sh  con un nds_recompile por overlay

Todos se generan para usarse con --validate-live-bytes: el runner solo usa
el codigo de un overlay cuando sus bytes estan cargados de verdad en RAM.

Uso (desde C:\\dev\\ie1recomp):
  python scripts/generar_overlays.py run/ie1_eur-coverage-*.json
"""
import base64, hashlib, json, os, struct, sys
from collections import defaultdict

PAGE = 0x1000
IMG, CFG = "images", os.path.join("configs", "overlays")
RECOMP = "/c/dev/ndsrecomp/recompiler/build/nds_recompile.exe"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))
    ovs = {}
    for ov in info["overlays_arm9"]:
        data = open(os.path.join(IMG, "overlays", f"ov9_{ov['id']:03d}.bin"), "rb").read()
        ovs[ov["id"]] = (ov, int(ov["ram_address"], 16), data)

    import base64

    def owners_at(addr, page_versions, n=32):
        """Overlays cuyos bytes coinciden con lo que habia en RAM en `addr`
        (comparando n bytes a partir de la entrada en cada version de la pagina)."""
        res = set()
        for pbase, pdata in page_versions:
            off = addr - pbase
            win = pdata[off:off + n]
            if len(win) < 4:
                continue
            for oid, (ov, base, data) in ovs.items():
                if base <= addr and addr + len(win) <= base + len(data):
                    if data[addr - base:addr - base + len(win)] == win:
                        res.add(oid)
        return res

    seeds = defaultdict(dict)       # oid -> {addr: mode}
    active = set()
    sin_dueno = 0
    for path in sys.argv[1:]:
        cov = json.load(open(path, encoding="utf-8"))
        pages = defaultdict(list)   # direccion de pagina -> [(base, bytes)] (todas las versiones)
        for p in cov["pages"]["entries"]:
            if p["cpu"] == 9 and p.get("data"):
                a = int(p["addr"], 16)
                pages[a].append((a, base64.b64decode(p["data"])))
        for e in cov["entry_points_arm9"]:
            a = int(e["addr"], 16)
            mode = e["mode"]
            if a % (2 if mode == "thumb" else 4):
                continue
            if not any(base <= a < base + len(data) for ov, base, data in ovs.values()):
                continue
            own = owners_at(a, pages.get(a & ~(PAGE - 1), []))
            if not own:
                sin_dueno += 1
                continue
            active.update(own)
            for oid in own:
                seeds[oid].setdefault(a, mode)
    print(f"(entradas de overlay sin dueno identificable: {sin_dueno})")

    os.makedirs(CFG, exist_ok=True)
    lines = ["#!/usr/bin/env bash", "# Generado por generar_overlays.py", "set -e",
             "cd /c/dev/ie1recomp"]
    for oid in sorted(active):
        ov, base, data = ovs[oid]
        s = dict(seeds[oid])
        # Tabla de inicializacion estatica (punteros a funciones dentro del overlay)
        si, se = int(ov["sinit_start"], 16), int(ov["sinit_end"], 16)
        if base <= si < se <= base + len(data):
            for off in range(si - base, se - base, 4):
                ptr = struct.unpack_from("<I", data, off)[0]
                t = ptr & ~1
                if base <= t < base + len(data):
                    s.setdefault(t, "thumb" if ptr & 1 else "arm")
        if not s:
            continue
        first = min(s)
        bank = f"arm9_ov{oid:03d}"
        out = [f"# Overlay {oid} (Inazuma Eleven EUR) - generado por generar_overlays.py", "",
               "[program]", f'name         = "Inazuma Eleven ov{oid:03d}"',
               f'id           = "ie1_{bank}"', 'cpu          = "arm9"', 'isa          = "armv5te"',
               f"load_address = 0x{base:08X}", f"size         = 0x{len(data):08X}",
               f"entry_pc     = 0x{first:08X}", "", "[identity]",
               f'sha1 = "{hashlib.sha1(data).hexdigest()}"', ""]
        for a in sorted(s):
            out += ["[[entry_point]]", f"addr = 0x{a:08X}", f'mode = "{s[a]}"',
                    f'name = "ov{oid:03d}_{a:08X}"', ""]
        open(os.path.join(CFG, f"ov9_{oid:03d}.toml"), "w", encoding="utf-8").write("\n".join(out))
        lines.append(f'echo "=== overlay {oid} ==="')
        lines.append(f"{RECOMP} --config configs/overlays/ov9_{oid:03d}.toml "
                     f"--bin images/overlays/ov9_{oid:03d}.bin --out generated "
                     f"--bank {bank} --shards 2 --validate-live-bytes")
        print(f"ov{oid:03d}: 0x{base:08X} + 0x{len(data):X}  {len(s)} semillas")
    open(os.path.join(CFG, "recompilar.sh"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"\nScript: {CFG}/recompilar.sh")


if __name__ == "__main__":
    main()
