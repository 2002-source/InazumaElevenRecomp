#!/usr/bin/env python3
"""
Generador flat (recompiler/src/flat_codegen.cpp): las operaciones de
mantenimiento de la cache de datos del CP15 (MCR p15,0,Rd,c7,c10/c14/c6,x:
limpiar, invalidar, vaciar el buffer de escritura) pasan a ser NOP dentro de
las regiones flat en lugar de salir al interprete. El runner no emula las
caches del ARM9, asi que estas instrucciones no tienen efecto observable;
lo que costaba era la salida y reentrada en la region por cada una.
La espera de interrupcion (c7,c0,4 / c7,c8,2) y el resto del CP15 NO cambian.

Despues hay que recompilar el recompilador y regenerar los bancos flat:
  bash scripts/perf.sh   (perf.sh ya recompila el recompilador si hace falta)
Deshacer: cd /c/dev/ndsrecomp && git checkout recompiler/src/flat_codegen.cpp
"""
import sys
PATH = "C:/dev/ndsrecomp/recompiler/src/flat_codegen.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
v1 = "    return crm == 6u || crm == 10u || crm == 14u;          // invalidar/limpiar D-cache, drain WB"
v2 = "    return crm == 5u || crm == 6u || crm == 10u || crm == 14u;  // I-cache, D-cache, drain WB"
if "IE1_FLAT_MCR" in s:
    if v1 in s:
        s = s.replace(v1, v2)
        open(PATH, "w", encoding="utf-8", newline="").write(s)
        print("Actualizado (v2): tambien la invalidacion de la cache de instrucciones (c7,c5).")
    else:
        print("El parche ya estaba aplicado.")
    sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
a1 = "std::string hex(uint32_t v) {"
a2 = "        if(missing || !admitted(in,body)) {"
if s.count(a1) != 1 or s.count(a2) != 1:
    sys.exit("flat_codegen.cpp no tiene la forma esperada; no toco nada.")
helper = nl.join([
    "// IE1_FLAT_MCR: mantenimiento de la cache de datos del CP15 = NOP en regiones flat",
    "bool ie1_dcache_maintenance(uint32_t raw) {",
    "    if ((raw >> 28) != 0xEu) return false;                 // solo incondicional",
    "    if ((raw & 0x0F100010u) != 0x0E000010u) return false;  // MCR (no MRC)",
    "    if (((raw >> 8) & 15u) != 15u) return false;           // coprocesador 15",
    "    if (((raw >> 21) & 7u) != 0u) return false;            // opc1 = 0",
    "    if (((raw >> 16) & 15u) != 7u) return false;           // CRn = c7",
    "    const uint32_t crm = raw & 15u;",
    "    return crm == 5u || crm == 6u || crm == 10u || crm == 14u;  // I-cache, D-cache, drain WB",
    "}", ""])
s = s.replace(a1, helper + a1)
nop = nl.join([
    "        if(!thumb && ie1_dcache_maintenance(in.raw)) {  // IE1_FLAT_MCR",
    "            if(instructions.count(pc+step))out<<\"    goto \"<<label(pc+step)<<\";\\n\";",
    "            else out<<\"    goto NDS_REGION_TRANSFER;\\n\";",
    "            out<<\"}\\n\";",
    "            continue;",
    "        }", ""])
s = s.replace(a2, nop + a2)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
