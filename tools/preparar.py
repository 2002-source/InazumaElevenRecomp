#!/usr/bin/env python3
"""
Preparador del port de Inazuma Eleven (arrastra tus ROM sobre
"PREPARAR - arrastra aqui tus ROM.bat").

Reconoce cada ROM por su huella y hace lo que corresponda:
  - Inazuma Eleven (Europa, ingles)         -> la ROM base del port   [OBLIGATORIA]
  - Inazuma Eleven (Europa, espanol)        -> paquete de idioma espanol (textos y voces)
  - Inazuma Eleven (Japon)                   -> mod de voces japonesas (opcional)
Con la ROM base se completan los mods incluidos (NPC entrenador y niveles de
supertecnicas). Una ROM del IE2 no hace falta (los mods ya traen lo necesario).

No modifica ninguna ROM. Todo lo generado queda dentro de la carpeta del port.
Se puede volver a ejecutar cuando quieras (por ejemplo, para anadir el espanol
despues): solo rehace lo que corresponda a las ROM que arrastres.
"""
import hashlib, os, shutil, struct, subprocess, sys

# este archivo esta en <port>/herramientas/scripts/preparar.py
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
HERR = os.path.dirname(SCRIPTS)
RAIZ = os.path.dirname(HERR)                                          # carpeta del port
TRABAJO = os.path.join(HERR, "trabajo")
sys.path.insert(0, SCRIPTS)

SHA_IE1_EN = "d55169c0b93d26b4037379d3b81a61b5404945e5"
SHA_IE1_ES = "1977bf71a45a9ab654427f359eb7fbaa62d97ebe"


def sha1(ruta):
    h = hashlib.sha1()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def tiene_carpeta(rom, nombre):
    """Busca un directorio con ese nombre en el sistema de archivos de la ROM."""
    fnt = struct.unpack_from("<I", rom, 0x40)[0]
    ndirs = struct.unpack_from("<H", rom, fnt + 6)[0]
    for d in range(ndirs):
        p = fnt + struct.unpack_from("<I", rom, fnt + d * 8)[0]
        while True:
            n = rom[p]; p += 1
            if not n: break
            nom = rom[p:p + (n & 0x7F)]; p += n & 0x7F
            if n & 0x80:
                if nom == nombre.encode(): return True
                p += 2
    return False


def identificar(ruta):
    with open(ruta, "rb") as f:
        cab = f.read(0x200)
    titulo, codigo = cab[0:12].rstrip(b"\0").decode("latin-1", "replace"), cab[12:16].decode("latin-1", "replace")
    h = sha1(ruta)
    if h == SHA_IE1_EN: return "ie1_en", "Inazuma Eleven (Europa, ingles)"
    if h == SHA_IE1_ES: return "ie1_es", "Inazuma Eleven (Europa, espanol)"
    if titulo.startswith("INAZUMA") and codigo == "YEEJ":
        return "ie1_jp", "Inazuma Eleven (Japon) - voces japonesas / Japanese voices"
    if titulo == "INAZUMA11" and codigo.startswith("BE"):
        rom = open(ruta, "rb").read()
        if tiene_carpeta(rom, "sp"): return "ie2_es", f"Inazuma Eleven 2 ({codigo}, espanol)"
        return "ie2_en", f"Inazuma Eleven 2 ({codigo}, ingles)"
    if titulo.startswith("INAZUMA"):
        return None, f"{titulo} ({codigo}): version no compatible / unsupported version (SHA-1 {h})"
    return None, f"no es una ROM de Inazuma Eleven / not an Inazuma Eleven ROM ({titulo} {codigo})"


def ejecutar(script, *args, cwd=TRABAJO):
    print(f"   > {script} {' '.join(os.path.basename(a) if os.path.isabs(a) else a for a in args)}")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], cwd=cwd)
    if r.returncode != 0:
        raise SystemExit(f"Fallo {script}; revisa los mensajes de arriba. / {script} failed; check the messages above.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        input("Pulsa Intro para salir / Press Enter to exit...")
        return
    roms = {}
    print("=== ROM recibidas / ROMs received ===")
    for ruta in sys.argv[1:]:
        if not os.path.isfile(ruta):
            print(f" - {ruta}: no es un archivo / not a file"); continue
        tipo, desc = identificar(ruta)
        print(f" - {os.path.basename(ruta)}: {desc}")
        if tipo: roms[tipo] = ruta
    os.makedirs(TRABAJO, exist_ok=True)
    for d in ("games", "images", "run"):
        os.makedirs(os.path.join(TRABAJO, d), exist_ok=True)

    base = os.path.join(RAIZ, "rom", "ie1_eur.nds")
    if "ie1_en" in roms:
        print("\n=== ROM base / Base ROM ===")
        os.makedirs(os.path.dirname(base), exist_ok=True)
        shutil.copyfile(roms["ie1_en"], base)
        print("   copiada a / copied to rom\\ie1_eur.nds")
    if not os.path.exists(base):
        raise SystemExit("\nFalta la ROM base: Inazuma Eleven (Europa, ingles). Arrastrala junto con las demas.\n"
                         "The base ROM is missing: Inazuma Eleven (Europe, English). Drag it together with the others.")
    # copia de trabajo de la base para las herramientas (rutas relativas games/ e images/)
    trabajo_base = os.path.join(TRABAJO, "games", "ie1_eur.nds")
    if not os.path.exists(trabajo_base) or sha1(trabajo_base) != SHA_IE1_EN:
        shutil.copyfile(base, trabajo_base)
    if not os.path.exists(os.path.join(TRABAJO, "images", "arm9.bin")):
        ejecutar("extraer_rom.py", "games/ie1_eur.nds", "images")

    if "ie1_es" in roms:
        print("\n=== Idioma espanol / Spanish language ===")
        ejecutar("crear_paquete_idioma.py", roms["ie1_es"], "es", "--base", "games/ie1_eur.nds",
                 "--salida", os.path.join(RAIZ, "idiomas"))
        ejecutar("analizar_cadenas.py", roms["ie1_es"])
        ejecutar("crear_parche_textos.py", "es")
        origen = os.path.join(TRABAJO, "idiomas", "es", "arm9_textos.bin")
        destino = os.path.join(RAIZ, "idiomas", "es", "arm9_textos.bin")
        if os.path.exists(origen):
            shutil.move(origen, destino)
        cfg = os.path.join(RAIZ, "datos", "idiomas.cfg")
        if not os.path.exists(cfg):
            open(cfg, "w").write("textos=es\nvoces=es\n")
            print("   idioma del juego: espanol (se cambia en Opciones o en Esc)\n   game language: Spanish (change it in Options or Esc)")

    if "ie1_jp" in roms:
        print("\n=== Mod: voces japonesas / Japanese voices ===")
        ejecutar("crear_paquete_idioma.py", roms["ie1_jp"], "voces_jp", "--base", "games/ie1_eur.nds",
                 "--solo-sonido", "--salida", os.path.join(RAIZ, "mods"))
        # solo las voces de las cinematicas: archivos "capitulo_escena.SAD" (01_1.SAD, 02_18.SAD...)
        import re
        carpeta_voces = os.path.join(RAIZ, "mods", "voces_jp", "data_iz", "sound", "en")
        quedan = 0
        for raiz_d, _, nombres in os.walk(os.path.join(RAIZ, "mods", "voces_jp", "data_iz")):
            for n in nombres:
                ruta = os.path.join(raiz_d, n)
                if os.path.dirname(ruta) == carpeta_voces and re.fullmatch(r"\d+_\d+\.SAD", n, re.I):
                    quedan += 1
                else:
                    os.remove(ruta)
        print(f"   {quedan} voces de cinematicas / cutscene voices")
        import crear_npc_entrenador as C0
        C0.escribir_mod_txt(os.path.join(RAIZ, "mods", "voces_jp"), {
            "nombre": "Voces japonesas", "nombre_en": "Japanese voices",
            "descripcion": "Las cinematicas suenan con las voces originales japonesas.",
            "descripcion_en": "Cutscenes play with the original Japanese voices.",
            "desbloqueo": "Siempre activo: se oye en la intro de anime y en las cinematicas.",
            "desbloqueo_en": "Always on: you hear it in the anime intro and in the cutscenes.",
        })
    # mods generados con las ROM del usuario
    import crear_npc_entrenador, crear_mod_niveles, crear_marca_prueba
    for m in (crear_npc_entrenador, crear_mod_niveles, crear_marca_prueba):
        m.IE1 = RAIZ
    es_pack = os.path.join(RAIZ, "idiomas", "es", "data_iz", "script", "en", "evet.pkb")
    print("\n=== Mod: NPC entrenador / Trainer NPC ===")
    args = ["x", "--rom", base]
    if os.path.exists(es_pack): args += ["--es", es_pack]
    sys.argv = args
    crear_npc_entrenador.main()
    activar = ["entrenamiento_libre", "npc_entrenador"] + (["voces_jp"] if "ie1_jp" in roms else [])
    if "ie2_en" not in roms and "ie2_es" not in roms and \
            os.path.exists(os.path.join(RAIZ, "mods", "niveles_supertecnicas", "parches.txt")):
        # el mod ya viene con lo del IE2: solo faltan los guiones, que salen de la ROM base
        print("\n=== Mod: Niveles de supertecnicas / Move levels ===")
        sys.argv = ["x", "--ie1", base, "--solo-guiones", "--idiomas", os.path.join(RAIZ, "idiomas")]
        crear_mod_niveles.main()
        activar.append("niveles_supertecnicas")
    elif "ie2_en" in roms or "ie2_es" in roms:
        print("\n=== Mod: Niveles de supertecnicas / Move levels ===")
        ie2 = roms.get("ie2_en") or roms.get("ie2_es")
        args = ["x", "--ie1", base, "--ie2", ie2, "--idiomas", os.path.join(RAIZ, "idiomas")]
        if "ie2_es" in roms: args += ["--ie2-es", roms["ie2_es"]]
        sys.argv = args
        crear_mod_niveles.main()
        activar.append("niveles_supertecnicas")
    # activar los mods generados (respetando los que ya hubiera)
    cfg = os.path.join(RAIZ, "mods", "mods.cfg")
    activos = []
    if os.path.exists(cfg):
        activos = [l.strip() for l in open(cfg) if l.strip() and not l.startswith("#")]
    for m in activar:
        if m not in activos and os.path.isdir(os.path.join(RAIZ, "mods", m)): activos.append(m)
    open(cfg, "w").write("# Un mod activo por linea, en orden (el ultimo gana)\n" + "".join(a + "\n" for a in activos))
    print("\nListo. Abre \"Inazuma Eleven.exe\" para jugar.\nDone. Open \"Inazuma Eleven.exe\" to play.")
    input("Pulsa Intro para salir / Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code)
            input("Pulsa Intro para salir / Press Enter to exit...")
        raise
