#!/usr/bin/env bash
# ============================================================
#  PGO (optimizacion guiada por perfil) del runner, con Clang.
#  Hace TODO de una vez, en la terminal "MSYS2 CLANG64":
#     bash /c/dev/ie1recomp/scripts/pgo.sh
#  Para volver al runner normal:
#     bash /c/dev/ie1recomp/scripts/pgo.sh quitar
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
NDS=/c/dev/ndsrecomp
BUILD=$NDS/runner/build-mingw
PGODIR=$IE1/run/pgo
PROFDATA="C:/dev/ie1recomp/run/pgo/ie1.profdata"

modo() {   # cambia el modo en la cache de CMake y recompila (solo el nucleo del runner)
    cmake -S $NDS/runner -B $BUILD "$@" > /dev/null
    bash $IE1/scripts/paso_mingw.sh
}

if [ "${1:-}" = "quitar" ]; then
    echo "=== Volviendo al runner sin PGO ==="
    modo -DIE1_CLANG_PGO=OFF
    exit 0
fi

usar() {
    echo; echo "=== 3. Mezclar perfiles y compilar el runner optimizado (USE) ==="
    llvm-profdata merge -o "$PROFDATA" "$PGODIR"/*.profraw
    ls -la "$PROFDATA"
    modo -DIE1_CLANG_PGO=USE "-DIE1_CLANG_PGO_FILE=$PROFDATA"
    echo
    echo "Listo. Mide con:  python scripts/bench.py todos"
}

if [ "${1:-}" = "usar" ]; then
    usar
    exit 0
fi

echo "=== 0. Parche de CMake ==="
python $IE1/scripts/parche_pgo_clang.py

echo; echo "=== 1. Runner con medicion (GENERATE) ==="
modo -DIE1_CLANG_PGO=GENERATE

echo; echo "=== 2. Entrenamiento con tus 6 estados (bench.py) ==="
rm -rf "$PGODIR"; mkdir -p "$PGODIR"
export LLVM_PROFILE_FILE="C:/dev/ie1recomp/run/pgo/ie1-%p.profraw"
( cd $IE1 && python scripts/bench.py todos --frames 900 --rep 1 )
n=$(ls "$PGODIR"/*.profraw 2>/dev/null | wc -l)
if [ "$n" -eq 0 ]; then
    echo
    echo "No se genero ningun perfil (el runner no se cerro de forma normal)."
    echo "Plan B: juega con el runner de medicion y sal con Esc -> Quit:"
    echo "   LLVM_PROFILE_FILE=$LLVM_PROFILE_FILE bash $IE1/scripts/jugar.sh"
    echo "Visita varias escenas (puedes cargar tus estados) unos 3-4 minutos."
    echo "Despues ejecuta:  bash $IE1/scripts/pgo.sh usar"
    exit 1
fi
echo "Perfiles generados: $n"

usar
