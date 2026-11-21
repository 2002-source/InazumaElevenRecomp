#!/usr/bin/env python3
"""
Junta los mods de las mecanicas del IE2 en uno solo, "Mecanicas IE2" (mods/mecanicas_ie2):
  - niveles_supertecnicas: las supertecnicas suben de nivel (todos sus archivos: parches.txt,
    guiones de los carteles, graficos de las marcas...)
  - tiro_ie2: boton de tiro, tiro largo, area azul, marcas T/L y B, bloqueos (tiro.cfg)
  - talentos_ie2: talentos en los partidos (talentos.cfg)
  - Mark libre: con la historia terminada, Mark se puede quitar del equipo (capitan.cfg)
  - EXP x2: en los encuentros, ganar por 5 o mas goles sin encajar dobla la EXP (exp_x2.cfg)
Despues borra las tres carpetas y cambia mods.cfg: donde estaba el primero de los tres pone
mecanicas_ie2 y quita los otros dos. El panel de valor (valor_escenas) sigue aparte.

Uso (desde C:/dev/ie1recomp):
   python scripts/crear_mod_mecanicas_ie2.py
   (opcional: --mods RUTA/mods, por defecto C:/dev/ie1recomp/mods)
Se puede ejecutar otra vez sin problema (si las carpetas viejas ya no estan, solo
actualiza la ficha y mods.cfg).
"""
import argparse
import os
import shutil
import sys

NUEVO = "mecanicas_ie2"
VIEJOS = ["niveles_supertecnicas", "tiro_ie2", "talentos_ie2"]

FICHA = {
    "nombre": "Mecanicas IE2",
    "nombre_en": "IE2 mechanics",
    "descripcion": "Trae a los partidos las mecanicas de Inazuma Eleven 2: las supertecnicas suben de nivel con "
                   "el uso (aviso Nv + y su marca junto al nombre); boton de tiro en la pantalla tactil, tiros "
                   "largos desde fuera del area con su marca y el area de tiro azul; bloqueos de tiro con "
                   "tecnicas de defensa o de tiro (marca B); y los talentos (Ahorro, Ultratecnica...) con su "
                   "efecto en el partido. Usa el propio codigo del juego, que lo tenia sin activar; la partida "
                   "guardada no cambia, salvo los usos de cada tecnica, que el juego ya guardaba. "
                   "Y como en el IE2, al terminar el juego Mark deja de ser fijo y se puede quitar del equipo. "
                   "Y en los encuentros, si ganas por 5 o más goles sin encajar ninguno, la experiencia se dobla.",
    "descripcion_en": "Brings Inazuma Eleven 2's mechanics to matches: special moves level up with use (Lv + "
                      "notice and their mark next to the name); a shoot button on the touch screen, long shots "
                      "from outside the box with their mark and the blue shooting area; shot blocks with block "
                      "or shoot moves (B mark); and talents (Saving, Ultra Moves...) with their effect in "
                      "matches. It uses the game's own code, which was switched off; your save file does not "
                      "change, except for each move's use count, which the game already saved. "
                      "And like in IE2, once you finish the game Mark is no longer fixed and can be removed from the team. "
                      "And in random encounters, winning by 5 or more goals without conceding doubles the experience.",
    "desbloqueo": "Siempre activo: se nota en cuanto empieza un partido.",
    "desbloqueo_en": "Always on: you notice it as soon as a match starts.",
    "nombre_fr": "Mecaniques IE2",
    "descripcion_fr": "Apporte aux matchs les mécaniques d'Inazuma Eleven 2 : les techniques montent de niveau "
                      "à l'usage (avis Niv + et leur marque à côté du nom) ; bouton de tir sur l'écran tactile, "
                      "tirs lointains hors de la surface avec leur marque et la zone de tir bleue ; blocages de "
                      "tir avec des techniques de défense ou de tir (marque B) ; et les talents (Économies, "
                      "Super techniques...) avec leur effet pendant le match. Il utilise le code du jeu lui-même, "
                      "qui était désactivé ; ta sauvegarde ne change pas, sauf le nombre d'utilisations de chaque "
                      "technique, que le jeu enregistrait déjà. "
                      "Et comme dans IE2, une fois le jeu terminé, Mark n'est plus fixe et peut quitter l'équipe. "
                      "Et dans les rencontres, gagner par 5 buts ou plus sans en encaisser double l'expérience.",
    "desbloqueo_fr": "Toujours actif : tu le remarques dès qu'un match commence.",
    "nombre_de": "IE2-Mechaniken",
    "descripcion_de": "Bringt die Mechaniken von Inazuma Eleven 2 in die Spiele: Spezialtechniken steigen durch "
                      "Benutzung im Level (Hinweis Lv + und ihr Zeichen neben dem Namen); Schuss-Taste auf dem "
                      "Touchscreen, Fernschüsse von außerhalb des Strafraums mit ihrem Zeichen und dem blauen "
                      "Schussbereich; Schussblocks mit Abwehr- oder Schusstechniken (Zeichen B); und die Talente "
                      "mit ihrer Wirkung im Spiel. Es nutzt den eigenen Code des Spiels, der abgeschaltet war; "
                      "dein Spielstand ändert sich nicht, außer der Zahl der Einsätze jeder Technik, die das "
                      "Spiel schon speicherte. Und wie in IE2 ist Mark nach dem Ende des Spiels nicht mehr fest und "
                      "kann aus dem Team genommen werden. Und bei Zufallsbegegnungen verdoppelt ein Sieg mit 5 oder mehr "
                      "Toren Unterschied ohne Gegentor die Erfahrung.",
    "desbloqueo_de": "Immer aktiv: Du merkst es, sobald ein Spiel beginnt.",
    "nombre_it": "Meccaniche IE2",
    "descripcion_it": "Porta nelle partite le meccaniche di Inazuma Eleven 2: le tecniche salgono di livello con "
                      "l'uso (avviso Liv + e il loro segno accanto al nome); pulsante di tiro sul touch screen, "
                      "tiri da lontano fuori area con il loro segno e l'area di tiro blu; blocchi dei tiri con "
                      "tecniche di difesa o di tiro (segno B); e i talenti con il loro effetto in partita. Usa il "
                      "codice del gioco stesso, che era disattivato; il salvataggio non cambia, tranne il numero "
                      "di usi di ogni tecnica, che il gioco già salvava. E come in IE2, finito il gioco Mark non è "
                      "più fisso e può uscire dalla squadra. E negli incontri, vincere con 5 o più gol di scarto senza "
                      "subirne raddoppia l'esperienza.",
    "desbloqueo_it": "Sempre attivo: lo noti appena inizia una partita.",
}

EXP_X2_CFG = "# EXP x2: en los encuentros, ganar por 5 o mas goles sin encajar dobla la EXP (como en el IE2)\n"
CAPITAN_CFG = "# Mark libre: con la historia terminada, Mark se puede quitar del equipo (como en el IE2)\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mods", default="C:/dev/ie1recomp/mods")
    a = ap.parse_args()
    mods = a.mods
    dest = os.path.join(mods, NUEVO)
    niveles = os.path.join(mods, "niveles_supertecnicas")
    if not os.path.isdir(niveles) and not os.path.exists(os.path.join(dest, "parches.txt")):
        sys.exit(f"No encuentro {niveles} (ni un {NUEVO} ya creado). Crea primero el mod de niveles con "
                 "scripts/crear_mod_niveles.py y vuelve a ejecutar este.")
    os.makedirs(dest, exist_ok=True)
    # 1) todo lo del mod de niveles (menos su ficha)
    if os.path.isdir(niveles):
        n = 0
        for raiz, _, archivos in os.walk(niveles):
            for f in archivos:
                origen = os.path.join(raiz, f)
                rel = os.path.relpath(origen, niveles)
                if rel == "mod.txt":
                    continue
                destino = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(origen, destino)
                n += 1
        print(f"Copiados {n} archivos del mod de niveles")
    # 2) tiro y bloqueos, y talentos: los activa el complemento con estos dos archivos
    open(os.path.join(dest, "tiro.cfg"), "w", encoding="utf-8").write("# boton de tiro, tiro largo, area azul, marcas y bloqueos (como el IE2)\n")
    open(os.path.join(dest, "talentos.cfg"), "w", encoding="utf-8").write("# talentos en los partidos (como el IE2)\n")
    open(os.path.join(dest, "capitan.cfg"), "w", encoding="utf-8").write(CAPITAN_CFG)
    open(os.path.join(dest, "exp_x2.cfg"), "w", encoding="utf-8").write(EXP_X2_CFG)
    # 3) ficha en los 5 idiomas
    open(os.path.join(dest, "mod.txt"), "w", encoding="utf-8").write("".join(f"{k}={v}\n" for k, v in FICHA.items()))
    # 4) mods.cfg: el nuevo en el sitio del primero de los viejos
    cfg = os.path.join(mods, "mods.cfg")
    lineas = open(cfg, encoding="utf-8").read().splitlines() if os.path.exists(cfg) else []
    nuevas, puesto = [], False
    for l in lineas:
        nombre = l.strip()
        if nombre in VIEJOS or nombre == NUEVO:
            if not puesto:
                nuevas.append(NUEVO)
                puesto = True
            continue
        nuevas.append(l)
    if not puesto:
        nuevas.append(NUEVO)
    open(cfg, "w", encoding="utf-8").write("\n".join(nuevas) + "\n")
    print(f"mods.cfg: {NUEVO} activo (y quitados {', '.join(VIEJOS)})")
    # 5) borrar las carpetas viejas
    for v in VIEJOS:
        p = os.path.join(mods, v)
        if os.path.isdir(p):
            shutil.rmtree(p)
            print(f"Borrada la carpeta {p}")
    print(f"Listo: {dest}")


if __name__ == "__main__":
    main()
