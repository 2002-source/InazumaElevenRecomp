#!/usr/bin/env python3
"""
Mod "Ojeo al estilo del IE2" (version 3): la busqueda de Celia o Nelly queda lista al
momento, sin espera ni llamada; al volver a hablarles se ve la lista de candidatos.

Lo que dice la traza (IE1_TRAZA=1):
  - La lista de candidatos NO se calcula al acabar el temporizador: se calcula al abrir
    la ventana de la lista. La llamada solo cambia el estado 4 ("buscando") a 2
    ("resultados listos"); las marcas que comprueba no las cambia nadie.
  - Algunas instrucciones del encargo son "expresiones" que otras leen (por ejemplo la
    duracion: 7001 tiempo = <instr 526> -> 7001 = <instr 528> ...). Quitarlas hace que el
    juego lea basura y se cuelgue (eso paso en las versiones anteriores).
Cambios de esta version (minimos):
  - En cada encargo, "estado = 4" pasa a "estado = 2". El temporizador se registra igual,
    pero la llamada solo salta con el estado en 4, asi que no llega.
  - Celia: se quitan su despedida ("Alla voy!") y su paseo hasta la puerta (instrucciones
    sueltas que nadie lee), para que se quede en la caseta y se le pueda hablar al momento.
  - Nelly: solo el estado (sus animaciones van en bloques paralelos y no se tocan).
  - La parte de resultados queda como en el juego (dialogo y pregunta incluidos).
   python scripts/crear_mod_ojeo_ie2.py games/ie1_eur.nds
"""
import os
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


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rom = open(sys.argv[1], "rb").read()
    E = dict(C.pk_leer(C.archivo_rom(rom, "/data_iz/script/eve.pkh"), C.archivo_rom(rom, "/data_iz/script/eve.pkb")))
    dest = os.path.join(C.IE1, "mods", "ojeo_ie2")
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
        p = os.path.join(dest, "pk", "eve", f"{gid}.lz")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(C.lz10_com(nuevo))
        print(f"   {GUIONES[gid]}: {n} cambios")
    C.escribir_mod_txt(dest, {
        "nombre": "Ojeo al estilo del IE2", "nombre_en": "IE2-style scouting",
        "descripcion": "La busqueda de Celia o Nelly queda lista al momento, sin escenas, espera ni llamada: "
                       "vuelve a hablarles y te enseñan los candidatos.",
        "descripcion_en": "Celia's and Nelly's searches are ready instantly, with no cutscenes, wait or phone call: "
                          "talk to them again to see the candidates.",
        "desbloqueo": "Siempre activo: se nota al encargar una busqueda a Celia o a Nelly.",
        "desbloqueo_en": "Always on: you notice it when you ask Celia or Nelly to search.",
    })
    print("Mod creado en", dest, "- activalo en el lanzador (Mods) o en Esc > Mods")


if __name__ == "__main__":
    main()
