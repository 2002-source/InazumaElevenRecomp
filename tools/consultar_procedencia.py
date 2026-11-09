#!/usr/bin/env python3
"""
Pregunta al servidor de depuracion del runner por la "procedencia de
escritura" de las funciones que mas se interpretan, para saber por que la
validacion por bytes las rechaza.

Uso (con el juego ya corriendo y en el mapa):
  python scripts/consultar_procedencia.py run/ie1_eur-coverage-XXXX-part00.json [puerto]
"""
import json, socket, sys

PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 19842


class Client:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.buf = b""

    def cmd(self, name, **kw):
        msg = dict(cmd=name, **kw)
        self.sock.sendall((json.dumps(msg) + "\n").encode())
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("el servidor cerro la conexion")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)


def main():
    cov = json.load(open(sys.argv[1], encoding="utf-8"))
    try:
        c = Client(PORT)
    except OSError as e:
        print(f"No pude conectar al puerto {PORT}: {e}")
        print("El modo --interactive quiza no abre el servidor; avisame y probamos --serve.")
        return
    print("ping:", c.cmd("ping"))

    def top(key, lo, hi, n):
        es = [e for e in cov[key] if lo <= int(e["addr"], 16) < hi]
        return sorted(es, key=lambda e: -e["hits"])[:n]

    grupos = [
        ("ARM9 principal", 9, top("entry_points_arm9", 0x02000000, 0x020C3000, 12)),
        ("ARM9 ITCM", 9, top("entry_points_arm9", 0x01FF8000, 0x02000000, 4)),
        ("ARM7 WRAM", 7, top("entry_points_arm7", 0x037F8000, 0x03810000, 6)),
    ]
    for nombre, cpu, entradas in grupos:
        print(f"\n=== {nombre} ===")
        for e in entradas:
            a = int(e["addr"], 16)
            # Muestreo los primeros 64 bytes de la funcion, de 4 en 4
            marcas = []
            gens = set()
            for off in range(0, 64, 4):
                p = c.cmd("exec_provenance", cpu=cpu, addr=a + off)
                marcas.append("W" if p.get("written") else ".")
                gens.add(p.get("generation"))
            p0 = c.cmd("exec_provenance", cpu=cpu, addr=a)
            print(f"0x{a:08X} hits={e['hits']:8d} writable={p0.get('writable')} "
                  f"bytes[0..64]={''.join(marcas)} generaciones={sorted(gens)}")

    for extra in ("static_coverage", "dispatch_stats", "execution_model"):
        try:
            r = c.cmd(extra)
            print(f"\n=== {extra} ===\n{json.dumps(r)[:1500]}")
        except Exception as ex:
            print(f"\n=== {extra} === error: {ex}")


if __name__ == "__main__":
    main()
