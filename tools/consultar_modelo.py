#!/usr/bin/env python3
"""
Con el juego abierto (arrancado con --port 19842), pregunta al runner cuantas
regiones nativas del modelo de ejecucion se estan usando.
Uso:  python scripts/consultar_modelo.py
"""
import json, socket, sys, time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 19842
s = socket.create_connection(("127.0.0.1", port), timeout=10)
buf = b""


def cmd(name):
    global buf
    s.sendall((json.dumps({"cmd": name}) + "\n").encode())
    while b"\n" not in buf:
        buf += s.recv(1 << 16)
    line, buf = buf.split(b"\n", 1)
    return json.loads(line)


a = cmd("execution_model")
da = cmd("dispatch_stats")
time.sleep(5)
b = cmd("execution_model")
db = cmd("dispatch_stats")
print("Modelo:", b.get("model"))
for k in ("native_regions", "reference_steps", "blocked_observer", "blocked_debt",
          "blocked_boundary", "blocked_deadline", "unsupported_exits", "io_exits"):
    if isinstance(b.get(k), int) and isinstance(a.get(k), int):
        print(f"  {k:18s} +{b[k] - a[k]:>12,} en 5 s   (total {b[k]:,})")
print("Dispatcher ARM9 (en 5 s):")
for k in ("dispatch_total", "cache_hit", "cache_hit_absent", "cache_slow_lookup",
          "crs_hit", "crs_miss", "dispatch_slice_yield"):
    x, y = da.get("arm9", {}).get(k), db.get("arm9", {}).get(k)
    if isinstance(x, int) and isinstance(y, int):
        print(f"  {k:22s} +{y - x:>12,}")
print("Interprete:", json.dumps(cmd("static_coverage")))
