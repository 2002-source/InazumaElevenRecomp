#!/usr/bin/env python3
"""
Crea el mod 'entrenamiento_libre' a partir de tu diseno del menu (PNG 256x192).
  python scripts/preparar_entrenamiento.py "D:/Inazuma Eleven 1 Port/Menu_Nuevo_Entrenamiento_en_espanol.png"
Despues: activalo en Esc > Mods y, en el juego, pulsa T para abrir el menu.
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
open(os.path.join(dest, "mod.txt"), "w", encoding="utf-8").write(
    "nombre=Entrenamiento libre\ndescripcion=Reparte puntos pagando 450 de Pasion por punto (tecla T).\n")
print("Mod creado en", dest)
