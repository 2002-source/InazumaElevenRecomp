#!/usr/bin/env bash
# ============================================================
#  Crea la carpeta del proyecto del Inazuma Eleven 2 (Firestorm / Tormenta
#  de Fuego, EUR) con la misma estructura que la del 1:
#     D:\Inazuma Eleven 2 Port\dev\ie2recomp   (acceso: C:\dev\ie2recomp)
#  En la terminal "MSYS2 CLANG64":
#     bash /c/dev/ie1recomp/scripts/crear_proyecto_ie2.sh "/c/Users/admin/Downloads/6010 - Inazuma Eleven 2 - Firestorm (E).nds"
#  - Copia la ROM a games/ie2_ff_eur.nds y comprueba su huella.
#  - Copia los scripts generales del 1 adaptando rutas y nombres; los que son
#    propios del 1 (mods, entrenamiento, NPC, HLE con direcciones del 1,
#    parches del runner) van a scripts/_ie1_referencia/ solo como consulta.
#  El runner (ndsrecomp) es el MISMO para los dos juegos: no se toca.
# ============================================================
set -euo pipefail
ROM_ORIGEN="${1:-}"
SHA_ESPERADO=e4fc850fb5e574d5cce7b33ea333a4851eaea061
RAIZ_D="/d/Inazuma Eleven 2 Port/dev/ie2recomp"
IE1=/c/dev/ie1recomp
[ -n "$ROM_ORIGEN" ] && [ -f "$ROM_ORIGEN" ] || { echo "Uso: bash crear_proyecto_ie2.sh RUTA_DE_LA_ROM.nds"; exit 1; }

echo "=== 1. Carpetas ==="
mkdir -p "$RAIZ_D"/{games,scripts/_ie1_referencia,run/estados,idiomas,lanzador,images,configs}
if [ ! -e /c/dev/ie2recomp ]; then
    # (con PowerShell: cmd/mklink se lia con las barras al llamarlo desde MSYS2)
    powershell.exe -NoProfile -Command "New-Item -ItemType Junction -Path 'C:\\dev\\ie2recomp' -Target 'D:\\Inazuma Eleven 2 Port\\dev\\ie2recomp' | Out-Null"
    echo "   acceso C:\\dev\\ie2recomp -> D:\\Inazuma Eleven 2 Port\\dev\\ie2recomp"
fi
IE2=/c/dev/ie2recomp

echo "=== 2. ROM base ==="
SHA=$(sha1sum "$ROM_ORIGEN" | cut -d' ' -f1)
[ "$SHA" = "$SHA_ESPERADO" ] || { echo "La ROM no es la esperada (SHA-1 $SHA)"; exit 1; }
[ -f "$IE2/games/ie2_ff_eur.nds" ] || cp "$ROM_ORIGEN" "$IE2/games/ie2_ff_eur.nds"
echo "   games/ie2_ff_eur.nds  (Inazuma Eleven 2 Firestorm EUR, BEEP, SHA-1 $SHA)"

echo "=== 3. Scripts ==="
# propios del 1: solo como referencia
PROPIOS='parche_|integrar_|ie1_mods|compilar_mods|entrenamiento|npc_|crear_npc|preparar_entrenamiento|parche_overlay|ie1_ar|trucos|comparar_roms|extraer_codigo_es'
for f in "$IE1"/scripts/*; do
    [ -f "$f" ] || continue
    n=$(basename "$f")
    if echo "$n" | grep -q -E "$PROPIOS"; then
        cp -u "$f" "$IE2/scripts/_ie1_referencia/"
        continue
    fi
    # adaptar rutas y nombres del 1 al 2
    sed -e 's#ie1recomp#ie2recomp#g' -e 's#Inazuma Eleven 1 Port#Inazuma Eleven 2 Port#g' \
        -e 's#ie1_eur\.nds#ie2_ff_eur.nds#g' -e 's#ie1_eur\.sav#ie2_ff_eur.sav#g' \
        -e 's#Juegos/Inazuma Eleven 1#Juegos/Inazuma Eleven 2#g' \
        -e 's#d55169c0b93d26b4037379d3b81a61b5404945e5#e4fc850fb5e574d5cce7b33ea333a4851eaea061#g' \
        "$f" > "$IE2/scripts/$n"
done
# lanzador: mismas fuentes que el del 1
cp -u "$IE1"/lanzador/*.cpp "$IE1"/lanzador/*.hpp "$IE2/lanzador/" 2>/dev/null || true
echo "   $(ls "$IE2/scripts" | wc -l) scripts generales adaptados; propios del 1 en scripts/_ie1_referencia/"

echo "=== 4. Configuracion inicial ==="
[ -f "$IE2/run/idiomas.cfg" ] || printf 'textos=en\nvoces=en\n' > "$IE2/run/idiomas.cfg"
cat > "$IE2/LEEME.txt" <<'TXT'
Recomp de Inazuma Eleven 2 - Firestorm (EUR)
  games/ie2_ff_eur.nds   ROM base (SHA-1 e4fc850fb5e574d5cce7b33ea333a4851eaea061)
  scripts/               scripts generales (adaptados del 1)
  scripts/_ie1_referencia/  scripts propios del 1 (solo para consultar)
  run/                   partida, estados, configuracion y logs
  idiomas/               paquetes de idioma (de otras ROM de Firestorm/Tormenta de Fuego)
El runner (C:/dev/ndsrecomp) es compartido con el Inazuma Eleven 1.
TXT
echo
echo "Listo: $IE2"
echo "Siguiente paso: extraer la ROM (lo indicara Claude con los scripts ya adaptados)."
