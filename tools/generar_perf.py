#!/usr/bin/env python3
"""
Prepara los bancos "flat" (modelo performance) del ARM9 principal y de la ITCM.
En el modelo flat cada banco debe estar en su direccion real, asi que la ITCM
va en un banco propio (no como copia dentro del ARM9).

Crea images/arm9_static.bin, images/arm9_itcm.bin y
     configs/perf/ie1_perf_arm9.toml, configs/perf/ie1_perf_arm9_itcm.toml
Las semillas salen de configs/semillas_arm9.toml (las mismas que el modo normal).
"""
import hashlib, json, os, re, struct

IMG, CFG = "images", os.path.join("configs", "perf")
info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))
arm9 = open(os.path.join(IMG, "arm9.bin"), "rb").read()
ram9 = int(info["arm9"]["ram_address"], 16)
entry9 = int(info["arm9"]["entry"], 16)
static = arm9[:int(info["arm9"]["bss_start"], 16) - ram9]
itcm_a = [a for a in info["autoloads"] if int(a["destino"], 16) == 0x01FF8000][0]
off = int(itcm_a["origen_en_arm9"], 16)
itcm = arm9[off:off + itcm_a["tamano"]]
open(os.path.join(IMG, "arm9_static.bin"), "wb").write(static)
open(os.path.join(IMG, "arm9_itcm.bin"), "wb").write(itcm)

seeds = {}
p = os.path.join("configs", "semillas_arm9.toml")
if os.path.exists(p):
    for a, m in re.findall(r'addr\s*=\s*0x([0-9A-Fa-f]+)\s*\nmode\s*=\s*"(\w+)"', open(p).read()):
        seeds[int(a, 16)] = m

# Paridad con el banco normal: todas las funciones que el banco normal del ARM9
# conoce (incluidas las que solo se alcanzan desde la ITCM o por punteros) se
# siembran tambien en los bancos flat. Si faltan, una region flat que cubre su
# direccion ejecuta cada instruccion por el interprete, una a una.
disp = os.path.join("generated", "arm9_main_dispatch.c")
paridad = 0
if os.path.exists(disp):
    for a in re.findall(r"NdsStaticValidation\s+\w+\s*=\s*\{0x([0-9A-Fa-f]+)u,", open(disp, errors="ignore").read()):
        a = int(a, 16)
        # Solo el ARM9 principal: en la ITCM estas semillas empeoraban las regiones.
        if a % 4 == 0 and a not in seeds and ram9 <= a < ram9 + len(static):
            seeds[a] = "arm"
            paridad += 1
print(f"Semillas: {len(seeds)} ({paridad} anadidas del banco normal)")

# Saltos calculados "add pc, pc, rX, lsl #n":
#  - switch: les sigue una tabla de saltos "b destino" (cada entrada, semilla);
#  - division desenrollada: les sigue un bloque largo al que se salta A MITAD.
# El codigo que va detras no es alcanzable de forma directa, asi que sin
# semillas el buscador no lo traduce y el codigo flat lo manda al interprete.
# Sembrar pc+4 y pc+8 hace que el bloque se decodifique entero.
tablas = 0
def sembrar(a):
    global tablas
    if a not in seeds:
        seeds[a] = "arm"
        tablas += 1
for off in range(0, len(static) - 8, 4):
    w = struct.unpack_from("<I", static, off)[0]
    if (w & 0x0FFFF010) != 0x008FF000:          # add pc, pc, rM, <desplazamiento inmediato>
        continue
    sembrar(ram9 + off + 4)
    sembrar(ram9 + off + 8)
    k = off + 4
    while k < len(static) - 4 and k - off <= 4 * 64:
        e = struct.unpack_from("<I", static, k)[0]
        if (e & 0xFF000000) != 0xEA000000:      # b incondicional
            break
        sembrar(ram9 + k)
        k += 4
print(f"Destinos de saltos calculados sembrados: {tablas}")

os.makedirs(CFG, exist_ok=True)


def toml(bank, load, data, entry, extra):
    out = [f"# Banco flat {bank} - generado por generar_perf.py", "", "[program]",
           f'name         = "Inazuma Eleven {bank}"', f'id           = "{bank}"',
           'cpu          = "arm9"', 'isa          = "armv5te"',
           f"load_address = 0x{load:08X}", f"size         = 0x{len(data):08X}",
           f"entry_pc     = 0x{entry:08X}", "", "[identity]",
           f'sha1 = "{hashlib.sha1(data).hexdigest()}"', ""]
    for a, m in sorted(extra.items()):
        out += ["[[entry_point]]", f"addr = 0x{a:08X}", f'mode = "{m}"', f'name = "pf_{a:08X}"', ""]
    open(os.path.join(CFG, f"{bank}.toml"), "w", encoding="utf-8").write("\n".join(out))
    print(f"{bank}: 0x{load:08X} + 0x{len(data):X} bytes, {len(extra)} semillas")


main_seeds = {a: m for a, m in seeds.items() if ram9 <= a < ram9 + len(static)}
main_seeds[entry9] = "arm"
toml("ie1_perf_arm9", ram9, static, entry9, main_seeds)
itcm_seeds = {a: m for a, m in seeds.items() if 0x01FF8000 <= a < 0x01FF8000 + len(itcm)}
toml("ie1_perf_arm9_itcm", 0x01FF8000, itcm, min(itcm_seeds) if itcm_seeds else 0x01FF8000, itcm_seeds)
