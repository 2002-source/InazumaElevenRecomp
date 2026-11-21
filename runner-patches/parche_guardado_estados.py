#!/usr/bin/env python3
"""
Parche para el runner de ndsrecomp: guardar la partida aunque se haya cargado un
estado guardado.

Problema: el estado guardado lleva dentro la marca "sesion separada"
(backup_persistence_detached). Al cargarlo, el runner la copia y, desde ese
momento, cuando guardas dentro del juego NO escribe ie1_eur.sav. En el registro sale:
   [save] historical savestate session is detached; canonical cartridge save was not replaced
Si un estado se crea estando ya separado, lleva la marca y cada carga vuelve a
desconectar la partida.

Cambio (runner/src/io.cpp, al cargar un estado):
  - la marca de sesion separada no se hereda del estado (queda en false);
  - la partida cargada del estado no queda "pendiente de escribir" (dirty = false).
Asi ie1_eur.sav solo se escribe cuando el juego guarda (como sin estados), y cargar
un estado viejo y salir sin guardar no toca tu partida.

Uso (terminal MSYS2 CLANG64):
   python /c/dev/ie1recomp/scripts/parche_guardado_estados.py
   bash /c/dev/ie1recomp/scripts/paso_mingw.sh
Se puede ejecutar otra vez sin problema.
"""
import sys

PATH = "C:/dev/ndsrecomp/runner/src/io.cpp" if sys.platform == "win32" else "/c/dev/ndsrecomp/runner/src/io.cpp"
if len(sys.argv) > 1:
    PATH = sys.argv[1]

MARCA = "parche_guardado_estados.py"

src = open(PATH, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in src else "\n"
if MARCA in src:
    print("El parche ya estaba aplicado en", PATH)
    sys.exit(0)

viejo = nl.join([
    "    g_cart_backup.dirty = in.backup_dirty != 0u;",
    "    g_cart_persistence_detached =",
    "        in.backup_persistence_detached != 0u;",
])
nuevo = nl.join([
    "    // Parche local (" + MARCA + "): al cargar un estado, la partida no queda",
    "    // separada ni pendiente; ie1_eur.sav se escribe cuando el juego guarda.",
    "    (void)in.backup_dirty;",
    "    (void)in.backup_persistence_detached;",
    "    g_cart_backup.dirty = false;",
    "    g_cart_persistence_detached = false;",
])
if src.count(viejo) != 1:
    sys.exit("No encontre la carga del estado de la partida en io.cpp (no toco nada). "
             "Pasame el archivo runner/src/io.cpp.")
src = src.replace(viejo, nuevo)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche aplicado en", PATH)
print("Ahora recompila el port: bash /c/dev/ie1recomp/scripts/paso_mingw.sh")
