#!/usr/bin/env bash
# ============================================================
#  Wi-Fi local ENTRE DOS PC (misma red de casa, o por internet con una red
#  local virtual como Radmin VPN o ZeroTier).
#     Jugador 1 (anfitrion):  bash scripts/jugar_red.sh 1 IP_DEL_OTRO_PC
#     Jugador 2 (invitado):   bash scripts/jugar_red.sh 2 IP_DEL_OTRO_PC
#  Cada uno pone la IP del OTRO PC. El jugador 1 escucha en el puerto 7030 y
#  el 2 en el 7031 (UDP): la primera vez Windows pedira permiso para el
#  cortafuegos -> "Permitir" (redes privadas).
#  Puerto base: IE1_PUERTO_WIFI (por defecto 7030; los dos PC iguales).
# ============================================================
JUG="${1:-}"; IP="${2:-}"
if [ "$JUG" != "1" ] && [ "$JUG" != "2" ] || [ -z "$IP" ]; then
    echo "Uso: bash scripts/jugar_red.sh 1|2 IP_DEL_OTRO_PC"; exit 1
fi
BASE="${IE1_PUERTO_WIFI:-7030}"
YO=$((JUG - 1))                    # indice de instancia: 0 o 1
OTRO=$((1 - YO))
export IE1_WIFI_PEERS="$IP:$((BASE + OTRO))"
echo "Jugador $JUG: escucho en el puerto $((BASE + YO)) y envio a $IE1_WIFI_PEERS"
exec bash /c/dev/ie1recomp/scripts/jugar.sh --execution-model performance \
    --instance-index "$YO" --local-wireless on --local-wireless-port "$BASE" "${@:3}"
