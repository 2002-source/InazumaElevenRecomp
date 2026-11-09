#!/usr/bin/env bash
# ============================================================
#  Crea una carpeta PORTABLE del port de Inazuma Eleven para llevarla
#  a otro PC: ejecutable, bibliotecas, BIOS libre, ROM, idiomas y lanzador.
#
#     bash /c/dev/ie1recomp/scripts/crear_port.sh            (sin tu partida)
#     bash /c/dev/ie1recomp/scripts/crear_port.sh --partida  (copia tu partida y ajustes)
#     ... --mods   incluye tambien el complemento cargador de mods (ie1_mods.dll)
#
#  Resultado: D:\Juegos\Inazuma Eleven 1\
#  (otra carpeta: DESTINO="/e/otra/carpeta" bash scripts/crear_port.sh)
#  Si la carpeta ya existe, se ACTUALIZA: no se borra nada de lo que haya en
#  ella, y una partida que ya este alli no se sobrescribe salvo con --partida.
#  La carpeta incluye la ROM y los paquetes de idioma: es para TUS equipos,
#  no para compartirla con otras personas.
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
NDS=/c/dev/ndsrecomp
# Version compatible con cualquier PC (paso_port.sh); si no existe, la de este PC
EXE=$NDS/runner/build-port/nds_runner.exe
if [ ! -f "$EXE" ]; then
    EXE=$NDS/runner/build-mingw/nds_runner.exe
    echo "AVISO: no hay version compatible (bash scripts/paso_port.sh); uso la optimizada"
    echo "       para ESTE procesador, que puede no funcionar en otro PC."
fi
DLLS_DIR=$(dirname "$EXE")
DEST="${DESTINO:-/d/Juegos/Inazuma Eleven 1}"

[ -f "$EXE" ] || { echo "No encuentro $EXE; compila antes con paso_mingw.sh"; exit 1; }
echo "=== Carpeta: $DEST ==="
mkdir -p "$DEST/bin" "$DEST/rom" "$DEST/datos/estados"

echo "=== 1. Ejecutable y bibliotecas ==="
cp "$EXE" "$DEST/bin/"
# Todas las DLL que no son de Windows (las de MSYS2 CLANG64, SDL3, etc.)
ldd "$EXE" | awk '{print $3}' | grep -v -i -E '^/c/windows|^$|not' | sort -u | while read -r dll; do
    cp "$dll" "$DEST/bin/" && echo "   $(basename "$dll")"
done
# Por si alguna DLL esta junto al ejecutable y ldd no la resuelve
for dll in "$DLLS_DIR"/*.dll; do
    [ "$(basename "$dll")" = "ie1_mods.dll" ] && continue   # el complemento de mods va aparte
    [ -f "$dll" ] && cp -n "$dll" "$DEST/bin/" || true
done
rm -f "$DEST/bin/ie1_mods.dll"
if [[ " $* " == *" --mods "* ]] && [ -f "$IE1/plugin/ie1_mods.dll" ]; then
    cp "$IE1/plugin/ie1_mods.dll" "$DEST/bin/"
    mkdir -p "$DEST/mods"
    [ -f "$DEST/mods/mods.cfg" ] || printf '# Un mod activo por linea, en orden (el ultimo gana)\n' > "$DEST/mods/mods.cfg"
    echo "   + complemento de mods (ie1_mods.dll) y carpeta mods\\"
fi

echo "=== 2. BIOS libre y firmware generado ==="
mkdir -p "$DEST/bios" && cp -r "$NDS/bios/." "$DEST/bios/"

echo "=== 3. ROM e idiomas ==="
cp "$IE1/games/ie1_eur.nds" "$DEST/rom/"
if [ -d "$IE1/idiomas" ]; then mkdir -p "$DEST/idiomas" && cp -r "$IE1/idiomas/." "$DEST/idiomas/"; fi

echo "=== 4. Configuracion del juego ==="
cp "$IE1/run/game.toml" "$DEST/datos/"
for f in idiomas.cfg ie1_menu.cfg; do
    [ -f "$IE1/run/$f" ] && cp "$IE1/run/$f" "$DEST/datos/" || true
done
if [[ " $* " == *" --partida "* ]]; then
    echo "   (copiando tu partida y el estado del firmware)"
    for f in ie1_eur.sav firmware_state.bin; do
        [ -f "$IE1/run/$f" ] && cp "$IE1/run/$f" "$DEST/datos/" || true
    done
fi

echo "=== 5. Lanzador ==="
# Lanzador grafico (compilar_lanzador.sh): "Inazuma Eleven.exe" en la raiz, con sus DLL
if [ -f "$IE1/lanzador/lanzador.exe" ]; then
    cp "$IE1/lanzador/lanzador.exe" "$DEST/Inazuma Eleven.exe"
    ldd "$IE1/lanzador/lanzador.exe" | awk '{print $3}' | grep -v -i -E '^/c/windows|^$|not' | sort -u | while read -r dll; do
        cp -u "$dll" "$DEST/"
    done
    rm -f "$DEST/lanzador.ini"          # en el port valen las rutas por defecto (bin, rom, datos...)
    echo "   Inazuma Eleven.exe (lanzador grafico)"
else
    echo "   AVISO: sin lanzador grafico (bash scripts/compilar_lanzador.sh); queda el .bat"
fi
cat > "$DEST/Inazuma Eleven.bat" <<'EOF'
@echo off
rem Inazuma Eleven (port) - doble clic para jugar
set "RAIZ=%~dp0"
set "PATH=%RAIZ%bin;%PATH%"
set NDS_FAST_CARD=1
set "IE1_IDIOMAS_DIR=%RAIZ%idiomas"
cd /d "%RAIZ%datos"
if not exist estados mkdir estados
"%RAIZ%bin\nds_runner.exe" "%RAIZ%bios" ^
  --interactive --freebios --generated-firmware --boot direct ^
  --firmware-state-path firmware_state.bin ^
  --save-path ie1_eur.sav --savestate-dir estados ^
  --virtual-stylus off --config game.toml --performance-governor stage1 ^
  --execution-model performance --diagnostics off --no-coverage-manifest ^
  --rom "%RAIZ%rom\ie1_eur.nds" > ultima_sesion.log 2>&1
EOF
sed -i 's/$/\r/' "$DEST/Inazuma Eleven.bat"

cat > "$DEST/LEEME.txt" <<'EOF'
Inazuma Eleven - port (recompilacion estatica)

Jugar:      doble clic en "Inazuma Eleven.exe" (lanzador: Jugar, Mods, Opciones)
            o en "Inazuma Eleven.bat" (directo, sin lanzador)
Menu:       Esc  (idioma, pantalla, estados, reiniciar)
Partida:    datos\ie1_eur.sav     Estados: datos\estados\
Log:        datos\ultima_sesion.log

Contiene la ROM y los paquetes de idioma: solo para uso personal.
EOF
sed -i 's/$/\r/' "$DEST/LEEME.txt"

du -sh "$DEST" | awk '{print "Tamano de la carpeta: " $1}'
echo
echo "Listo. Para jugar: doble clic en \"$DEST/Inazuma Eleven.bat\""
