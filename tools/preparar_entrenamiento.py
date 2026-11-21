#!/usr/bin/env python3
"""
Crea el mod 'entrenamiento_libre' a partir de tu diseno del menu (PNG 256x192).
  python scripts/preparar_entrenamiento.py "D:/Inazuma Eleven 1 Port/Menu_Nuevo_Entrenamiento_en_espanol.png"
Despues: crea el NPC (crear_npc_entrenador.py), activa el mod en Esc > Mods y habla
con el entrenador en lo alto de la Torre.
"""
import os, struct, sys
from PIL import Image
if len(sys.argv) < 2:
    sys.exit(__doc__)
import glob
ruta = sys.argv[1]
if not os.path.isfile(ruta):
    # Acepta una carpeta o un nombre aproximado: busca el PNG del menu
    base = ruta if os.path.isdir(ruta) else os.path.dirname(ruta) or "."
    candidatos = [f for f in glob.glob(os.path.join(base, "**", "*.png"), recursive=True)
                  if "entrenamiento" in os.path.basename(f).lower()]
    espanol = [f for f in candidatos if "espa" in os.path.basename(f).lower()]
    if espanol: candidatos = espanol
    if not candidatos:
        sys.exit(f"No encontre ninguna imagen del menu en {base}. Archivos PNG que hay: "
                 + ", ".join(glob.glob(os.path.join(base, "*.png"))[:10]))
    ruta = candidatos[0]
    print("Usando", ruta)
im = Image.open(ruta).convert("RGB")
if im.size != (256, 192):
    sys.exit(f"La imagen debe ser de 256x192 (es {im.size[0]}x{im.size[1]}).")
dest = os.path.join("C:/dev/ie1recomp/mods", "entrenamiento_libre")
os.makedirs(dest, exist_ok=True)
datos = bytearray()
for y in range(192):
    for x in range(256):
        r, g, b = im.getpixel((x, y))
        datos += struct.pack("<I", 0xFF000000 | r << 16 | g << 8 | b)
open(os.path.join(dest, "fondo_entrenamiento.argb"), "wb").write(datos)


def guardar_argb(img, nombre):
    b = bytearray()
    for yy in range(192):
        for xx in range(256):
            r, g, bl = img.getpixel((xx, yy))
            b += struct.pack("<I", 0xFF000000 | r << 16 | g << 8 | bl)
    open(os.path.join(dest, nombre), "wb").write(b)


# Fondos por idioma: el diseno en espanol, el ingles (si esta junto al espanol) y uno limpio
# sin textos; en los demas idiomas el complemento pone las etiquetas del juego (msup_bg02)
# y la palabra "Libertad" con la fuente del juego.
guardar_argb(im, "fondo_entrenamiento_es.argb")
ingles = [f for f in glob.glob(os.path.join(os.path.dirname(ruta) or ".", "*.png"))
          if "entrenamiento" in os.path.basename(f).lower() and "ingl" in os.path.basename(f).lower()]
if ingles:
    en = Image.open(ingles[0]).convert("RGB")
    if en.size == (256, 192):
        guardar_argb(en, "fondo_entrenamiento_en.argb")
        print("Menu en ingles:", ingles[0])
limpio = im.copy()
for k in range(7):                    # etiquetas (barras con y = 65 + 12k): franja de la barra vacia de y = 53
    Y = 65 + 12 * k
    for dy in range(-5, 8):
        for xx in range(118, 212):
            limpio.putpixel((xx, Y + dy), im.getpixel((xx, 53 + dy)))
for yy in range(8, 29):               # "Libertad" de la cabecera: color de su fila
    c = im.getpixel((150, yy))
    for xx in range(160, 240):
        limpio.putpixel((xx, yy), c)
guardar_argb(limpio, "fondo_entrenamiento_limpio.argb")
# Fondo de la pantalla de arriba: la pagina 2 de la ficha del juego (msup_bg03),
# convertida antes con convertir_graficos.py (preferimos la version en espanol)
graf = "D:/Inazuma Eleven 1 Port/Recursos/graficos"
fichas = sorted(glob.glob(os.path.join(graf, "*msup_bg03*_es.png"))) or sorted(glob.glob(os.path.join(graf, "*msup_bg03*.png")))
if fichas:
    f = Image.open(fichas[0]).convert("RGBA")
    datos2 = bytearray()
    for y in range(192):
        for x in range(256):
            r, g, b, a = f.getpixel((x, y))
            if a == 0: r, g, b = 2, 52, 77          # fondo de la pantalla
            datos2 += struct.pack("<I", 0xFF000000 | r << 16 | g << 8 | b)
    open(os.path.join(dest, "fondo_ficha.argb"), "wb").write(datos2)
    print("Ficha (pantalla de arriba):", fichas[0])
else:
    print("Aviso: no encontre msup_bg03 en", graf, "(ejecuta convertir_graficos.py); la pantalla de arriba no cambiara.")
# ficha del mod (la misma que pone crear_npc_entrenador.py: el NPC y el menu son un solo mod)
import crear_npc_entrenador
crear_npc_entrenador.escribir_mod_txt(dest, crear_npc_entrenador.MOD_TXT)
print("Mod creado en", dest)
