#!/usr/bin/env python3
"""
DIAGNOSTICO (runner/src/runtime_arm.cpp): cuenta por pagina de 4 KB cuantas
veces una escritura del juego obliga al runner a REVALIDAR codigo nativo
(comparar los bytes de la funcion con los esperados). Solo actua con la
variable NDS_IE1_DIAG_ESCRITURAS=1; sin ella no cambia nada.
Al cerrar el juego escribe en el log las paginas con mas revalidaciones:
  [escrituras] ...
Deshacer: cd /c/dev/ndsrecomp && git checkout runner/src/runtime_arm.cpp
"""
import sys
PATH = "C:/dev/ndsrecomp/runner/src/runtime_arm.cpp"
s = open(PATH, encoding="utf-8", newline="").read()
if "IE1_DIAG_ESCRITURAS" in s:
    print("El parche ya estaba aplicado."); sys.exit(0)
nl = "\r\n" if "\r\n" in s else "\n"
def N(t): return t.replace("\n", nl)
def rep(viejo, nuevo, nombre):
    global s
    viejo, nuevo = N(viejo), N(nuevo)
    if s.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)

# 1) contadores + informe al salir, justo antes de cached_lookup_live
rep('''bool cached_lookup_live(const CachedStaticLookup& cached) {''',
'''// IE1_DIAG_ESCRITURAS: revalidaciones de codigo por pagina (parche_diag_escrituras.py)
struct Ie1DiagPagina { uint64_t guarda = 0, busqueda = 0; uint32_t pc = 0; };
struct Ie1Diag {
    bool activo = false, iniciado = false;
    uint64_t escrituras = 0;
    std::map<uint32_t, Ie1DiagPagina> paginas;
};
Ie1Diag& ie1_diag() {
    static Ie1Diag d;
    if (!d.iniciado) {
        d.iniciado = true;
        const char* e = std::getenv("NDS_IE1_DIAG_ESCRITURAS");
        d.activo = e && *e == '1';
        if (d.activo) std::atexit([] {
            Ie1Diag& d2 = ie1_diag();
            std::vector<std::pair<uint32_t, Ie1DiagPagina>> v(d2.paginas.begin(), d2.paginas.end());
            std::sort(v.begin(), v.end(), [](const auto& a, const auto& b) {
                return a.second.guarda + a.second.busqueda > b.second.guarda + b.second.busqueda; });
            uint64_t tg = 0, tb = 0;
            for (const auto& p : v) { tg += p.second.guarda; tb += p.second.busqueda; }
            std::fprintf(stderr, "[escrituras] escrituras del juego en RAM: %llu; revalidaciones: %llu (codigo en ejecucion) + %llu (busquedas)\\n",
                         (unsigned long long)d2.escrituras, (unsigned long long)tg, (unsigned long long)tb);
            for (size_t i = 0; i < v.size() && i < 25; ++i)
                std::fprintf(stderr, "[escrituras] pagina %08X: %llu en ejecucion + %llu en busquedas (pc ejemplo %08X)\\n",
                             v[i].first, (unsigned long long)v[i].second.guarda,
                             (unsigned long long)v[i].second.busqueda, v[i].second.pc);
        });
    }
    return d;
}

bool cached_lookup_live(const CachedStaticLookup& cached) {''', "cached_lookup_live")

# 2) en la busqueda cacheada: contar la pagina cuya generacion cambio
rep('''        if (live_generation != cached.generation[i])
            return false;
    }
    return true;
}

bool cache_page_generation(''',
'''        if (live_generation != cached.generation[i]) {
            Ie1Diag& d = ie1_diag();  // IE1_DIAG_ESCRITURAS
            if (d.activo) { auto& p = d.paginas[cached.page_addr[i] & ~0xFFFu]; ++p.busqueda; p.pc = g_cpu.R[15]; }
            return false;
        }
    }
    return true;
}

bool cache_page_generation(''', "fallo de la busqueda cacheada")

# 3) en la guarda del codigo en ejecucion: contar antes de revalidar
rep('''bool refresh_guard_after_generation_change(StaticExecutionGuard& guard) {
    if (!guard.validation) return true;''',
'''bool refresh_guard_after_generation_change(StaticExecutionGuard& guard) {
    if (!guard.validation) return true;
    {   // IE1_DIAG_ESCRITURAS
        Ie1Diag& d = ie1_diag();
        if (d.activo)
            for (uint32_t i = 0; i < guard.page_count; ++i) {
                const uint32_t g = guard.generation_ptr[i] ? *guard.generation_ptr[i]
                                                           : bus_exec_page_generation(guard.page_addr[i]);
                if (g != guard.generation[i]) { auto& p = d.paginas[guard.page_addr[i] & ~0xFFFu]; ++p.guarda; p.pc = g_cpu.R[15]; }
            }
    }''', "refresh_guard_after_generation_change")

# 4) contar las escrituras totales
rep('''    ++g_coverage_write_epoch;''',
'''    ++g_coverage_write_epoch;
    { Ie1Diag& d = ie1_diag(); if (d.activo) ++d.escrituras; }  // IE1_DIAG_ESCRITURAS''', "runtime_note_code_write")

if "#include <map>" not in s:
    s = s.replace("#include <algorithm>", "#include <algorithm>" + nl + "#include <map>  // IE1_DIAG_ESCRITURAS", 1)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print("Diagnostico de escrituras anadido en", PATH)
