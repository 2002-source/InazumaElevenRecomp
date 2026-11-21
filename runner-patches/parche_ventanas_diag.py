#!/usr/bin/env python3
"""
Diagnostico de las rondas largas del planificador (va despues de
parche_ventanas_eventos.py v2).

En la prueba del 2026-11-16 9:28 el ejecutable ya tenia el parche y el lanzador
pone NDS_ARM9_EVENT_WINDOWS=1, pero en el registro no salio la linea "[ventanas]".
Este parche anade al registro:
  1. Al arrancar: el valor con el que llega la variable y si las rondas largas
     quedan encendidas o apagadas.
       [ventanas] NDS_ARM9_EVENT_WINDOWS=1 -> rondas largas encendidas
  2. Cuantas rondas largas se abren y cuantas corta la E/S, cuando se llega a
     1, 1.000, 100.000 y 10.000.000 rondas largas:
       [ventanas] 1000 rondas largas, 950 cortadas por la E/S
Todo con fflush, para que no se pierda aunque el programa se cierre de golpe.

Uso (terminal MSYS2 CLANG64):
   python /c/dev/ie1recomp/scripts/parche_ventanas_diag.py
   bash /c/dev/ie1recomp/scripts/paso_mingw.sh
Se puede ejecutar otra vez sin problema.
"""
import os
import sys

RAIZ = "C:/dev/ndsrecomp/runner/src" if sys.platform == "win32" else "/c/dev/ndsrecomp/runner/src"
if len(sys.argv) > 1:
    RAIZ = sys.argv[1]
OPCIONES = os.path.join(RAIZ, "arm9_native_options.h")
PLANIFICADOR = os.path.join(RAIZ, "scheduler.cpp")
MARCA = "parche_ventanas_diag.py"


def leer(p):
    s = open(p, encoding="utf-8", newline="").read()
    return s, ("\r\n" if "\r\n" in s else "\n")


def escribir(p, s):
    open(p, "w", encoding="utf-8", newline="").write(s)


for p in (OPCIONES, PLANIFICADOR):
    if not os.path.isfile(p):
        sys.exit("No encuentro " + p + " (no toco nada).")

# ---------------------------------------------------------------- opciones
src, nl = leer(OPCIONES)
if MARCA in src:
    print("arm9_native_options.h: ya estaba.")
else:
    if "parche_ventanas_eventos.py" not in src:
        sys.exit("Primero aplica parche_ventanas_eventos.py (no toco nada).")
    inc = "#include <cstring>"
    viejo = "#endif" + nl + "        return o;" + nl + "    }();"
    if src.count(inc) != 1 or src.count(viejo) != 1:
        sys.exit("arm9_native_options.h no tiene la forma esperada (no toco nada). Pasame el archivo.")
    src = src.replace(inc, inc + nl + "#include <cstdio>  // " + MARCA)
    src = src.replace(viejo, nl.join([
        "#endif",
        "        {   // Parche local (" + MARCA + "): estado de las rondas largas",
        "            const char* v=std::getenv(\"NDS_ARM9_EVENT_WINDOWS\");",
        "            std::fprintf(stderr,\"[ventanas] NDS_ARM9_EVENT_WINDOWS=%s -> rondas largas %s\\n\",",
        "                         v?v:\"(sin definir)\",o.events?\"encendidas\":\"apagadas\");",
        "            std::fflush(stderr);",
        "        }",
        "        return o;",
        "    }();",
    ]))
    escribir(OPCIONES, src)
    print("arm9_native_options.h: parcheado.")

# ---------------------------------------------------------------- planificador
src, nl = leer(PLANIFICADOR)
if MARCA in src:
    print("scheduler.cpp: ya estaba.")
else:
    viejo = nl.join([
        "    if(performance_window_active&&performance_windows==1u)",
        "        std::fprintf(stderr,\"[ventanas] rondas largas del planificador en uso (NDS_ARM9_EVENT_WINDOWS=1)\\n\");",
    ])
    if src.count(viejo) != 1:
        sys.exit("scheduler.cpp no tiene la forma esperada (aplica antes parche_ventanas_eventos.py; no toco nada).")
    src = src.replace(viejo, nl.join([
        "    if(performance_window_active&&(performance_windows==1u||performance_windows==1000u||",
        "       performance_windows==100000u||performance_windows==10000000u)) {  // " + MARCA,
        "        std::fprintf(stderr,\"[ventanas] %llu rondas largas, %llu cortadas por la E/S\\n\",",
        "                     (unsigned long long)performance_windows,(unsigned long long)performance_fences);",
        "        std::fflush(stderr);",
        "    }",
    ]))
    escribir(PLANIFICADOR, src)
    print("scheduler.cpp: parcheado.")

print("Ahora recompila: bash /c/dev/ie1recomp/scripts/paso_mingw.sh")
