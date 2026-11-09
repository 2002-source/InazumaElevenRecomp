import struct
def lz10(d):
    if d[0] not in (0x10,0x11): return None
    size = d[1]|d[2]<<8|d[3]<<16
    out = bytearray(); p = 4
    if d[0]==0x10:
        while len(out) < size and p < len(d):
            f = d[p]; p += 1
            for b in range(8):
                if len(out) >= size: break
                if f & (0x80>>b):
                    x = d[p]<<8 | d[p+1]; p += 2
                    n = (x>>12)+3; disp = (x & 0xFFF)+1
                    for _ in range(n): out.append(out[-disp])
                else:
                    out.append(d[p]); p += 1
    else:
        while len(out) < size and p < len(d):
            f = d[p]; p += 1
            for b in range(8):
                if len(out) >= size: break
                if f & (0x80>>b):
                    i = d[p]>>4
                    if i == 0:
                        n = ((d[p]&15)<<4 | d[p+1]>>4) + 0x11; disp = ((d[p+1]&15)<<8 | d[p+2]) + 1; p += 3
                    elif i == 1:
                        n = ((d[p]&15)<<12 | d[p+1]<<4 | d[p+2]>>4) + 0x111; disp = ((d[p+2]&15)<<8 | d[p+3]) + 1; p += 4
                    else:
                        n = i + 1; disp = ((d[p]&15)<<8 | d[p+1]) + 1; p += 2
                    for _ in range(n): out.append(out[-disp])
                else:
                    out.append(d[p]); p += 1
    return bytes(out)

from PIL import Image
def bgr555(c): return ((c&31)*255//31, (c>>5&31)*255//31, (c>>10&31)*255//31)
def pac_parts(d):
    n = struct.unpack_from('<I', d, 0)[0]
    if n == 0 or n > 64: return None
    parts = []
    for i in range(n):
        off, size = struct.unpack_from('<II', d, 4 + 8*i)
        if off + size > len(d): return None
        parts.append(d[off:off+size])
    return parts
def render_bg(pal, mp, tiles, width=32, bpp=4):
    cols = [bgr555(struct.unpack_from('<H', pal, i)[0]) for i in range(0, len(pal)-1, 2)]
    ents = [struct.unpack_from('<H', mp, i)[0] for i in range(0, len(mp)-1, 2)]
    h = (len(ents) + width - 1)//width
    im = Image.new('RGBA', (width*8, h*8), (0,0,0,0))
    px = im.load()
    tsz = 32 if bpp == 4 else 64
    for k, e in enumerate(ents):
        t = e & 0x3FF; hf = e >> 10 & 1; vf = e >> 11 & 1; pb = e >> 12
        tx, ty = (k % width)*8, (k//width)*8
        base = t*tsz
        if base + tsz > len(tiles): continue
        for y in range(8):
            for x in range(8):
                if bpp == 4:
                    b = tiles[base + y*4 + x//2]; ci = (b >> 4) if x & 1 else (b & 15)
                    idx = pb*16 + ci if ci else 0
                else:
                    ci = tiles[base + y*8 + x]; idx = ci
                if ci == 0: continue
                c = cols[idx] if idx < len(cols) else cols[ci % len(cols)]
                xx = 7-x if hf else x; yy = 7-y if vf else y
                px[tx+xx, ty+yy] = c + (255,)
    return im

# ---------------------------------------------------------------------------
#  convertir_graficos.py
#  Convierte los paneles de menu (pic2d/*.pac y *.pac_) a PNG con su tamano real.
#  Uso: python scripts/convertir_graficos.py "D:/Inazuma Eleven 1 Port/Recursos"
#  (usa Recursos/archivos/ de extraer_recursos.py; para los textos en espanol,
#   pasa tambien --idioma C:/dev/ie1recomp/idiomas/es)
# ---------------------------------------------------------------------------
import argparse, csv, glob, os
from PIL import ImageDraw

def convertir(raiz, salida, filas, etiqueta=""):
    for f in sorted(glob.glob(os.path.join(raiz, "**", "*.pac*"), recursive=True)):
        if "pic2d" not in f.replace("\\", "/"):
            continue
        raw = open(f, "rb").read()
        d = lz10(raw) if f.endswith("_") else raw
        if not d:
            continue
        p = pac_parts(d)
        if not p or len(p) < 3:
            continue
        rel = os.path.relpath(f, raiz).replace("\\", "/")
        try:
            im = render_bg(p[0], p[1], p[2], 32)
        except Exception:
            continue
        if im.size[0] == 0 or im.size[1] == 0:
            continue
        nombre = rel.replace("/", "__").replace(".", "_") + etiqueta + ".png"
        try:
            im.save(os.path.join(salida, nombre))
        except Exception:
            continue
        filas.append([rel + etiqueta, nombre, im.size[0], im.size[1], len(p[0]) // 2, len(p[2]) // 32])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recursos")
    ap.add_argument("--idioma", help="carpeta de un paquete de idioma (p. ej. idiomas/es) para convertir tambien sus graficos")
    a = ap.parse_args()
    salida = os.path.join(a.recursos, "graficos")
    os.makedirs(salida, exist_ok=True)
    filas = []
    convertir(os.path.join(a.recursos, "archivos"), salida, filas)
    if a.idioma:
        convertir(a.idioma, salida, filas, "_es")
    with open(os.path.join(salida, "graficos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["archivo_original", "png", "ancho", "alto", "colores", "tiles"])
        w.writerows(filas)
    # Hoja de miniaturas para encontrar las piezas rapido
    W, H = 260, 200
    cols = 6
    filas_h = (len(filas) + cols - 1) // cols
    hoja = Image.new("RGB", (cols * W, max(1, filas_h) * (H + 14)), (40, 40, 40))
    dr = ImageDraw.Draw(hoja)
    for i, r in enumerate(filas):
        im = Image.open(os.path.join(salida, r[1]))
        im.thumbnail((W - 4, H - 4))
        x, y = (i % cols) * W, (i // cols) * (H + 14)
        hoja.paste(im, (x + 2, y + 14), im)
        dr.text((x + 2, y), r[0][-34:], fill=(255, 255, 0))
    hoja.save(os.path.join(salida, "_hoja.png"))
    print(f"{len(filas)} graficos convertidos en {salida} (lista en graficos.csv, vista rapida en _hoja.png)")

if __name__ == "__main__":
    main()
