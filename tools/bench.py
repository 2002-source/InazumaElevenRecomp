#!/usr/bin/env python3
"""
Benchmark reproducible del recomp de Inazuma Eleven.

Arranca el runner SIN ventana (--serve), carga un estado guardado, ejecuta
fotogramas lo mas rapido posible y mide cuanto cuesta cada fotograma en tu
PC. Al final pide al runner su perfil de CPU (que funciones consumen el tiempo).

Uso (terminal MSYS2 CLANG64, desde C:/dev/ie1recomp):
  python scripts/bench.py                 lista los estados encontrados
  python scripts/bench.py 2               mide el estado de la ranura 2
  python scripts/bench.py 2 --frames 900  mas fotogramas
  python scripts/bench.py todos           mide todas las ranuras

Resultado: ms por fotograma (60 FPS = 16.67 ms) y "velocidad" (200 % =
podria ir el doble de rapido). Guarda bench_<ranura>.json con todos los datos.
"""
import argparse, glob, json, os, re, socket, subprocess, sys, time

RUNNER = "C:/dev/ndsrecomp/runner/build-mingw/nds_runner.exe"
BIOS = "C:/dev/ndsrecomp/bios"
ROM = "C:/dev/ie1recomp/games/ie1_eur.nds"
RUN = "C:/dev/ie1recomp/run"


def estados():
    files = [f for f in glob.glob(os.path.join(RUN, "estados", "**", "*"), recursive=True)
             if os.path.isfile(f)]
    res = {}
    for f in files:
        m = re.findall(r"(\d+)", os.path.basename(f))
        if m:
            res.setdefault(int(m[-1]), f)
    return res, files


class Client:
    def __init__(self, port):
        for _ in range(100):
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=600)
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("el runner no abrio el servidor de depuracion")
        self.buf = b""

    def cmd(self, name, **kw):
        self.sock.sendall((json.dumps(dict(cmd=name, **kw)) + "\n").encode())
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise RuntimeError("el runner cerro la conexion")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)


def medir(slot, path, frames, port, perfil=False, gov="off", modelo="faithful"):
    env = dict(os.environ, NDS_FAST_CARD="1", NDS_SAVESTATE_ANY_BUILD="1")
    args = [RUNNER, BIOS, "--serve", "--port", str(port), "--freebios",
            "--generated-firmware", "--boot", "direct",
            "--firmware-state-path", os.path.join(RUN, "firmware_state.bin"),
            "--config", os.path.join(RUN, "game.toml"), "--no-save",
            "--no-coverage-manifest", "--performance-governor", gov,
            "--execution-model", modelo, "--rom", ROM]
    if perfil:   # volcado completo del perfilador al cerrar (para hostprof_symbolize.py)
        os.makedirs(os.path.join(RUN, "perfiles"), exist_ok=True)
        args += ["--diagnostics", "on", "--diagnostics-dir", os.path.join(RUN, "perfiles")]
    log = open(os.path.join(RUN, f"bench_{slot}.log"), "w")
    proc = subprocess.Popen(args, cwd=RUN, env=env, stdout=log, stderr=subprocess.STDOUT)
    c = None
    try:
        c = Client(port)
        c.cmd("ping")
        r = c.cmd("state_load", path=path.replace("\\", "/"))
        if "error" in r:
            print(f"  No pude cargar el estado: {r['error']}")
            print("  (los estados de otra version del runner no cargan; vuelve a guardarlos)")
            return None
        c.cmd("run_vblanks", count=60)                      # calentamiento
        t0 = time.perf_counter()
        r = c.cmd("run_vblanks", count=frames)
        dt = time.perf_counter() - t0
        if "error" in r:
            print(f"  Error ejecutando: {r['error']}")
            return None
        ms = dt * 1000.0 / frames
        prof = c.cmd("hostprof_top", window_ms=int(dt * 1000), top=300)
        stats = c.cmd("dispatch_stats")
        try:
            pc_hot = c.cmd("pc_hot")          # direcciones del JUEGO mas ejecutadas
        except Exception as ex:
            pc_hot = {"error": str(ex)}
        cov = c.cmd("static_coverage")
        try:
            modelo_stats = c.cmd("execution_model")
        except Exception as ex:
            modelo_stats = {"error": str(ex)}
        datos = dict(ranura=slot, estado=path, fotogramas=frames, segundos=dt,
                     ms_por_fotograma=ms, velocidad_pct=1666.7 / ms,
                     hostprof=prof, pc_hot=pc_hot, modelo=modelo_stats, dispatch=stats, cobertura=cov, run_vblanks=r)
        json.dump(datos, open(os.path.join(RUN, f"bench_{slot}.json"), "w"), indent=1)
        return datos
    finally:
        # Cierre ordenado (necesario para que la PGO escriba su perfil al salir)
        if c is not None:
            try:
                c.sock.settimeout(10)
                c.cmd("frontend_exit")
            except Exception:
                pass
            try:
                c.sock.close()
            except Exception:
                pass
        try:
            proc.wait(20)
        except Exception:
            pass
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(5)
        except Exception:
            if proc.poll() is None:
                proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ranura", nargs="?")
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--port", type=int, default=19851)
    ap.add_argument("--modelo", default="faithful",
                    help="modelo de ejecucion: faithful (normal) o performance")
    ap.add_argument("--gov", default="off",
                    help="regulador de rendimiento del runner: off, stage1, stage2, auto")
    ap.add_argument("--perfil", action="store_true",
                    help="guarda el volcado del perfilador en run/perfiles")
    ap.add_argument("--rep", type=int, default=3,
                    help="repeticiones por ranura; se informa el minimo y la mediana")
    a = ap.parse_args()
    slots, files = estados()
    if not a.ranura:
        print("Estados encontrados:")
        for f in files:
            print("  ", f)
        print("Ranuras detectadas:", sorted(slots))
        return
    pedidas = sorted(slots) if a.ranura == "todos" else [int(a.ranura)]
    resumen = []
    for s in pedidas:
        if s not in slots:
            print(f"No hay estado para la ranura {s}")
            continue
        print(f"Ranura {s}: {a.frames} fotogramas x {a.rep} repeticiones...")
        tiempos = []
        for r in range(a.rep):
            d = medir(s, slots[s], a.frames, a.port, a.perfil, a.gov, a.modelo)
            if not d:
                break
            tiempos.append(d['ms_por_fotograma'])
            print(f"    rep {r + 1}: {d['ms_por_fotograma']:.2f} ms")
        if tiempos:
            t = sorted(tiempos)
            mn, med = t[0], t[len(t) // 2]
            dispersion = (t[-1] - t[0]) / t[0] * 100
            aviso = "   <-- mucha variacion: cierra otros programas" if dispersion > 8 else ""
            print(f"  minimo {mn:.2f} ms ({1666.7 / mn:.0f} %)  mediana {med:.2f} ms"
                  f"  variacion {dispersion:.0f} %{aviso}")
            resumen.append((s, mn, med, dispersion))
    if len(resumen) > 1:
        print("\nResumen (minimo / mediana / variacion entre repeticiones):")
        for s, mn, med, disp in resumen:
            print(f"  ranura {s}: {mn:.2f} / {med:.2f} ms  ({1666.7 / mn:.0f} %)  var {disp:.0f} %")


if __name__ == "__main__":
    main()
