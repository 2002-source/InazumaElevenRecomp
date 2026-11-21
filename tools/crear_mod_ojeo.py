#!/usr/bin/env python3
"""
Mod "Ojeo instantaneo" (mods/ojeo_instantaneo): junta los dos mods de ojeo en uno.
  - Lo del IE2 (antes mod ojeo_ie2): la busqueda de Celia o Nelly queda lista al momento,
    sin escenas, espera ni llamada; al volver a hablarles se ve la lista de candidatos.
    Son los guiones de Celia y Nelly (pk/eve), que salen de la ROM de cada persona.
  - Lo de antes (ojeo.cfg, en el complemento): si ya habia una busqueda en marcha (por
    ejemplo, en una partida guardada de antes), la llamada llega al momento.
Despues borra la carpeta del mod ojeo_ie2 y lo quita de mods.cfg (ojeo_instantaneo se
queda activo en su sitio). Se puede ejecutar otra vez sin problema.

Como funcionan los guiones (IE1_TRAZA=1):
  - La lista de candidatos NO se calcula al acabar el temporizador: se calcula al abrir
    la ventana de la lista. La llamada solo cambia el estado 4 ("buscando") a 2
    ("resultados listos"); las marcas que comprueba no las cambia nadie.
  - Algunas instrucciones del encargo son "expresiones" que otras leen (por ejemplo la
    duracion: 7001 tiempo = <instr 526> -> 7001 = <instr 528> ...). Quitarlas hace que el
    juego lea basura y se cuelgue.
Cambios en los guiones:
  - En cada encargo, "estado = 4" pasa a "estado = 2". El temporizador se registra igual,
    pero la llamada solo salta con el estado en 4, asi que no llega.
  - Celia: se quitan su despedida ("Alla voy!") y su paseo hasta la puerta, para que se
    quede en la caseta y se le pueda hablar al momento.
  - Nelly: solo el estado (sus animaciones van en bloques paralelos y no se tocan).
  - La parte de resultados queda como en el juego (dialogo y pregunta incluidos).

Uso (desde C:/dev/ie1recomp):
   python scripts/crear_mod_ojeo.py games/ie1_eur.nds
"""
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crear_npc_entrenador as C   # noqa: E402

GUIONES = {0x5C81A41: "Celia", 0x5C81A42: "Nelly"}
# variable de estado (2 = resultados listos, 4 = buscando) y una que el propio bloque pone
# a 0 (sirve de instruccion de relleno)
VARIABLES = {0x5C81A41: (65557, 65553), 0x5C81A42: (65563, 65558)}
# instrucciones de control (bloques, condiciones, hilos paralelos): nunca se quitan
CONTROL = {0x6001, 0x6002, 0x6008, 0x600C, 0x6012, 0x6013, 0x6014}
QUITAR_DIALOGO_RESULTADOS = False


def expresiones(ins):
    """Indices de instrucciones que son la "expresion" de otra. Un dato de tipo 4 en la
    instruccion k vale t: las instrucciones k+1 .. t-1 son su expresion (por ejemplo,
    7001 tiempo=<4,526> en 524: la 525 es el numero al azar). No se pueden quitar."""
    r = set()
    for k, x in enumerate(ins):
        if x.op:
            for i in range(x.argc):
                if x.tipo(i) == 4 and x.arg(i) > k:
                    r.update(range(k + 1, x.arg(i)))
    return r


def relleno(ins, var):
    for x in ins:
        if x.op == 0x7001 and x.argc == 2 and x.tipo(0) == 6 and x.arg(0) == var and x.tipo(1) == 1 and x.arg(1) == 0:
            return x
    raise SystemExit(f"No encontre la instruccion de relleno (7001 {var} 0).")


def quitar(ins, j, nop):
    i = ins[j].idx
    ins[j] = nop.copia()
    ins[j].idx = i


def modificar(gid, ins):
    estado, var_relleno = VARIABLES[gid]
    nop = relleno(ins, var_relleno)
    exprs = expresiones(ins)
    cambios = 0
    # 1) encargos: "estado = 4" -> 2, y fuera la escena (dialogo, Celia saliendo, el
    #    ayudante de Nelly entrando y saliendo). Se quita todo lo que hay en el bloque del
    #    encargo antes del estado, menos el control y las expresiones de lo que se queda.
    for k, x in enumerate(ins):
        if x.op != 0x4079:
            continue
        e = next((j for j in range(k - 1, max(k - 12, 0), -1)
                  if ins[j].op == 0x7001 and ins[j].argc == 2 and ins[j].tipo(0) == 6
                  and ins[j].arg(0) == estado and ins[j].tipo(1) == 1 and ins[j].arg(1) == 4), None)
        if e is None:
            print(f"   {GUIONES[gid]}: encargo en {k} sin 'estado = 4' cerca; se deja igual")
            continue
        ins[e].set(1, 2); cambios += 1
        ini = next((j for j in range(e - 1, max(e - 80, 0), -1)
                    if ins[j].op == 0x6001 and ins[j].argc == 2 and ins[j].arg(1) > k), None)
        quitadas = 0
        if ini is not None:
            # quitar una instruccion con expresion quita tambien su expresion
            libres = set()
            for j in range(ini + 1, e):
                y = ins[j]
                if y.op and y.op not in CONTROL and j not in exprs:
                    libres.add(j)
                    for i in range(y.argc):
                        if y.tipo(i) == 4 and y.arg(i) > j:
                            libres.update(range(j + 1, y.arg(i)))
            for j in sorted(libres):
                if ins[j].op and ins[j].op not in CONTROL and not (ins[j].op == 0x7001 and ins[j].raw == nop.raw):
                    quitar(ins, j, nop); cambios += 1; quitadas += 1
        print(f"   {GUIONES[gid]}: encargo ({k}) -> resultados listos al momento, {quitadas} instrucciones de escena quitadas")
    # 2) resultados (bloque "si estado == 2"): fuera "He encontrado..." y "Quieres verlos?".
    #    DESACTIVADO: el recuadro del dialogo se queda vacio y queda raro; los dialogos de
    #    los resultados se quedan como en el juego (QUITAR_DIALOGO_RESULTADOS = True para probarlo).
    for k, x in enumerate(ins if QUITAR_DIALOGO_RESULTADOS else []):
        if x.op != 0x6012 or k + 1 >= len(ins):
            continue
        c = ins[k + 1]
        if not (c.op == 0x7003 and c.argc == 2 and c.arg(0) == estado and c.arg(1) == 2):
            continue
        for j in range(k + 2, min(k + 20, len(ins))):
            y = ins[j]
            if y.op in (0x301D, 0x3057):
                quitar(ins, j, nop); cambios += 1
            elif y.op == 0x4020:                              # respuesta "si" -> siempre
                i = y.idx
                ins[j] = c.copia(); ins[j].idx = i; cambios += 1
                print(f"   {GUIONES[gid]}: resultados ({k}-{j}) -> lista directa")
                break
    return cambios


NUEVO = "ojeo_instantaneo"
VIEJO = "ojeo_ie2"
FICHA = {
    "nombre": "Ojeo instantaneo",
    "nombre_en": "Instant scouting",
    "descripcion": "Las busquedas de Celia y Nelly quedan listas al momento, como en Inazuma Eleven 2: sin "
                   "escenas, espera ni llamada; vuelve a hablarles y te enseñan los candidatos. Si ya tenias "
                   "una busqueda en marcha, la llamada llega al instante. Los candidatos y los fichajes son los "
                   "del juego.",
    "descripcion_en": "Celia's and Nelly's searches are ready instantly, as in Inazuma Eleven 2: no cutscenes, "
                      "wait or phone call; talk to them again to see the candidates. If a search was already "
                      "under way, the call arrives right away. Candidates and recruitments are the game's own.",
    "desbloqueo": "Siempre activo: se nota al encargar una busqueda a Celia o a Nelly.",
    "desbloqueo_en": "Always on: you notice it when you ask Celia or Nelly to search.",
    "nombre_fr": "Recrutement instantane",
    "descripcion_fr": "Les recherches de Celia et de Nelly sont prêtes tout de suite, comme dans Inazuma "
                      "Eleven 2 : sans scène, attente ni appel ; reparle-leur pour voir les candidats. Si une "
                      "recherche était déjà en cours, l'appel arrive immédiatement. Les candidats et les "
                      "recrutements sont ceux du jeu.",
    "desbloqueo_fr": "Toujours actif : tu le remarques en demandant une recherche à Celia ou à Nelly.",
    "nombre_de": "Sofortige Spielersuche",
    "descripcion_de": "Die Suchen von Celia und Nelly sind sofort fertig, wie in Inazuma Eleven 2: ohne "
                      "Zwischensequenz, Wartezeit oder Anruf; sprich sie noch einmal an, um die Kandidaten zu "
                      "sehen. Lief schon eine Suche, kommt der Anruf sofort. Kandidaten und Anwerbungen sind die "
                      "des Spiels.",
    "desbloqueo_de": "Immer aktiv: Du merkst es, wenn du Celia oder Nelly um eine Suche bittest.",
    "nombre_it": "Osservazione istantanea",
    "descripcion_it": "Le ricerche di Celia e Nelly sono pronte subito, come in Inazuma Eleven 2: senza scene, "
                      "attese né chiamate; parla di nuovo con loro per vedere i candidati. Se una ricerca era già "
                      "in corso, la chiamata arriva subito. Candidati e reclutamenti sono quelli del gioco.",
    "desbloqueo_it": "Sempre attivo: lo noti quando chiedi una ricerca a Celia o a Nelly.",
}


def main(rom_ruta=None, mods=None):
    if rom_ruta is None:
        if len(sys.argv) < 2:
            sys.exit(__doc__)
        rom_ruta = sys.argv[1]
    mods = mods or os.path.join(C.IE1, "mods")
    rom = open(rom_ruta, "rb").read()
    E = dict(C.pk_leer(C.archivo_rom(rom, "/data_iz/script/eve.pkh"), C.archivo_rom(rom, "/data_iz/script/eve.pkb")))
    dest = os.path.join(mods, NUEVO)
    guiones = {}
    for gid in GUIONES:
        if gid not in E:
            sys.exit(f"No encontre el guion {gid:#x} en la ROM.")
        d = C.lz10_des(E[gid])
        cab, ins = C.ssd_leer(d)
        n = modificar(gid, ins)
        if not n:
            sys.exit(f"{GUIONES[gid]}: no se encontro nada que cambiar; no se crea el mod.")
        nuevo = C.ssd_escribir(cab, ins, struct.unpack_from("<I", cab, 0x14)[0], struct.unpack_from("<H", cab, 0x0E)[0])
        _, comprobar = C.ssd_leer(nuevo)
        assert len(comprobar) == len(ins), "el guion modificado no se relee igual"
        guiones[gid] = C.lz10_com(nuevo)
        print(f"   {GUIONES[gid]}: {n} cambios")
    # todo bien: se escribe el mod
    for gid, datos in guiones.items():
        p = os.path.join(dest, "pk", "eve", f"{gid}.lz")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(datos)
    open(os.path.join(dest, "ojeo.cfg"), "w", encoding="utf-8").write(
        "# la llamada de una busqueda ya en marcha llega al momento\n")
    open(os.path.join(dest, "mod.txt"), "w", encoding="utf-8").write("".join(f"{k}={v}\n" for k, v in FICHA.items()))
    # mods.cfg: ojeo_instantaneo en el sitio del primero de los dos, sin ojeo_ie2
    cfg = os.path.join(mods, "mods.cfg")
    if os.path.exists(cfg):
        lineas = open(cfg, encoding="utf-8").read().splitlines()
        nuevas, puesto = [], False
        for l in lineas:
            if l.strip() in (NUEVO, VIEJO):
                if not puesto:
                    nuevas.append(NUEVO)
                    puesto = True
                continue
            nuevas.append(l)
        open(cfg, "w", encoding="utf-8").write("\n".join(nuevas) + "\n")
        if puesto:
            print(f"   mods.cfg: {NUEVO} activo (y quitado {VIEJO})")
    viejo = os.path.join(mods, VIEJO)
    if os.path.isdir(viejo):
        shutil.rmtree(viejo)
        print(f"   Borrada la carpeta {viejo}")
    print("Mod creado en", dest, "- activalo en el lanzador (Mods) o en Esc > Mods")


if __name__ == "__main__":
    main()
