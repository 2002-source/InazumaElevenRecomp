#!/usr/bin/env python3
"""
Permite el modelo de ejecucion "performance" (flat AOT) para Inazuma Eleven.
El runner lo tenia atado a la ROM de Mario Kart DS; este parche lo hace
configurable con dos opciones de CMake (por defecto, Mario Kart como antes):
  NDS_PERF_ROM_SHA1      SHA-1 de la ROM que puede usar el modo performance
  NDS_PERF_BANK_PREFIX   prefijo de los bancos flat (<prefijo>_arm9, _arm9_itcm)
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/execution_model.cpp runner/CMakeLists.txt
          (y vuelve a ejecutar integrar_hle_cartucho.py y parche_pgo_clang.py)
"""
import sys
MKDS = "691e00d9a5dd80b04f80cc7559503e8b06848785"
CM = "C:/dev/ndsrecomp/runner/CMakeLists.txt"
EM = "C:/dev/ndsrecomp/runner/src/execution_model.cpp"

def leer(p):
    s = open(p, encoding="utf-8", newline="").read()
    return s, ("\r\n" if "\r\n" in s else "\n")

# --- CMakeLists.txt ---
s, nl = leer(CM)
if "NDS_PERF_ROM_SHA1" in s:
    print("CMakeLists.txt ya estaba modificado")
else:
    a = '    "Generated mkds_perf_arm9 and mkds_perf_arm9_itcm banks")'
    b = 'foreach(_bank mkds_perf_arm9 mkds_perf_arm9_itcm)'
    c = f'TITLE_GROUP_${{_gi}}_SHA1 STREQUAL "{MKDS}"'
    d = 'target_compile_definitions(nds_runner PRIVATE NDS_MKDS_PERFORMANCE=1)'
    if s.count(a) != 1 or s.count(b) != 2 or s.count(c) != 1 or s.count(d) != 1:
        sys.exit("CMakeLists.txt no tiene la forma esperada; no toco nada.")
    s = s.replace(a, a + nl + nl.join([
        "# IE1_PERF: el modelo performance deja de estar atado a Mario Kart (parche_perf.py)",
        f'set(NDS_PERF_ROM_SHA1 "{MKDS}" CACHE STRING "ROM que puede usar el modelo performance")',
        'set(NDS_PERF_BANK_PREFIX "mkds_perf" CACHE STRING "Prefijo de los bancos flat")']))
    s = s.replace(b, 'foreach(_bank ${NDS_PERF_BANK_PREFIX}_arm9 ${NDS_PERF_BANK_PREFIX}_arm9_itcm)')
    s = s.replace(c, 'TITLE_GROUP_${_gi}_SHA1 STREQUAL "${NDS_PERF_ROM_SHA1}"')
    s = s.replace(d, d + nl + '    target_compile_definitions(nds_runner PRIVATE '
                  '"NDS_PERF_ROM_SHA1=\\"${NDS_PERF_ROM_SHA1}\\"")  # IE1_PERF')
    open(CM, "w", encoding="utf-8", newline="").write(s)
    print("modificado CMakeLists.txt")

# --- execution_model.cpp ---
s, nl = leer(EM)
if "NDS_PERF_ROM_SHA1" in s:
    print("execution_model.cpp ya estaba modificado")
else:
    v = f'    if (sha1 != "{MKDS}") {{'
    if s.count(v) != 1:
        sys.exit("execution_model.cpp no tiene la forma esperada; no toco nada.")
    s = s.replace(v, '    if (sha1 != NDS_PERF_ROM_SHA1) {  // IE1_PERF')
    i = s.index("namespace {")
    s = s[:i] + nl.join(["#ifndef NDS_PERF_ROM_SHA1",
                         f'#define NDS_PERF_ROM_SHA1 "{MKDS}"', "#endif", "", ""]) + s[i:]
    open(EM, "w", encoding="utf-8", newline="").write(s)
    print("modificado execution_model.cpp")
# --- v2: lista de bancos flat configurable (para anadir los overlays) ---
s, nl = leer(CM)
if "NDS_PERF_BANKS" in s:
    print("CMakeLists.txt ya admite la lista de bancos (v2)")
else:
    viejo = 'foreach(_bank ${NDS_PERF_BANK_PREFIX}_arm9 ${NDS_PERF_BANK_PREFIX}_arm9_itcm)'
    ancla = 'set(NDS_PERF_BANK_PREFIX "mkds_perf" CACHE STRING "Prefijo de los bancos flat")'
    if s.count(viejo) != 2 or s.count(ancla) != 1:
        sys.exit("CMakeLists.txt no tiene la forma esperada para la v2; no toco nada.")
    s = s.replace(ancla, ancla + nl +
        'set(NDS_PERF_BANKS "" CACHE STRING "Bancos flat (lista; vacio = <prefijo>_arm9 y _arm9_itcm)")' + nl +
        'if(NOT NDS_PERF_BANKS)' + nl +
        '    set(NDS_PERF_BANKS "${NDS_PERF_BANK_PREFIX}_arm9;${NDS_PERF_BANK_PREFIX}_arm9_itcm")' + nl +
        'endif()')
    s = s.replace(viejo, 'foreach(_bank IN LISTS NDS_PERF_BANKS)')
    open(CM, "w", encoding="utf-8", newline="").write(s)
    print("modificado CMakeLists.txt (v2: lista de bancos)")
print("Listo.")
