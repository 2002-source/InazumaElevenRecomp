#!/usr/bin/env python3
"""
Analiza los textos de interfaz que estan DENTRO del ARM9 (menus del mapa, etc.)
para poder traducirlos manteniendo el codigo ingles como base.

Para cada cadena del ARM9 ingles en la zona de datos, busca los punteros que
la usan. Como el ARM9 espanol tiene la misma estructura (solo recolocada),
el puntero equivalente del ARM9 espanol apunta a la cadena traducida: asi se
emparejan las dos versiones sin depender del orden.

Uso (desde C:/dev/ie1recomp):
  python scripts/analizar_cadenas.py "/c/ruta/rom_es.nds" > run/cadenas.txt
"""
import os, re, struct, sys
from bisect import bisect_right

sys.path.insert(0, os.path.dirname(__file__))
from comparar_arm9 import arm9
from comparar_codigo import partes

BASE = 0x02000000
INI_DATOS = 0x020A0000          # zona donde buscar cadenas (datos del final del ARM9)
DESPL = 0x440                   # desplazamiento de la version espanola tras la tabla


def es_letra(b):
    # Texto: ASCII imprimible o cualquier byte alto (acentos, ñ y simbolos del juego)
    return 0x20 <= b < 0x7F or b >= 0x80


def cadenas(a9, ini, fin):
    """Cadenas terminadas en 0. Se admiten bytes de control (colores, simbolos
    especiales como el de apertura de exclamacion) siempre que la mayoria del
    texto sea legible y tenga al menos 2 letras."""
    res, i = {}, ini
    while i < fin:
        if a9[i] != 0 and (i == 0 or a9[i - 1] == 0):
            j = a9.find(b"\0", i, min(fin, i + 200))
            t = a9[i:j] if j > i + 1 else b""
            if t and sum(1 for x in t if es_letra(x)) >= 0.6 * len(t) and \
               sum(chr(x).isalpha() for x in t if x < 0x80) >= 2:
                res[BASE + i] = t
                i = j + 1
                continue
        i += 1
    return res


def rangos_funciones():
    p = os.path.join("generated", "arm9_main_dispatch.c")
    if not os.path.exists(p):
        return [], []
    r = sorted((int(a, 16), int(n)) for a, n in
               re.findall(r"NdsStaticValidation\s+\w+\s*=\s*\{0x([0-9A-Fa-f]+)u,\s*(\d+)u,",
                          open(p, errors="ignore").read()))
    return [a for a, _ in r], [a + n for a, n in r]


def leer_cadena(a9, addr):
    o = addr - BASE
    if not (0 <= o < len(a9)):
        return None
    j = a9.find(b"\0", o, o + 300)
    return a9[o:j] if j > o else None


def refs_de(a9, cads):
    lst = []
    for pos in range(0x4000, len(a9) - 3, 4):
        v = struct.unpack_from("<I", a9, pos)[0]
        if v in cads:
            lst.append((BASE + pos, v))
    return lst


def main():
    en = open(os.path.join("images", "arm9.bin"), "rb").read()
    es, _, _ = arm9(sys.argv[1])
    def bss_de(a9):
        return struct.unpack_from("<I", a9, a9.find(struct.pack("<II", 0xDEC00621, 0x2106C0DE)) - 0x1C + 12)[0]
    ce = cadenas(en, INI_DATOS - BASE, bss_de(en) - BASE)
    cs = cadenas(es, INI_DATOS - BASE, bss_de(es) - BASE)
    re_en, re_es = refs_de(en, ce), refs_de(es, cs)
    print(f"Cadenas EN {len(ce)}, ES {len(cs)}; punteros EN {len(re_en)}, ES {len(re_es)}")
    if len(re_en) != len(re_es):
        print("AVISO: distinto numero de punteros; el emparejado por orden puede fallar")
    # Emparejar por orden de aparicion de los punteros (misma estructura de programa)
    # Emparejar: antes de la tabla de textos (0x020B04C8) las posiciones son las
    # mismas. Despues, se buscan las TABLAS de punteros a textos (rachas de
    # punteros seguidos) en las dos versiones y se emparejan tabla con tabla
    # por su forma (numero de entradas y distancia a la tabla anterior); dentro
    # de cada tabla, entrada con entrada.
    import difflib
    INI_TABLA = 0x020B04C8
    def tablas(a9, cads, fin, techo):
        # Una entrada de tabla es cualquier puntero a la zona de textos (aunque el
        # detector no haya reconocido esa cadena), para que la forma de cada
        # tabla sea igual en las dos versiones.
        res, actual, prev_fin = [], None, INI_TABLA
        for p in range(INI_TABLA - BASE, fin - BASE, 4):
            v = struct.unpack_from("<I", a9, p)[0]
            if v in cads or (INI_DATOS <= v < techo):
                if actual is None:
                    actual = [BASE + p, []]
                actual[1].append(v)
            elif actual is not None:
                ini = actual[0]
                res.append((ini, actual[1], ini - prev_fin))
                prev_fin = ini + 4 * len(actual[1])
                actual = None
        if actual is not None:
            res.append((actual[0], actual[1], actual[0] - prev_fin))
        return res
    te = tablas(en, ce, bss_de(en), 0x020B4000)
    ts = tablas(es, cs, bss_de(es), 0x020B4000 + DESPL)
    firma = lambda t: [(len(v), g) for _, v, g in t]
    sm = difflib.SequenceMatcher(None, firma(te), firma(ts), autojunk=False)
    traduccion, conflictos, emparejadas = {}, 0, 0
    desplaz = []          # (inicio EN, fin EN, desplazamiento a ES) de tablas emparejadas
    locs = []             # (posicion EN, posicion ES) de cada entrada emparejada
    def anota(a, b):
        nonlocal conflictos
        if a in traduccion and traduccion[a] != b:
            conflictos += 1
        traduccion.setdefault(a, b)
    fmt_re = re.compile(rb"%[-+ 0#]*\d*(?:\.\d+)?[a-zA-Z]")
    def firma_txt(v, cads):
        t = cads.get(v)
        if t is None:
            return ("?",)
        fin = t[-1:] if t[-1:] in (b"!", b"?", b".", b":") else b""
        return (tuple(fmt_re.findall(t)), fin, t[:1] == b"%")
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        bloques = []
        if tag == "replace":
            # Tablas que no coinciden en forma (p. ej. una entrada de mas o de menos):
            # se alinean ENTRADA a ENTRADA por la "firma" de cada texto (huecos %s/%d
            # y puntuacion final), que es igual en ingles y en espanol.
            ent_e = [(t[0] + 4 * i, v) for t in te[i1:i2] for i, v in enumerate(t[1])]
            ent_s = [(t[0] + 4 * i, v) for t in ts[j1:j2] for i, v in enumerate(t[1])]
            m2 = difflib.SequenceMatcher(None, [firma_txt(v, ce) for _, v in ent_e],
                                         [firma_txt(v, cs) for _, v in ent_s], autojunk=False)
            for bi, bj, n in m2.get_matching_blocks():
                firmas = [firma_txt(v, ce) for _, v in ent_e[bi:bi + n]]
                # Solo bloques con algun hueco %s/%d (ancla fiable) y de 3 o mas entradas
                if n < 3 or not any(f[0] for f in firmas if len(f) > 1):
                    continue
                for k in range(n):
                    (xe2, a), (xs2, b) = ent_e[bi + k], ent_s[bj + k]
                    f = firmas[k]
                    # Solo frases (con hueco o puntuacion final), no palabras sueltas
                    if len(f) > 1 and (f[0] or f[1]) and a in ce and b in cs:
                        anota(a, b)
        if tag == "equal":
            bloques = list(zip(te[i1:i2], ts[j1:j2]))
        for (xe, ve, _), (xs, vs, _) in bloques:
            emparejadas += 1
            desplaz.append((xe, xe + 4 * len(ve), xs - xe))
            for i, (a, b) in enumerate(zip(ve, vs)):
                locs.append((xe + 4 * i, xs + 4 * i))
                if a in ce and b in cs:
                    anota(a, b)
    print(f"Tablas de punteros: EN {len(te)}, ES {len(ts)}; emparejadas {emparejadas}")
    # Punteros sueltos de la zona de tablas (estructuras con texto y otros datos):
    # si las tablas emparejadas mas cercanas antes y despues tienen el MISMO
    # desplazamiento, el puntero esta en ese mismo tramo desplazado.
    # Punteros sueltos de la zona de tablas: se usa el desplazamiento de las
    # entradas emparejadas MAS CERCANAS (antes y despues). Si coinciden, el
    # puntero suelto esta en el mismo tramo y se desplaza igual.
    from bisect import bisect_left
    locs.sort()
    pos_e = [e for e, _ in locs]
    pal_es_t = {BASE + p: struct.unpack_from("<I", es, p)[0]
                for p in range(INI_TABLA - BASE, bss_de(es) - BASE, 4)}
    extra = 0
    for x, a in re_en:
        if x < INI_TABLA or a in traduccion or a not in ce:
            continue
        k = bisect_left(pos_e, x)
        cands = []
        if k > 0:
            cands.append(locs[k - 1][1] - locs[k - 1][0])
        if k < len(locs):
            cands.append(locs[k][1] - locs[k][0])
        for d in dict.fromkeys(cands):           # primero el de antes, luego el de despues
            b = pal_es_t.get(x + d)
            if b in cs:
                anota(a, b)
                extra += 1
                break
    print(f"Punteros sueltos emparejados por su tramo: {extra}")
    # Punteros de la zona de codigo (antes de la tabla): misma posicion
    pal_es = {BASE + p: struct.unpack_from("<I", es, p)[0] for p in range(0x4000, INI_TABLA - BASE, 4)}
    for x, a in re_en:
        if x < INI_TABLA and pal_es.get(x) in cs:
            anota(a, pal_es[x])
    print(f"Cadenas emparejadas: {len(traduccion)} de {len({a for _, a in re_en})}")
    # Textos usados TAMBIEN desde los overlays (constantes dentro de su codigo).
    # No se pueden mover sin tocar el codigo de los overlays: se traduciran EN SU
    # SITIO si caben. Los overlays tienen el mismo tamano en las dos versiones,
    # asi que la palabra k del overlay ingles corresponde a la palabra k del espanol.
    pe = partes(open(os.path.join("games", "ie1_eur.nds"), "rb").read())
    ps = partes(open(sys.argv[1], "rb").read())
    fijos = {}
    for nombre, de in pe.items():
        if not nombre.startswith("ov9_") or nombre.endswith("_tabla"):
            continue
        ds = ps.get(nombre)
        if not ds or len(ds) != len(de):
            continue
        for k in range(0, len(de) - 3, 4):
            a = struct.unpack_from("<I", de, k)[0]
            if a in ce and a >= 0x020B0000:
                b = struct.unpack_from("<I", ds, k)[0]
                fijos.setdefault(a, set()).add(nombre)
                if b in cs:
                    anota(a, b)
    print(f"Textos de interfaz usados desde overlays: {len(fijos)}")
    # Textos SIN punteros directos (el codigo llega a ellos de otra forma, p. ej.
    # base + desplazamiento): se emparejan por su ORDEN en la zona de textos entre
    # dos parejas ya conocidas, y se marcan como fijos (solo se traducen en su sitio).
    zona_en = sorted(a for a in ce if 0x020B0000 <= a < 0x020B4000)
    zona_es = sorted(b for b in cs if 0x020B0000 <= b < 0x020B4000 + DESPL)
    idx_es = {b: i for i, b in enumerate(zona_es)}
    anclas = sorted((a, traduccion[a]) for a in zona_en if a in traduccion and traduccion[a] in idx_es)
    con_ref = {t for _, t in re_en}
    por_orden = 0
    pos_en = {a: i for i, a in enumerate(zona_en)}
    for (a1, b1), (a2, b2) in zip(anclas, anclas[1:]):
        en_medio = zona_en[pos_en[a1] + 1:pos_en[a2]]
        es_medio = zona_es[idx_es[b1] + 1:idx_es[b2]]
        if len(en_medio) != len(es_medio):
            continue
        for a, b in zip(en_medio, es_medio):
            if a not in traduccion and a not in con_ref:
                anota(a, b)
                fijos.setdefault(a, set()).add("sin-puntero")
                por_orden += 1
    print(f"Textos sin puntero directo emparejados por orden: {por_orden}")
    # Solo textos de interfaz (desde 0x020B0000); por debajo hay identificadores
    # (codigos de idioma, rutas...) que NO se deben cambiar.
    # Seguridad: los formatos (%s, %d, %2d...) deben ser los MISMOS y en el mismo
    # orden; si no, el juego podria leer datos equivocados al mostrar el texto.
    fmt = re.compile(rb"%[-+ 0#]*\d*(?:\.\d+)?[a-zA-Z]")
    distintas, formato_distinto = {}, 0
    for a, b in traduccion.items():
        if a >= 0x020B0000 and ce[a] != cs.get(b):
            if fmt.findall(ce[a]) != fmt.findall(cs[b]):
                formato_distinto += 1
                continue
            distintas[a] = b
    print(f"Descartadas por formato distinto (%s/%d): {formato_distinto}")
    en_b = sum(len(ce[a]) + 1 for a in distintas)
    es_b = sum(len(cs[b]) + 1 for b in distintas.values())
    zona_codigo = sum(1 for x, a in re_en if a in distintas and x < INI_DATOS)
    zona_datos = sum(1 for x, a in re_en if a in distintas and x >= INI_DATOS)
    print(f"Conflictos de emparejado: {conflictos}")
    print(f"Cadenas que cambian con el idioma: {len(distintas)} (EN {en_b} bytes, ES {es_b} bytes)")
    print(f"Sus punteros: {zona_codigo} en la zona de codigo (constantes de funciones), "
          f"{zona_datos} en tablas de datos")
    # Archivo para el parche: cadena inglesa -> texto espanol y punteros a cambiar
    import json
    salida = {f"0x{a:08X}": {"en": ce[a].hex(), "es": cs[distintas[a]].hex(),
                             "punteros": [f"0x{x:08X}" for x, t in re_en if t == a],
                             "fijo": a in fijos}
              for a in sorted(distintas)}
    # Textos usados desde overlays que NO cambian o no tienen pareja: su sitio
    # no se puede reutilizar para otros textos.
    reservados = sorted(a for a in fijos if a not in distintas)
    json.dump([f"0x{a:08X}" for a in reservados],
              open(os.path.join("run", "cadenas_reservadas.json"), "w"))
    os.makedirs("run", exist_ok=True)
    json.dump(salida, open(os.path.join("run", "cadenas_es.json"), "w"), indent=1)
    print("Traducciones guardadas en run/cadenas_es.json")
    # Textos de interfaz con referencias que se quedaron SIN pareja
    def legible(b):          # texto latino (no nombres internos en japones)
        return sum(1 for c in b if 0x20 <= c < 0x7F) >= 0.8 * len(b)
    sin = sorted(a for a in {t for _, t in re_en}
                 if a >= 0x020B0000 and a not in traduccion and legible(ce[a]))
    with open(os.path.join("run", "cadenas_sin_pareja.txt"), "w", encoding="latin-1") as f:
        for a in sin:
            xs = [x for x, t in re_en if t == a][:3]
            f.write(f"0x{a:08X} {ce[a].decode('latin-1')!r:40.40} " +
                    " ".join(f"0x{x:08X}" for x in xs) + "\n")
    print(f"Textos de interfaz sin pareja: {len(sin)} (lista en run/cadenas_sin_pareja.txt)")
    print()
    for a in sorted(distintas):
        b = distintas[a]
        xs = [x for x, t in re_en if t == a][:3]
        print(f"0x{a:08X} {ce[a].decode('latin-1')!r:34.34} -> {cs[b].decode('latin-1')!r:40.40} "
              + " ".join(f"0x{x:08X}{'(c)' if x < INI_DATOS else '(d)'}" for x in xs))

if __name__ == "__main__":
    main()
