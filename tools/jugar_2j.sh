#!/usr/bin/env bash
# ============================================================
#  Prueba de Wi-Fi local: DOS copias del juego en este PC, conectadas como si
#  fueran dos DS cerca (modo "inalambrico local" del runner, por localhost).
#     bash /c/dev/ie1recomp/scripts/jugar_2j.sh
#  - Jugador 1: carpeta run/  (tu partida de siempre)
#  - Jugador 2: carpeta run2/ (la primera vez, una COPIA de tu partida)
#  Cada ventana se maneja cuando esta activa (clic en ella). En las dos, entra
#  en el modo de conexion inalambrica del juego.
#  Registros: run/ultima_sesion_j1.log y run2/ultima_sesion_j2.log
#  Puerto del enlace local: IE1_PUERTO_WIFI (por defecto 7030)
#  Probar el modo "entre PC" en este mismo PC (con la IP de red de este PC):
#     IE1_RED_IP=192.168.1.35 bash scripts/jugar_2j.sh
#  Cobertura (para recompilar el codigo del modo inalambrico, que ahora va
#  interpretado y lento):  IE1_COBERTURA=1 bash scripts/jugar_2j.sh
# ============================================================
export IE1_IDIOMAS_DIR="${IE1_IDIOMAS_DIR:-C:/dev/ie1recomp/idiomas}"
export IE1_MODS_DIR="${IE1_MODS_DIR:-C:/dev/ie1recomp/mods}"
RUNNER="${RUNNER_EXE:-/c/dev/ndsrecomp/runner/build-mingw/nds_runner.exe}"
ROM=/c/dev/ie1recomp/games/ie1_eur.nds
PUERTO="${IE1_PUERTO_WIFI:-7030}"
R1=/c/dev/ie1recomp/run
R2=/c/dev/ie1recomp/run2
COBERTURA="--no-coverage-manifest"
[ "${IE1_COBERTURA:-0}" = "1" ] && COBERTURA="" && echo "Recogiendo cobertura (jugador 1 y 2) para la proxima ronda."

# carpeta del jugador 2: copia de la configuracion y, la primera vez, de la partida
mkdir -p "$R1/estados" "$R2/estados"
for f in game.toml idiomas.cfg ie1_menu.cfg controles.cfg; do
    [ -f "$R1/$f" ] && cp -u "$R1/$f" "$R2/"
done
if [ ! -f "$R2/ie1_eur.sav" ] && [ -f "$R1/ie1_eur.sav" ]; then
    cp "$R1/ie1_eur.sav" "$R2/ie1_eur.sav"
    echo "Jugador 2: copia de tu partida en run2/ie1_eur.sav"
fi

arrancar() {   # $1 carpeta, $2 indice de instancia, $3 puerto de depuracion, $4 registro
    local pares=""
    [ -n "${IE1_RED_IP:-}" ] && pares="$IE1_RED_IP:$((PUERTO + 1 - $2))"   # el otro jugador, por la IP de red
    ( cd "$1" && IE1_WIFI_PEERS="$pares" SDL_RENDER_DRIVER=direct3d11 NDS_FAST_CARD=1 "$RUNNER" /c/dev/ndsrecomp/bios \
        --interactive --freebios --generated-firmware --boot direct \
        --firmware-state-path firmware_state.bin \
        --save-path ie1_eur.sav --savestate-dir estados \
        --virtual-stylus off --config game.toml --performance-governor stage1 \
        --execution-model performance $COBERTURA \
        --instance-index "$2" --port "$3" \
        --local-wireless on --local-wireless-port "$PUERTO" \
        --rom "$ROM" > "$4" 2>&1 ) &
}
echo "Arrancando jugador 1 (instancia 0) y jugador 2 (instancia 1), enlace local en el puerto $PUERTO..."
arrancar "$R1" 0 19842 "$R1/ultima_sesion_j1.log"
sleep 3
arrancar "$R2" 1 19843 "$R2/ultima_sesion_j2.log"
wait
# la cobertura del jugador 2 se junta con la del 1 (ronda.sh la busca en run/)
for f in "$R2"/*coverage*.json; do [ -f "$f" ] && mv "$f" "$R1/" && echo "Cobertura del jugador 2 movida a run/: $(basename "$f")"; done
echo "Cerrados. Registros: run/ultima_sesion_j1.log y run2/ultima_sesion_j2.log"
