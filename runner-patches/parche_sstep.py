#!/usr/bin/env python3
"""
Diagnostico: cuenta en que direcciones el codigo flat entrega instrucciones al
interprete (unsupported_exits) y que instruccion hay ahi. Solo se activa con
la variable de entorno NDS_IE1_SSTEP_STATS=1; al cerrar el juego (Esc -> Quit)
imprime las 40 mas frecuentes como lineas "[sstep] ...".
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/execution_region.cpp
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/execution_region.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "NDS_IE1_SSTEP_STATS" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
ancla = "extern \"C\" void runtime_region_single_step() {" + nl + "    if (runtime_should_yield()) return;" + nl
if s.count(ancla) != 1:
    sys.exit("execution_region.cpp no tiene la forma esperada; no toco nada.")
ayuda = nl.join([
    "// IE1_SSTEP: estadistica de instrucciones entregadas al interprete (parche_sstep.py)",
    "#include <algorithm>",
    "#include <cstdio>",
    "#include <cstdlib>",
    "#include <unordered_map>",
    "#include <utility>",
    "#include <vector>",
    "#include \"runtime_arm.h\"",
    "namespace {",
    "struct Ie1Sstep { uint64_t count = 0; uint32_t word = 0; bool thumb = false; };",
    "std::unordered_map<uint32_t, Ie1Sstep>* g_ie1_sstep = nullptr;",
    "void ie1_sstep_dump() {",
    "    if (!g_ie1_sstep) return;",
    "    std::vector<std::pair<uint32_t, Ie1Sstep>> v(g_ie1_sstep->begin(), g_ie1_sstep->end());",
    "    std::sort(v.begin(), v.end(), [](auto& a, auto& b) { return a.second.count > b.second.count; });",
    "    uint64_t total = 0; for (auto& e : v) total += e.second.count;",
    "    std::fprintf(stderr, \"[sstep] total %llu en %zu direcciones\\n\", (unsigned long long)total, v.size());",
    "    for (std::size_t i = 0; i < v.size() && i < 40; ++i)",
    "        std::fprintf(stderr, \"[sstep] %08X %s %08X %llu\\n\", v[i].first,",
    "                     v[i].second.thumb ? \"thumb\" : \"arm\", v[i].second.word,",
    "                     (unsigned long long)v[i].second.count);",
    "}",
    "bool ie1_sstep_on() {",
    "    static const bool on = [] { const char* e = std::getenv(\"NDS_IE1_SSTEP_STATS\");",
    "        return e && e[0] == '1'; }();",
    "    return on;",
    "}",
    "}  // namespace",
    "", ""])
nuevo = ayuda + ancla + nl.join([
    "    if (ie1_sstep_on()) {  // IE1_SSTEP",
    "        if (!g_ie1_sstep) { g_ie1_sstep = new std::unordered_map<uint32_t, Ie1Sstep>(); std::atexit(ie1_sstep_dump); }",
    "        const uint32_t pc = g_cpu.R[15];",
    "        auto& e = (*g_ie1_sstep)[pc];",
    "        if (e.count++ == 0) { e.thumb = (g_cpu.cpsr & CPSR_T_BIT) != 0; e.word = bus_read_u32(pc & ~3u); }",
    "    }", ""])
s = s.replace(ancla, nuevo)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
