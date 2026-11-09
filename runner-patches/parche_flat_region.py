#!/usr/bin/env python3
"""
Generador flat (recompiler/src/main.cpp, build_flat_regions): permite regiones
flat MAS GRANDES, para que mas llamadas entre funciones se resuelvan dentro de
la region (un goto) en vez de salir y pasar por el dispatcher.

Hoy una region agrupa las funciones que empiezan en la misma pagina de 4 KB.
Con la variable de entorno IE1_FLAT_REGION_KB=N (al generar los bancos), una
region agrupa funciones consecutivas mientras todo el tramo que ocupan quepa
en N KB (maximo 12, para no superar las 4 paginas que vigila la cache del
dispatcher). Sin la variable, el comportamiento es exactamente el de antes.
Deshacer: cd /c/dev/ndsrecomp && git checkout recompiler/src/main.cpp
"""
import sys
PATH = "C:/dev/ndsrecomp/recompiler/src/main.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_FLAT_REGION_KB" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
old = nl.join([
    "        while(last<funcs.size() && funcs[last].mode==funcs[first].mode &&",
    "              (funcs[last].addr>>12)==page &&"])
if s.count(old) != 1 or s.count("SuperblockPlan build_flat_regions(const std::vector<Function>& funcs) {") != 1:
    sys.exit("main.cpp no tiene la forma esperada; no toco nada.")
new = nl.join([
    "        // IE1_FLAT_REGION_KB: regiones de hasta N KB (parche_flat_region.py)",
    "        static const uint32_t ie1_span = [] {",
    "            const char* v = std::getenv(\"IE1_FLAT_REGION_KB\");",
    "            const long kb = v ? std::strtol(v, nullptr, 10) : 0;",
    "            return (kb >= 1 && kb <= 12) ? uint32_t(kb) * 1024u : 0u;",
    "        }();",
    "        while(last<funcs.size() && funcs[last].mode==funcs[first].mode &&",
    "              (ie1_span ? (funcs[last].addr >= funcs[first].addr &&",
    "                           uint64_t(funcs[last].end_addr) - funcs[first].addr <= ie1_span)",
    "                        : ((funcs[last].addr>>12)==page)) &&"])
s = s.replace(old, new)
if "#include <cstdlib>" not in s:
    i = s.index("#include")
    s = s[:i] + "#include <cstdlib>" + nl + s[i:]
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
