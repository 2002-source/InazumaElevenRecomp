#!/usr/bin/env python3
"""
Genera el parche de los textos de interfaz que estan DENTRO del ARM9
(menus del mapa, zonas, mensajes del sistema) para el paquete de idioma.

Entrada: run/cadenas_<idioma>.json (de analizar_cadenas.py) e images/arm9.bin
Salida:  idiomas/<idioma>/arm9_textos.bin

Las cadenas traducidas se colocan en el espacio que ocupaban las inglesas
(reorganizandolas para que quepan) y se redirigen sus punteros, que estan
todos en tablas de datos. El codigo del juego no se toca.

Formato del archivo: "IE1T", n_verificar, [addr, len, bytes]..., n_escribir,
[addr, len, bytes]...  (todo little-endian, u32)

Uso (desde C:/dev/ie1recomp):
  python scripts/crear_parche_textos.py es
"""
import json, os, struct, sys

BASE = 0x02000000


def main():
    idioma = sys.argv[1] if len(sys.argv) > 1 else "es"
    datos = json.load(open(os.path.join("run", f"cadenas_{idioma}.json")))
    a9 = open(os.path.join("images", "arm9.bin"), "rb").read()

    huecos, verificar, cadenas, punteros = [], [], [], []
    en_sitio, sin_traducir = [], []
    reservados = set()
    rp = os.path.join("run", f"cadenas_reservadas.json")
    if os.path.exists(rp):
        reservados = {int(x, 16) for x in json.load(open(rp))}
    for k, v in datos.items():
        a = int(k, 16)
        en = bytes.fromhex(v["en"])
        es = bytes.fromhex(v["es"]) + b"\0"
        o = a - BASE
        if a9[o:o + len(en)] != en or a9[o + len(en)] != 0:
            sys.exit(f"La cadena 0x{a:08X} no coincide con images/arm9.bin; ¿ARM9 distinto?")
        fin = o + len(en) + 1
        while fin % 4 and a9[fin] == 0:          # relleno de alineacion
            fin += 1
        verificar.append((a, en + b"\0"))
        if v.get("fijo"):
            # Usado desde un overlay: solo se puede traducir en su sitio
            if len(es) <= BASE + fin - a:
                en_sitio.append((a, es + bytes(BASE + fin - a - len(es))))
            else:
                sin_traducir.append(a)
            continue
        huecos.append([a, BASE + fin])
        cadenas.append((a, es, [int(p, 16) for p in v["punteros"]]))
        for p in v["punteros"]:
            if struct.unpack_from("<I", a9, int(p, 16) - BASE)[0] != a:
                sys.exit(f"El puntero {p} no apunta a 0x{a:08X}")

    # Textos del curso de los jugadores (Album, fichas): el analisis no los empareja
    # porque el codigo los usa directamente (sin tabla). Se traducen en su sitio.
    extra = {
        "es": {0x020B02E0: b"%s\n3.~", 0x020B02F8: b"%s\n1.~", 0x020B0318: b"%s\n2.~",
               0x020B0358: b"%s 1.~", 0x020B0398: b"%s 3.~", 0x020B03A0: b"%s 2.~"},
    }
    for a, es in extra.get(idioma, {}).items():
        o = a - BASE
        fin = a9.index(b"\0", o) + 1
        en = a9[o:fin]
        if len(es) + 1 <= len(en) and not any(v[0] == a for v in en_sitio):
            verificar.append((a, en))
            en_sitio.append((a, es + bytes(len(en) - len(es))))

    def unir(hs):
        hs = sorted(hs)
        res = []
        for ini, fin in hs:
            if res and res[-1][1] == ini:
                res[-1][1] = fin
            else:
                res.append([ini, fin])
        return res

    def colocar(cads, hs):
        """Coloca los textos (sin repetir: textos iguales o finales de otro texto
        comparten memoria). Devuelve (escrituras, huecos sobrantes) o None."""
        libres = unir([list(h) for h in hs])
        sitio = {}                               # texto -> direccion
        escr = []
        for t in sorted({c[1] for c in cads}, key=len, reverse=True):
            # Reutilizar si es el final de un texto ya colocado (mismo 0 final)
            reuso = next((d + len(u) - len(t) for u, d in sitio.items() if u.endswith(t)), None)
            if reuso is not None:
                sitio[t] = reuso
                continue
            mejor = None
            for h in libres:
                if h[1] - h[0] >= len(t) and (mejor is None or h[1] - h[0] < mejor[1] - mejor[0]):
                    mejor = h
            if mejor is None:
                return None
            sitio[t] = mejor[0]
            escr.append((mejor[0], t))
            mejor[0] += len(t)
        for a, t, ptrs in cads:
            for p in ptrs:
                escr.append((p, struct.pack("<I", sitio[t])))
        return escr, libres

    # Si no cabe todo, se dejan en ingles los textos que mas espacio de mas
    # necesitan (su hueco se conserva intacto) hasta que el resto quepa.
    tam_hueco = {a: f - a for a, f in huecos}
    activos, en_ingles = list(cadenas), []
    while True:
        r = colocar(activos, [h for h in huecos if h[0] in {c[0] for c in activos}])
        if r is not None:
            break
        peor = max(activos, key=lambda c: len(c[1]) - tam_hueco[c[0]])
        activos.remove(peor)
        en_ingles.append(peor[0])
    escrituras_txt, libres = r
    escrituras = list(en_sitio) + escrituras_txt
    total_libre = sum(tam_hueco[c[0]] for c in activos)
    cadenas = activos
    if en_ingles:
        print(f"{len(en_ingles)} textos no caben y se quedan en ingles: " +
              ", ".join(f"0x{a:08X}" for a in en_ingles[:10]) + (" ..." if len(en_ingles) > 10 else ""))
    # Rellenar con ceros lo que sobra de los huecos
    for ini, fin in libres:
        if fin > ini:
            escrituras.append((ini, bytes(fin - ini)))

    out_dir = os.path.join("idiomas", idioma)
    os.makedirs(out_dir, exist_ok=True)
    out = bytearray(b"IE1T")
    out += struct.pack("<I", len(verificar))
    for a, b in verificar:
        out += struct.pack("<II", a, len(b)) + b
    out += struct.pack("<I", len(escrituras))
    for a, b in escrituras:
        out += struct.pack("<II", a, len(b)) + b
    ruta = os.path.join(out_dir, "arm9_textos.bin")
    open(ruta, "wb").write(out)
    usado = sum(len(c[1]) for c in cadenas)
    if sin_traducir:
        print(f"{len(sin_traducir)} textos usados desde overlays no caben en su sitio y quedan en ingles")
    print(f"{len(en_sitio)} textos traducidos en su sitio (usados desde overlays)")
    print(f"{len(cadenas)} textos: {usado} bytes en {total_libre} disponibles "
          f"({len(libres)} zonas). Parche: {ruta} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
