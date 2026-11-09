#!/usr/bin/env bash
# Juega con la version EXPERIMENTAL con JIT (runner/build-native).
# Activa las opciones del JIT que funcionaron en Mario Kart:
#   lecturas directas de memoria y lotes de geometria 3D.
# Uso: bash /c/dev/ie1recomp/scripts/jugar_native.sh
export NDS_ARM9_DIRECT_READS=1
export NDS_ARM9_GX_BATCH=1
RUNNER_EXE=/c/dev/ndsrecomp/runner/build-native/nds_runner.exe \
    bash /c/dev/ie1recomp/scripts/jugar.sh --execution-model performance "$@"
