#!/usr/bin/env bash
# ============================================================
#  Perfil de CPU con nombres de funcion de la ULTIMA partida jugada
#  (la que se cerro con Esc -> Quit). Uso:
#     bash /c/dev/ie1recomp/scripts/perfil_juego.sh [nombre]
#  Resultado: run/perfil_<nombre>.txt  (por defecto perfil_juego.txt)
# ============================================================
set -euo pipefail
NOMBRE="${1:-juego}"
cd /c/dev/ie1recomp/run
f=$(ls -t hostprof-*.ndshp 2>/dev/null | head -1 || true)
if [ -z "$f" ]; then
    echo "No hay volcado del perfilador (cierra el juego con Esc -> Quit)."
    exit 1
fi
echo "Volcado: $f"
PYTHONIOENCODING=utf-8 python /c/dev/ndsrecomp/tools/hostprof_symbolize.py "$f" \
    --top 60 --nm llvm-nm --addr2line llvm-addr2line --role emu \
    --json "perfil_${NOMBRE}.json" > "perfil_${NOMBRE}.txt" 2>&1
echo "Listo: run/perfil_${NOMBRE}.txt"
sed -n '/BUSY samples only/,/SELF time, top/p' "perfil_${NOMBRE}.txt"
