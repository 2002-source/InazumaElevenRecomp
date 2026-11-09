#!/usr/bin/env python3
"""
Crea el mod 'niveles_supertecnicas': las supertecnicas suben de nivel con el
uso, como en el Inazuma Eleven 2. El motor del IE1 ya tiene el sistema (contador
de usos y calculo del grado); lo tiene apagado porque en sus datos todas las
tecnicas tienen la categoria 0. El mod copia del IE2:
  - la categoria de cada tecnica (command.dat, byte +0x10 de cada registro),
    emparejando las tecnicas por NOMBRE (en ingles) entre los dos juegos;
  - los umbrales y bonos de cada categoria (lvup_command.dat).
No toca la ROM: genera mods/niveles_supertecnicas/parches.txt (cambios de bytes
que el complemento aplica al arrancar, en el idioma que uses).

  python scripts/crear_mod_niveles.py
  python scripts/crear_mod_niveles.py --ie2 "D:/ruta/ie2.nds"
"""
import argparse, os, re, struct, sys

IE1 = "C:/dev/ie1recomp"


def archivo_rom(rom, ruta):
    u32 = lambda o: struct.unpack_from("<I", rom, o)[0]
    u16 = lambda o: struct.unpack_from("<H", rom, o)[0]
    fnt, fat = u32(0x40), u32(0x48)
    partes = ruta.strip("/").split("/")
    did = 0xF000
    for i, parte in enumerate(partes):
        ent = fnt + (did & 0xFFF) * 8
        p = fnt + u32(ent); fid = u16(ent + 4)
        hallado = None
        while True:
            n = rom[p]; p += 1
            if n == 0: break
            nombre = rom[p:p + (n & 0x7F)].decode("latin-1"); p += n & 0x7F
            if n & 0x80:
                sid = u16(p); p += 2
                if nombre == parte and i < len(partes) - 1: hallado = ("d", sid); break
            else:
                if nombre == parte and i == len(partes) - 1: hallado = ("f", fid); break
                fid += 1
        if not hallado: raise SystemExit(f"No esta en la ROM: {ruta}")
        if hallado[0] == "d": did = hallado[1]
        else:
            return rom[u32(fat + 8 * hallado[1]):u32(fat + 8 * hallado[1] + 4)]


def lz10_des(d):
    n = d[1] | d[2] << 8 | d[3] << 16
    out = bytearray(); p = 4
    while len(out) < n:
        f = d[p]; p += 1
        for b in range(8):
            if len(out) >= n: break
            if f & (0x80 >> b):
                x = d[p] << 8 | d[p + 1]; p += 2
                for _ in range((x >> 12) + 3): out.append(out[-((x & 0xFFF) + 1)])
            else:
                out.append(d[p]); p += 1
    return bytes(out)


def nombres_tecnicas(cmd, strs):
    """Nombre (ingles) de cada uno de los 512 registros de command.dat."""
    tabla = [strs[i * 32:i * 32 + 32].split(b"\0")[0] for i in range(len(strs) // 32)]
    res = []
    for i in range(len(cmd) // 28):
        k = struct.unpack_from("<H", cmd, i * 28 + 0x14)[0]
        res.append(tabla[k].decode("latin-1") if k < len(tabla) else "")
    return res


def clave(n):   # "Emperor Penguin No.2" == "Emperor Penguin No. 2", "Fist Of" == "Fist of"
    return re.sub(r"[^a-z0-9]", "", n.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ie1", default=f"{IE1}/games/ie1_eur.nds")
    ap.add_argument("--ie2", default="C:/dev/ie2recomp/games/ie2_ff_eur.nds")
    ap.add_argument("--idiomas", default=f"{IE1}/idiomas", help="paquetes de idioma (para medir los nombres en espanol)")
    ap.add_argument("--solo-guiones", action="store_true",
                    help="sin ROM del IE2: rehace solo los guiones con las marcas que ya trae el mod")
    ap.add_argument("--dy", type=int, default=-8, help="ajuste vertical de la marca del cartel")
    ap.add_argument("--hueco", type=int, default=2, help="pixeles entre el nombre y la marca del cartel")
    ap.add_argument("--ie2-es", default=None,
                    help="ROM espanola de Tormenta de Fuego (para el cartel 'Nv +' en espanol)")
    a = ap.parse_args()
    r1 = open(a.ie1, "rb").read()
    if a.solo_guiones:
        dest = f"{IE1}/mods/niveles_supertecnicas"
        guiones_desde_mod(a, r1, dest)
        return
    r2 = open(a.ie2, "rb").read()
    def de_ie2(ruta):          # ROM del IE2 inglesa (en) o espanola (sp)
        try:
            return archivo_rom(r2, ruta)
        except SystemExit:
            return archivo_rom(r2, ruta.replace("/en/", "/sp/"))
    c1, c2 = archivo_rom(r1, "/data_iz/logic/en/command.dat"), de_ie2("/data_iz/logic/en/command.dat")
    n1 = nombres_tecnicas(c1, archivo_rom(r1, "/data_iz/logic/en/command.STR"))
    n2 = nombres_tecnicas(c2, de_ie2("/data_iz/logic/en/command.STR"))
    try:
        archivo_rom(r2, "/data_iz/logic/en/command.dat"); ie2_ingles = True
    except SystemExit:
        ie2_ingles = False
    l1, l2 = archivo_rom(r1, "/data_iz/logic/lvup_command.dat"), archivo_rom(r2, "/data_iz/logic/lvup_command.dat")

    # tecnica del IE2 por nombre -> categoria
    cat2 = {}
    for i, n in enumerate(n2):
        c = c2[i * 28 + 0x10]
        if n and c: cat2.setdefault(clave(n), c)
    lineas = ["# Niveles de supertecnicas (categorias y umbrales del Inazuma Eleven 2)",
              "# <ruta> <desplazamiento> <bytes>"]
    cambios, distinto_indice = 0, 0
    for i, n in enumerate(n1):
        if not n: continue
        # misma tecnica en la misma posicion (lo normal): su categoria, aunque sea 0;
        # si no, se busca por nombre en todo el IE2
        # Las tecnicas tienen el mismo numero en los dos juegos (comprobado por nombre:
        # 330 iguales y 2 que solo cambian una mayuscula o un espacio). Si los nombres
        # coinciden o el IE2 no esta en ingles, vale la misma posicion.
        mismo = i < len(n2) and (clave(n2[i]) == clave(n) or not ie2_ingles)
        c = (c2[i * 28 + 0x10] or None) if mismo else cat2.get(clave(n))
        if c is None or c1[i * 28 + 0x10] == c: continue
        lineas.append(f"/data_iz/logic/en/command.dat 0x{i * 28 + 0x10:05X} {c:02X}   # {n}")
        cambios += 1
        if not (i < len(n2) and clave(n2[i]) == clave(n)): distinto_indice += 1
    # umbrales y bonos: misma estructura (6 filas de 41 bytes, mismas clases en el mismo orden)
    umbrales = 0
    if len(l1) == len(l2) and all(l1[k * 41] == l2[k * 41] for k in range(len(l1) // 41)):
        for o in range(len(l1)):
            if l1[o] != l2[o]:
                lineas.append(f"/data_iz/logic/lvup_command.dat 0x{o:04X} {l2[o]:02X}")
                umbrales += 1
    else:
        print("AVISO: lvup_command.dat no tiene la misma estructura en los dos juegos; no se copian los umbrales")
    dest = f"{IE1}/mods/niveles_supertecnicas"
    os.makedirs(dest, exist_ok=True)

    # Cartel "Nv +": el IE1 dibuja los bocadillos de los jugadores con
    # pic3d/<idioma>/ply_bkr01.pac_, que solo tiene 8 animaciones (!, Miss,
    # Direct, Charge, Nice...). El evento del cartel es la animacion 9, que solo
    # existe en el archivo del IE2 (mismos bocadillos + "Lv +"/"Nv +"). Se usa el
    # del IE2 del mismo idioma, solo con ese idioma de textos.
    def bocadillos(rom, nombre_idioma):
        import zlib
        for carpeta in ("en", "sp", "es"):
            try:
                return archivo_rom(rom, f"/data_iz/pic3d/{carpeta}/ply_bkr01.pac_")
            except SystemExit:
                pass
            # En el IE2 va dentro de pic3d/<idioma>/common.pkb: indice de 16 bytes por
            # entrada (CRC32 del nombre, desplazamiento, tamano, info)
            try:
                h = archivo_rom(rom, f"/data_iz/pic3d/{carpeta}/common.pkh")
                b = archivo_rom(rom, f"/data_iz/pic3d/{carpeta}/common.pkb")
            except SystemExit:
                continue
            buscado = zlib.crc32(b"ply_bkr01.pac_")
            for k in range(len(h) // 16):
                hs, of, sz, _ = struct.unpack_from("<4I", h, 16 * k)
                if hs == buscado and of + sz <= len(b):
                    return b[of:of + sz]
        print(f"AVISO: no encontre ply_bkr01.pac_ en la ROM del IE2 ({nombre_idioma})")
        return None
    def animaciones(pac):
        try:
            d = lz10_des(pac)
            n = struct.unpack_from("<I", d, 0)[0]
            off = struct.unpack_from("<I", d, 4 + 8 * (n - 1))[0]
            return d[off]
        except Exception:
            return 0
    import shutil
    shutil.rmtree(os.path.join(dest, "idioma"), ignore_errors=True)
    for lang, ruta_rom in (("en", a.ie2), ("es", a.ie2_es)):
        if not ruta_rom:
            continue
        pac = bocadillos(r2 if ruta_rom == a.ie2 else open(ruta_rom, "rb").read(), lang)
        if pac is None:
            continue
        n = animaciones(pac)
        if n < 9:
            print(f"AVISO: el ply_bkr01 del IE2 ({lang}) tiene {n} animaciones; no lo uso")
            continue
        p = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "en")
        os.makedirs(p, exist_ok=True)
        open(os.path.join(p, "ply_bkr01.pac_"), "wb").write(pac)
        print(f"Cartel 'Nv +' ({lang}): bocadillos del IE2 con {n} animaciones")
    if not a.ie2_es:
        print("(Para el cartel en espanol: --ie2-es \"RUTA/Tormenta de Fuego espanola.nds\")")
    crear_marcas_cartel(a, r1, dest)
    open(os.path.join(dest, "parches.txt"), "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_npc_entrenador as C3
    C3.escribir_mod_txt(dest, {
        "nombre": "Niveles de supertecnicas", "nombre_en": "Move levels",
        "descripcion": "Las supertecnicas suben de nivel con el uso, como en el Inazuma Eleven 2: ganan poder, "
                       "sale el aviso Nv + al subir y su marca (+, ++, G2...) junto al nombre.",
        "descripcion_en": "Special moves level up with use, like in Inazuma Eleven 2: they gain power, a Lv + notice "
                          "appears when they level up and their mark (+, ++, L2...) is shown next to the name.",
        "desbloqueo": "Siempre activo: usa las supertecnicas en los partidos (segun el tipo, suben entre 6 y 100 usos).",
        "desbloqueo_en": "Always on: use your special moves in matches (depending on the type, they level up after 6 to 100 uses).",
    })
    print(f"{cambios} tecnicas con categoria del IE2 ({distinto_indice} en otra posicion), {umbrales} bytes de umbrales")
    print("Mod creado en", dest, "- activalo en el lanzador (Mods) o en Esc > Mods")


# ---- Marca de grado en el cartel de la tecnica (+, ++, NV2/NV3, G2..G5) --------
# Como el IE2 (instruccion 0x30FB de sus guiones), pero con las piezas del IE1:
#  - Graficos: las 9 marcas del IE2 (mbv_c050..058, en su mbv_c.pkb) van en
#    graficos de guion que no usa nadie (tt70..tt78) y tt79 es una marca vacia.
#  - Guiones de tecnica (act.pkb, uno por idioma porque el nombre dibujado mide
#    distinto): antes de 0x3078 guardan la tecnica en su variable 20; despues de
#    0x3079 cargan en una ranura libre el grafico cuyo nombre deja en la variable
#    21 el codigo inyectado por el complemento (segun el grado del jugador), y lo
#    mueven y retiran junto con el nombre.
VAR_TECNICA, VAR_MARCA = 20, 21
HUECOS = ["tt70", "tt71", "tt72", "tt73", "tt74", "tt75", "tt76", "tt77", "tt78"]
HUECO_VACIO = "tt85"   # tt79 no existe en la ROM: se usa otro grafico sin uso


def crear_marcas_cartel(a, r1, dest):
    import shutil, struct as st
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_npc_entrenador as C
    import crear_marca_prueba as MP
    C.archivo_rom = archivo_rom
    roms = {"en": a.ie2, "es": a.ie2_es}
    marcas_x0 = {}
    for lang, ruta in roms.items():
        if not ruta: continue
        rom2 = open(ruta, "rb").read()
        p = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "script", "en")
        os.makedirs(p, exist_ok=True)
        primera = None
        for k, hueco in enumerate(HUECOS):
            pac = MP.marca_ie2(rom2, "en", 50 + k)
            if pac is None:
                print(f"AVISO: falta la marca mbv_c0{50 + k} en el IE2 ({lang})"); continue
            open(os.path.join(p, hueco + ".pac_"), "wb").write(pac)
            if primera is None: primera = pac
        if primera is None: continue
        # marca vacia: el mismo formato con la textura a cero
        d = bytearray(C.lz10_des(primera))
        t0, tl = st.unpack_from("<II", d, 4)
        d[t0:t0 + tl] = bytes(tl)
        open(os.path.join(p, HUECO_VACIO + ".pac_"), "wb").write(C.lz10_com(bytes(d)))
        marcas_x0[lang] = MP.visibles(MP.marca_ie2(rom2, "en", 50))[0]
        print(f"Marcas del cartel ({lang}): {HUECOS[0]}..{HUECOS[-1]} y {HUECO_VACIO} (vacia)")
    if not marcas_x0:
        return
    generar_guiones_marca(a, r1, dest, marcas_x0)


def guiones_desde_mod(a, r1, dest):
    """Sin ROM del IE2: rehace los guiones de tecnica (que salen de la ROM del IE1)
    usando las marcas que ya trae el mod (distribucion del port)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_marca_prueba as MP
    marcas_x0 = {}
    for lang in ("en", "es"):
        ruta = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "script", "en", HUECOS[0] + ".pac_")
        if os.path.exists(ruta):
            marcas_x0[lang] = MP.visibles(open(ruta, "rb").read())[0]
    if not marcas_x0:
        print("AVISO: el mod no trae las marcas del cartel; sin marca en el nombre de la tecnica")
        return
    generar_guiones_marca(a, r1, dest, marcas_x0)


def generar_guiones_marca(a, r1, dest, marcas_x0):
    import shutil
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_npc_entrenador as C
    import crear_marca_prueba as MP
    C.archivo_rom = archivo_rom
    shutil.rmtree(os.path.join(dest, "pk"), ignore_errors=True)
    # nombre dibujado de una tecnica en cada idioma
    def nombre_pac(lang, nombre):
        if lang == "es":
            ruta = os.path.join(a.idiomas, "es", "data_iz", "pic3d", "script", "en", nombre + ".pac_")
            if os.path.exists(ruta): return open(ruta, "rb").read()
        try:
            return archivo_rom(r1, f"/data_iz/pic3d/script/en/{nombre}.pac_")
        except SystemExit:
            return None
    E = C.pk_leer(archivo_rom(r1, "/data_iz/script/act.pkh"), archivo_rom(r1, "/data_iz/script/act.pkb"))
    import crear_npc_entrenador as C2
    C2.OTROS_GUIONES[:] = []
    for i, dd in E:
        try:
            x = C.lz10_des(dd)
            if x[:4] == b"SSD\0": C2.OTROS_GUIONES.append(C.ssd_leer(MP.textos_act(x)[0])[1])
        except Exception:
            pass
    hechos = {lang: 0 for lang in marcas_x0}
    medidas = {}
    for gid, comp in E:
        try:
            d = C.lz10_des(comp)
        except Exception:
            continue
        if d[:4] != b"SSD\0": continue
        code, T = MP.textos_act(d)
        _, ins0 = C.ssd_leer(code)
        if not any(x.op == 0x3078 for x in ins0): continue
        # texto del nombre del cartel (mbv_cNNN) cargado en alguna ranura
        cartel = None
        for x in ins0:
            if x.op == 0x3008 and x.argc >= 2 and x.tipo(0) == 1 and x.tipo(1) == 3:
                n = T[x.arg(1)][2].split(b"\0")[0].decode("latin-1") if x.arg(1) < len(T) else ""
                if re.fullmatch(r"mbv_c\d+", n): cartel = (x.arg(0), n); break
        if not cartel: continue
        ranura_nombre, nombre = cartel
        tecnica = int(nombre[5:])
        usadas = {x.arg(0) for x in ins0 if x.op in (0x3008, 0x3009, 0x300A, 0x300B, 0x300E) and x.argc and x.tipo(0) == 1}
        libre = next((r for r in (1, 2, 3, 5, 6) if r not in usadas), None)
        if libre is None: continue
        for lang in marcas_x0:
            clave = (lang, nombre)
            if clave not in medidas:
                pac = nombre_pac(lang, nombre)
                medidas[clave] = MP.visibles(pac)[1] if pac else None
            if medidas[clave] is None: continue
            dx = medidas[clave] + 1 + a.hueco - marcas_x0[lang]
            nuevo = guion_con_marca(C, MP, d, ranura_nombre, libre, tecnica, dx, a.dy)
            if nuevo is None: continue
            p = os.path.join(dest, "pk", "act", lang); os.makedirs(p, exist_ok=True)
            open(os.path.join(p, f"{gid}.lz"), "wb").write(C.lz10_com(nuevo))
            hechos[lang] += 1
    for lang, n in hechos.items():
        print(f"Guiones de tecnica con marca de grado ({lang}): {n}")


def guion_con_marca(C, MP, d, rn, rm, tecnica, dx, dy):
    """Anade la marca (ranura rm) junto al nombre (ranura rn) en un guion de tecnica."""
    code, T = MP.textos_act(d)
    cab, ins = C.ssd_leer(code)
    def N(op, tipos, args): return C.nueva(ins, op, tipos, args)
    def insertar(despues_idx, nuevas):
        C.ssd_insertar(ins, despues_idx, nuevas)
        for t in T:
            if t[0] > despues_idx: t[0] += len(nuevas)
    pos0 = next((x for x in ins if x.op == 0x300A and x.argc >= 3 and x.tipo(0) == 1 and x.arg(0) == rn), None)
    if pos0 is None: return None
    x0 = struct.unpack("<i", struct.pack("<I", pos0.arg(1)))[0]; y0 = pos0.arg(2)
    # movimientos y retirada del nombre: lo mismo para la marca (de atras hacia delante)
    for x in sorted([x for x in ins if x.op in (0x300B, 0x3009) and x.argc >= 1 and x.tipo(0) == 1 and x.arg(0) == rn],
                    key=lambda z: -z.idx):
        y = x.copia(); y.set(0, rm)
        if x.op == 0x300B:
            xv = struct.unpack("<i", struct.pack("<I", x.arg(1)))[0]
            destino = xv + dx
            if xv < 0:                     # el nombre sale por la izquierda: la marca tambien, entera
                destino = min(destino, -64)
            y.set(1, destino & 0xFFFFFFFF); y.set(2, x.arg(2) + dy)
        insertar(x.idx, [y])
    # tras 0x3079 (o 0x3078): cargar el grafico de la variable 21, colocarlo y mostrarlo
    fin = next((x for x in ins if x.op == 0x3079), None) or next(x for x in ins if x.op == 0x3078)
    insertar(fin.idx, [N(0x3008, [1, 5], [rm, VAR_MARCA]),
                       N(0x300A, [1, 1, 1], [rm, x0 + dx, y0 + dy]),
                       N(0x300E, [1, 1], [rm, 1])])
    # antes de 0x3078: la tecnica en la variable 20
    c = next(x for x in ins if x.op == 0x3078)
    antes = next(x.idx for x in ins if x.idx == c.idx - 1)
    insertar(antes, [N(0x7001, [6, 1], [VAR_TECNICA, tecnica])])
    return MP.escribir_act(cab, ins, T)


if __name__ == "__main__":
    main()
