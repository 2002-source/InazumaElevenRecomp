#!/usr/bin/env python3
"""
Rendimiento, paso 2 (version 2): "ventanas de eventos" del planificador con los
bancos flat de Inazuma Eleven.

El planificador del runner reparte el tiempo en rondas cortas: en cada una ejecuta
la ARM9, despues la ARM7 y los dispositivos. Cada ronda tiene un coste fijo, y en
las escenas pesadas (Regate Multiple, Ruptura Relampago...) hay unas 6.000-6.500
rondas por fotograma.

El runner trae una opcion (NDS_ARM9_EVENT_WINDOWS, nds_native_event_quantum):
cuando la ARM7 esta dormida sin nada que la despierte, sin DMA y sin el GXFIFO
atascado, la ronda es de 256 ciclos en vez de 64. Si la ARM9 toca la E/S durante la
ronda larga (scheduler_performance_io_fence) la ronda se corta en ese punto.

La version 1 de este parche solo dejaba leer la variable sin el JIT, pero el
planificador ademas exigia el modelo de ejecucion "performance", que en este runner
solo existe para Mario Kart DS; Inazuma corre como "faithful-v1" (sale en el
registro), asi que las ventanas nunca se abrian. Esta version:
  1. arm9_native_options.h: lee NDS_ARM9_EVENT_WINDOWS tambien sin el JIT (como v1).
  2. scheduler.cpp: las ventanas no exigen el modelo "performance", solo la variable.
  3. scheduler.cpp: escribe en el registro "[ventanas] ..." la primera vez que se abre
     una, para poder comprobar que esta funcionando.
Antes de tocar nada comprueba que el corte por E/S (scheduler_performance_io_fence)
se llama desde el codigo del runner y que no depende del modelo "performance".
Sin la variable a 1 no cambia nada.

Uso (terminal MSYS2 CLANG64):
   python /c/dev/ie1recomp/scripts/parche_ventanas_eventos.py
   bash /c/dev/ie1recomp/scripts/paso_mingw.sh
Se puede ejecutar otra vez sin problema (tambien si ya estaba la version 1).
"""
import os
import re
import sys

RAIZ = "C:/dev/ndsrecomp/runner/src" if sys.platform == "win32" else "/c/dev/ndsrecomp/runner/src"
if len(sys.argv) > 1:
    RAIZ = sys.argv[1]
OPCIONES = os.path.join(RAIZ, "arm9_native_options.h")
PLANIFICADOR = os.path.join(RAIZ, "scheduler.cpp")
MARCA = "parche_ventanas_eventos.py"
MARCA2 = "parche_ventanas_eventos.py v2"


def leer(p):
    s = open(p, encoding="utf-8", newline="").read()
    return s, ("\r\n" if "\r\n" in s else "\n")


def escribir(p, s):
    open(p, "w", encoding="utf-8", newline="").write(s)


# ---------------------------------------------------------------- comprobaciones
for p in (OPCIONES, PLANIFICADOR):
    if not os.path.isfile(p):
        sys.exit("No encuentro " + p + " (no toco nada).")

llamadas = []
for nombre in sorted(os.listdir(RAIZ)):
    if not nombre.endswith((".cpp", ".h", ".inc")):
        continue
    ruta = os.path.join(RAIZ, nombre)
    try:
        lineas = open(ruta, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        continue
    for i, l in enumerate(lineas):
        if "scheduler_performance_io_fence" in l and not re.search(r"\bvoid\s+scheduler_performance_io_fence", l):
            llamadas.append((nombre, i + 1, l.strip(), lineas[max(0, i - 3):i + 1]))
if not llamadas:
    sys.exit("No encontre ninguna llamada a scheduler_performance_io_fence en " + RAIZ +
             " (no toco nada): sin ese corte las rondas largas no son seguras. "
             "Pasame la salida de: grep -rn performance_io_fence /c/dev/ndsrecomp/runner/src")
dependientes = [c for c in llamadas if any("nds_performance_execution" in x for x in c[3])]
print("Corte por E/S encontrado en:")
for n, num, l, _ in llamadas:
    print("   %s:%d  %s" % (n, num, l))
if len(dependientes) == len(llamadas):
    sys.exit("Todas las llamadas al corte dependen del modelo \"performance\" (no toco nada). "
             "Pasame los archivos donde salen.")

# ---------------------------------------------------------------- 1. opciones
src, nl = leer(OPCIONES)
if MARCA in src:
    print("arm9_native_options.h: ya estaba (version 1).")
else:
    viejo = nl.join([
        "        o.events=on(\"NDS_ARM9_EVENT_WINDOWS\");",
        "#endif",
        "        return o;",
    ])
    nuevo = nl.join([
        "        o.events=on(\"NDS_ARM9_EVENT_WINDOWS\");",
        "#else",
        "        // Parche local (" + MARCA + "): las ventanas de eventos del",
        "        // planificador tambien sin el JIT (bancos flat de Inazuma Eleven).",
        "        {const char* v=std::getenv(\"NDS_ARM9_EVENT_WINDOWS\");o.events=v&&std::strcmp(v,\"1\")==0;}",
        "#endif",
        "        return o;",
    ])
    if src.count(viejo) != 1:
        sys.exit("arm9_native_options.h no tiene la forma esperada (no toco nada). Pasame el archivo.")
    escribir(OPCIONES, src.replace(viejo, nuevo))
    print("arm9_native_options.h: parcheado.")

# ---------------------------------------------------------------- 2/3. planificador
src, nl = leer(PLANIFICADOR)
if MARCA2 in src:
    print("scheduler.cpp: ya estaba.")
else:
    viejo = "        nds_performance_execution()&&nds_native_options().events&&g_slot[0].started&&g_slot[1].started,"
    nuevo = ("        // Parche local (" + MARCA2 + "): sin exigir el modelo \"performance\"." + nl +
             "        nds_native_options().events&&g_slot[0].started&&g_slot[1].started,")
    if src.count(viejo) != 1:
        sys.exit("scheduler.cpp no tiene la forma esperada (no toco nada). Pasame runner/src/scheduler.cpp.")
    src = src.replace(viejo, nuevo)
    viejo2 = "    if(performance_window_active)++performance_windows;"
    nuevo2 = nl.join([
        "    if(performance_window_active)++performance_windows;",
        "    if(performance_window_active&&performance_windows==1u)",
        "        std::fprintf(stderr,\"[ventanas] rondas largas del planificador en uso (NDS_ARM9_EVENT_WINDOWS=1)\\n\");",
    ])
    if src.count(viejo2) != 1:
        sys.exit("scheduler.cpp no tiene la forma esperada (no toco nada). Pasame runner/src/scheduler.cpp.")
    src = src.replace(viejo2, nuevo2)
    escribir(PLANIFICADOR, src)
    print("scheduler.cpp: parcheado.")

print("Ahora recompila: bash /c/dev/ie1recomp/scripts/paso_mingw.sh")
