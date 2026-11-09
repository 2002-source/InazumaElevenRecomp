#!/usr/bin/env bash
# ============================================================
#  Perfil de CPU con nombres de funcion de UNA ranura, sin ventana.
#     bash /c/dev/ie1recomp/scripts/perfil.sh 6
#  Resultado: run/perfil_<ranura>.txt (sube ese archivo)
# ============================================================
set -euo pipefail
SLOT="${1:?indica la ranura, por ejemplo: bash scripts/perfil.sh 6}"
cd /c/dev/ie1recomp
rm -rf run/perfiles
python scripts/bench.py "$SLOT" --rep 1 --frames 1200 --perfil
f=$(ls -t run/perfiles/hostprof-*.ndshp 2>/dev/null | head -1 || true)
if [ -z "$f" ]; then
    echo "No se genero el volcado del perfilador (revisa run/bench_${SLOT}.log)"
    exit 1
fi
PYTHONIOENCODING=utf-8 python /c/dev/ndsrecomp/tools/hostprof_symbolize.py "$f" \
    --top 60 --nm llvm-nm --addr2line llvm-addr2line --role emu \
    --json "run/perfil_${SLOT}.json" > "run/perfil_${SLOT}.txt" 2>&1
echo "Listo: run/perfil_${SLOT}.txt"
head -60 "run/perfil_${SLOT}.txt"
