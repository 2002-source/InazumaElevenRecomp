#!/usr/bin/env python3
"""
Amplia el bufer de audio del runner (runner/src/frontend.cpp) para que los
picos cortos (cargas, escenas pesadas) no vacien la cola y no se oigan cortes.

  kAudioQueueFrames: audio que el runner mantiene en cola en regimen normal.
  Original 2048 muestras (~63 ms). Por defecto aqui 4096 (~125 ms).

Uso:  python scripts/parche_audio.py          -> 4096
      python scripts/parche_audio.py 6144     -> ~188 ms (mas margen, algo mas de retardo)
      python scripts/parche_audio.py 2048     -> vuelve al original
Despues: bash scripts/paso_mingw.sh
"""
import re, sys
PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
valor = int(sys.argv[1]) if len(sys.argv) > 1 else 4096
if valor < 1024 or valor > 16384 or valor % 256:
    sys.exit("Valor no valido: usa un multiplo de 256 entre 1024 y 16384.")
s = open(PATH, encoding="utf-8", newline="").read()
patron = re.compile(r"constexpr uint32_t kAudioQueueFrames = (\d+);( *// IE1_AUDIO[^\r\n]*)?")
m = patron.findall(s)
if len(m) != 1:
    sys.exit("No encontre kAudioQueueFrames exactamente una vez; no toco nada.")
anterior = m[0][0]
s = patron.sub(f"constexpr uint32_t kAudioQueueFrames = {valor};  // IE1_AUDIO (original 2048)", s)
open(PATH, "w", encoding="utf-8", newline="").write(s)
print(f"Bufer de audio: {anterior} -> {valor} muestras (~{valor * 1000 // 32728} ms). Compila con paso_mingw.sh")
