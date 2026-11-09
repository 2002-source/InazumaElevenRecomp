#!/usr/bin/env python3
"""
PRUEBA de la marca de grado en el cartel de la tecnica (fase A, paso 3).
Solo para la Zona Mortal (guiones 100070 y 100071): junto al nombre se muestra
SIEMPRE la marca "++" del IE2, con las mismas instrucciones de guion que usa el
juego para el nombre (ranura 3 en vez de la 0). Sirve para comprobar que el
grafico carga, donde queda y que se mueve con el nombre.

  python scripts/crear_marca_prueba.py --ie2-es "RUTA/Tormenta de Fuego espanola.nds"

Crea el mod 'marca_prueba' (activalo junto con niveles_supertecnicas).
"""
import argparse, os, struct, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crear_npc_entrenador as C          # ROM, LZ10, paquetes y guiones (SSD)

IE1 = "C:/dev/ie1recomp"
HUECO = "tt70"            # grafico de guion que ningun guion ni el codigo usan: aloja la marca
GUIONES = (100070, 100071)
NOMBRE = "mbv_c147"       # nombre dibujado de la Zona Mortal


def textos_act(d):
    """Guion de tecnica: codigo + tabla de textos al final (cabecera +0x14 = tamano)."""
    tam = struct.unpack_from("<I", d, 0x14)[0]
    code, txt = d[:len(d) - tam], d[len(d) - tam:]
    T, p = [], 0
    while p + 8 <= len(txt):
        idx, tipo, n = struct.unpack_from("<HHI", txt, p)
        if n < 8 or p + n > len(txt): break
        T.append([idx, tipo, txt[p + 8:p + n]]); p += n
    return code, T


def escribir_act(cab, ins, T):
    cuerpo = b"".join(bytes(x.raw) for x in ins)
    txt = b"".join(struct.pack("<HHI", i, t, 8 + len(dd)) + dd for i, t, dd in T)
    d = bytearray(cab) + cuerpo
    struct.pack_into("<I", d, 0x08, len(d) + len(txt))
    struct.pack_into("<H", d, 0x0C, len(ins))
    struct.pack_into("<H", d, 0x0E, len(T))
    struct.pack_into("<I", d, 0x10, len(d) - 32)
    struct.pack_into("<I", d, 0x14, len(txt))
    return bytes(d) + txt


def visibles(pac):
    """Primera y ultima columna con pixeles del primer cuadro de un PAC de textura."""
    d = C.lz10_des(pac)
    n = struct.unpack_from("<I", d, 0)[0]
    t0, tl = struct.unpack_from("<II", d, 4)
    q0, _ = struct.unpack_from("<II", d, 4 + 8 * (n - 1))
    w_frame = struct.unpack_from("<H", d, q0 + 12)[0]
    h_frame = struct.unpack_from("<H", d, q0 + 14)[0]
    ancho_tex = 8 << ((d[q0 + 2]) & 7)       # el byte 2 del descriptor da el ancho de la textura
    alto = tl * 2 // ancho_tex
    cols = [x for x in range(min(w_frame, ancho_tex))
            if any((d[t0 + (y * ancho_tex + x) // 2] >> (4 * (x & 1))) & 15 for y in range(min(alto, h_frame)))]
    return (cols[0], cols[-1], w_frame, h_frame) if cols else (0, w_frame - 1, w_frame, h_frame)


def marca_ie2(rom, carpeta_idioma, numero):
    for carpeta in (carpeta_idioma, "en", "sp", "es"):
        try:
            h = C.archivo_rom(rom, f"/data_iz/pic3d/script/{carpeta}/mbv_c.pkh")
            b = C.archivo_rom(rom, f"/data_iz/pic3d/script/{carpeta}/mbv_c.pkb")
        except SystemExit:
            continue
        buscado = zlib.crc32(f"mbv_c{numero:03d}.pac_".encode())
        for k in range(len(h) // 16):
            hs, of, sz, _ = struct.unpack_from("<4I", h, 16 * k)
            if hs == buscado: return b[of:of + sz]
    return None


def generar_guion(E, gid, lang, dx, a, dest):
    d = C.lz10_des(next(x for i, x in E if i == gid))
    code, T = textos_act(d)
    cab, ins = C.ssd_leer(code)
    nuevas_despues = []
    for x in ([] if a.vacio else ins):
        if x.op in (0x3008, 0x300A, 0x300B, 0x300E, 0x3009) and x.argc >= 1 and x.tipo(0) == 1 and x.arg(0) == 0:
            y = x.copia(); y.set(0, a.ranura)
            if x.op in (0x300A, 0x300B):
                xv = struct.unpack("<i", struct.pack("<I", x.arg(1)))[0]
                y.set(1, xv + dx); y.set(2, x.arg(2) + a.dy)
            nuevas_despues.append((x.idx, y))
    for idx, y in sorted(nuevas_despues, key=lambda t: -t[0]):
        C.ssd_insertar(ins, idx, [y])
        for t in T:
            if t[0] > idx: t[0] += 1
    if not a.vacio:
        for x in ins:
            if x.op == 0x3008 and x.arg(0) == a.ranura:
                nombre_txt = NOMBRE if a.sin_texto else HUECO
                pos = next((i for i, t in enumerate(T) if t[0] > x.idx), len(T))
                for z in ins:
                    for k in range(z.argc):
                        if z.tipo(k) == 3 and z.arg(k) >= pos: z.set(k, z.arg(k) + 1)
                T.insert(pos, [x.idx, 2, (nombre_txt + "\0").encode() + b"\0" * ((-len(nombre_txt) - 1) % 4)])
                x.set(1, pos)
    nuevo = escribir_act(cab, ins, T)
    p = os.path.join(dest, "pk", "act", lang); os.makedirs(p, exist_ok=True)
    open(os.path.join(p, f"{gid}.lz"), "wb").write(C.lz10_com(nuevo))
    print(f"[{lang}] guion {gid}: {len(nuevas_despues)} instrucciones de la marca anadidas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=f"{IE1}/games/ie1_eur.nds")
    ap.add_argument("--ie2", default="C:/dev/ie2recomp/games/ie2_ff_eur.nds")
    ap.add_argument("--ie2-es", default=None)
    ap.add_argument("--dy", type=int, default=-8, help="ajuste vertical de la marca")
    ap.add_argument("--hueco", type=int, default=2, help="pixeles entre la ultima letra y la marca")
    ap.add_argument("--idiomas", default=f"{IE1}/idiomas", help="carpeta de paquetes de idioma")
    ap.add_argument("--ranura", type=int, default=1, help="ranura de grafico para la marca (la Zona Mortal no usa la 1)")
    ap.add_argument("--marca", choices=["+", "++"], default="+",
                    help="que marca poner (la Zona Mortal de Shadow va a '+')")
    ap.add_argument("--sin-texto", action="store_true",
                    help="prueba: la ranura nueva carga el MISMO texto del nombre (no se anade texto nuevo)")
    ap.add_argument("--vacio", action="store_true",
                    help="control: guiones SIN cambios (solo recomprimidos y combinados por el mod)")
    ap.add_argument("--grafico", choices=["ie2", "nombre"], default="ie2",
                    help="'ie2' = marca '++' del IE2; 'nombre' = copia del propio nombre (para descartar el formato)")
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    E = C.pk_leer(C.archivo_rom(rom, "/data_iz/script/act.pkh"), C.archivo_rom(rom, "/data_iz/script/act.pkb"))
    dest = f"{IE1}/mods/marca_prueba"
    os.makedirs(dest, exist_ok=True)
    # grafico de la marca "++" (mbv_c051 del IE2) en el hueco, por idioma
    import shutil
    shutil.rmtree(os.path.join(dest, "pk"), ignore_errors=True)
    nombre_ie1 = C.archivo_rom(rom, f"/data_iz/pic3d/script/en/{NOMBRE}.pac_")
    # El nombre dibujado cambia con el idioma ("Death Zone" / "Triangulo letal"): la
    # marca va detras de la ultima letra, asi que cada idioma lleva su guion.
    nombres = {"en": nombre_ie1}
    pac_es = os.path.join(a.idiomas, "es", "data_iz", "pic3d", "script", "en", NOMBRE + ".pac_")
    if os.path.exists(pac_es): nombres["es"] = open(pac_es, "rb").read()
    mx0 = {}
    for lang, ruta in (("en", a.ie2), ("es", a.ie2_es)):
        if not ruta: continue
        pac = (marca_ie2(open(ruta, "rb").read(), "en", 50 if a.marca == "+" else 51)
               if a.grafico == "ie2" else nombres.get(lang, nombre_ie1))
        if pac is None:
            print(f"AVISO: no encontre la marca en el IE2 ({lang})"); continue
        mx0[lang], _, mw, mh = visibles(pac)
        p = os.path.join(dest, "idioma", lang, "data_iz", "pic3d", "script", "en")
        os.makedirs(p, exist_ok=True)
        open(os.path.join(p, HUECO + ".pac_"), "wb").write(pac)
        print(f"Marca '{a.marca}' ({lang}) en {HUECO}.pac_ ({mw}x{mh})")
    for lang in mx0:
        n0, n1, _, _ = visibles(nombres.get(lang, nombre_ie1))
        dx = n1 + 1 + a.hueco - mx0[lang]          # justo a la derecha de la ultima letra
        print(f"[{lang}] nombre visible en columnas {n0}-{n1}: la marca va {dx} px a la derecha del cartel")
        for gid in GUIONES:
            generar_guion(E, gid, lang, dx, a, dest)

    open(os.path.join(dest, "mod.txt"), "w", encoding="utf-8").write(
        "nombre=Prueba marca de grado\ndescripcion=Muestra siempre '++' junto a la Zona Mortal (prueba).\n")
    print("Mod creado en", dest)


if __name__ == "__main__":
    main()
