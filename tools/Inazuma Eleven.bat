@echo off
rem ============================================================
rem  Inazuma Eleven (recomp) - lanzador de doble clic
rem  Hace lo mismo que scripts/jugar.sh --execution-model performance
rem  El log queda en C:\dev\ie1recomp\run\ultima_sesion.log
rem ============================================================

rem Bibliotecas que necesita el ejecutable (compilado con MSYS2 CLANG64)
set "PATH=C:\dev\ndsrecomp\runner\build-mingw;C:\msys64\clang64\bin;%PATH%"

set NDS_FAST_CARD=1
set "IE1_IDIOMAS_DIR=C:/dev/ie1recomp/idiomas"

cd /d C:\dev\ie1recomp\run
if not exist estados mkdir estados

"C:\dev\ndsrecomp\runner\build-mingw\nds_runner.exe" C:/dev/ndsrecomp/bios ^
  --interactive --freebios --generated-firmware --boot direct ^
  --firmware-state-path firmware_state.bin ^
  --save-path ie1_eur.sav --savestate-dir estados ^
  --virtual-stylus off --config game.toml --performance-governor stage1 ^
  --execution-model performance ^
  --rom C:/dev/ie1recomp/games/ie1_eur.nds > ultima_sesion.log 2>&1
