#!/usr/bin/env bash
# ============================================================
#  Recomp Inazuma Eleven - jugar
#  En la terminal "MSYS2 CLANG64":
#     bash /c/dev/ie1recomp/scripts/jugar.sh
#  El log de la sesion queda en C:/dev/ie1recomp/run/ultima_sesion.log
# ============================================================
# Idiomas (paquetes en C:/dev/ie1recomp/idiomas, ver crear_paquete_idioma.py):
#   IE1_TEXTOS=es IE1_VOCES=en bash scripts/jugar.sh
export IE1_IDIOMAS_DIR="${IE1_IDIOMAS_DIR:-C:/dev/ie1recomp/idiomas}"
# Cobertura: solo hace falta para las rondas (ronda.sh) y cuesta ~1 % de CPU.
#   Jugar normal:                bash scripts/jugar.sh
#   Jugar recogiendo cobertura:  IE1_COBERTURA=1 bash scripts/jugar.sh
COBERTURA="--no-coverage-manifest"
[ "${IE1_COBERTURA:-0}" = "1" ] && COBERTURA="" && echo "Recogiendo cobertura para la proxima ronda."
cd /c/dev/ie1recomp/run || exit 1
mkdir -p estados
SDL_RENDER_DRIVER=direct3d11 NDS_FAST_CARD=1 \
"${RUNNER_EXE:-/c/dev/ndsrecomp/runner/build-mingw/nds_runner.exe}" /c/dev/ndsrecomp/bios \
  --interactive --freebios --generated-firmware --boot direct \
  --firmware-state-path firmware_state.bin \
  --save-path ie1_eur.sav --savestate-dir estados \
  --virtual-stylus off --config game.toml --performance-governor stage1 \
  --rom /c/dev/ie1recomp/games/ie1_eur.nds $COBERTURA "$@" 2>&1 | tee ultima_sesion.log
