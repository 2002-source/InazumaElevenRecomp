#!/usr/bin/env bash
# ============================================================
#  Compila la version del runner COMPATIBLE CON CUALQUIER PC moderno
#  (x86-64-v2: procesadores de ~2009 en adelante, Intel y AMD), en una
#  carpeta aparte: runner/build-port. La version de siempre
#  (runner/build-mingw, optimizada para este PC) no se toca.
#
#     bash /c/dev/ie1recomp/scripts/paso_port.sh
#
#  La primera vez es LARGA (compila todos los bancos otra vez).
# ============================================================
BUILD_DIR=runner/build-port MARCH="x86-64-v2 -mtune=generic" \
    bash /c/dev/ie1recomp/scripts/paso_mingw.sh "$@"
