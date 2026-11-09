#!/usr/bin/env bash
# ============================================================
#  Monta la carpeta del repositorio de GitHub con el codigo PROPIO del port
#  (sin ROM, sin codigo generado, sin datos del juego, sin tu configuracion).
#     bash /c/dev/ie1recomp/scripts/crear_repositorio.sh
#  Destino: D:\Inazuma Eleven 1 Port\Archivos de GitHub
#  (otro: REPO="/e/otra" bash scripts/crear_repositorio.sh)
#  Los textos fijos (README, LICENSE, pins, docs) salen de scripts/github/.
# ============================================================
set -euo pipefail
IE1=/c/dev/ie1recomp
NDS=/c/dev/ndsrecomp
UI=/c/dev/recomp-ui
S=$IE1/scripts
G=$S/github
REPO="${REPO:-/d/Inazuma Eleven 1 Port/Archivos de GitHub}"
[ -f "$G/README.md" ] || { echo "Faltan los textos del repositorio en $G"; exit 1; }

echo "=== Carpeta: $REPO ==="
mkdir -p "$REPO"
# se rehace todo menos la carpeta .git (para poder usar git en ella)
find "$REPO" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir -p "$REPO"/{tools,plugin,launcher,runner-patches,mods,config,coverage,packaging,docs}

echo "=== 1. Textos fijos ==="
cp "$G/README.md" "$G/README.es.md" "$G/LICENSE" "$G/ndsrecomp.pin" "$G/recomp-ui.pin" "$G/.gitignore" "$REPO/"
cp -r "$G/docs/." "$REPO/docs/"
cp "$G/runner-patches/LICENSE.md" "$REPO/runner-patches/"

echo "=== 2. Herramientas, parches del runner y complemento ==="
for f in "$S"/*.py "$S"/*.sh "$S"/*.bat; do
    [ -f "$f" ] || continue
    n=$(basename "$f")
    case "$n" in
        *" ("*|*"(1)"*) echo "   (omitido, copia duplicada de una descarga: $n)"; continue;;
        *IE3*|*ie3*|*f133*|*F133*) echo "   (omitido, es de otro proyecto: $n)"; continue;;
    esac
    case "$n" in
        parche_*|integrar_*)                  cp "$f" "$REPO/runner-patches/";;
        crear_distribucion.sh|crear_repositorio.sh) cp "$f" "$REPO/packaging/";;
        *)                                    cp "$f" "$REPO/tools/";;
    esac
done
for f in ie1_mods.cpp ie1_ar.hpp ie1_fuente.inc; do
    [ -f "$S/$f" ] && cp "$S/$f" "$REPO/plugin/"
done
cp -r "$S/textos_port" "$REPO/packaging/" 2>/dev/null || true

echo "=== 3. Cambios exactos del runner (diff contra las versiones fijadas) ==="
diff_completo() {   # $1 repositorio git, $2 salida: cambios + archivos nuevos (sin tocar su indice)
    local idx; idx=$(mktemp)
    cp "$1/.git/index" "$idx"
    local fuera=(':!*build*' ':!*.bin' ':!*.nds' ':!*.sav' ':!*.nss' ':!*.log' ':!*.json' ':!*.jsonl' ':!*generated*')
    GIT_INDEX_FILE="$idx" git -C "$1" add -A -N -- . "${fuera[@]}" 2>/dev/null || true
    GIT_INDEX_FILE="$idx" git -C "$1" diff --binary -- . "${fuera[@]}" > "$2"
    rm -f "$idx"
    echo "   $(basename "$2"): $(grep -c '^diff --git' "$2") archivos"
}
diff_completo "$NDS" "$REPO/runner-patches/ndsrecomp.diff"
[ -d "$UI/.git" ] && diff_completo "$UI" "$REPO/runner-patches/recomp-ui.diff"

echo "=== 4. Lanzador, mods propios, configuracion y coberturas ==="
cp "$IE1"/lanzador/lanzador.cpp "$IE1"/lanzador/lanzador_ui.hpp "$REPO/launcher/"
if [ -d "$IE1/mods/entrenamiento_libre" ]; then
    mkdir -p "$REPO/mods/entrenamiento_libre"
    cp "$IE1"/mods/entrenamiento_libre/mod.txt "$IE1"/mods/entrenamiento_libre/*.argb "$REPO/mods/entrenamiento_libre/" 2>/dev/null || true
fi
# del mod de niveles solo su mod.txt (los graficos y guiones salen de las ROM)
[ -f "$IE1/mods/niveles_supertecnicas/mod.txt" ] && mkdir -p "$REPO/mods/niveles_supertecnicas" && \
    cp "$IE1/mods/niveles_supertecnicas/mod.txt" "$REPO/mods/niveles_supertecnicas/"
cp "$IE1"/configs/*.toml "$REPO/config/" 2>/dev/null || true
cp "$IE1/run/game.toml" "$REPO/config/"
cp "$IE1"/run/*coverage*.json "$REPO/coverage/" 2>/dev/null || true
echo "   $(ls "$REPO/coverage" | wc -l) archivos de cobertura (solo direcciones)"

echo "=== 5. Comprobacion: nada del juego ni personal ==="
fallos=0
for patron in '*.nds' '*.sav' '*.nss' '*.pkb' '*.pkh' '*.pac_' '*.SAD' '*.NFTR' '*.exe' '*.dll' \
              'controles.cfg' 'lanzador.cfg' 'ie1_menu.cfg' 'idiomas.cfg' 'firmware_state.bin' 'generated-identity.bin'; do
    if find "$REPO" -path "$REPO/.git" -prune -o -name "$patron" -print | grep -q .; then
        echo "   ATENCION: hay archivos '$patron'"; fallos=1
    fi
done
# el diff del runner no debe llevar codigo generado de la ROM
if grep -q -E '^\+\+\+ b/.*(generated|_dispatch\.c|arm9_main|arm7_main)' "$REPO/runner-patches/ndsrecomp.diff"; then
    echo "   ATENCION: ndsrecomp.diff incluye codigo generado"; fallos=1
fi
[ $fallos -eq 0 ] && echo "   ok"
du -sh "$REPO" | awk '{print "Tamano: " $1}'
echo
echo "Listo. Para subirlo (la primera vez), en esa carpeta:"
echo "   git init -b main && git add . && git commit -m \"InazumaElevenRecomp v1.0\""
echo "   git remote add origin https://github.com/2002-source/InazumaElevenRecomp.git && git push -u origin main"
