#!/usr/bin/env python3
"""
Genera los TOML iniciales de ndsrecomp para Inazuma Eleven (EUR, YEEP)
a partir de images/rom_info.json y los binarios que saco extraer_rom.py.

Crea:
  configs/arm9.toml      banco ARM9 (arm9.bin completo + code_copy a ITCM)
  configs/arm7.toml      banco ARM7

Uso (desde C:\\dev\\ie1recomp):
  python scripts\\generar_toml.py
"""
import hashlib, json, os

IMG, CFG = "images", "configs"


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def toml(name, pid, cpu, isa, load, size, entry, digest, entries, comment, copies=()):
    out = [f"# {comment}", "", "[program]",
           f'name         = "{name}"', f'id           = "{pid}"',
           f'cpu          = "{cpu}"', f'isa          = "{isa}"',
           f"load_address = 0x{load:08X}", f"size         = 0x{size:08X}",
           f"entry_pc     = 0x{entry:08X}", "", "[identity]", f'sha1 = "{digest}"', ""]
    for addr, mode, ename in entries:
        out += ["[[entry_point]]", f"addr = 0x{addr:08X}", f'mode = "{mode}"', f'name = "{ename}"', ""]
    for rt, src, sz, cname, note in copies:
        out += ["[[code_copy]]", f"runtime_start = 0x{rt:08X}", f"source_start  = 0x{src:08X}",
                f"size          = 0x{sz:X}", f'name = "{cname}"', f'note = "{note}"', ""]
    return "\n".join(out)


def semillas(cpu):
    """Contenido de configs/semillas_armN.toml (si existe) para anadir al TOML."""
    p = os.path.join(CFG, f"semillas_arm{cpu}.toml")
    if not os.path.exists(p):
        return ""
    txt = open(p, encoding="utf-8").read()
    n = txt.count("[[entry_point]]")
    print(f"  + {n} semillas de {p}")
    return "\n" + txt


def main():
    info = json.load(open(os.path.join(IMG, "rom_info.json"), encoding="utf-8"))
    os.makedirs(CFG, exist_ok=True)

    # ---------- ARM9 (completo, con autoloads) ----------
    arm9 = open(os.path.join(IMG, "arm9.bin"), "rb").read()
    ram9 = int(info["arm9"]["ram_address"], 16)
    entry9 = int(info["arm9"]["entry"], 16)
    copies = []
    for a in info["autoloads"]:
        dest, size = int(a["destino"], 16), a["tamano"]
        src = ram9 + int(a["origen_en_arm9"], 16)
        if dest == 0x01FF8000 and size:
            copies.append((dest, src, size, "arm9_itcm_autoload",
                           "codigo ITCM copiado por el arranque del SDK"))
        else:
            print(f"(autoload a 0x{dest:08X}, {size} bytes: datos, no se declara como code_copy)")
    if os.path.exists(os.path.join(CFG, "arm9_itcm.toml")):
        os.remove(os.path.join(CFG, "arm9_itcm.toml"))
    open(os.path.join(CFG, "arm9.toml"), "w", encoding="utf-8").write(toml(
        "Inazuma Eleven ARM9", "ie1_arm9", "arm9", "armv5te", ram9, len(arm9), entry9,
        sha1(arm9), [(entry9, "arm", "_start")],
        "Inazuma Eleven (Europe, YEEP rev0) ARM9 completo - generado por generar_toml.py",
        copies) + semillas(9))
    print(f"arm9.toml       : 0x{ram9:08X} + 0x{len(arm9):X} bytes, entrada 0x{entry9:08X}, "
          f"{len(copies)} code_copy")
    for rt, src, sz, *_ in copies:
        print(f"                  code_copy 0x{src:08X} -> 0x{rt:08X} (0x{sz:X} bytes)")

    # ---------- ARM7 ----------
    arm7 = open(os.path.join(IMG, "arm7.bin"), "rb").read()
    ram7 = int(info["arm7"]["ram_address"], 16)
    entry7 = int(info["arm7"]["entry"], 16)
    open(os.path.join(CFG, "arm7.toml"), "w", encoding="utf-8").write(toml(
        "Inazuma Eleven ARM7", "ie1_arm7", "arm7", "armv4t", ram7, len(arm7), entry7,
        sha1(arm7), [(entry7, "arm", "_start")],
        "Inazuma Eleven (Europe, YEEP rev0) ARM7 - generado por generar_toml.py") + semillas(7))
    print(f"arm7.toml       : 0x{ram7:08X} + 0x{len(arm7):X} bytes, entrada 0x{entry7:08X}")
    print("Listo.")


if __name__ == "__main__":
    main()
