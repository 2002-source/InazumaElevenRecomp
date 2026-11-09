#!/usr/bin/env bash
# ============================================================
#  Recomp Inazuma Eleven - compilar el runner con MSYS2 CLANG64
#  Ejecutar DENTRO de la terminal "MSYS2 CLANG64":
#     bash /c/dev/ie1recomp/scripts/paso_mingw.sh [nucleos]
# ============================================================
set -euo pipefail
if [ -n "${1:-}" ]; then
    JOBS="$1"
else
    # Automatico: ~3 GB de RAM por proceso (los bancos son archivos enormes)
    mem_gb=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 / 1024 ))
    JOBS=$(( mem_gb / 3 ))
    threads=$(nproc)
    [ "$JOBS" -gt "$threads" ] && JOBS=$threads
    [ "$JOBS" -lt 2 ] && JOBS=2
fi
LOG=/c/dev/ie1recomp/build_mingw.log

if [[ "${MSYSTEM:-}" != "CLANG64" ]]; then
    echo "ERROR: abre la terminal 'MSYS2 CLANG64' (no MSYS, no UCRT64) y vuelve a ejecutarme."
    exit 1
fi

cd /c/dev/ndsrecomp

echo "=== 1. Estado del codigo de ndsrecomp (parches locales) ==="
# Ya no se deshace nada: runner/CMakeLists.txt lleva la opcion del HLE de Inazuma.
git status --short
echo
echo "=== 2. Herramientas ==="
for t in clang++ cmake ninja git; do
    printf '%-8s ' "$t"; command -v "$t" || { echo "FALTA $t"; exit 1; }
done

echo
# Carpeta y CPU de destino (por defecto: la de siempre, optimizada para este PC).
# Version compatible con cualquier PC:  bash scripts/paso_port.sh
BUILD_DIR="${BUILD_DIR:-runner/build-mingw}"
MARCH="${MARCH:-native}"
echo "=== 3. Configurando el runner en $BUILD_DIR (CPU: $MARCH) ==="
# Modelo performance: solo si existen los bancos flat (scripts/perf.sh los genera)
PERF_ARGS=()
if [ -f /c/dev/ie1recomp/generated_perf/ie1_perf_arm9_dispatch.c ]; then
    PERF_ARGS=(-DNDS_MKDS_PERFORMANCE=ON
               -DNDS_MKDS_PERFORMANCE_BANK_DIR=C:/dev/ie1recomp/generated_perf
               -DNDS_PERF_ROM_SHA1=d55169c0b93d26b4037379d3b81a61b5404945e5
               -DNDS_PERF_BANK_PREFIX=ie1_perf
               "-DNDS_PERF_BANKS=$(ls /c/dev/ie1recomp/generated_perf/*_dispatch.c | xargs -n1 basename | sed 's/_dispatch\.c$//' | paste -sd';')")
    echo "(con bancos flat del modelo performance)"
fi
cmake -G Ninja -S runner -B "$BUILD_DIR" "${PERF_ARGS[@]}" ${EXTRA_CMAKE_ARGS:-} \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="-march=$MARCH" \
  -DCMAKE_CXX_FLAGS="-march=$MARCH ${CXX_EXTRA:-}" \
  -DNDS_BOOTSTRAP_FIRMWARE=ON \
  -DNDS_GX_COMMAND_CACHE=ON \
  -DNDS_IE1_CARD_IMPLEMENTATION=HLE \
  -DNDS_RECOMP_UI_ROOT=C:/dev/recomp-ui \
  -DNDS_TITLE_BANK_DIR=C:/dev/ie1recomp/generated \
  -DNDS_TITLE_ROM_SHA1=d55169c0b93d26b4037379d3b81a61b5404945e5

echo
echo "=== 4. Compilando con $JOBS procesos (log en $LOG) ==="
if cmake --build "$BUILD_DIR" --target nds_runner -j "$JOBS" > "$LOG" 2>&1; then
    echo
    echo "============================================================"
    echo " COMPILADO: C:/dev/ndsrecomp/$BUILD_DIR/nds_runner.exe"
    command -v ccache >/dev/null && ccache -s 2>/dev/null | grep -i -E "hits|misses" | head -3 || true
    echo "============================================================"
else
    echo
    echo "============================================================"
    echo " LA COMPILACION FALLO. Errores encontrados:"
    echo "============================================================"
    grep -n -E "error:|FAILED:|undefined reference|undefined symbol" "$LOG" | head -40
    echo
    echo "Pega estas lineas en el chat (o adjunta $LOG)."
    exit 1
fi
