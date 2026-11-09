#!/usr/bin/env python3
"""
runner/src/bus.cpp: acelera bus_range_has_write_provenance (la comprobacion de
"esta memoria ha sido escrita por el juego" que el dispatcher hace en cada
validacion de codigo). Antes recorria byte a byte toda la zona cada vez.
Ahora recuerda por pagina de 4 KB cuando la pagina entera ya esta escrita
(eso no puede deshacerse: las marcas solo se ponen, y se borran unicamente al
reiniciar o cargar un estado, momentos en los que se invalida lo recordado).
El resultado de la comprobacion es exactamente el mismo.
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/bus.cpp
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/bus.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_PROV_CACHE" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)
d1 = "std::vector<uint8_t> g_arm7_wram_written;" + nl
r1 = "    g_arm7_wram_written.assign(g_arm7_wram.size(), 0u);" + nl
r2 = "    g_arm7_wram_written = in.arm7_wram_written;" + nl
f0 = "bool bus_range_has_write_provenance(uint32_t addr, uint32_t size) {" + nl
old = N("""        if (!written || written_offset + chunk > written->size() ||
            !std::all_of(written->begin() + written_offset,
                         written->begin() + written_offset + chunk,
                         [](uint8_t value) { return value != 0u; }))
            return false;
        offset += chunk;
""")
for a in (d1, r1, r2, f0, old):
    if s.count(a) != 1:
        sys.exit("bus.cpp no tiene la forma esperada; no toco nada.")
s = s.replace(d1, d1 + N("// IE1_PROV_CACHE: epoca de las marcas de escritura (parche_prov.py)\nuint32_t g_ie1_prov_epoch = 1u;\n"))
s = s.replace(r1, r1 + N("    ++g_ie1_prov_epoch;  // IE1_PROV_CACHE\n"))
s = s.replace(r2, r2 + N("    ++g_ie1_prov_epoch;  // IE1_PROV_CACHE\n"))
helper = N("""// IE1_PROV_CACHE: paginas de 4 KB ya escritas por completo en esta epoca
struct Ie1ProvPages { std::vector<uint32_t> full, tried; };
static Ie1ProvPages* ie1_prov_pages(const std::vector<uint8_t>* w) {
    static Ie1ProvPages p[5];
    const int i = w == &g_main_ram_written ? 0 : w == &g_itcm_written ? 1 :
                  w == &g_dtcm_written ? 2 : w == &g_shared_wram_written ? 3 :
                  w == &g_arm7_wram_written ? 4 : -1;
    if (i < 0) return nullptr;
    const std::size_t pages = (w->size() + kExecPageSize - 1u) / kExecPageSize;
    if (p[i].full.size() != pages) { p[i].full.assign(pages, 0u); p[i].tried.assign(pages, 0u); }
    return &p[i];
}

""")
s = s.replace(f0, helper + f0)
new = N("""        // IE1_PROV_CACHE: pagina ya escrita entera -> no hace falta recorrerla
        Ie1ProvPages* pp = written ? ie1_prov_pages(written) : nullptr;
        const uint32_t pg = written_offset / kExecPageSize;
        if (pp && pg < pp->full.size() && pp->full[pg] == g_ie1_prov_epoch) {
            offset += chunk;
            continue;
        }
        if (!written || written_offset + chunk > written->size() ||
            !std::all_of(written->begin() + written_offset,
                         written->begin() + written_offset + chunk,
                         [](uint8_t value) { return value != 0u; }))
            return false;
        if (pp && pg < pp->full.size()) {
            // Reintentar solo si la pagina ha cambiado desde el ultimo intento.
            uint32_t go = 0u;
            const std::vector<uint32_t>* gens = generation_for_ptr(live, &go);
            const uint32_t gi = go / kExecPageSize;
            const uint32_t gen = (gens && gi < gens->size()) ? (*gens)[gi] + 1u : 0u;
            if (gen == 0u || pp->tried[pg] != gen) {
                pp->tried[pg] = gen;
                const std::size_t ps = std::size_t{pg} * kExecPageSize;
                const std::size_t pe = std::min<std::size_t>(written->size(), ps + kExecPageSize);
                if (std::all_of(written->begin() + ps, written->begin() + pe,
                                [](uint8_t value) { return value != 0u; }))
                    pp->full[pg] = g_ie1_prov_epoch;
            }
        }
        offset += chunk;
""")
s = s.replace(old, new)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Parche aplicado en", PATH)
