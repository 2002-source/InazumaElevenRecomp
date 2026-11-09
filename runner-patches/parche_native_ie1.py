#!/usr/bin/env python3
"""
Modo JIT (runner/src/arm9_native.cpp): ademas de los HLE de Mario Kart, usa los
HLE de Inazuma Eleven (lectura del cartucho, LZ, descompresion de overlays,
ID del chip). Sin esto, el JIT traduciria y ejecutaria las rutinas originales.
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/arm9_native.cpp
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/arm9_native.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_NATIVE_HLE" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
inc = '#include "hle_mkds.h"' + nl
c1 = "(!thumb&&mkds_hle::resolve(NDS_ARM9,pc,false).function)"
c2 = ("        const auto hle=mkds_hle::resolve(NDS_ARM9,n.pending_pc,(g_cpu.cpsr&CPSR_T_BIT)!=0);" + nl +
      "        if(hle.function)hle.function();else tier3_step_one(n.pending_pc);")
for a in (inc, c1, c2):
    if s.count(a) != 1:
        sys.exit("arm9_native.cpp no tiene la forma esperada; no toco nada.")
s = s.replace(inc, inc + nl.join([
    "// IE1_NATIVE_HLE: HLE de Inazuma Eleven en el modo JIT (parche_native_ie1.py)",
    "#if defined(NDS_IE1_CARD_HLE)",
    '#include "hle_ie1_card.h"',
    "static void (*ie1_native_hle(uint32_t pc,bool thumb))(void) {",
    "    return ie1_hle::resolve_card(NDS_ARM9,pc,thumb).function;",
    "}",
    "#else",
    "static void (*ie1_native_hle(uint32_t,bool))(void) {return nullptr;}",
    "#endif", ""]))
s = s.replace(c1, "(!thumb&&(mkds_hle::resolve(NDS_ARM9,pc,false).function||ie1_native_hle(pc,false)))")
s = s.replace(c2, nl.join([
    "        const auto hle=mkds_hle::resolve(NDS_ARM9,n.pending_pc,(g_cpu.cpsr&CPSR_T_BIT)!=0);",
    "        auto* ie1=hle.function?nullptr:ie1_native_hle(n.pending_pc,(g_cpu.cpsr&CPSR_T_BIT)!=0);  // IE1_NATIVE_HLE",
    "        if(hle.function)hle.function();else if(ie1)ie1();else tier3_step_one(n.pending_pc);"]))
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
