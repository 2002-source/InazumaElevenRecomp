#!/usr/bin/env python3
"""
Lista los archivos que son DISTINTOS entre la ROM inglesa y la espanola, y si
el paquete de idioma (idiomas/es) los incluye o no.

  python scripts/comparar_roms.py games/ie1_eur.nds "RUTA/ie1_eur_es.nds"

Resultado en pantalla y en run/diferencias_roms.txt
"""
import hashlib, os, struct, sys


def archivos(rom):
    u32 = lambda o: struct.unpack_from("<I", rom, o)[0]
    u16 = lambda o: struct.unpack_from("<H", rom, o)[0]
    fnt, fat = u32(0x40), u32(0x48)
    res = {}
    def rec(did, ruta, prof=0):
        if prof > 32: return
        ent = fnt + (did & 0xFFF) * 8
        p = fnt + u32(ent); fid = u16(ent + 4)
        while True:
            n = rom[p]; p += 1
            if not n: break
            nom = rom[p:p + (n & 0x7F)].decode("latin-1"); p += n & 0x7F
            if n & 0x80:
                sid = u16(p); p += 2
                rec(sid, ruta + nom + "/", prof + 1)
            else:
                s, e = u32(fat + 8 * fid), u32(fat + 8 * fid + 4)
                res[ruta + nom] = hashlib.sha1(rom[s:e]).hexdigest() + f" {e - s}"
                fid += 1
    rec(0xF000, "/")
    return res


def main():
    en = archivos(open(sys.argv[1], "rb").read())
    es = archivos(open(sys.argv[2], "rb").read())
    paquete = sys.argv[3] if len(sys.argv) > 3 else "C:/dev/ie1recomp/idiomas/es"
    lineas = []
    for ruta in sorted(set(en) | set(es)):
        if en.get(ruta) == es.get(ruta):
            continue
        en_paquete = os.path.exists(os.path.join(paquete, ruta.lstrip("/")))
        estado = "solo EN" if ruta not in es else "solo ES" if ruta not in en else "distinto"
        lineas.append(f"{'PAQUETE ' if en_paquete else 'FALTA   '} {estado:8s} {ruta}  "
                      f"(en {en.get(ruta, '-').split()[-1]} / es {es.get(ruta, '-').split()[-1]} bytes)")
    faltan = [l for l in lineas if l.startswith("FALTA")]
    texto = "\n".join(lineas) + f"\n\n{len(lineas)} archivos distintos; {len(faltan)} NO estan en el paquete\n"
    os.makedirs("C:/dev/ie1recomp/run", exist_ok=True)
    open("C:/dev/ie1recomp/run/diferencias_roms.txt", "w", encoding="utf-8").write(texto)
    print("\n".join(faltan[:80]))
    print(f"\n{len(lineas)} archivos distintos; {len(faltan)} NO estan en el paquete "
          f"(lista completa en run/diferencias_roms.txt)")


if __name__ == "__main__":
    main()
