#!/usr/bin/env python3
"""
Crea el mod de niveles (ahora dentro de 'mecanicas_ie2', ver crear_mod_mecanicas_ie2.py): las supertecnicas suben de nivel con el
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
    ap.add_argument("--hueco", type=int, default=3, help="pixeles libres a la derecha del nombre (como el marco del IE2)")
    ap.add_argument("--ie2-es", default=None,
                    help="ROM espanola de Tormenta de Fuego (para el cartel 'Nv +' en espanol)")
    for l, n in (("fr", "francesa"), ("de", "alemana"), ("it", "italiana")):
        ap.add_argument(f"--ie2-{l}", default=None, help=f"ROM {n} del IE2 (cartel 'Nv +' y marcas en ese idioma)")
    a = ap.parse_args()
    r1 = leer_rom(a.ie1)
    if a.solo_guiones:
        dest = f"{IE1}/mods/mecanicas_ie2"   # (antes niveles_supertecnicas: ahora va dentro de Mecanicas IE2)
        guiones_desde_mod(a, r1, dest)
        return
    r2 = leer_rom(a.ie2)
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
    dest = f"{IE1}/mods/mecanicas_ie2"   # (antes niveles_supertecnicas: ahora va dentro de Mecanicas IE2)
    os.makedirs(dest, exist_ok=True)

    # Cartel "Nv +": el IE1 dibuja los bocadillos de los jugadores con
    # pic3d/<idioma>/ply_bkr01.pac_, que solo tiene 8 animaciones (!, Miss,
    # Direct, Charge, Nice...). El evento del cartel es la animacion 9, que solo
    # existe en el archivo del IE2 (mismos bocadillos + "Lv +"/"Nv +"). Se usa el
    # del IE2 del mismo idioma, solo con ese idioma de textos.
    def bocadillos(rom, nombre_idioma):
        import zlib
        for carpeta in CARPETAS_IE2:   # en, sp (espanol), fr, ge (aleman), it
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
    for lang, ruta_rom in roms_ie2(a).items():
        if not ruta_rom:
            continue
        pac = bocadillos(r2 if ruta_rom == a.ie2 else leer_rom(ruta_rom), lang)
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
    crear_iconos_grado(a, dest)
    crear_graficos_exp(a, dest)
    crear_marcas_cartel(a, r1, dest)
    open(os.path.join(dest, "parches.txt"), "w", encoding="utf-8").write("\n".join(lineas) + "\n")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_npc_entrenador as C3
    # Mecanicas IE2: niveles + tiro y bloqueos (tiro.cfg) + talentos (talentos.cfg) + Mark libre (capitan.cfg) + EXP x2 (exp_x2.cfg), con su ficha
    import crear_mod_mecanicas_ie2 as MEC
    for cfg, txt in (("tiro.cfg", "# boton de tiro, tiro largo, area azul, marcas y bloqueos (como el IE2)\n"),
                     ("talentos.cfg", "# talentos en los partidos (como el IE2)\n"),
                     ("capitan.cfg", MEC.CAPITAN_CFG),
                     ("exp_x2.cfg", MEC.EXP_X2_CFG)):
        if not os.path.exists(os.path.join(dest, cfg)):
            open(os.path.join(dest, cfg), "w", encoding="utf-8").write(txt)
    open(os.path.join(dest, "mod.txt"), "w", encoding="utf-8").write("".join(f"{k}={v}\n" for k, v in MEC.FICHA.items()))
    print(f"{cambios} tecnicas con categoria del IE2 ({distinto_indice} en otra posicion), {umbrales} bytes de umbrales")
    print("Mod creado en", dest, "(Mecanicas IE2) - activalo en el lanzador (Mods) o en Esc > Mods")
    return
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
IDIOMAS = ("en", "es", "fr", "de", "it")


_ROMS = {}


def leer_rom(ruta):
    """Lee una ROM .nds; tambien dentro de un .zip (la primera .nds que haya)."""
    if ruta not in _ROMS:
        if ruta.lower().endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(ruta) as z:
                nds = [n for n in z.namelist() if n.lower().endswith(".nds")]
                if not nds:
                    raise SystemExit(f"No hay ninguna ROM .nds dentro de {ruta}")
                _ROMS[ruta] = z.read(nds[0])
        else:
            _ROMS[ruta] = open(ruta, "rb").read()
    return _ROMS[ruta]


def roms_ie2(a):
    """ROM del IE2 de cada idioma (las que se hayan dado)."""
    return {"en": a.ie2, "es": a.ie2_es, "fr": a.ie2_fr, "de": a.ie2_de, "it": a.ie2_it}


def con_paquete(a, lang):
    """Hay paquete de idioma (idiomas/<lang>) con los nombres dibujados de las tecnicas."""
    return lang == "en" or os.path.isdir(os.path.join(a.idiomas, lang, "data_iz", "pic3d", "script", "en"))
HUECOS = ["tt70", "tt71", "tt72", "tt73", "tt74", "tt75", "tt76", "tt77", "tt78"]
HUECO_VACIO = "tt85"   # tt79 no existe en la ROM: se usa otro grafico sin uso


# Iconos de grado de los menus (ficha del jugador y barra encima del boton de tecnica
# antes de tirar). El IE1 los lee de pic2d/menu/<idioma>/msup_z06/z07/z08.pac_ y solo
# trae los ingleses en todos los idiomas ("L" + numero, "+1", "+2"). El IE2 los lleva
# dentro de pic2d/menu/<idioma>/SMStat.SPF_ (piezas MSUP_Z06/Z07/Z08), cada idioma con
# los suyos: espanol "G", "+", "++"; frances "N", "2", "3"; italiano "E1", "E2"...
# Mismo formato de pieza (paleta, mapa de 8 entradas, tiles): se copian tal cual.
CARPETAS_IE2 = ("en", "sp", "es", "fr", "ge", "de", "it")
CARPETA_IE2 = {"en": "en", "es": "sp", "fr": "fr", "de": "ge", "it": "it"}   # carpeta de cada idioma en el IE2


def piezas_spf(spf):
    """Piezas de un paquete SPF de Level-5: {nombre sin extension: datos}."""
    d = lz10_des(spf) if spf[:1] == b"\x10" else spf
    if d[:3] != b"SFP":
        return {}
    u32 = lambda o: struct.unpack_from("<I", d, o)[0]
    base, out, e = u32(0x10), {}, 0x20
    while e + 16 <= len(d):
        nom, tam, des = u32(e), u32(e + 4), u32(e + 8)
        if not nom or nom >= len(d):
            break
        n = d[nom:d.index(0, nom)].decode("latin-1")
        if ".PAC" not in n.upper():
            break
        out[n.split(".")[0].upper()] = d[base + des * 32:base + des * 32 + tam]
        e += 16
    return out


def reemplazar_pieza(spl, spd, nombre, datos):
    """Paquete .SPL/.SPD de pic3d: cambia la pieza 'nombre' por 'datos' (tal cual, ya
    comprimida o no). Entradas de 16 bytes desde 0x20 en el SPL: [nombre, tamano,
    desplazamiento / 32, ...]. Si no cabe en su hueco, va al final del SPD."""
    spl, spd = bytearray(spl), bytearray(spd)
    e = 0x20
    while e + 16 <= len(spl):
        nom, tam, des = struct.unpack_from("<III", spl, e)
        if not nom or nom >= len(spl):
            break
        n = spl[nom:spl.index(0, nom)].decode("latin-1")
        if n.upper() == nombre.upper():
            hueco = (tam + 31) // 32 * 32
            if len(datos) <= hueco:
                spd[des * 32:des * 32 + len(datos)] = datos
            else:
                while len(spd) % 32:
                    spd.append(0)
                des = len(spd) // 32
                spd += datos
            struct.pack_into("<II", spl, e + 4, len(datos), des)
            return bytes(spl), bytes(spd)
        e += 16
    return None


def crear_iconos_grado(a, dest):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_npc_entrenador as C
    for lang, ruta in roms_ie2(a).items():
        if not ruta:
            continue
        rom2 = leer_rom(ruta)
        spf = None
        for carpeta in CARPETAS_IE2:
            try:
                spf = archivo_rom(rom2, f"/data_iz/pic2d/menu/{carpeta}/SMStat.SPF_"); break
            except SystemExit:
                pass
        P = piezas_spf(spf) if spf else {}
        if not all(f"MSUP_Z0{n}" in P for n in (6, 7, 8)):
            print(f"AVISO: no encontre los iconos de grado (MSUP_Z06..Z08) en el IE2 ({lang})")
            continue
        p = os.path.join(dest, "idioma", lang, "data_iz", "pic2d", "menu", "en")
        os.makedirs(p, exist_ok=True)
        for n in (6, 7, 8):
            open(os.path.join(p, f"msup_z0{n}.pac_"), "wb").write(C.lz10_com(P[f"MSUP_Z0{n}"]))
        print(f"Iconos de grado de los menus ({lang}): los del IE2")
        # Selector de tecnicas del partido: la marca de la barra de encima de cada boton
        # sale de pic2d/<idioma>/mbd_z01..z04.pac_ (el ov1 los carga como recursos 56-59 de
        # la ventana; mbd_z02 = "+1"/"+2", mbd_z03 = "L"). El IE1 trae los ingleses en todos
        # los idiomas; el IE2 los de cada idioma (espanol "+"/"++" y "G").
        p2 = os.path.join(dest, "idioma", lang, "data_iz", "pic2d", "en")
        hechos = 0
        for n in ("mbd_z01.pac_", "mbd_z02.pac_", "mbd_z03.pac_", "mbd_z04.pac_"):
            try:
                datos = archivo_rom(rom2, f"/data_iz/pic2d/{CARPETA_IE2[lang]}/{n}")
            except SystemExit:
                continue
            os.makedirs(p2, exist_ok=True)
            open(os.path.join(p2, n), "wb").write(datos)
            hechos += 1
        print(f"Marcas del selector de tecnicas ({lang}): " + ("las del IE2" if hechos == 4 else "AVISO: no las encontre"))
        # Pantalla de supertecnicas del equipo (Datos > Supertecnicas): las marcas van en la
        # pieza HWD_I04 de pic3d/<idioma>/menu_special_comand.SPL/.SPD (16x16, dos dibujos).
        # Se cambia solo esa pieza en el archivo del IE1 de ese idioma (paquete de idioma o,
        # en ingles, la ROM), para no tocar lo demas de la pantalla.
        try:
            l2 = archivo_rom(rom2, f"/data_iz/pic3d/{CARPETA_IE2[lang]}/menu_special_comand.SPL")
            d2 = archivo_rom(rom2, f"/data_iz/pic3d/{CARPETA_IE2[lang]}/menu_special_comand.SPD")
        except SystemExit:
            l2 = d2 = None
        pieza = None
        if l2:
            e = 0x20
            while e + 16 <= len(l2):
                nom, tam, des = struct.unpack_from("<III", l2, e)
                if not nom or nom >= len(l2): break
                if l2[nom:l2.index(0, nom)].decode("latin-1").upper() == "HWD_I04.PAC_":
                    pieza = d2[des * 32:des * 32 + tam]; break
                e += 16
        l1 = d1 = None
        paquete = os.path.join(a.idiomas, lang, "data_iz", "pic3d", "en")
        if lang != "en" and os.path.exists(os.path.join(paquete, "menu_special_comand.SPL")):
            l1 = open(os.path.join(paquete, "menu_special_comand.SPL"), "rb").read()
            d1 = open(os.path.join(paquete, "menu_special_comand.SPD"), "rb").read()
        else:
            try:
                l1 = archivo_rom(leer_rom(a.ie1), "/data_iz/pic3d/en/menu_special_comand.SPL")
                d1 = archivo_rom(leer_rom(a.ie1), "/data_iz/pic3d/en/menu_special_comand.SPD")
            except SystemExit:
                pass
        nuevo = reemplazar_pieza(l1, d1, "HWD_I04.PAC_", pieza) if (pieza and l1 and d1) else None
        if nuevo:
            p3 = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "en")
            os.makedirs(p3, exist_ok=True)
            open(os.path.join(p3, "menu_special_comand.SPL"), "wb").write(nuevo[0])
            open(os.path.join(p3, "menu_special_comand.SPD"), "wb").write(nuevo[1])
            print(f"Marcas de la pantalla de supertecnicas ({lang}): las del IE2")
        else:
            print(f"AVISO: no pude cambiar las marcas de la pantalla de supertecnicas ({lang})")


def piezas_spl(spl, spd):
    """Piezas de un paquete .SPL/.SPD de pic3d: {nombre: datos} (entradas de 16 bytes
    desde 0x20 en el SPL: [nombre, tamano, desplazamiento / 32, ...])."""
    out, e = {}, 0x20
    while e + 16 <= len(spl):
        nom, tam, des = struct.unpack_from("<III", spl, e)
        if not nom or nom >= len(spl):
            break
        out[spl[nom:spl.index(0, nom)].decode("latin-1").upper()] = spd[des * 32:des * 32 + tam]
        e += 16
    return out


# Pantalla de EXP (pic3d/<idioma>/cl_bonus.SPL/.SPD): el IE2 tiene las mismas piezas que el
# IE1 (barra de cada jugador con "Niv.", "NUEVA", "SIG.", "Sube niv.", numeros, barras) en
# cada idioma, y una mas, BGDN_B06 = "x2!!" (EXP doble en los encuentros ganados por 5+ sin
# encajar). Las comunes se cambian en el archivo del IE1 de cada idioma (mismo orden de
# piezas: el juego las pide por numero); la del x2 se guarda aparte (exp_x2.pac) y la dibuja
# el mod encima de cada fila, porque el IE1 no tiene sitio para ella en las filas.
def crear_graficos_exp(a, dest):
    x2 = None
    for lang, ruta in roms_ie2(a).items():
        if not ruta:
            continue
        rom2 = leer_rom(ruta)
        try:
            P2 = piezas_spl(archivo_rom(rom2, f"/data_iz/pic3d/{CARPETA_IE2[lang]}/cl_bonus.SPL"),
                            archivo_rom(rom2, f"/data_iz/pic3d/{CARPETA_IE2[lang]}/cl_bonus.SPD"))
        except SystemExit:
            print(f"AVISO: no encontre la pantalla de EXP del IE2 ({lang})")
            continue
        if x2 is None and "BGDN_B06.PAC_" in P2:
            x2 = P2["BGDN_B06.PAC_"]
        paquete = os.path.join(a.idiomas, lang, "data_iz", "pic3d", "en")
        if lang != "en" and os.path.exists(os.path.join(paquete, "cl_bonus.SPL")):
            l1 = open(os.path.join(paquete, "cl_bonus.SPL"), "rb").read()
            d1 = open(os.path.join(paquete, "cl_bonus.SPD"), "rb").read()
        else:
            try:
                l1 = archivo_rom(leer_rom(a.ie1), "/data_iz/pic3d/en/cl_bonus.SPL")
                d1 = archivo_rom(leer_rom(a.ie1), "/data_iz/pic3d/en/cl_bonus.SPD")
            except SystemExit:
                print(f"AVISO: no encontre la pantalla de EXP del IE1 ({lang})")
                continue
        cambiadas = 0
        for nombre in piezas_spl(l1, d1):
            if nombre in P2:
                nuevo = reemplazar_pieza(l1, d1, nombre, P2[nombre])
                if nuevo:
                    l1, d1 = nuevo
                    cambiadas += 1
        p3 = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "en")
        os.makedirs(p3, exist_ok=True)
        open(os.path.join(p3, "cl_bonus.SPL"), "wb").write(l1)
        open(os.path.join(p3, "cl_bonus.SPD"), "wb").write(d1)
        print(f"Pantalla de EXP ({lang}): {cambiadas} graficos del IE2")
    if x2:
        open(os.path.join(dest, "exp_x2.pac"), "wb").write(x2)
        print("Grafico x2!! de la EXP doble: el del IE2")
    else:
        print("AVISO: no encontre el grafico x2!! del IE2 (la EXP doble funciona igual, sin el grafico)")


def crear_marcas_cartel(a, r1, dest):
    import shutil, struct as st
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_npc_entrenador as C
    import crear_marca_prueba as MP
    C.archivo_rom = archivo_rom
    roms = roms_ie2(a)
    marcas_x0 = {}
    for lang, ruta in roms.items():
        if not ruta: continue
        rom2 = leer_rom(ruta)
        p = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "script", "en")
        os.makedirs(p, exist_ok=True)
        primera = None
        for k, hueco in enumerate(HUECOS):
            pac = MP.marca_ie2(rom2, CARPETA_IE2[lang], 50 + k)
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
        marcas_x0[lang] = MP.visibles(MP.marca_ie2(rom2, CARPETA_IE2[lang], 50))[0]
        print(f"Marcas del cartel ({lang}): {HUECOS[0]}..{HUECOS[-1]} y {HUECO_VACIO} (vacia)")
    if not marcas_x0:
        return
    # Idiomas con paquete pero sin ROM del IE2 en ese idioma: las marcas inglesas
    # (el cartel "Nv +" no, porque sus bocadillos llevan textos de cada idioma)
    if "en" in marcas_x0:
        origen = os.path.join(dest, "idioma", "en", "data_iz", "pic3d", "script", "en")
        for lang in IDIOMAS:
            if lang in marcas_x0 or not con_paquete(a, lang):
                continue
            p = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "script", "en")
            shutil.copytree(origen, p, dirs_exist_ok=True)
            marcas_x0[lang] = marcas_x0["en"]
            print(f"Marcas del cartel ({lang}): las inglesas (sin ROM del IE2 en ese idioma)")
    generar_guiones_marca(a, r1, dest, marcas_x0)


def guiones_desde_mod(a, r1, dest):
    """Sin ROM del IE2: rehace los guiones de tecnica (que salen de la ROM del IE1)
    usando las marcas que ya trae el mod (distribucion del port)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crear_marca_prueba as MP
    marcas_x0 = {}
    for lang in IDIOMAS:
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
        if lang != "en":
            ruta = os.path.join(a.idiomas, lang, "data_iz", "pic3d", "script", "en", nombre + ".pac_")
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
                medidas[clave] = MP.visibles(pac) if pac else None
            if medidas[clave] is None: continue
            pos = posiciones_cartel(medidas[clave], a.hueco)
            nuevo = guion_con_marca(C, MP, d, ranura_nombre, libre, tecnica, pos, a.dy)
            if nuevo is None: continue
            p = os.path.join(dest, "pk", "act", lang); os.makedirs(p, exist_ok=True)
            open(os.path.join(p, f"{gid}.lz"), "wb").write(C.lz10_com(nuevo))
            hechos[lang] += 1
    for lang, n in hechos.items():
        print(f"Guiones de tecnica con marca de grado ({lang}): {n}")


# Colocacion del cartel como el IE2. En el IE2 el marco de cada nombre mide lo que el
# texto (de 50 a 160 px, con 2-4 px libres a la derecha), el nombre se centra en la
# pantalla (instruccion 0x3087 [0, 50, 0]: punto de anclaje en el centro) y, con marca,
# el grupo nombre + marca (marco de 48 px pegado al del nombre) se centra entero: el
# nombre se corre a la izquierda y la marca queda justo detras. Medido en el IE2
# espanol (Baile de mariposas con "+"): nombre visible 27..181, marca 188..222.
# En el IE1 los nombres van en un marco fijo de 160 px con el texto a la izquierda y
# anclados a la izquierda (x = 48), asi que se calcula el marco "del IE2" con lo que
# mide el texto. Sin marca el nombre se centra igual que en el IE2.
X_DESCANSO = 48          # x de descanso del nombre en los guiones del IE1
ANCHO_MARCA = 48         # marco de las marcas mbv_c050..058 del IE2
VAR_X_CON, VAR_X_SIN = 22, 23   # x del nombre con marca / sin marca (el gancho elige)


def posiciones_cartel(medida, hueco):
    v0, v1, w, _ = medida
    ancho = min(w, v1 + 1 + hueco)
    con = round(128 - (ancho + ANCHO_MARCA) / 2)
    sin = round(128 - ancho / 2)
    return con, sin, con + ancho     # nombre con marca, nombre sin marca, marca


def poner_tipo(x, k, t):
    b = x.raw[8 + k // 2]
    x.raw[8 + k // 2] = (b & 0x0F) | (t << 4) if k % 2 else (b & 0xF0) | t


def guion_con_marca(C, MP, d, rn, rm, tecnica, pos, dy):
    """Anade la marca (ranura rm) junto al nombre (ranura rn) en un guion de tecnica."""
    x_con, x_sin, x_marca = pos
    dx = x_marca - x_con                  # la marca va siempre a esta distancia del nombre
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
            if xv == X_DESCANSO:           # descanso: nombre en la x que elija el gancho, marca detras
                destino = x_marca
                poner_tipo(x, 1, 5); x.set(1, VAR_X_CON)
            elif xv < 0:                   # el nombre sale por la izquierda: la marca tambien, entera
                destino = min(destino, -64)
            y.set(1, destino & 0xFFFFFFFF); y.set(2, x.arg(2) + dy)
        insertar(x.idx, [y])
    # en cada cartel (algunos guiones tienen dos caminos, cada uno con su 0x3078: la Mano
    # Celestial, 0x19258): antes de 0x3078 la tecnica en la variable 20; tras su 0x3079 (o
    # el propio 0x3078) cargar el grafico de la variable 21, colocarlo y mostrarlo
    for c in [x for x in ins if x.op == 0x3078]:
        sig = next((x for x in ins if x.idx > c.idx and x.op in (0x3078, 0x3079)), None)
        fin = sig if sig is not None and sig.op == 0x3079 else c
        pos = [x for x in ins if x.op == 0x300A and x.argc >= 3 and x.tipo(0) == 1 and x.arg(0) == rn and x.idx < c.idx]
        p = pos[-1] if pos else pos0
        xc = struct.unpack("<i", struct.pack("<I", p.arg(1)))[0]; yc = p.arg(2)
        insertar(fin.idx, [N(0x3008, [1, 5], [rm, VAR_MARCA]),
                           N(0x300A, [1, 1, 1], [rm, xc + dx, yc + dy]),
                           N(0x300E, [1, 1], [rm, 1])])
        insertar(c.idx - 1, [N(0x7001, [6, 1], [VAR_TECNICA, tecnica]),
                             N(0x7001, [6, 1], [VAR_X_CON, x_con]),
                             N(0x7001, [6, 1], [VAR_X_SIN, x_sin])])
    return MP.escribir_act(cab, ins, T)


if __name__ == "__main__":
    main()
