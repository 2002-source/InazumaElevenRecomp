#!/usr/bin/env python3
"""
Vuelca a un archivo de texto los guiones de eventos relacionados con el ojeo/fichajes
(los que abren las ventanas de busqueda o de candidatos, o encargan una busqueda), con
sus instrucciones y sus dialogos. Sirve para el IE1 y para el IE2 (mismo motor de
guiones), y no copia nada mas de la ROM.
   python scripts/volcar_guiones_ojeo.py ROM.nds salida.txt [idioma_textos]
   (idioma_textos: en por defecto; es para la ROM espanola)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crear_npc_entrenador as C   # noqa: E402

# textos de depuracion que delatan un guion de ojeo/fichajes (estan en los dos juegos)
CLAVES = ("SearchWindow", "ScoutFunc", "HeadhuntEvent", "Scout_Timer", "Headhunt_Timer")


def textos_evet(d):
    try:
        d = C.lz10_des(d)
    except Exception:
        pass
    o, tx = 4, []
    while o + 8 <= len(d):
        _, _, n = struct.unpack_from("<HHI", d, o)
        if n < 8 or o + n > len(d):
            break
        tx.append(d[o + 8:o + n].split(b"\0")[0].decode("latin-1"))
        o += n
    return tx


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    rom = open(sys.argv[1], "rb").read()
    lang = sys.argv[3] if len(sys.argv) > 3 else "en"
    print("ROM:", rom[0x0C:0x10].decode("latin-1"), rom[0x00:0x0C].decode("latin-1").strip("\0"))
    # Las rutas cambian entre juegos: se buscan en el sistema de archivos de la ROM
    import listar_cambios_mod as L
    todos = L.archivos(rom)
    def buscar(nombre, preferir=""):
        c = [r for r in todos if r.lower().endswith("/" + nombre)]
        c.sort(key=lambda r: (preferir not in r, len(r)))
        return c[0] if c else None
    eve = buscar("eve.pkh")
    if not eve:
        pk = sorted(r for r in todos if r.lower().endswith(".pkh"))
        sys.exit("No encontre eve.pkh. Paquetes .pkh de la ROM:\n  " + "\n  ".join(pk))
    print("guiones de", eve)
    E = C.pk_leer(todos[eve], todos[eve[:-1] + "b"])
    T = {}
    evet = buscar("evet.pkh", "/" + lang + "/")
    if evet:
        T = dict(C.pk_leer(todos[evet], todos[evet[:-1] + "b"]))
        print("textos de", evet)
    # diagnostico: cuantos guiones y cuantos tienen textos legibles
    con_textos = sum(1 for g, _ in E if g in T and textos_evet(T[g]))
    print(f"guiones: {len(E)}, paquetes de textos: {len(T)}, guiones con textos legibles: {con_textos}")
    for g, _ in E[:3]:
        if g in T:
            print(f"  ejemplo {g:#x}:", [t[:40] for t in textos_evet(T[g])[:4]], T[g][:24].hex(" "))
    salida = []
    n = 0
    claves = CLAVES
    if not any(any(c in t for t in textos_evet(T[g]) for c in claves) for g, _ in E if g in T):
        claves = ("Scout", "Headhunt", "Recruit", "Search")        # por si el IE2 los llama distinto
        print("sin los textos de siempre; busco con:", claves)
    for gid, comp in E:
        try:
            d = C.lz10_des(comp)
            cab, ins = C.ssd_leer(d)
        except Exception:
            continue
        tx = textos_evet(T[gid]) if gid in T else []
        por_texto = any(c in t for t in tx for c in claves)
        # o por instrucciones: abre una ventana 0x20xx y mira su resultado (variable 131078),
        # como hacen los guiones de Celia y Nelly en el IE1
        ventanas = any(x.op in (0x2004, 0x2005, 0x2008) for x in ins)
        resultado = any(x.op and any(x.tipo(i) == 5 and x.arg(i) == 131078 for i in range(x.argc)) for x in ins)
        encargo = any(x.op == 0x4079 for x in ins)
        if not (por_texto or (ventanas and resultado) or encargo):
            continue
        n += 1
        salida.append(f"===== guion {gid:#x} ({len(ins)} instrucciones, {len(tx)} textos) =====")
        for k, x in enumerate(ins):
            if x.op is None:
                salida.append(f"{k:5d} --")
                continue
            a = [(x.tipo(i), x.arg(i)) for i in range(x.argc)]
            extra = ""
            for t, v in a:
                if t == 3 and v < len(tx):
                    extra += "  <<" + tx[v].replace("\n", "\\n")[:70] + ">>"
            salida.append(f"{k:5d} {x.op:#06x} {a}{extra}")
        salida.append("")
    open(sys.argv[2], "w", encoding="utf-8").write("\n".join(salida) + "\n")
    print(f"{n} guiones de ojeo volcados en {sys.argv[2]}")


if __name__ == "__main__":
    main()
