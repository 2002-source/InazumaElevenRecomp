#!/usr/bin/env bash
# ============================================================
#  Complemento cargador de mods (ie1_mods.dll)
#     bash scripts/compilar_mods.sh            compila y lo activa en el juego de desarrollo
#     bash scripts/compilar_mods.sh quitar     lo quita (el juego vuelve a ignorar los mods)
#
#  El .dll queda en C:\dev\ie1recomp\plugin\ie1_mods.dll. Para usarlo en el
#  port, copialo a la carpeta bin\ del port (junto a nds_runner.exe).
#  Los mods van en C:\dev\ie1recomp\mods\ (y en el port, en <port>\mods\).
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
DEV=/c/dev/ndsrecomp/runner/build-mingw
if [ "${1:-}" = "quitar" ]; then
    rm -f "$DEV/ie1_mods.dll"
    echo "Complemento quitado del juego de desarrollo: los mods se ignoran."
    exit 0
fi
mkdir -p "$IE1/plugin" "$IE1/mods"
clang++ -std=c++20 -O2 -shared -I"$IE1/scripts" -o "$IE1/plugin/ie1_mods.dll" "$IE1/scripts/ie1_mods.cpp"
cp "$IE1/plugin/ie1_mods.dll" "$DEV/"
[ -f "$IE1/mods/mods.cfg" ] || printf '# Un mod activo por linea, en orden (el ultimo gana)\n' > "$IE1/mods/mods.cfg"
echo "Compilado: $IE1/plugin/ie1_mods.dll (activado en $DEV)"
echo "Mods en:   $IE1/mods/   (activa cada uno escribiendo su carpeta en mods.cfg)"
