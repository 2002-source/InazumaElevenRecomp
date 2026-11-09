#!/usr/bin/env python3
"""
Convierte las entradas al interprete registradas en los archivos de cobertura
en semillas [[entry_point]] para los bancos ARM9 y ARM7.

Se acumulan ronda tras ronda: las semillas ya guardadas se conservan y solo
se anaden las nuevas.

Crea / actualiza:
  configs/semillas_arm9.toml
  configs/semillas_arm7.toml
(generar_toml.py los anade al final de arm9.toml / arm7.toml)

Uso (desde C:\\dev\\ie1recomp):
  python scripts/semillas_cobertura.py run/ie1_eur-coverage-*.json
"""
import json, os, re, sys

CFG = "configs"
IMG = "images"


def rangos():
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))
    ram9 = int(info["arm9"]["ram_address"], 16)
    size9 = os.path.getsize(os.path.join(IMG, "arm9.bin"))
    r9 = [(ram9, ram9 + size9)]
    for a in info["autoloads"]:
        if int(a["destino"], 16) == 0x01FF8000:
            r9.append((0x01FF8000, 0x01FF8000 + a["tamano"]))
    ram7 = int(info["arm7"]["ram_address"], 16)
    r7 = [(ram7, ram7 + info["arm7"]["size"]),
          (0x037F8000, 0x037F8000 + 0xFCA8)]   # copia a WRAM detectada por el reloc-scan
    return {9: r9, 7: r7}


def cargar(path):
    seeds = {}
    if os.path.exists(path):
        txt = open(path, encoding="utf-8").read()
        for addr, mode in re.findall(r'addr\s*=\s*0x([0-9A-Fa-f]+)\s*\nmode\s*=\s*"(\w+)"', txt):
            seeds[int(addr, 16)] = mode
    return seeds


def guardar(path, seeds, cpu):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Semillas ARM{cpu} obtenidas de la cobertura (semillas_cobertura.py)\n\n")
        for addr in sorted(seeds):
            f.write(f"[[entry_point]]\naddr = 0x{addr:08X}\nmode = \"{seeds[addr]}\"\n"
                    f"name = \"cov_{addr:08X}\"\n\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    r = rangos()
    for cpu in (9, 7):
        path = os.path.join(CFG, f"semillas_arm{cpu}.toml")
        seeds = cargar(path)
        antes = len(seeds)
        descartes = 0
        for cov_path in sys.argv[1:]:
            cov = json.load(open(cov_path, encoding="utf-8"))
            for e in cov[f"entry_points_arm{cpu}"]:
                a = int(e["addr"], 16)
                mode = e["mode"]
                if not any(lo <= a < hi for lo, hi in r[cpu]):
                    continue          # overlays u otras zonas: no van en este banco
                if a % (2 if mode == "thumb" else 4):
                    descartes += 1    # direccion desalineada: no es inicio valido
                    continue
                seeds.setdefault(a, mode)
        guardar(path, seeds, cpu)
        print(f"ARM{cpu}: {len(seeds)} semillas ({len(seeds) - antes} nuevas, {descartes} descartadas)")


if __name__ == "__main__":
    main()
