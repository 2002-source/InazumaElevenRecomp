#!/usr/bin/env python3
"""
Titulo de la ventana del juego: "Inazuma Eleven Recomp - 59.9 FPS - v1.1"
(antes "ndsrecomp firmware preview - 59.9 FPS - Gov S1").

Toca runner/src/frontend.cpp. Se puede ejecutar varias veces: si ya estaba
cambiado, solo actualiza la version. Para otra version cambia VERSION abajo.
Despues: bash scripts/paso_mingw.sh
"""
import re, sys

FRONTEND = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
VERSION = "v1.1"
NOMBRE = "Inazuma Eleven Recomp"
MARCA = "IE1_TITULO"

# (texto original, texto nuevo, obligatorio)
CAMBIOS = [
    # titulo al crear la ventana (antes del primer recuento de FPS)
    ('''        presentation.separate ? "ndsrecomp - Top Screen"
                               : "ndsrecomp firmware preview",''',
     '''        presentation.separate ? "%NOMBRE% - Top Screen"
                               : "%NOMBRE% - %VERSION%",  // IE1_TITULO''', True),
    ('''            "ndsrecomp - Bottom Screen",''',
     '''            "%NOMBRE% - Bottom Screen",  // IE1_TITULO''', False),
    # titulo con los FPS (cada segundo): la version en lugar del "Gov S1"
    ('''            const std::string top_title = !savestate_notice.empty()
                ? "ndsrecomp - " + savestate_notice
                : presentation.separate
                ? "ndsrecomp - Top Screen - " + fps_text + governor_text
                : "ndsrecomp firmware preview - " + fps_text +
                      governor_text;''',
     '''            (void)governor_text;  // IE1_TITULO: en el titulo va la version
            const std::string top_title = !savestate_notice.empty()
                ? "%NOMBRE% - " + savestate_notice
                : presentation.separate
                ? "%NOMBRE% - Top Screen - " + fps_text + " - %VERSION%"
                : "%NOMBRE% - " + fps_text + " - %VERSION%";''', True),
    ('''                    "ndsrecomp - Bottom Screen - " + fps_text +
                    governor_text;''',
     '''                    "%NOMBRE% - Bottom Screen - " + fps_text + " - %VERSION%";  // IE1_TITULO''', False),
]


def main():
    try:
        s = open(FRONTEND, encoding="utf-8", newline="").read()
    except OSError:
        sys.exit("No encuentro %s. No toco nada." % FRONTEND)
    nl = "\r\n" if "\r\n" in s else "\n"
    if MARCA in s:
        # ya cambiado: solo se pone la version actual
        n = len(re.findall(r'"%s - v[0-9][^"]*"' % re.escape(NOMBRE), s)) + \
            len(re.findall(r'" - v[0-9][^"]*"', s))
        s = re.sub(r'("%s - )v[0-9][^"]*(")' % re.escape(NOMBRE), r'\g<1>%s\2' % VERSION, s)
        s = re.sub(r'(" - )v[0-9][^"]*(")', r'\g<1>%s\2' % VERSION, s)
        open(FRONTEND, "w", encoding="utf-8", newline="").write(s)
        print("frontend.cpp: el titulo ya estaba cambiado; version puesta: %s (%d sitios)" % (VERSION, n))
        return
    for viejo, nuevo, obligatorio in CAMBIOS:
        v = viejo.replace("\n", nl)
        if s.count(v) != 1:
            if obligatorio:
                sys.exit("frontend.cpp no tiene la forma esperada (titulo de la ventana). No toco nada.")
            continue
    for viejo, nuevo, obligatorio in CAMBIOS:
        v = viejo.replace("\n", nl)
        if s.count(v) == 1:
            s = s.replace(v, nuevo.replace("%NOMBRE%", NOMBRE).replace("%VERSION%", VERSION).replace("\n", nl))
    open(FRONTEND, "w", encoding="utf-8", newline="").write(s)
    print('frontend.cpp: titulo de la ventana "%s - <FPS> - %s"' % (NOMBRE, VERSION))
    print("Compila el runner con: bash scripts/paso_mingw.sh")


if __name__ == "__main__":
    main()
