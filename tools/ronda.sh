#!/usr/bin/env bash
# ============================================================
#  Recomp Inazuma Eleven - una ronda completa de mejora
#  (semillas desde la cobertura -> bancos ARM9/ARM7 -> overlays -> runner)
#  Ejecutar en la terminal "MSYS2 CLANG64":
#     bash /c/dev/ie1recomp/scripts/ronda.sh
# ============================================================
set -euo pipefail
cd /c/dev/ie1recomp
RECOMP=/c/dev/ndsrecomp/recompiler/build/nds_recompile.exe
# Opciones de generacion de todos los bancos (validacion + menos paso por el dispatcher)
RFLAGS="--validate-live-bytes"
# Prueba opcional: IE1_DIRECTAS=1 bash scripts/ronda.sh  activa las llamadas
# directas validadas solo en overlays y capturas (sin unir bloques).
if [ "${IE1_DIRECTAS:-0}" = "1" ]; then
    RFLAGS="--validate-live-bytes --validated-live-direct-calls"
    echo ">>> Prueba: llamadas directas validadas en overlays y capturas"
fi
# Nota: --coalesce-fallthroughs se probo y NO sirve para este juego
# (validaciones enormes que fallan al mezclarse codigo y datos; ~20 FPS).
MFLAGS="--validate-live-bytes"

echo "=== 1. Semillas del ARM9/ARM7 desde todas las coberturas ==="
python scripts/semillas_cobertura.py run/ie1_eur-coverage-*.json
python scripts/generar_toml.py

echo
echo "=== 2. Bancos ARM7 y ARM9 ==="
"$RECOMP" --config configs/arm7.toml --bin images/arm7.bin --out generated \
    --bank arm7_main --shards 2 $MFLAGS | grep -E "finder\]|emit\]|rror"
"$RECOMP" --config configs/arm9.toml --bin images/arm9.bin --out generated \
    --bank arm9_main --shards 8 $MFLAGS | grep -E "finder\]|emit\]|rror"

echo
echo "=== 3. Overlays ==="
rm -f generated/arm9_ov???.c
python scripts/generar_overlays.py run/ie1_eur-coverage-*.json
sed -i "s/--validate-live-bytes\$/$RFLAGS/" configs/overlays/recompilar.sh
sed -i "s/--shards 2 /--shards 4 /" configs/overlays/recompilar.sh   # trozos mas pequenos
bash configs/overlays/recompilar.sh | grep -E "=== overlay|finder\] functions|rror"

echo
echo "=== 4. Codigo capturado de RAM (modulos que no vienen de ningun binario) ==="
rm -f generated/arm9_cap_*
python scripts/capturar_codigo.py run/ie1_eur-coverage-*.json
if [ -f configs/capturas/recompilar.sh ]; then
    sed -i "s/--validate-live-bytes\$/$RFLAGS/" configs/capturas/recompilar.sh
    bash configs/capturas/recompilar.sh | grep -E "=== captura|finder\] functions|rror"
fi

echo
echo "=== 5. Runner ==="
bash scripts/paso_mingw.sh
echo
echo "Overlays registrados: $(grep -c "arm9_ov" /c/dev/ndsrecomp/runner/build-mingw/title_bank_registry.cpp)"
