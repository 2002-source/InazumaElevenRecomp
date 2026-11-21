#!/usr/bin/env python3
"""
Esc > Sistema > Reiniciar con el lanzador (version 2): el juego se cierra
(guardando como al salir) dejando datos/reiniciar.marca, y el lanzador, que lo
esta esperando sin ensenarse, lo vuelve a abrir solo. Al arrancar otra vez lee el
idioma y los mods elegidos. No se encadenan procesos (antes cada reinicio abria
una copia nueva desde la anterior y al tercero el juego se cerraba).

El lanzador pone IE1_LANZADOR=1 al abrir el juego. Sin esa variable (por
ejemplo, jugando desde el .bat) Reiniciar sigue abriendo otra vez el juego.

Toca runner/src/ie1_idiomas.cpp (solo la funcion ie1_reiniciar_programa).
Sirve tanto si no estaba aplicado como si estaba la version 1 (la que volvia al
lanzador). Se puede ejecutar varias veces. Despues: bash scripts/paso_mingw.sh
(y bash scripts/paso_port.sh para el .zip).
"""
import sys

IDIOMAS = "C:/dev/ndsrecomp/runner/src/ie1_idiomas.cpp"
MARCA = "IE1_REINICIO_LANZADOR2"

NUEVA = '''extern "C" void ie1_reiniciar_programa() {  // IE1_REINICIO_LANZADOR2
    static bool hecho = false;
    if (hecho) return;
    hecho = true;
    // Abierto desde el lanzador (IE1_LANZADOR=1): el juego se cierra (guardando como al
    // salir) y deja reiniciar.marca; el lanzador lo vuelve a abrir solo, sin ensenarse.
    if (const char* l = std::getenv("IE1_LANZADOR"); l && *l == '1') {
        std::remove("reinicio.pid");
        if (std::FILE* m = std::fopen("reiniciar.marca", "wb")) { std::fputs("1\\n", m); std::fclose(m); }
        std::fprintf(stderr, "[menu] reiniciar: el lanzador vuelve a abrir el juego\\n");
        return;
    }
    // Sin lanzador (por ejemplo desde el .bat): se abre otra vez el mismo ejecutable.
    // Las variables que vinieron de idiomas.cfg se quitan, para que el proceso
    // nuevo vuelva a leer el archivo (por si el idioma se cambio en el menu).
    for (const char* v : g_desde_cfg) poner_env(v, "");
    std::atexit(relanzar);
    std::fprintf(stderr, "[menu] reiniciando el programa\\n");
}'''


def main():
    try:
        s = open(IDIOMAS, encoding="utf-8", newline="").read()
    except OSError:
        sys.exit("No encuentro %s. No toco nada." % IDIOMAS)
    if MARCA in s:
        print("ie1_idiomas.cpp: el reinicio con el lanzador (version 2) ya estaba puesto.")
        return
    cabecera = 'extern "C" void ie1_reiniciar_programa() {'
    ini = s.find(cabecera)
    fin_txt = 'std::fprintf(stderr, "[menu] reiniciando el programa\\n");'
    fin = s.find(fin_txt, ini) if ini >= 0 else -1
    cierre = s.find("}", fin) if fin >= 0 else -1
    if ini < 0 or fin < 0 or cierre < 0 or s.count(cabecera) != 1:
        sys.exit("ie1_idiomas.cpp no tiene la funcion ie1_reiniciar_programa esperada. No toco nada.")
    nl = "\r\n" if "\r\n" in s else "\n"
    s = s[:ini] + NUEVA.replace("\n", nl) + s[cierre + 1:]
    open(IDIOMAS, "w", encoding="utf-8", newline="").write(s)
    print("ie1_idiomas.cpp: Reiniciar ahora deja reiniciar.marca y el lanzador vuelve a abrir el juego.")
    print("Compila el runner con: bash scripts/paso_mingw.sh  (y paso_port.sh para el .zip)")


if __name__ == "__main__":
    main()
