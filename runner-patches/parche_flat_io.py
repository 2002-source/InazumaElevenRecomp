#!/usr/bin/env python3
"""
Regiones flat (recompiler/armv4t/execution_region.h): ciertos registros de
hardware se atienden SIN salir de la region:
  - unidad de division y raiz cuadrada   0x04000280-0x040002BF (leer/escribir)
  - FIFO y puertos de comandos 3D        0x04000400-0x040005FF (escribir)
  - estado del motor 3D (GXSTAT)         0x04000600-0x04000603 (leer)
Antes de cada acceso se publica el tiempo emulado de la region y despues se
recoge, asi los dispositivos ven el mismo tiempo que antes. Si el dispositivo
pide parar (FIFO llena, interrupcion...), la region sale en la comprobacion
que ya se hace tras cada acceso a memoria.
Desactivar sin recompilar: NDS_IE1_FLAT_IO=0
Despues: bash scripts/paso_mingw.sh   (recompila los bancos flat)
Deshacer: cd /c/dev/ndsrecomp && git checkout recompiler/armv4t/execution_region.h
"""
import sys
PATH = "C:/dev/ndsrecomp/recompiler/armv4t/execution_region.h"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_FLAT_IO" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
a0 = "NDS_MACHINERY_INLINE uint32_t nds_region_read(NdsExecRegion* r, uint32_t addr,"
r_old = nl.join(["    nds_region_publish(r);", "    r->io = 1;", "    if (width == 4) return bus_read_u32_slow(addr);"])
w_old = nl.join(["    nds_region_publish(r);", "    r->io = 1;", "    if (width == 4) bus_write_u32_slow(addr, value);"])
if s.count(a0) != 1 or s.count(r_old) != 1 or s.count(w_old) != 1:
    sys.exit("execution_region.h no tiene la forma esperada; no toco nada.")
helper = nl.join([
    "/* IE1_FLAT_IO: registros atendidos sin salir de la region (parche_flat_io.py) */",
    "#include <stdlib.h>",
    "NDS_MACHINERY_INLINE int ie1_flat_io_enabled(void) {",
    "    static int on = -1;",
    "    if (on < 0) { const char* v = getenv(\"NDS_IE1_FLAT_IO\"); on = !(v && v[0] == '0'); }",
    "    return on;",
    "}",
    "NDS_MACHINERY_INLINE int ie1_flat_io_fast(uint32_t addr, int write) {",
    "    if (!ie1_flat_io_enabled()) return 0;",
    "    if (addr >= 0x04000280u && addr < 0x040002C0u) return 1;            /* division / raiz */",
    "    if (write && addr >= 0x04000400u && addr < 0x04000600u) return 1;  /* FIFO y puertos 3D */",
    "    if (!write && addr >= 0x04000600u && addr < 0x04000604u) return 1; /* GXSTAT */",
    "    return 0;",
    "}", ""])
s = s.replace(a0, helper + a0)
r_new = nl.join([
    "    if (ie1_flat_io_fast(addr, 0)) {  /* IE1_FLAT_IO */",
    "        uint32_t v;",
    "        g_runtime_cycles = r->cycles;",
    "        if (width == 4) v = bus_read_u32_slow(addr);",
    "        else if (width == 2) v = bus_read_u16_slow(addr);",
    "        else v = bus_read_u8_slow(addr);",
    "        r->cycles = g_runtime_cycles;",
    "        return v;",
    "    }", ""]) + r_old
s = s.replace(r_old, r_new)
w_new = nl.join([
    "    if (ie1_flat_io_fast(addr, 1)) {  /* IE1_FLAT_IO */",
    "        g_runtime_cycles = r->cycles;",
    "        if (width == 4) bus_write_u32_slow(addr, value);",
    "        else if (width == 2) bus_write_u16_slow(addr, (uint16_t)value);",
    "        else bus_write_u8_slow(addr, (uint8_t)value);",
    "        r->cycles = g_runtime_cycles;",
    "        return;",
    "    }", ""]) + w_old
s = s.replace(w_old, w_new)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
