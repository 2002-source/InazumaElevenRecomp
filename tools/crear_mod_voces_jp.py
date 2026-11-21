#!/usr/bin/env python3
"""
Crea el mod 'voces_jp' con la ROM japonesa de Inazuma Eleven 1 (tuya):
  - las voces de las cinematicas (archivos .SAD de data_iz/sound), en japones;
  - las voces de los partidos y de las escenas: los bancos de sonido .SWD/.SED, que en la
    europea van empaquetados en data_iz/sound/en/sound.pb (indice sound.ph) y en la japonesa
    sueltos en data_iz/sound/. Se rehace el paquete con los bancos japoneses que cambian; los
    efectos (iguales en las dos) y los bancos que solo tiene la europea se quedan;
  - el opening japones completo: su cancion (op00.SAD) y su video (data_iz/movie/op00.mods),
    sin los subtitulos de la letra que trae la version europea (data_iz/movie/txt/<idioma>/
    op00.dat), que van con su cancion y su video.
NO toca las ROM: lee la japonesa y la europea (base) y escribe en mods/voces_jp/ solo los
archivos que cambian, con las rutas de la version europea.

Uso (terminal MSYS2 CLANG64, desde cualquier carpeta):
   python /c/dev/ie1recomp/scripts/crear_mod_voces_jp.py "RUTA/rom_japonesa.nds"
   (tambien vale un .zip con la ROM dentro)
Opciones: --base RUTA (por defecto C:/dev/ie1recomp/games/ie1_eur.nds), --mods RUTA,
          --wav CARPETA (saca en .wav las voces de los bancos que cambian y de los que solo
          tiene la europea, para escucharlas e identificarlas).
Despues: activa "Voces japonesas" en Esc > Mods (o en el lanzador) y reinicia.
El mod es contenido del juego: es para tu uso, no lo distribuyas (el preparador del port
lo crea en cada PC con la ROM de cada persona).
"""
import argparse
import hashlib
import os
import shutil
import struct
import sys
import zipfile

IE1 = "C:/dev/ie1recomp"

FICHA = {
    "nombre": "Voces japonesas",
    "nombre_en": "Japanese voices",
    "descripcion": "Las cinematicas suenan con las voces originales japonesas y el opening es el japones, "
                   "con su cancion y su video (sin los subtitulos de la letra).",
    "descripcion_en": "Cutscenes play with the original Japanese voices and the opening is the Japanese one, "
                      "with its song and its video (without the lyrics subtitles).",
    "desbloqueo": "Siempre activo: se oye en el opening y en las cinematicas.",
    "desbloqueo_en": "Always on: you hear it in the opening and in the cutscenes.",
}


def leer_rom(ruta):
    if ruta.lower().endswith(".zip"):
        with zipfile.ZipFile(ruta) as z:
            nds = [n for n in z.namelist() if n.lower().endswith(".nds")]
            if not nds:
                sys.exit(f"No hay ninguna ROM .nds dentro de {ruta}")
            return z.read(nds[0])
    return open(ruta, "rb").read()


def archivos(rom):
    """Todos los archivos de la ROM: {ruta: datos}."""
    fnt_off = struct.unpack_from("<I", rom, 0x40)[0]
    fat_off = struct.unpack_from("<I", rom, 0x48)[0]
    res = {}

    def recorrer(dir_id, ruta):
        sub, first, _ = struct.unpack_from("<IHH", rom, fnt_off + (dir_id & 0xFFF) * 8)
        p, fid = fnt_off + sub, first
        while True:
            n = rom[p]; p += 1
            if n == 0:
                break
            es_dir, largo = n & 0x80, n & 0x7F
            nombre = rom[p:p + largo].decode("latin-1"); p += largo
            if es_dir:
                sid = struct.unpack_from("<H", rom, p)[0]; p += 2
                recorrer(sid, ruta + nombre + "/")
            else:
                s, e = struct.unpack_from("<II", rom, fat_off + fid * 8)
                res[ruta + nombre] = rom[s:e]
                fid += 1

    recorrer(0xF000, "/")
    return res


# ---- bancos de sonido (formato swdl de Procyon) ----------------------------------------
def leer_paquete(ph, pb):
    """sound.ph: entradas de 32 bytes [nombre 24][offset u32][largo u32] sobre sound.pb."""
    res = []
    for i in range(0, len(ph) - 31, 32):
        nombre = ph[i:i + 24].split(b"\0")[0].decode("latin-1")
        o, n = struct.unpack_from("<II", ph, i + 24)
        res.append((nombre, pb[o:o + n]))
    return res


def hacer_paquete(entradas):
    ph, pb = bytearray(), bytearray()
    for nombre, datos in entradas:
        ph += nombre.encode("latin-1")[:24].ljust(24, b"\0") + struct.pack("<II", len(pb), len(datos))
        pb += datos
    return bytes(ph), bytes(pb)


def muestras_swd(d):
    """[(formato, hz, datos)] de un .SWD; formato 0 PCM8, 1 PCM16, 2 ADPCM."""
    if d[:4] != b"swdl":
        return []
    p, wavi, pcmd = 0x50, None, None
    while p + 16 <= len(d):
        tag, ln = d[p:p + 4], struct.unpack_from("<I", d, p + 12)[0]
        if tag == b"wavi":
            wavi = d[p + 16:p + 16 + ln]
        elif tag == b"pcmd":
            pcmd = d[p + 16:p + 16 + ln]
        p = (p + 16 + ln + 15) & ~15
    if wavi is None or pcmd is None:
        return []
    n = struct.unpack_from("<H", d, 0x46)[0]
    res = []
    for k in range(min(n, len(wavi) // 2)):
        o = struct.unpack_from("<H", wavi, 2 * k)[0]
        if not o or o + 64 > len(wavi):
            continue
        e = wavi[o:o + 64]
        fmt = e[0x13]
        hz, pos, lb, ll = struct.unpack_from("<IIII", e, 0x20)
        largo = (lb + ll) * 4
        res.append((fmt, hz, pcmd[pos:pos + largo]))
    return res


def silenciar_swd(d):
    """El mismo banco con todas sus muestras en silencio (ceros en pcmd: en ADPCM la
    cabecera 0/0 y los nibbles 0 dan silencio). Mismo tamano y estructura."""
    d = bytearray(d)
    p = 0x50
    while p + 16 <= len(d):
        tag, ln = bytes(d[p:p + 4]), struct.unpack_from("<I", d, p + 12)[0]
        if tag == b"pcmd":
            d[p + 16:p + 16 + ln] = bytes(ln)
        p = (p + 16 + ln + 15) & ~15
    return bytes(d)


def voz_inglesa_sin_pareja(nombre, nombres_base=()):
    """Bancos de voces que anadio la version europea y que la japonesa no tiene:
    3D_NNN0 = gritos con el nombre de la tecnica NNN, SOLO si existe su banco 3D_NNN (igual
    en las dos versiones, con los efectos). Las tecnicas sin 3D_NNN (090, 124-146, 222-252,
    323-349) llevan los efectos dentro de su 3D_NNN0: esos no se tocan, o la tecnica se
    queda muda. 3D_003_31..48 = voces de gol de los equipos rivales."""
    n = nombre.upper()
    if not n.endswith(".SWD"):
        return False
    b = n[:-4]
    if len(b) == 7 and b.startswith("3D_") and b[3:].isdigit() and b.endswith("0") and b[3] in "0123":
        return (b[:6] + ".SWD") in nombres_base
    if len(b) in (9, 10) and b.startswith("3D_003_") and b[7:9].isdigit() and 31 <= int(b[7:9]) <= 48:   # y 33b
        return True
    return False


def segundos(m):
    fmt, hz, d = m
    n = len(d) if fmt == 0 else len(d) // 2 if fmt == 1 else max(0, len(d) - 4) * 2
    return n / hz if hz else 0


_PASO = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97,
         107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
         876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871,
         5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623,
         27086, 29794, 32767]
_IND = [-1, -1, -1, -1, 2, 4, 6, 8]


def a_pcm16(m):
    fmt, hz, d = m
    if fmt == 1:
        return d[:len(d) & ~1]
    if fmt == 0:
        return b"".join(struct.pack("<h", (b - 256 if b > 127 else b) * 256) for b in d)
    if len(d) < 4:
        return b""
    v, i = struct.unpack_from("<hB", d, 0)
    i = min(i, 88)
    out = bytearray()
    for b in d[4:]:
        for nib in (b & 15, b >> 4):
            st = _PASO[i]
            dif = st >> 3
            if nib & 1: dif += st >> 2
            if nib & 2: dif += st >> 1
            if nib & 4: dif += st
            v = max(-32768, min(32767, v - dif if nib & 8 else v + dif))
            i = max(0, min(88, i + _IND[nib & 7]))
            out += struct.pack("<h", v)
    return bytes(out)


def guardar_wav(ruta, m):
    pcm = a_pcm16(m)
    hz = m[1] or 32728
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, 1, hz, hz * 2, 2, 16) + b"data" + struct.pack("<I", len(pcm)) + pcm)


def resumen_banco(d):
    m = [x for x in muestras_swd(d)]
    return f"{len(m)} sonidos, {sum(segundos(x) for x in m):.1f} s"


def escribir_mod_txt(carpeta, campos):
    ruta = os.path.join(carpeta, "mod.txt")
    actual = {}
    if os.path.exists(ruta):
        for l in open(ruta, encoding="utf-8", errors="replace"):
            if "=" in l and not l.startswith("#"):
                k, v = l.rstrip("\r\n").split("=", 1); actual[k] = v
    actual.update(campos)
    open(ruta, "w", encoding="utf-8").write("".join(f"{k}={v}\n" for k, v in actual.items()))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("jp", help="ROM japonesa de Inazuma Eleven 1 (.nds o .zip)")
    ap.add_argument("--base", default=f"{IE1}/games/ie1_eur.nds")
    ap.add_argument("--mods", default=f"{IE1}/mods")
    ap.add_argument("--wav", default=None, help="carpeta donde sacar las voces en .wav")
    ap.add_argument("--con-ingles", action="store_true",
                    help="no silenciar las voces que solo tiene la europea (tecnicas, goles rivales)")
    a = ap.parse_args(argv)
    jp = archivos(leer_rom(a.jp))
    base = archivos(leer_rom(a.base))
    if not any(r.startswith("/data_iz/sound/") for r in jp):
        sys.exit("Esa ROM no parece Inazuma Eleven 1 (no tiene data_iz/sound). No toco nada.")
    dest = os.path.join(a.mods, "voces_jp")
    shutil.rmtree(os.path.join(dest, "data_iz"), ignore_errors=True)   # restos de versiones anteriores
    os.makedirs(dest, exist_ok=True)

    def poner(ruta_en, datos):
        out = os.path.join(dest, ruta_en.lstrip("/"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(datos)

    # 1) voces y cancion del opening: los .SAD de sound (la japonesa no tiene carpetas de
    #    idioma); se emparejan por nombre con sound/en de la europea
    voces = cancion = 0
    iguales, solo_jp = [], []
    sad_jp = {r.rsplit("/", 1)[1].upper() for r in jp if r.startswith("/data_iz/sound/") and r.upper().endswith(".SAD")}
    for ruta, datos in sorted(jp.items()):
        if not ruta.startswith("/data_iz/sound/") or not ruta.upper().endswith(".SAD"):
            continue
        nombre = ruta.rsplit("/", 1)[1]
        ruta_en = "/data_iz/sound/en/" + nombre
        if ruta_en not in base:
            solo_jp.append(f"{nombre} ({len(datos) // 1024} KB)")
            continue
        if hashlib.sha1(base[ruta_en]).digest() == hashlib.sha1(datos).digest():
            iguales.append(nombre)
            continue
        poner(ruta_en, datos)
        if nombre.lower().startswith("op"):
            cancion += 1
        else:
            voces += 1
    # 2) video del opening: data_iz/movie/op00.mods
    video = 0
    for ruta, datos in jp.items():
        if ruta.lower().endswith("/op00.mods"):
            destino = next((r for r in base if r.lower().endswith("/op00.mods")), None)
            if destino and base[destino] != datos:
                poner(destino, datos)
                video += 1
            break
    # 3) sin subtitulos en el opening. op00.dat son entradas [inicio, fin, largo, texto] (u32,
    #    fotogramas del video); se deja una sola entrada vacia que empieza despues del final del
    #    video, asi el juego lee un archivo valido y no ensena nada. Va en todas las carpetas
    #    de idioma de la base (los paquetes de idioma usan la ruta de "en").
    vacio = struct.pack("<III", 0x7FFFFFF0, 0x7FFFFFFF, 4) + bytes(4)
    subtitulos = 0
    for ruta in base:
        if "/movie/txt/" in ruta and ruta.lower().endswith("/op00.dat"):
            poner(ruta, vacio)
            subtitulos += 1
    # 4) bancos de sonido de los partidos y escenas (.SWD + .SED) dentro de sound.pb
    sueltos = {r.rsplit("/", 1)[1]: d for r, d in jp.items()
               if r.startswith("/data_iz/sound/") and r.count("/") == 3 and r.upper().endswith((".SWD", ".SED", ".SMD"))}
    bancos_cambiados, bancos_solo_eu, silenciados = [], [], []
    for ruta_ph in sorted(r for r in base if r.startswith("/data_iz/sound/") and r.endswith("/sound.ph")):
        ruta_pb = ruta_ph[:-1] + "b"
        if ruta_pb not in base:
            continue
        entradas = leer_paquete(base[ruta_ph], base[ruta_pb])
        nombres_paquete = {n.upper() for n, _ in entradas}
        nuevas = []
        for nombre, datos in entradas:
            j = sueltos.get(nombre)
            if j is not None and j != datos:
                nuevas.append((nombre, j))
                if nombre.upper().endswith(".SWD"):
                    bancos_cambiados.append((nombre, datos, j))
            elif j is None and not a.con_ingles and voz_inglesa_sin_pareja(nombre, nombres_paquete):
                nuevas.append((nombre, silenciar_swd(datos)))
                silenciados.append(nombre)
                bancos_solo_eu.append((nombre, datos))
            else:
                nuevas.append((nombre, datos))
                if j is None and nombre.upper().endswith(".SWD"):
                    bancos_solo_eu.append((nombre, datos))
        if any(a[1] is not b[1] for a, b in zip(entradas, nuevas)):
            ph, pb = hacer_paquete(nuevas)
            poner(ruta_ph, ph)
            poner(ruta_pb, pb)
        if ruta_ph.startswith("/data_iz/sound/en/"):
            break
    if a.wav:
        for nombre, eu, j in bancos_cambiados:
            for etiqueta, d in (("eu", eu), ("jp", j)):
                for k, m in enumerate(muestras_swd(d)):
                    guardar_wav(os.path.join(a.wav, "cambian", nombre[:-4], f"{etiqueta}_{k:03d}.wav"), m)
        for nombre, eu in bancos_solo_eu:
            for k, m in enumerate(muestras_swd(eu)):
                guardar_wav(os.path.join(a.wav, "solo_europea", nombre[:-4], f"eu_{k:03d}.wav"), m)
        # pareja de cada banco de voces de tecnica de la europea (3D_NNN0): el banco 3D_NNN de
        # la misma tecnica, que es igual en las dos versiones (para ver si lleva las voces
        # japonesas originales)
        todos = dict(entradas)
        for nombre, _ in bancos_solo_eu:
            if len(nombre) == 11 and nombre.startswith("3D_") and nombre[6] == "0" and nombre[3:7].isdigit():
                par = nombre[:6] + ".SWD"
                if par in todos:
                    for k, m in enumerate(muestras_swd(todos[par])):
                        guardar_wav(os.path.join(a.wav, "tecnicas_banco_comun", par[:-4], f"{k:03d}.wav"), m)
    escribir_mod_txt(dest, FICHA)
    solo_eu = sorted(f"{r.rsplit('/', 1)[1]} ({len(d) // 1024} KB)" for r, d in base.items()
                     if r.startswith("/data_iz/sound/en/") and r.upper().endswith(".SAD")
                     and r.rsplit("/", 1)[1].upper() not in sad_jp)
    # informe para identificar los audios
    with open(os.path.join(dest, "informe_audios.txt"), "w", encoding="utf-8") as f:
        f.write("Audios .SAD: europea (sound/en) frente a japonesa\n\n")
        f.write(f"Iguales en las dos ({len(iguales)}):\n" + "".join(f"  {n}\n" for n in iguales))
        f.write(f"\nSolo en la europea, sin version japonesa ({len(solo_eu)}):\n" + "".join(f"  {n}\n" for n in solo_eu))
        f.write(f"\nSolo en la japonesa, sin sitio en la europea ({len(solo_jp)}):\n" + "".join(f"  {n}\n" for n in solo_jp))
        f.write(f"\n\nBancos de sonido (.SWD de sound.pb) que pasan a japones ({len(bancos_cambiados)}):\n")
        f.write("".join(f"  {n:<16} europea: {resumen_banco(e):<24} japonesa: {resumen_banco(j)}\n"
                        for n, e, j in bancos_cambiados))
        f.write(f"\nBancos que solo tiene la europea ({len(bancos_solo_eu)}; los marcados con * se silencian:"
                " voces inglesas de tecnicas y de goles rivales, que la japonesa no tiene):\n")
        f.write("".join(f"  {'*' if n in silenciados else ' '} {n:<16} {resumen_banco(e)}\n" for n, e in bancos_solo_eu))
    print(f"Voces de cinematicas: {voces}")
    print(f"Bancos de voces de partidos y escenas: {len(bancos_cambiados)} pasan a japones, "
          f"{len(bancos_solo_eu)} solo existen en la europea ({len(silenciados)} voces inglesas silenciadas)"
          + (f" (voces en .wav en {a.wav})" if a.wav else ""))
    print(f"Iguales en las dos: {len(iguales)}; solo en la europea: {len(solo_eu)}; solo en la japonesa: {len(solo_jp)}"
          f" (detalle en {os.path.join(dest, 'informe_audios.txt')})")
    print(f"Opening: cancion {'japonesa' if cancion else 'NO ENCONTRADA'}, "
          f"video {'japones' if video else 'NO ENCONTRADO'}, "
          f"subtitulos {'quitados (' + str(subtitulos) + ' idiomas)' if subtitulos else 'NO ENCONTRADOS'}")
    print("Mod creado en", dest, "- activa 'Voces japonesas' en Esc > Mods y reinicia")


if __name__ == "__main__":
    main()
