#!/usr/bin/env bash
# ============================================================
#  Modelo de ejecucion "performance" (flat AOT) para Inazuma Eleven
#     bash /c/dev/ie1recomp/scripts/perf.sh          genera bancos flat y compila
#     bash /c/dev/ie1recomp/scripts/perf.sh quitar   vuelve al runner sin ellos
#  Para jugar con el modelo:  bash scripts/jugar.sh --execution-model performance
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
NDS=/c/dev/ndsrecomp
RECOMP=$NDS/recompiler/build/nds_recompile.exe
cd $IE1

if [ "${1:-}" = "quitar" ]; then
    rm -rf generated_perf
    cmake -S $NDS/runner -B $NDS/runner/build-mingw -DNDS_MKDS_PERFORMANCE=OFF > /dev/null
    bash scripts/paso_mingw.sh
    exit 0
fi

echo "=== 1. Parches del runner y del generador flat ==="
python scripts/parche_perf.py
python scripts/parche_flat_mcr.py
python scripts/parche_flat_msr.py
python scripts/parche_flat_hle.py
python scripts/parche_flat_io.py
python scripts/parche_flat_region.py
python scripts/integrar_hle_cartucho.py

echo; echo "=== 1b. Recompilador (compilado en CLANG64, con los parches del generador flat) ==="
if [ ! -f $NDS/recompiler/build-mingw/build.ninja ]; then
    cmake -G Ninja -S $NDS/recompiler -B $NDS/recompiler/build-mingw -DCMAKE_BUILD_TYPE=Release > /dev/null
fi
cmake --build $NDS/recompiler/build-mingw --target nds_recompile | tail -1
RECOMP=$NDS/recompiler/build-mingw/nds_recompile.exe

# Tamano maximo de cada region flat en KB (1-12; 0 = una pagina de 4 KB como antes)
export IE1_FLAT_REGION_KB="${IE1_FLAT_REGION_KB:-8}"
echo; echo "=== 2. Bancos flat (ARM9 principal e ITCM), regiones de hasta ${IE1_FLAT_REGION_KB} KB ==="
python scripts/generar_perf.py
mkdir -p generated_perf
rm -f generated_perf/*
for bank in ie1_perf_arm9 ie1_perf_arm9_itcm; do
    bin=images/arm9_static.bin; [ "$bank" = "ie1_perf_arm9_itcm" ] && bin=images/arm9_itcm.bin
    "$RECOMP" --config configs/perf/$bank.toml --bin $bin --out generated_perf \
        --bank $bank --shards 8 --flat-execution --validate-live-bytes \
        | grep -E "finder\] functions|emit\] bank|rror|requires"
done

echo; echo "=== 2b. Bancos flat de overlays y capturas ==="
for cfg in configs/overlays/ov9_*.toml; do
    id=$(basename "$cfg" .toml | sed 's/ov9_//')
    "$RECOMP" --config "$cfg" --bin images/overlays/ov9_$id.bin --out generated_perf \
        --bank ie1_perf_ov$id --shards 2 --flat-execution --validate-live-bytes \
        | grep -E "emit\] bank|rror|requires" || true
done
for cfg in configs/capturas/cap_*.toml; do
    [ -f "$cfg" ] || continue
    n=$(basename "$cfg" .toml)
    "$RECOMP" --config "$cfg" --bin images/capturas/$n.bin --out generated_perf \
        --bank ie1_perf_${n,,} --shards 2 --flat-execution --validate-live-bytes \
        | grep -E "emit\] bank|rror|requires" || true
done
echo "Bancos flat: $(ls generated_perf/*_dispatch.c | wc -l)"

echo; echo "=== 3. Runner con el modelo performance ==="
bash scripts/paso_mingw.sh
echo
echo "Prueba:  python scripts/bench.py 7 --modelo performance"
echo "Juega:   bash scripts/jugar.sh --execution-model performance"
