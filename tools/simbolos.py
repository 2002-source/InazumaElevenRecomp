#!/usr/bin/env python3
"""
Pone nombre a las direcciones del perfil que guarda bench.py (run/bench_N.json)
y suma las muestras por funcion.

Uso (terminal MSYS2 CLANG64, desde C:/dev/ie1recomp):
  python scripts/simbolos.py run/bench_6.json
"""
import bisect, json, subprocess, sys
from collections import Counter

EXE = "C:/dev/ndsrecomp/runner/build-mingw/nds_runner.exe"
IMAGE_BASE = 0x140000000          # base de los ejecutables PE de 64 bits
CONOCIDOS = {("ntdll.dll", 1464772): "ZwWaitForSingleObject (esperando)"}


def tabla_simbolos():
    out = subprocess.run(["llvm-nm", "-C", "--defined-only", EXE],
                         capture_output=True, text=True, errors="replace").stdout
    syms = []
    for line in out.splitlines():
        partes = line.split(" ", 2)
        if len(partes) == 3 and partes[1].lower() in ("t", "w"):
            try:
                syms.append((int(partes[0], 16), partes[2]))
            except ValueError:
                pass
    syms.sort()
    return [a for a, _ in syms], [n for _, n in syms]


def main():
    datos = json.load(open(sys.argv[1], encoding="utf-8"))
    prof = datos["hostprof"]
    total = prof["samples"]
    addrs, names = tabla_simbolos()
    por_func = Counter()
    for e in prof["top"]:
        if e["module"] == "nds_runner.exe":
            va = IMAGE_BASE + e["rva"]
            i = bisect.bisect_right(addrs, va) - 1
            nombre = names[i] if i >= 0 else f"? rva {e['rva']:#x}"
        else:
            nombre = CONOCIDOS.get((e["module"], e["rva"]), f"{e['module']}+{e['rva']:#x}")
        por_func[nombre[:110]] += e["count"]
    cubiertas = sum(por_func.values())
    print(f"Ranura {datos['ranura']}: {datos['ms_por_fotograma']:.2f} ms/fotograma, "
          f"{total} muestras del hilo de emulacion ({cubiertas} en esta lista)\n")
    for nombre, n in por_func.most_common(45):
        print(f"{n:6d}  {100.0 * n / total:5.1f} %  {nombre}")
    print("\nModelo de ejecucion:", json.dumps(datos.get("modelo")))
    print("Interprete:", json.dumps(datos.get("cobertura")))
    hot = datos.get("pc_hot")
    if hot:
        print("\nDirecciones del juego mas ejecutadas (pc_hot, datos crudos):")
        print(json.dumps(hot)[:3000])


if __name__ == "__main__":
    main()
