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
#  Resultado: D:\Juegos\Inazuma Eleven Recomp v1.1\  y un .zip al lado.
#  Las instrucciones salen de scripts/textos_port/: README (ingles), LEEME
#  (espanol), LISEZMOI (frances), LIESMICH (aleman), LEGGIMI (italiano) y los
#  de mods (MODS_*.txt).
#  (otra carpeta: DESTINO="/e/otra" bash scripts/crear_distribucion.sh)
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
NDS=/c/dev/ndsrecomp
S=$IE1/scripts
VERSION=1.1
DEST="${DESTINO:-/d/Juegos/Inazuma Eleven Recomp v$VERSION}"
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
# (Mecanicas IE2: niveles + tiro y bloqueos + talentos; tiro.cfg y talentos.cfg los activan)
if [ -d "$IE1/mods/mecanicas_ie2" ]; then
    mkdir -p "$DEST/mods/mecanicas_ie2"
    ( cd "$IE1/mods/mecanicas_ie2" && cp -r mod.txt parches.txt idioma tiro.cfg talentos.cfg capitan.cfg exp_x2.cfg "$DEST/mods/mecanicas_ie2/" )
    echo "   mod 'mecanicas_ie2' (sin guiones: los crea el preparador)"
fi
# Ojeo instantaneo: su ficha y ojeo.cfg; los guiones de Celia y Nelly los crea el preparador
if [ -d "$IE1/mods/ojeo_instantaneo" ]; then
    mkdir -p "$DEST/mods/ojeo_instantaneo"
    ( cd "$IE1/mods/ojeo_instantaneo" && cp mod.txt ojeo.cfg "$DEST/mods/ojeo_instantaneo/" )
    echo "   mod 'ojeo_instantaneo' (sin guiones: los crea el preparador)"
fi
# Entrenamiento libre: el menu (fondos y ficha); el NPC entrenador (pk/) lo crea el preparador
if [ -d "$IE1/mods/entrenamiento_libre" ]; then
    mkdir -p "$DEST/mods/entrenamiento_libre"
    # fondos del menu por idioma (la pantalla de arriba sale del juego, ya no se copia fondo_ficha)
    ( cd "$IE1/mods/entrenamiento_libre" && cp mod.txt fondo_entrenamiento_*.argb "$DEST/mods/entrenamiento_libre/" )
    echo "   mod 'entrenamiento_libre' (sin el NPC: lo crea el preparador)"
fi
for m in "$IE1"/mods/*/; do
    n=$(basename "$m")
    # los ya copiados arriba, los antiguos (ahora dentro de otros) y los de prueba
    case "$n" in entrenamiento_libre|npc_entrenador|mecanicas_ie2|niveles_supertecnicas|tiro_ie2|talentos_ie2|ojeo_instantaneo|ojeo_ie2|marca_prueba|truco_*|*prueba*|voces_jp) continue;; esac
    if [ -d "$m/pk" ] || [ -d "$m/idioma" ] || [ -d "$m/data_iz" ] || [ -f "$m/parches.txt" ]; then
        echo "   (no se copia '$n': lleva datos del juego)"; continue
    fi
    mkdir -p "$DEST/mods/$n" && cp -r "$m." "$DEST/mods/$n/"
    echo "   mod '$n'"
done

# fichas de los mods (mod.txt) tambien en frances, aleman e italiano
if [ -f "$S/traducir_mods.py" ]; then
    python "$S/traducir_mods.py" "$DEST/mods" | sed 's/^/   /'
fi

echo "=== 4. Lanzador ==="
cp "$IE1/lanzador/lanzador.exe" "$DEST/Inazuma Eleven.exe"
ldd "$IE1/lanzador/lanzador.exe" | awk '{print $3}' | grep -v -i -E '^/c/windows|^$|not' | sort -u | while read -r dll; do cp -u "$dll" "$DEST/"; done

echo "=== 5. Herramientas (preparador y Python portable) ==="
for f in preparar.py extraer_rom.py crear_paquete_idioma.py analizar_cadenas.py comparar_arm9.py \
         comparar_codigo.py crear_parche_textos.py crear_npc_entrenador.py crear_mod_niveles.py crear_marca_prueba.py \
         crear_mod_ojeo.py crear_mod_voces_jp.py ampliar_cadenas.py revisar_roms_idiomas.py listar_cambios_mod.py; do
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

# Instrucciones: en la raiz y en mods\, en los cinco idiomas
T=$S/textos_port
for f in README LEEME LISEZMOI LIESMICH LEGGIMI; do
    [ -f "$T/$f.txt" ] && [ -f "$T/MODS_$f.txt" ] || { echo "Faltan los textos del port ($f) en $T"; exit 1; }
    cp "$T/$f.txt" "$DEST/$f.txt"
    cp "$T/MODS_$f.txt" "$DEST/mods/$f.txt"
    for g in "$DEST/$f.txt" "$DEST/mods/$f.txt"; do
        sed -i 's/\r$//; s/$/\r/' "$g"
        printf '\xEF\xBB\xBF' | cat - "$g" > "$g.tmp" && mv "$g.tmp" "$g"      # UTF-8 con BOM (acentos en el Bloc de notas)
    done
done
for f in "$DEST/PREPARAR - arrastra aqui tus ROM.bat" "$DEST/Inazuma Eleven.bat"; do sed -i 's/$/\r/' "$f"; done

echo "=== 6. Comprobacion: nada personal ni del juego ==="
fallos=0
for patron in '*.nds' '*.sav' '*.nss' 'controles.cfg' 'lanzador.cfg' 'ie1_menu.cfg' 'idiomas.cfg' \
              'firmware_state.bin' 'generated-identity.bin' 'ultima_sesion.log' '*.pkb' '*.pac_'; do
    if find "$DEST" -name "$patron" -not -path '*/python/*' -not -path '*/mecanicas_ie2/*' | grep -q .; then
        echo "   ATENCION: hay archivos '$patron' en la distribucion"; fallos=1
    fi
done
[ $fallos -eq 0 ] && echo "   ok: sin ROM, sin partida y sin ajustes (solo los graficos del IE2 del mod Mecanicas IE2)"

echo "=== 7. Archivo .zip ==="
( cd "$(dirname "$DEST")" && rm -f "$(basename "$DEST").zip" && \
  powershell.exe -NoProfile -Command "Compress-Archive -Path '$(basename "$DEST")' -DestinationPath '$(basename "$DEST").zip'" )
du -sh "$DEST" | awk '{print "Tamano de la carpeta: " $1}'
ls "$DEST"/mods | sed 's/^/   mods: /'
echo "Listo: $DEST  (y el .zip al lado)"
