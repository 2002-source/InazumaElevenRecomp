#!/usr/bin/env python3
"""
Permite cargar un estado guardado con OTRO build del runner, solo si se pide
con la variable de entorno NDS_SAVESTATE_ANY_BUILD=1 (bench.py la activa).
Sin la variable, todo sigue igual. La comprobacion de la ROM (SHA-1) se
mantiene siempre.

Deshacer:  cd /c/dev/ndsrecomp && git checkout runner/src/savestate.cpp
"""
import sys

PATH = "C:/dev/ndsrecomp/runner/src/savestate.cpp"
src = open(PATH, encoding="utf-8", newline="").read()
if "NDS_SAVESTATE_ANY_BUILD" in src:
    print("El parche ya estaba aplicado.")
    sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"
viejo = nl.join([
    "    if (identity.build_id != expected_identity.build_id) {",
    '        set_error(error, "savestate build id mismatch");',
    "        return false;",
    "    }"])
if src.count(viejo) != 1:
    sys.exit("No encontre la comprobacion del build id; no toco nada.")
nuevo = nl.join([
    "    // NDS_SAVESTATE_ANY_BUILD=1: aceptar estados de otro build (benchmark)",
    "    const char* ie1_any_build = std::getenv(\"NDS_SAVESTATE_ANY_BUILD\");",
    "    if (identity.build_id != expected_identity.build_id &&",
    "        !(ie1_any_build && ie1_any_build[0] == '1')) {",
    '        set_error(error, "savestate build id mismatch");',
    "        return false;",
    "    }"])
src = src.replace(viejo, nuevo)
if "#include <cstdlib>" not in src:
    i = src.index("#include")
    src = src[:i] + "#include <cstdlib>" + nl + src[i:]
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("Parche aplicado en", PATH)
