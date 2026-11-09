#!/usr/bin/env bash
# ============================================================
#  Crea la version del port PARA COMPARTIR con otras personas:
#    - SIN ROM, sin paquetes de idioma y sin mods generados (todo eso sale de
#      las ROM de cada persona con el preparador de arrastrar y soltar);
#    - SIN tu configuracion: ni partida, ni estados, ni teclas, ni ajustes,
#      ni la identidad Wi-Fi (MAC) de tu instalacion;
#    - CON el lanzador, el preparador ("PREPARAR - arrastra aqui tus ROM.bat"),
#      un Python portable para las herramientas y las instrucciones.
#
#     bash /c/dev/ie1recomp/scripts/crear_distribucion.sh
#  Resultado: D:\Juegos\Inazuma Eleven PC Port v1.0\  y un .zip al lado.
#  Las instrucciones salen de scripts/textos_port/ (README/LEEME y los de mods).
#  (otra carpeta: DESTINO="/e/otra" bash scripts/crear_distribucion.sh)
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
NDS=/c/dev/ndsrecomp
S=$IE1/scripts
VERSION=1.0
DEST="${DESTINO:-/d/Juegos/Inazuma Eleven PC Port v$VERSION}"
PY_VER=3.12.7
PY_ZIP="$IE1/run/python-$PY_VER-embed-amd64.zip"

EXE=$NDS/runner/build-port/nds_runner.exe
[ -f "$EXE" ] || { echo "Falta la version compatible del runner: bash scripts/paso_port.sh"; exit 1; }
[ -f "$IE1/lanzador/lanzador.exe" ] || { echo "Falta el lanzador: bash scripts/compilar_lanzador.sh"; exit 1; }
[ -f "$IE1/plugin/ie1_mods.dll" ] || { echo "Falta el complemento de mods: bash scripts/compilar_mods.sh"; exit 1; }

echo "=== Carpeta nueva: $DEST ==="
rm -rf "$DEST"
mkdir -p "$DEST"/{bin,bios,datos/estados,rom,idiomas,mods,herramientas/scripts,herramientas/trabajo/generated}

echo "=== 1. Ejecutable, bibliotecas y complemento de mods ==="
cp "$EXE" "$DEST/bin/"
ldd "$EXE" | awk '{print $3}' | grep -v -i -E '^/c/windows|^$|not' | sort -u | while read -r dll; do cp "$dll" "$DEST/bin/"; done
cp "$IE1/plugin/ie1_mods.dll" "$DEST/bin/"

# licencias: el runner es una obra GPL-3.0-or-later (ndsrecomp + melonDS)
for f in LICENSE-GPL LICENSE THIRD_PARTY_ATTRIBUTION.md; do
    [ -f "$NDS/$f" ] && mkdir -p "$DEST/licencias" && cp "$NDS/$f" "$DEST/licencias/ndsrecomp-$f"
done
cat > "$DEST/licencias/FUENTES.txt" <<'TXT'
Source code / Codigo fuente
- This port / Este port: https://github.com/2002-source/InazumaElevenRecomp
  (runner-patches/ = GPL-3.0-or-later changes to the ndsrecomp runner;
   ndsrecomp.pin / recomp-ui.pin = exact upstream versions)
- ndsrecomp: https://github.com/RetroPortingToolKit/ndsrecomp
The nds_runner executable is a GPL-3.0-or-later combined work (ndsrecomp-LICENSE-GPL).
El ejecutable nds_runner es una obra combinada GPL-3.0-or-later (ndsrecomp-LICENSE-GPL).
TXT

echo "=== 2. BIOS libre (sin tu identidad Wi-Fi) ==="
cp -r "$NDS/bios/." "$DEST/bios/"
rm -f "$DEST/bios/generated-identity.bin" "$DEST/bios/"*state*.bin     # cada instalacion genera la suya

echo "=== 3. Configuracion minima del juego ==="
cp "$IE1/run/game.toml" "$DEST/datos/"
printf '# Un mod activo por linea, en orden (el ultimo gana)\n' > "$DEST/mods/mods.cfg"
# Mods: se copian los que NO llevan datos del juego (tu diseno, trucos...). Los que
# salen de las ROM (NPC entrenador, niveles de supertecnicas) los crea el preparador.
# Niveles de supertecnicas: va con lo que sale del IE2 (categorias, umbrales, cartel
# "Nv +" y marcas del nombre), asi nadie necesita la ROM del IE2. Los guiones de
# tecnica salen de la ROM del IE1 de cada persona: los rehace el preparador.
if [ -d "$IE1/mods/niveles_supertecnicas" ]; then
    mkdir -p "$DEST/mods/niveles_supertecnicas"
    ( cd "$IE1/mods/niveles_supertecnicas" && cp -r mod.txt parches.txt idioma "$DEST/mods/niveles_supertecnicas/" )
    echo "   mod 'niveles_supertecnicas' (sin guiones: los crea el preparador)"
fi
for m in "$IE1"/mods/*/; do
    n=$(basename "$m")
    case "$n" in npc_entrenador|niveles_supertecnicas|marca_prueba|voces_jp) continue;; esac
    if [ -d "$m/pk" ] || [ -d "$m/idioma" ] || [ -d "$m/data_iz" ] || [ -f "$m/parches.txt" ]; then
        echo "   (no se copia '$n': lleva datos del juego)"; continue
    fi
    mkdir -p "$DEST/mods/$n" && cp -r "$m." "$DEST/mods/$n/"
    echo "   mod '$n'"
done

echo "=== 4. Lanzador ==="
cp "$IE1/lanzador/lanzador.exe" "$DEST/Inazuma Eleven.exe"
ldd "$IE1/lanzador/lanzador.exe" | awk '{print $3}' | grep -v -i -E '^/c/windows|^$|not' | sort -u | while read -r dll; do cp -u "$dll" "$DEST/"; done

echo "=== 5. Herramientas (preparador y Python portable) ==="
for f in preparar.py extraer_rom.py crear_paquete_idioma.py analizar_cadenas.py comparar_arm9.py \
         comparar_codigo.py crear_parche_textos.py crear_npc_entrenador.py crear_mod_niveles.py crear_marca_prueba.py; do
    cp "$S/$f" "$DEST/herramientas/scripts/"
done
# rangos de funciones del ARM9 (solo direcciones y tamanos, sin codigo del juego):
# analizar_cadenas.py los usa para no confundir codigo con textos
grep -o 'NdsStaticValidation[^;]*{0x[0-9A-Fa-f]*u, *[0-9]*u,' "$IE1/generated/arm9_main_dispatch.c" \
    > "$DEST/herramientas/trabajo/generated/arm9_main_dispatch.c" || true
if [ ! -f "$PY_ZIP" ]; then
    echo "   descargando Python $PY_VER portable (una sola vez)..."
    curl -L -o "$PY_ZIP" "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-embed-amd64.zip"
fi
mkdir -p "$DEST/herramientas/python"
unzip -q "$PY_ZIP" -d "$DEST/herramientas/python"
# el Python portable no busca modulos junto a los scripts: se le anade la carpeta
PTH=$(ls "$DEST/herramientas/python/"python3*._pth | head -1)
printf '../scripts\n' >> "$PTH"

cat > "$DEST/PREPARAR - arrastra aqui tus ROM.bat" <<'EOF'
@echo off
rem ES: Arrastra encima de este archivo tus ROM de Inazuma Eleven (puedes soltar varias a la vez)
rem EN: Drag and drop your Inazuma Eleven ROMs onto this file (you can drop several at once)
"%~dp0herramientas\python\python.exe" "%~dp0herramientas\scripts\preparar.py" %*
EOF
cat > "$DEST/Inazuma Eleven.bat" <<'EOF'
@echo off
rem Inazuma Eleven (port) - jugar directamente, sin el lanzador
set "RAIZ=%~dp0"
set "PATH=%RAIZ%bin;%PATH%"
set NDS_FAST_CARD=1
set "IE1_IDIOMAS_DIR=%RAIZ%idiomas"
set "IE1_MODS_DIR=%RAIZ%mods"
cd /d "%RAIZ%datos"
if not exist "%RAIZ%rom\ie1_eur.nds" (
  echo ES: Falta la ROM. Arrastra tu ROM sobre "PREPARAR - arrastra aqui tus ROM.bat".
  echo EN: The ROM is missing. Drag your ROM onto "PREPARAR - arrastra aqui tus ROM.bat".
  pause & exit /b
)
"%RAIZ%bin\nds_runner.exe" "%RAIZ%bios" ^
  --interactive --freebios --generated-firmware --boot direct ^
  --firmware-state-path firmware_state.bin ^
  --save-path ie1_eur.sav --savestate-dir estados ^
  --virtual-stylus off --config game.toml --performance-governor stage1 ^
  --execution-model performance --diagnostics off --no-coverage-manifest ^
  --rom "%RAIZ%rom\ie1_eur.nds" > ultima_sesion.log 2>&1
EOF

# Instrucciones: en la raiz y en mods\, en ingles (README) y en espanol (LEEME)
T=$S/textos_port
[ -f "$T/README.txt" ] || { echo "Faltan los textos del port en $T"; exit 1; }
cp "$T/README.txt" "$T/LEEME.txt" "$DEST/"
cp "$T/MODS_README.txt" "$DEST/mods/README.txt"
cp "$T/MODS_LEEME.txt" "$DEST/mods/LEEME.txt"
for f in "$DEST/README.txt" "$DEST/LEEME.txt" "$DEST/mods/README.txt" "$DEST/mods/LEEME.txt"; do
    sed -i 's/\r$//; s/$/\r/' "$f"
    printf '\xEF\xBB\xBF' | cat - "$f" > "$f.tmp" && mv "$f.tmp" "$f"      # UTF-8 con BOM (acentos en el Bloc de notas)
done
for f in "$DEST/PREPARAR - arrastra aqui tus ROM.bat" "$DEST/Inazuma Eleven.bat"; do sed -i 's/$/\r/' "$f"; done

echo "=== 6. Comprobacion: nada personal ni del juego ==="
fallos=0
for patron in '*.nds' '*.sav' '*.nss' 'controles.cfg' 'lanzador.cfg' 'ie1_menu.cfg' 'idiomas.cfg' \
              'firmware_state.bin' 'generated-identity.bin' 'ultima_sesion.log' '*.pkb' '*.pac_'; do
    if find "$DEST" -name "$patron" -not -path '*/python/*' -not -path '*/niveles_supertecnicas/*' | grep -q .; then
        echo "   ATENCION: hay archivos '$patron' en la distribucion"; fallos=1
    fi
done
[ $fallos -eq 0 ] && echo "   ok: sin ROM, sin partida y sin ajustes (solo los graficos del IE2 del mod de niveles)"

echo "=== 7. Archivo .zip ==="
( cd "$(dirname "$DEST")" && rm -f "$(basename "$DEST").zip" && \
  powershell.exe -NoProfile -Command "Compress-Archive -Path '$(basename "$DEST")' -DestinationPath '$(basename "$DEST").zip'" )
du -sh "$DEST" | awk '{print "Tamano de la carpeta: " $1}'
echo "Listo: $DEST  (y el .zip al lado)"
