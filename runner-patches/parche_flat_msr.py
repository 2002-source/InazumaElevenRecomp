#!/usr/bin/env python3
"""
Generador flat (recompiler/src/flat_codegen.cpp): admite dentro de las
regiones flat las instrucciones que usan OS_DisableInterrupts y
OS_RestoreInterrupts:
  - MRS Rd, CPSR      (leer el registro de estado) -> siempre nativo
  - MSR CPSR_<campos>  (escribirlo)                -> nativo si NO cambia el
    modo, el bit Thumb ni QUITA la mascara de IRQ/FIQ. Si reactiva las
    interrupciones o cambia de modo, se entrega al interprete exactamente
    como antes (para atender la interrupcion pendiente con el codigo original).
Solo instrucciones ARM incondicionales sobre el CPSR (nunca el SPSR).
Requiere parche_flat_mcr.py aplicado antes. Despues: bash scripts/perf.sh
Deshacer: cd /c/dev/ndsrecomp && git checkout recompiler/src/flat_codegen.cpp
          (quita tambien el de la cache: vuelve a ejecutar parche_flat_mcr.py)
"""
import sys
PATH = "C:/dev/ndsrecomp/recompiler/src/flat_codegen.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_FLAT_MSR" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
if "IE1_FLAT_MCR" not in s:
    sys.exit("Aplica antes parche_flat_mcr.py.")
nl = "\r\n" if "\r\n" in s else "\n"
a1 = 'std::string label(uint32_t v) {char s[24];std::snprintf(s,sizeof(s),"L_%08X",v);return s;}'
a2 = "        if(missing || !admitted(in,body)) {"
if s.count(a1) != 1 or s.count(a2) != 1:
    sys.exit("flat_codegen.cpp no tiene la forma esperada; no toco nada.")
helper = r'''
// IE1_FLAT_MSR: MRS/MSR del CPSR dentro de las regiones flat (parche_flat_msr.py)
bool ie1_mrs_cpsr(uint32_t raw) {
    return (raw >> 28) == 0xEu && (raw & 0x0FFF0FFFu) == 0x010F0000u &&
           ((raw >> 12) & 15u) != 15u;
}
bool ie1_msr_cpsr(uint32_t raw) {
    if ((raw >> 28) != 0xEu) return false;
    if ((raw & 0x0FF0FFF0u) == 0x0120F000u) return (raw & 15u) != 15u;  // registro
    if ((raw & 0x0FF0F000u) == 0x0320F000u) return true;                // inmediato
    return false;
}
std::string ie1_emit_msr(uint32_t raw, uint32_t pc) {
    uint32_t mask = 0;
    if (raw & (1u << 16)) mask |= 0x000000FFu;
    if (raw & (1u << 17)) mask |= 0x0000FF00u;
    if (raw & (1u << 18)) mask |= 0x00FF0000u;
    if (raw & (1u << 19)) mask |= 0xFF000000u;
    std::string src;
    if (raw & (1u << 25)) {
        uint32_t imm = raw & 0xFFu, rot = ((raw >> 8) & 15u) * 2u;
        if (rot) imm = (imm >> rot) | (imm << (32u - rot));
        src = hex(imm);
    } else {
        src = "_region.cpu.R[" + std::to_string(raw & 15u) + "]";
    }
    std::ostringstream o;
    o << "    { const uint32_t _v=" << src << "; uint32_t _m=" << hex(mask) << ";\n"
      << "      if ((_region.cpu.cpsr & 0x1Fu) == 0x10u) _m &= 0xFF000000u;\n"
      << "      const uint32_t _n = (_region.cpu.cpsr & ~_m) | (_v & _m);\n"
      << "      if (((_n ^ _region.cpu.cpsr) & 0x3Fu) != 0u ||\n"
      << "          ((_region.cpu.cpsr & ~_n) & 0xC0u) != 0u) {\n"
      << "          _region.cpu.R[15]=" << hex(pc) << "; _region.single_step=1; goto NDS_REGION_EXIT; }\n"
      << "      _region.cpu.cpsr = _n; }\n";
    return o.str();
}
'''.replace("\n", nl)
s = s.replace(a1, a1 + helper)
emit = nl.join([
    "        if(!thumb && (ie1_mrs_cpsr(in.raw) || ie1_msr_cpsr(in.raw))) {  // IE1_FLAT_MSR",
    "            if(ie1_mrs_cpsr(in.raw))",
    "                out<<\"    _region.cpu.R[\"<<((in.raw>>12)&15u)<<\"]=_region.cpu.cpsr;\\n\";",
    "            else out<<ie1_emit_msr(in.raw,pc);",
    "            if(instructions.count(pc+step))out<<\"    goto \"<<label(pc+step)<<\";\\n\";",
    "            else out<<\"    goto NDS_REGION_TRANSFER;\\n\";",
    "            out<<\"}\\n\";",
    "            continue;",
    "        }", ""])
s = s.replace(a2, emit + a2)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
