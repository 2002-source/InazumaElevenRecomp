#!/usr/bin/env python3
"""
Captura el codigo que el juego coloca en RAM y que NO viene de ningun binario
conocido (ni arm9.bin, ni los overlays): por ejemplo modulos que se cargan
desde archivos comprimidos del cartucho.

La cobertura guarda el contenido real de cada pagina ejecutada en el
interprete. Este script:
  1. Busca entradas del ARM9 cuyo codigo no coincide con arm9.bin ni con
     ningun overlay.
  2. Reconstruye esas zonas de memoria a partir de las paginas capturadas.
  3. Crea un banco por zona, con validacion por bytes: el runner solo usara
     ese codigo nativo cuando los bytes en RAM sean exactamente estos.

Crea:
  images/capturas/cap_XXXXXXXX.bin
  configs/capturas/cap_XXXXXXXX.toml
  configs/capturas/recompilar.sh

Uso (desde C:\\dev\\ie1recomp):
  python scripts/capturar_codigo.py run/ie1_eur-coverage-*.json
"""
import base64, glob, hashlib, json, os, sys
from collections import defaultdict

PAGE = 0x1000
IMG = "images"
OUT_IMG = os.path.join(IMG, "capturas")
OUT_CFG = os.path.join("configs", "capturas")
RECOMP = "/c/dev/ndsrecomp/recompiler/build/nds_recompile.exe"


def imagenes_conocidas():
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))
    res = []
    arm9 = open(os.path.join(IMG, "arm9.bin"), "rb").read()
    res.append((int(info["arm9"]["ram_address"], 16), arm9))
    for a in info["autoloads"]:
        off = int(a["origen_en_arm9"], 16)
        res.append((int(a["destino"], 16), arm9[off:off + a["tamano"]]))
    for ov in info["overlays_arm9"]:
        data = open(os.path.join(IMG, "overlays", f"ov9_{ov['id']:03d}.bin"), "rb").read()
        res.append((int(ov["ram_address"], 16), data))
    return res


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    conocidas = imagenes_conocidas()

    def conocida(addr, win):
        for base, data in conocidas:
            if base <= addr and addr + len(win) <= base + len(data):
                if data[addr - base:addr - base + len(win)] == win:
                    return True
        return False

    versiones = defaultdict(lambda: defaultdict(int))   # pagina -> {bytes: ejecuciones}
    entradas = {}                                        # addr -> mode (desconocidas)
    ventanas = defaultdict(set)                          # addr -> bytes desconocidos vistos
    for path in sys.argv[1:]:
        cov = json.load(open(path, encoding="utf-8"))
        paginas = defaultdict(list)
        for p in cov["pages"]["entries"]:
            if p["cpu"] == 9 and p.get("data"):
                a = int(p["addr"], 16)
                d = base64.b64decode(p["data"])
                paginas[a].append(d)
                versiones[a][d] += p["executions"]
        for e in cov["entry_points_arm9"]:
            a, mode = int(e["addr"], 16), e["mode"]
            if a % (2 if mode == "thumb" else 4):
                continue
            pg = a & ~(PAGE - 1)
            wins = [d[a - pg:a - pg + 32] for d in paginas.get(pg, [])]
            desconocidas = [w for w in wins if len(w) >= 4 and not conocida(a, w)]
            if desconocidas:
                entradas[a] = mode
                ventanas[a].update(desconocidas)

    if not entradas:
        print("No hay codigo desconocido en las coberturas. Nada que capturar.")
        return

    # Agrupar paginas con entradas desconocidas en zonas contiguas
    pags = sorted({a & ~(PAGE - 1) for a in entradas})
    zonas, actual = [], [pags[0]]
    for pg in pags[1:]:
        if pg <= actual[-1] + PAGE:
            actual.append(pg)
        else:
            zonas.append(actual)
            actual = [pg]
    zonas.append(actual)

    os.makedirs(OUT_IMG, exist_ok=True)
    os.makedirs(OUT_CFG, exist_ok=True)
    lines = ["#!/usr/bin/env bash", "# Generado por capturar_codigo.py", "set -e",
             "cd /c/dev/ie1recomp"]
    for zona in zonas:
        lo = zona[0]
        hi = zona[-1] + PAGE
        if hi in versiones:          # una pagina extra por si alguna funcion continua
            hi += PAGE
        img = bytearray(hi - lo)
        for pg in range(lo, hi, PAGE):
            if versiones.get(pg):
                # Preferir las versiones de la pagina que contienen el codigo
                # desconocido (no las de otro overlay cargado en otra sesion).
                propias = {a: ws for a, ws in ventanas.items() if pg <= a < pg + PAGE}
                def puntos(item):
                    d, ejec = item
                    acierto = sum(1 for a, ws in propias.items()
                                  if d[a - pg:a - pg + 32] in ws)
                    return (acierto, ejec)
                mejor = max(versiones[pg].items(), key=puntos)[0]
                img[pg - lo:pg - lo + PAGE] = mejor
        seeds = {a: m for a, m in entradas.items() if lo <= a < hi}
        nombre = f"cap_{lo:08X}"
        bank = f"arm9_{nombre.lower()}"
        open(os.path.join(OUT_IMG, f"{nombre}.bin"), "wb").write(img)
        out = [f"# Codigo capturado de RAM 0x{lo:08X}-0x{hi:08X} - generado por capturar_codigo.py",
               "", "[program]", f'name         = "Inazuma Eleven captura {lo:08X}"',
               f'id           = "ie1_{bank}"', 'cpu          = "arm9"', 'isa          = "armv5te"',
               f"load_address = 0x{lo:08X}", f"size         = 0x{len(img):08X}",
               f"entry_pc     = 0x{min(seeds):08X}", "", "[identity]",
               f'sha1 = "{hashlib.sha1(img).hexdigest()}"', ""]
        for a in sorted(seeds):
            out += ["[[entry_point]]", f"addr = 0x{a:08X}", f'mode = "{seeds[a]}"',
                    f'name = "cap_{a:08X}"', ""]
        open(os.path.join(OUT_CFG, f"{nombre}.toml"), "w", encoding="utf-8").write("\n".join(out))
        lines.append(f'echo "=== captura 0x{lo:08X} ==="')
        lines.append(f"{RECOMP} --config configs/capturas/{nombre}.toml "
                     f"--bin images/capturas/{nombre}.bin --out generated "
                     f"--bank {bank} --shards 2 --validate-live-bytes")
        print(f"{nombre}: 0x{lo:08X}-0x{hi:08X}  {len(seeds)} semillas")
    open(os.path.join(OUT_CFG, "recompilar.sh"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"\nScript: {OUT_CFG}/recompilar.sh")


if __name__ == "__main__":
    main()
