#!/usr/bin/env bash
# ============================================================
#  Compila el lanzador (Jugar / Mods / Opciones / Salir).
#  En la terminal "MSYS2 CLANG64":
#     bash /c/dev/ie1recomp/scripts/compilar_lanzador.sh
#  Fuentes: C:/dev/ie1recomp/lanzador/ (lanzador.cpp + lanzador_ui.hpp)
#  Resultado: C:/dev/ie1recomp/lanzador/lanzador.exe con un lanzador.ini que
#  apunta a tu entorno de desarrollo (para probarlo antes de crear el port).
# ============================================================
set -euo pipefail
SRC=/c/dev/ie1recomp/lanzador
cd "$SRC"
command -v pkg-config >/dev/null || { echo "Falta pkg-config (pacman -S mingw-w64-clang-x86_64-pkgconf)"; exit 1; }
pkg-config --exists sdl3 || { echo "No encuentro SDL3 (pacman -S mingw-w64-clang-x86_64-sdl3)"; exit 1; }
# Icono del .exe: el de la ROM (el que sale en el menu de la DS), con icono_rom.cpp
ROM=/c/dev/ie1recomp/games/ie1_eur.nds
ICONO_OBJ=""
RC=$(command -v llvm-windres || command -v windres || true)
if [ ! -f icono_rom.cpp ]; then
    echo "AVISO: falta icono_rom.cpp en $SRC: el .exe sale sin icono."
elif [ ! -f "$ROM" ]; then
    echo "AVISO: no encuentro la ROM ($ROM): el .exe sale sin icono."
elif [ -z "$RC" ]; then
    echo "AVISO: no encuentro llvm-windres (pacman -S mingw-w64-clang-x86_64-llvm): el .exe sale sin icono."
else
    clang++ -std=c++17 -O2 icono_rom.cpp -o icono_rom.exe
    ./icono_rom.exe "$ROM" icono.ico
    printf '1 ICON "icono.ico"\n' > icono.rc
    "$RC" icono.rc -O coff -o icono.o
    ICONO_OBJ=icono.o
fi
clang++ -std=c++17 -O2 -Wall lanzador.cpp $ICONO_OBJ -o lanzador.exe $(pkg-config --cflags --libs sdl3) -mwindows
# DLL que necesita (SDL3, libc++...) junto al ejecutable
ldd lanzador.exe | awk '{print $3}' | grep -v -i -E '^/c/windows|^$|not' | sort -u | while read -r dll; do
    [ "$dll" -ef "$SRC/$(basename "$dll")" ] && continue     # ya es la copia de esta carpeta
    cp -u "$dll" "$SRC/"
done
# comprobacion: que se ha compilado la version con la ficha de los mods
if ! grep -q "ModInfo" lanzador_ui.hpp; then
    echo "AVISO: lanzador_ui.hpp es una version antigua (sin la ficha de los mods)."
    echo "       Copia encima el lanzador_ui.hpp y el lanzador.cpp nuevos en $SRC y vuelve a compilar."
fi
# lanzador.ini de desarrollo (en el port se usan las rutas de su propia carpeta)
DLLS=$(cygpath -m /clang64/bin 2>/dev/null || echo C:/msys64/clang64/bin)
cat > lanzador.ini <<INI
# Rutas del lanzador (desarrollo). En el port no hace falta este archivo.
# dlls: donde estan las DLL que usa el juego compilado en MSYS2 (SDL3, libc++...)
dlls=$DLLS
runner=C:/dev/ndsrecomp/runner/build-mingw/nds_runner.exe
bios=C:/dev/ndsrecomp/bios
datos=C:/dev/ie1recomp/run
rom=C:/dev/ie1recomp/games/ie1_eur.nds
idiomas=C:/dev/ie1recomp/idiomas
mods=C:/dev/ie1recomp/mods
INI
echo "Compilado: $SRC/lanzador.exe"
echo "Pruebalo con:  $SRC/lanzador.exe   (o doble clic)"
