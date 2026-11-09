#!/usr/bin/env python3
"""
Generador flat (recompiler/src/flat_codegen.cpp): las regiones flat SALEN al
llegar a la entrada de las rutinas que tienen HLE en Inazuma Eleven, para que
el dispatcher aplique el reemplazo nativo (si no, el codigo flat ejecutaria la
rutina original y el HLE nunca se usaria dentro de una region).
Entradas: 0x02011CC0 (lectura del cartucho), 0x02009BE0 (LZ),
          0x02011B54 (ID del chip), 0x02000950 (descompresion de overlays).
La salida depende de g_ie1_flat_hle_exits (definida por el HLE del runner).
Requiere parche_flat_mcr.py. Despues: bash scripts/perf.sh
"""
import sys
PATH = "C:/dev/ndsrecomp/recompiler/src/flat_codegen.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
viejo_v1 = "pc == 0x02011CC0u || pc == 0x02009BE0u || pc == 0x02011B54u;"
nuevo_v2 = "pc == 0x02011CC0u || pc == 0x02009BE0u || pc == 0x02011B54u || pc == 0x02000950u;"
if "IE1_FLAT_HLE" in s:
    if nuevo_v2 in s:
        print("El parche ya estaba aplicado.")
    elif viejo_v1 in s:
        s = s.replace(viejo_v1, nuevo_v2)
        open(PATH, "w", encoding="utf-8", newline="").write(s)
        print("Parche actualizado: anadida la descompresion de overlays (0x02000950).")
    else:
        sys.exit("flat_codegen.cpp tiene una version desconocida del parche.")
    sys.exit(0)
if "IE1_FLAT_MCR" not in s:
    sys.exit("Aplica antes parche_flat_mcr.py.")
nl = "\r\n" if "\r\n" in s else "\n"
a1 = "bool ie1_dcache_maintenance(uint32_t raw) {"
a2 = "        if(!thumb && std::find(std::begin(retained_hle_entries),"
if s.count(a1) != 1 or s.count(a2) != 1:
    sys.exit("flat_codegen.cpp no tiene la forma esperada; no toco nada.")
helper = nl.join([
    "// IE1_FLAT_HLE: entradas de rutinas con HLE de Inazuma Eleven (parche_flat_hle.py)",
    "bool ie1_hle_entry(uint32_t pc) {",
    "    return " + nuevo_v2,
    "}", ""])
s = s.replace(a1, helper + a1)
exitcode = nl.join([
    "        if(!thumb && ie1_hle_entry(pc))  // IE1_FLAT_HLE",
    "            out<<\"    { extern uint32_t g_ie1_flat_hle_exits; if (g_ie1_flat_hle_exits) { _region.cpu.R[15]=\"<<hex(pc)<<\"; goto NDS_REGION_EXIT; } }\\n\";",
    ""])
s = s.replace(a2, exitcode + a2)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
