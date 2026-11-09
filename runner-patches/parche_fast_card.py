#!/usr/bin/env python3
"""
Parche OPCIONAL para el runner de ndsrecomp: "cartucho rapido".

Normalmente, cada palabra de 4 bytes leida del cartucho programa un evento y
corta la ejecucion del ARM9 (nds_reschedule_slice). En juegos que leen el
cartucho por sondeo, como Inazuma Eleven, eso son cientos de miles de cortes
por carga.

Con la variable de entorno NDS_FAST_CARD=1:
  - al leer una palabra, la siguiente queda lista al instante (y se avisa al
    DMA igual que haria el evento);
  - (v2) la espera de inicio de cada comando de lectura se reduce al minimo;
  - (v3) el divisor y la raiz cuadrada por hardware dan el resultado al
    instante (mismo resultado, sin esperas ni cortes del planificador).
El final de la transferencia y su interrupcion no cambian.
Sin la variable, el runner se comporta exactamente como antes.

Uso:
  python scripts/parche_fast_card.py            aplica el parche
Deshacer:
  cd /c/dev/ndsrecomp && git checkout runner/src/io.cpp
"""
import sys

PATH = r"C:/dev/ndsrecomp/runner/src/io.cpp"

src = open(PATH, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in src else "\n"

# --- Parte 2 (v2): acortar tambien la espera de inicio de cada comando ---
MARCA2 = "if (nds_fast_card()) command_delay = 1u;"
def aplicar_parte2(src):
    if MARCA2 in src:
        return src, False
    ancla2 = "            schedule_card_event(uint64_t{xfercycle} *" + nl
    if src.count(ancla2) != 1:
        sys.exit("No encontre la programacion del inicio de comando; no toco nada.")
    return src.replace(ancla2, "            " + MARCA2 + "  // NDS_FAST_CARD" + nl + ancla2), True

# --- Parte 3 (v3): divisor y raiz cuadrada instantaneos ---
MARCA3 = "nds_fast_math()"
def aplicar_parte3(src):
    if MARCA3 in src:
        return src, False
    a_div, a_sqrt = "void start_div() {", "void start_sqrt() {"
    if src.count(a_div) != 1 or src.count(a_sqrt) != 1:
        sys.exit("No encontre start_div/start_sqrt; no toco nada.")
    ayud = nl.join([
        "// NDS_FAST_CARD=1 (v3): divisor y raiz cuadrada con resultado inmediato",
        "void finish_div();",
        "void finish_sqrt();",
        "static bool nds_fast_math() {",
        "    static const bool on = [] {",
        "        const char* v = std::getenv(\"NDS_FAST_CARD\");",
        "        return v && v[0] == '1';",
        "    }();",
        "    return on;",
        "}",
        "", ""])
    src = src.replace(a_div, ayud + a_div + nl +
        "    if (nds_fast_math()) { g_divcnt |= 0x8000u; g_div_deadline = UINT64_MAX; finish_div(); return; }")
    src = src.replace(a_sqrt, a_sqrt + nl +
        "    if (nds_fast_math()) { g_sqrtcnt |= 0x8000u; g_sqrt_deadline = UINT64_MAX; finish_sqrt(); return; }")
    return src, True

if "NDS_FAST_CARD" in src:
    src, c3 = aplicar_parte3(src)
    if c3:
        open(PATH, "w", encoding="utf-8", newline="").write(src)
        print("Parche v3 aplicado (divisor y raiz cuadrada).")
    src, cambio = aplicar_parte2(src)
    if cambio:
        open(PATH, "w", encoding="utf-8", newline="").write(src)
        print("Parche v2 aplicado (espera de inicio de comando).")
    else:
        print("El parche (v2) ya estaba aplicado.")
    sys.exit(0)

viejo_llamada = "schedule_card_event(uint64_t{xfercycle} * delay, false);"
if src.count(viejo_llamada) != 1:
    sys.exit("No encontre exactamente una vez la llamada a reemplazar; no toco nada.")

nuevo_llamada = nl.join([
    "if (nds_fast_card()) {",
    "                        // NDS_FAST_CARD: siguiente palabra lista al instante",
    "                        g_romctrl |= 0x00800000u;",
    "                        nds_dma_trigger(g_card_irq_cpu,",
    "                                        g_card_irq_cpu == 0 ? 5u : 0x12u);",
    "                    } else {",
    "                        schedule_card_event(uint64_t{xfercycle} * delay, false);",
    "                    }",
])
src = src.replace(viejo_llamada, nuevo_llamada)

ancla = "void schedule_card_event(uint64_t delay, bool end_event) {"
if src.count(ancla) != 1:
    sys.exit("No encontre schedule_card_event; no toco nada.")
ayudante = nl.join([
    "// NDS_FAST_CARD=1: lectura rapida del cartucho (parche local, ver parche_fast_card.py)",
    "static bool nds_fast_card() {",
    "    static const bool on = [] {",
    "        const char* v = std::getenv(\"NDS_FAST_CARD\");",
    "        const bool en = v && v[0] == '1';",
    "        if (en) std::fprintf(stderr, \"[card] NDS_FAST_CARD=1: lectura rapida del cartucho\\n\");",
    "        return en;",
    "    }();",
    "    return on;",
    "}",
    "",
    "",
])
src = src.replace(ancla, ayudante + ancla)

src, _ = aplicar_parte2(src)
src, _ = aplicar_parte3(src)

if "#include <cstdlib>" not in src:
    i = src.index("#include")
    src = src[:i] + "#include <cstdlib>" + nl + src[i:]

open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche aplicado en", PATH)
