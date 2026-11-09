#!/usr/bin/env python3
"""
Crea el mod 'npc_entrenador': un NPC nuevo junto a la Torre (mapa mr02b13) que
ofrece el entrenamiento. NO toca la ROM: lee tus archivos y genera otros nuevos
dentro de mods/npc_entrenador/.

  python scripts/crear_npc_entrenador.py            (usa games/ie1_eur.nds e idiomas/es)
  python scripts/crear_npc_entrenador.py --dx 2 --dz 0 --angulo 90

Como funciona:
  - Guion 80000350 (colocacion de NPC de la torre): se anade la unidad 1696
    ("Old man 6", mismo aspecto que el senor de la torre, unidad 1691) junto a el.
  - Guion 81000350 (conversaciones de la torre): se anade un caso para la
    unidad 1696 con la pregunta Si/No (copiada de la estructura de Mr Veteran).
  - Textos nuevos en ingles y en espanol (paquetes evet de cada idioma).
Despues: activa el mod en Esc > Mods y reinicia.
"""
import argparse, os, struct, sys

IE1 = "C:/dev/ie1recomp"
UNIDAD_NUEVA = 1696          # "Old man 6": mismo aspecto que el Old man 1 (1691)
UNIDAD_MODELO = 1691
# Guiones de cada mapa (de los repartidores 88000001 y 89000001):
#   torre       = mr02b02 (la del Old man y la farola)
#   plataforma  = mr02b13 (arriba de la torre)
MAPAS = {"torre": (80000350, 81000350), "plataforma": (80000450, 81000450)}
GUION_OLDMAN = 80000350      # de aqui se copian las instrucciones de colocacion del Old man
GUION_COLOCACION = 80000450
GUION_DIALOGOS = 81000450
SENAL = 0x51E7A1A5           # valor que el complemento reconoce (ie1_mods.cpp, kSenal)
VARIABLE_SENAL = 0x10021     # variable global 0x21 (dentro del rango usado, pero ningun guion la usa)

TEXTOS = {
    "en": ["I am a master at training.\\nDo you want to try it?",
           "Let's get started!",
           "Come back whenever you want\\nto train."],
    "es": ["Soy un maestro en el entrenamiento.\\n\u00bfQuieres probarlo?",
           "\u00a1Pues empecemos!",
           "Vuelve cuando quieras entrenar."],
}
# Letras con tilde -> tabla propia del juego (fuentes, codigos 0xA1-0xDF)
TABLA = {"\u00e1": 0xB2, "\u00e9": 0xBA, "\u00ed": 0xBE, "\u00f3": 0xC4, "\u00fa": 0xCA, "\u00f1": 0xC2,
         "\u00d1": 0xA9, "\u00fc": 0xCC, "\u00c1": 0xD1, "\u00c9": 0xD9, "\u00cd": 0xA6, "\u00d3": 0xAB,
         "\u00da": 0xA2, "\u00bf": 0xA5, "\u00a1": 0xDF}

def a_juego(t):
    out = bytearray()
    for ch in t:
        if ch in TABLA: out.append(TABLA[ch])
        elif ord(ch) < 0x80: out.append(ord(ch))
        else: raise SystemExit(f"Caracter no admitido en el texto: {ch!r}")
    return bytes(out)

# ---------------------------------------------------------------- ROM ------
def archivo_rom(rom, ruta):
    u32 = lambda o: struct.unpack_from("<I", rom, o)[0]
    u16 = lambda o: struct.unpack_from("<H", rom, o)[0]
    fnt, fat = u32(0x40), u32(0x48)
    partes = ruta.strip("/").split("/")
    did = 0xF000
    for i, parte in enumerate(partes):
        ent = fnt + (did & 0xFFF) * 8
        p = fnt + u32(ent); fid = u16(ent + 4)
        encontrado = None
        while True:
            n = rom[p]; p += 1
            if n == 0: break
            nombre = rom[p:p + (n & 0x7F)].decode("latin-1"); p += n & 0x7F
            if n & 0x80:
                sid = u16(p); p += 2
                if nombre == parte and i < len(partes) - 1: encontrado = ("d", sid); break
            else:
                if nombre == parte and i == len(partes) - 1: encontrado = ("f", fid); break
                fid += 1
        if not encontrado: raise SystemExit(f"No esta en la ROM: {ruta}")
        if encontrado[0] == "d": did = encontrado[1]
        else:
            s, e = u32(fat + 8 * encontrado[1]), u32(fat + 8 * encontrado[1] + 4)
            return rom[s:e]

# ---------------------------------------------------------------- LZ10 -----
def lz10_des(d):
    n = d[1] | d[2] << 8 | d[3] << 16
    out = bytearray(); p = 4
    while len(out) < n:
        f = d[p]; p += 1
        for b in range(8):
            if len(out) >= n: break
            if f & (0x80 >> b):
                x = d[p] << 8 | d[p + 1]; p += 2
                ln, disp = (x >> 12) + 3, (x & 0xFFF) + 1
                for _ in range(ln): out.append(out[-disp])
            else:
                out.append(d[p]); p += 1
    return bytes(out)

def lz10_com(d):
    out = bytearray([0x10, len(d) & 0xFF, len(d) >> 8 & 0xFF, len(d) >> 16 & 0xFF])
    pos, n = 0, len(d)
    indice = {}
    while pos < n:
        flag_pos = len(out); out.append(0); flag = 0
        for b in range(8):
            if pos >= n: break
            mejor_ln, mejor_d = 0, 0
            if pos + 3 <= n:
                for cand in reversed(indice.get(d[pos:pos + 3], [])[-64:]):
                    dist = pos - cand
                    if dist > 4096: break
                    ln = 3
                    while ln < 18 and pos + ln < n and d[cand + ln] == d[pos + ln]: ln += 1
                    if ln > mejor_ln: mejor_ln, mejor_d = ln, dist
                    if ln == 18: break
            avanza = mejor_ln if mejor_ln >= 3 else 1
            if mejor_ln >= 3:
                flag |= 0x80 >> b
                v = (mejor_ln - 3) << 12 | (mejor_d - 1)
                out += bytes([v >> 8, v & 0xFF])
            else:
                out.append(d[pos])
            for k in range(avanza):
                if pos + k + 3 <= n: indice.setdefault(d[pos + k:pos + k + 3], []).append(pos + k)
            pos += avanza
        out[flag_pos] = flag
    while len(out) % 4: out.append(0)
    return bytes(out)

# ---------------------------------------------------------------- PK -------
def pk_leer(h, b):
    ents = []
    for o in range(0x30, len(h) - 11, 12):
        i, of, sz = struct.unpack_from("<3I", h, o)
        if i == 0xFFFFFFFF: break
        ents.append([i, b[of:of + sz]])
    return ents

def pk_escribir(h_orig, ents):
    h = bytearray(h_orig); b = bytearray()
    for k, (i, datos) in enumerate(ents):
        while len(b) % 16: b.append(0)
        struct.pack_into("<3I", h, 0x30 + 12 * k, i, len(b), len(datos))
        b += datos
    struct.pack_into("<I", h, 0x1C, max(max(len(d) for _, d in ents), struct.unpack_from("<I", h, 0x1C)[0]))
    return bytes(h), bytes(b)

# ---------------------------------------------------------------- SSD ------
class Instr:
    def __init__(s, raw):
        s.raw = bytearray(raw)
    @property
    def idx(s): return struct.unpack_from("<H", s.raw, 0)[0]
    @idx.setter
    def idx(s, v): struct.pack_into("<H", s.raw, 0, v)
    @property
    def etiqueta(s): return struct.unpack_from("<H", s.raw, 2)[0] == 0
    @property
    def op(s): return None if s.etiqueta else struct.unpack_from("<H", s.raw, 4)[0]
    @property
    def argc(s): return 0 if s.etiqueta else s.raw[6]
    def tipo(s, k):
        byte = s.raw[8 + k // 2]
        return (byte >> 4) & 15 if k % 2 else byte & 15
    def _off(s, k): return 8 + ((s.argc + 1) // 2 + 3) // 4 * 4 + 4 * k
    def arg(s, k): return struct.unpack_from("<I", s.raw, s._off(k))[0]
    def set(s, k, v): struct.pack_into("<I", s.raw, s._off(k), v & 0xFFFFFFFF)
    def args(s): return [s.arg(k) for k in range(s.argc)]
    def copia(s): return Instr(bytes(s.raw))

def ssd_leer(d):
    assert d[:4] == b"SSD\0"
    ins, o = [], 0x20
    while o + 4 <= len(d):
        size = struct.unpack_from("<H", d, o + 2)[0]
        if size == 0: ins.append(Instr(d[o:o + 4])); o += 4; continue
        ins.append(Instr(d[o:o + size])); o += size
    return bytearray(d[:0x20]), ins

def es_referencia(ins, k):
    return ins.tipo(k) == 4 or (ins.op in (0x6001, 0x6002) and k == 1)

def ssd_insertar(ins, despues_de_idx, nuevas):
    """Inserta 'nuevas' detras de la instruccion con indice 'despues_de_idx' y renumera."""
    pos = next(i for i, x in enumerate(ins) if x.idx == despues_de_idx) + 1
    n, primero = len(nuevas), despues_de_idx + 1
    for x in ins:
        for k in range(x.argc):
            if es_referencia(x, k) and x.arg(k) >= primero: x.set(k, x.arg(k) + n)
        if x.idx >= primero: x.idx = x.idx + n
    for k, x in enumerate(nuevas): x.idx = primero + k
    ins[pos:pos] = nuevas
    return primero

def ssd_escribir(cab, ins, tam_textos, n_textos):
    cuerpo = b"".join(bytes(x.raw) for x in ins)
    d = bytearray(cab) + cuerpo
    struct.pack_into("<I", d, 0x08, len(d) + tam_textos)
    struct.pack_into("<H", d, 0x0C, len(ins))
    struct.pack_into("<H", d, 0x0E, n_textos)
    struct.pack_into("<I", d, 0x10, len(d) - 32)
    struct.pack_into("<I", d, 0x14, tam_textos)
    return bytes(d)

OTROS_GUIONES = []   # guiones extra donde buscar ejemplos de instrucciones

def plantilla(ins, op, tipos=None):
    for lista in [ins] + OTROS_GUIONES:
        for x in lista:
            if x.op == op and (tipos is None or [x.tipo(k) for k in range(x.argc)] == tipos):
                return x.copia()
    raise SystemExit(f"No encontre una instruccion de ejemplo 0x{op:04X} {tipos}")

def nueva(ins, op, tipos, args):
    x = plantilla(ins, op, tipos)
    for k, v in enumerate(args): x.set(k, v)
    return x

# ---------------------------------------------------------------- EVET -----
def evet_leer(d):
    ents, o = [], 4
    while o + 8 <= len(d):
        idx, tipo, tam = struct.unpack_from("<HHI", d, o)
        if tam < 8: break
        ents.append([idx, tipo, d[o + 8:o + tam]]); o += tam
    return ents

def evet_escribir(ents):
    b = bytearray(4)
    for idx, tipo, datos in ents:
        b += struct.pack("<HHI", idx, tipo, 8 + len(datos)) + datos
    struct.pack_into("<I", b, 0, len(b) - 4)
    return bytes(b)

def entrada_texto(idx, texto):
    t = a_juego(texto) + b"\0"
    while len(t) % 4: t += b"\0"
    return [idx, 1, t]

# ---------------------------------------------------------------- MAIN -----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=f"{IE1}/games/ie1_eur.nds")
    ap.add_argument("--es", default=f"{IE1}/idiomas/es/data_iz/script/en/evet.pkb",
                    help="evet.pkb en espanol (del paquete de idioma)")
    ap.add_argument("--mapa", choices=list(MAPAS), default="plataforma",
                    help="mapa donde va el NPC: 'plataforma' (arriba de la torre, mr02b13) o 'torre' (mr02b02)")
    ap.add_argument("--dx", type=float, default=0.0, help="desplazamiento en X respecto a la referencia del mapa (unidades)")
    ap.add_argument("--dz", type=float, default=0.0, help="desplazamiento en Z respecto al Old man")
    ap.add_argument("--x", type=float, default=None, help="posicion X absoluta (en lugar de --dx)")
    ap.add_argument("--z", type=float, default=None, help="posicion Z absoluta (en lugar de --dz)")
    ap.add_argument("--y", type=float, default=None, help="altura (por defecto, la del Old man)")
    ap.add_argument("--desde", type=int, default=10150,
                    help="progreso minimo de la historia (variable 0x10004) para que aparezca; 0 = siempre")
    ap.add_argument("--angulo", type=int, default=90, help="orientacion en grados (90 = como el Old man)")
    ap.add_argument("--variante", choices=["juego", "envuelta"], default="juego",
                    help="estructura del dialogo: 'juego' (igual que los Si/No del juego) o 'envuelta' (version 1)")
    ap.add_argument("--hablante", type=int, default=0, help="unidad que 'habla' en el cuadro (por defecto, la del NPC)")
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    eve_h, eve_b = archivo_rom(rom, "/data_iz/script/eve.pkh"), archivo_rom(rom, "/data_iz/script/eve.pkb")
    evet = {"en": (archivo_rom(rom, "/data_iz/script/en/evet.pkh"), archivo_rom(rom, "/data_iz/script/en/evet.pkb"))}
    if os.path.exists(a.es) and os.path.exists(a.es[:-4] + ".pkh"):
        evet["es"] = (open(a.es[:-4] + ".pkh", "rb").read(), open(a.es, "rb").read())
    else:
        print("Aviso: no encontre evet.pkb/evet.pkh en espanol (" + a.es + "); solo se generara el ingles.")
    E = pk_leer(eve_h, eve_b)
    for i, d in E[:40]:                          # ejemplos de instrucciones de otros guiones
        try:
            dd = lz10_des(d)
            if dd[:4] == b"SSD\0": OTROS_GUIONES.append(ssd_leer(dd)[1])
        except Exception:
            pass
    global GUION_COLOCACION, GUION_DIALOGOS
    GUION_COLOCACION, GUION_DIALOGOS = MAPAS[a.mapa]
    guiones = {i: lz10_des(d) for i, d in E if i in (GUION_COLOCACION, GUION_DIALOGOS)}
    _, ins_om = ssd_leer(lz10_des(next(d for i, d in E if i == GUION_OLDMAN)))

    # --- 1) Colocacion: bloque propio al final del guion ----------------------
    #   si (progreso >= DESDE) { crear la unidad; posicion; orientacion }
    # Independiente de los bloques del juego: aparece aunque el Old man no este.
    cab, ins = ssd_leer(guiones[GUION_COLOCACION])
    OTROS_GUIONES.insert(0, ins_om)
    pos_om = next(x for x in ins_om if x.op == 0x305A and x.arg(0) == UNIDAD_MODELO)
    dir_om = next(x for x in ins_om if x.op == 0x305C and x.arg(0) == UNIDAD_MODELO)
    x0, y0, z0 = [struct.unpack("<i", struct.pack("<I", pos_om.arg(k)))[0] for k in (2, 3, 4)]
    if a.mapa == "plataforma":                   # referencia: el centro de la camara del mapa
        x0, y0, z0 = int(6.0 * 4096), int(3.3 * 4096), int(-2.5 * 4096)
    nx = int(a.x * 4096) if a.x is not None else x0 + int(a.dx * 4096)
    nz = int(a.z * 4096) if a.z is not None else z0 + int(a.dz * 4096)
    ny = int(a.y * 4096) if a.y is not None else y0
    crear = next(x for x in ins_om if x.op == 0x3058 and x.arg(0) == UNIDAD_MODELO).copia()
    crear.set(0, UNIDAD_NUEVA); crear.set(1, 0)
    pos = pos_om.copia(); pos.set(0, UNIDAD_NUEVA); pos.set(1, 0)
    pos.set(2, nx); pos.set(3, ny); pos.set(4, nz)
    ori = dir_om.copia(); ori.set(0, UNIDAD_NUEVA); ori.set(1, 0); ori.set(2, a.angulo * 4096)
    fin_main = max(x.idx for x in ins if x.op == 0x6002 and x.arg(0) == 0)   # cierre del bloque principal
    b0 = fin_main
    bloque = []
    cond = nueva(ins, 0x6008, [4], [b0 + 1]); bloque.append(cond)
    bloque.append(nueva(ins, 0x7006, [1, 5], [a.desde, 0x10004]))          # DESDE <= progreso
    abre = nueva(ins, 0x6001, [1, 1], [1, b0 + 6]); bloque.append(abre)
    bloque += [crear, pos, ori]
    bloque.append(nueva(ins, 0x6002, [1, 1], [1, b0 + 2]))
    ssd_insertar(ins, fin_main - 1, bloque)
    guiones[GUION_COLOCACION] = ssd_escribir(cab, ins, 0, struct.unpack_from("<H", cab, 0x0E)[0])
    print(f"Colocacion: unidad {UNIDAD_NUEVA} en x={nx / 4096:.2f} y={ny / 4096:.2f} z={nz / 4096:.2f}, "
          f"{a.angulo} grados, con progreso de la historia >= {a.desde} "
          f"(referencia del mapa '{a.mapa}': x={x0 / 4096:.2f} z={z0 / 4096:.2f})")

    # --- 2) Dialogo: caso nuevo en el guion de conversaciones ---------------
    cab, ins = ssd_leer(guiones[GUION_DIALOGOS])
    textos_por_idioma = {}
    for lang, (h, b) in evet.items():
        T = pk_leer(h, b)
        textos_por_idioma[lang] = (T, evet_leer(lz10_des(next(d for i, d in T if i == GUION_DIALOGOS))))
    n_txt = len(textos_por_idioma["en"][1])
    for lang, (_, ents) in textos_por_idioma.items():
        if len(ents) != n_txt:
            raise SystemExit(f"El guion de textos en '{lang}' tiene {len(ents)} entradas y el ingles {n_txt}; no coinciden.")
    N = lambda op, tipos, args: nueva(ins, op, tipos, args)
    nuevas = []
    def emit(x): nuevas.append(x); return base + len(nuevas) - 1
    tiene_switch = any(x.op == 0x4015 for x in ins)
    if tiene_switch:
        # el caso nuevo va justo antes del final del switch de unidades (tras el ultimo caso)
        fin_switch = max(x.idx for x in ins if x.op == 0x6002 and x.arg(0) == 1)
        ancla = fin_switch - 1                   # 0x600E [2] que cierra el ultimo caso
        base = ancla + 1
    else:
        # mapa sin conversaciones: el repartidor 89000001 llama a su funcion 0x2000
        # (8192), que esta vacia. Se mete dentro el "segun con quien hables".
        ancla = next(x.idx for x in ins if x.op == 0x6001 and x.arg(0) == 0)   # inicio del cuerpo
        base = ancla + 1
        i_sw = emit(N(0x600B, [4], [0]))
        i_u = emit(N(0x4015, [], []))            # unidad con la que hablas
        nuevas[i_sw - base].set(0, i_u)
        i_s1 = emit(N(0x6001, [1, 1], [1, 0]))
    hablante = a.hablante or UNIDAD_NUEVA
    emit(N(0x600D, [1, 1], [2, UNIDAD_NUEVA]))                  # caso unidad nueva
    if a.variante == "envuelta":                                # version 1: dentro de un "si" siempre cierto
        i_c = emit(N(0x6008, [4], [0]))
        i_cond = emit(N(0x7006, [1, 5], [0, 0x10004]))
        nuevas[i_c - base].set(0, i_cond)
        i_b2 = emit(N(0x6001, [1, 1], [2, 0]))
        nivel = 3
    else:                                                       # como los casos Si/No del propio juego
        nivel = 2
    emit(N(0x301A, [1, 1, 1, 1], [1, hablante, 0, 1]))
    emit(N(0x301D, [3], [n_txt]))                               # pregunta
    i_q = len(nuevas) - 1 + base
    # El byte 7 de 0x301D indica si el mensaje espera a que pulses A (1) o si
    # sigue sin esperar (0). Las preguntas usan 0 para que aparezca el Si/No.
    nuevas[i_q - base].raw[7] = 0
    emit(N(0x3057, [], []))                                     # Si / No
    i_c2 = emit(N(0x6008, [4], [0]))
    i_si = emit(N(0x4020, [], []))
    nuevas[i_c2 - base].set(0, i_si)
    i_b3 = emit(N(0x6001, [1, 1], [nivel, 0]))                  # si ha dicho Si
    emit(N(0x301A, [1, 1, 1, 1], [1, hablante, 0, 1]))
    emit(N(0x301D, [3], [n_txt + 1]))                           # "Empecemos"
    i_t2 = len(nuevas) - 1 + base
    emit(N(0x301E, [], []))
    # Senal para el complemento de mods: variable 0x10021 (ningun guion original
    # la usa) = SENAL. El complemento la detecta, abre el menu de
    # entrenamiento y la vuelve a poner a 0.
    emit(N(0x7001, [6, 1], [VARIABLE_SENAL, SENAL]))
    emit(N(0x600E, [1], [nivel + 1]))
    i_e3 = emit(N(0x6002, [1, 1], [nivel, i_b3])); nuevas[i_b3 - base].set(1, i_e3)
    emit(N(0x600C, [1], [nivel]))                               # si no
    i_b4 = emit(N(0x6001, [1, 1], [nivel, 0]))
    emit(N(0x301A, [1, 1, 1, 1], [1, hablante, 0, 1]))
    emit(N(0x301D, [3], [n_txt + 2]))                           # "Vuelve cuando quieras"
    i_t3 = len(nuevas) - 1 + base
    emit(N(0x301E, [], []))
    emit(N(0x600E, [1], [nivel + 1]))
    i_e4 = emit(N(0x6002, [1, 1], [nivel, i_b4])); nuevas[i_b4 - base].set(1, i_e4)
    emit(N(0x600E, [1], [nivel]))
    if a.variante == "envuelta":
        i_e2 = emit(N(0x6002, [1, 1], [2, i_b2])); nuevas[i_b2 - base].set(1, i_e2)
        emit(N(0x600E, [1], [2]))
    if not tiene_switch:
        i_s2 = emit(N(0x6002, [1, 1], [1, i_s1])); nuevas[i_s1 - base].set(1, i_s2)
    ssd_insertar(ins, ancla, nuevas)

    tam_max = 0
    for lang, (T, ents) in textos_por_idioma.items():
        for e in ents:                                          # renumerar los textos posteriores
            if e[0] > ancla: e[0] += len(nuevas)
        t = TEXTOS[lang]
        ents += [entrada_texto(i_q, t[0]), entrada_texto(i_t2, t[1]), entrada_texto(i_t3, t[2])]
        datos = evet_escribir(ents)
        tam_max = max(tam_max, len(datos) - 4)
        for k, (i, d) in enumerate(T):
            if i == GUION_DIALOGOS: T[k][1] = lz10_com(datos)
    guiones[GUION_DIALOGOS] = ssd_escribir(cab, ins, tam_max, n_txt + 3)
    print(f"Dialogo: caso para la unidad {UNIDAD_NUEVA} (instrucciones {base}-{base + len(nuevas) - 1}), "
          f"textos {n_txt}-{n_txt + 2}")

    # --- 3) Escribir el mod: solo las piezas que cambian ----------------------
    #   pk/eve/<id>.lz            guion (comprimido LZ10, como en el paquete)
    #   pk/evet/<idioma>/<id>.lz  textos de ese guion en ese idioma
    #   El complemento de mods las combina con los paquetes originales al arrancar.
    dest = f"{IE1}/mods/npc_entrenador"
    import shutil
    for viejo in ("data_iz", "idioma", "pk"):                 # restos de versiones anteriores
        shutil.rmtree(os.path.join(dest, viejo), ignore_errors=True)
    def guardar(rel, datos):
        p = os.path.join(dest, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(datos)
    for i, d in guiones.items():
        guardar(f"pk/eve/{i}.lz", lz10_com(d))
    for lang, (T, _) in textos_por_idioma.items():
        guardar(f"pk/evet/{lang}/{GUION_DIALOGOS}.lz", next(d for i, d in T if i == GUION_DIALOGOS))
    escribir_mod_txt(dest, {
        "nombre": "NPC entrenador", "nombre_en": "Trainer NPC",
        "descripcion": "Un entrenador en la plataforma de arriba de la Torre que te ofrece el menu de entrenamiento libre.",
        "descripcion_en": "A trainer on the top platform of the Tower who offers you the free training menu.",
        "desbloqueo": "Termina la historia (gana el Futbol Frontier) y sube a la plataforma de la Torre.",
        "desbloqueo_en": "Finish the story (win the Football Frontier) and go up to the Tower platform.",
    })
    # el menu de entrenamiento (tu diseno) se abre con este NPC: su informacion tambien
    entr = os.path.join(os.path.dirname(dest), "entrenamiento_libre")
    if os.path.isdir(entr):
        escribir_mod_txt(entr, {
            "nombre": "Entrenamiento libre", "nombre_en": "Free training",
            "descripcion": "Menu para entrenar a tus jugadores: sube su nivel, PE, PT y estadisticas a cambio de Pasion.",
            "descripcion_en": "Menu to train your players: raise their level, GP, TP and stats in exchange for Passion.",
            "desbloqueo": "Se abre hablando con el NPC entrenador de la Torre (activa tambien ese mod).",
            "desbloqueo_en": "Opened by talking to the trainer NPC at the Tower (turn that mod on too).",
        })
    print("Mod creado en", dest, "- activalo en Esc > Mods")

def escribir_mod_txt(carpeta, campos):
    """Escribe o actualiza mod.txt (clave=valor), conservando las claves que ya tenga."""
    ruta = os.path.join(carpeta, "mod.txt")
    actual = {}
    if os.path.exists(ruta):
        for l in open(ruta, encoding="utf-8", errors="replace"):
            if "=" in l and not l.startswith("#"):
                k, v = l.rstrip("\r\n").split("=", 1); actual[k] = v
    actual.update(campos)
    open(ruta, "w", encoding="utf-8").write("".join(f"{k}={v}\n" for k, v in actual.items()))


if __name__ == "__main__":
    main()
