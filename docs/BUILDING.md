# Building InazumaElevenRecomp from source

*(Resumen en español al final.)*

You need **your own** Inazuma Eleven ROM (Europe, English, `YEEP`, SHA-1
`d55169c0b93d26b4037379d3b81a61b5404945e5`). Everything derived from the ROM
(recompiled code, images, language packs, generated mods) is created locally
and never committed.

## 1. Tools (Windows)

- [MSYS2](https://www.msys2.org/), using the **CLANG64** terminal:
  ```
  pacman -S git mingw-w64-clang-x86_64-{clang,cmake,ninja,python,sdl3,pkgconf}
  ```

## 2. Sources, at the pinned versions

The scripts expect these paths:

```
git clone https://github.com/RetroPortingToolKit/ndsrecomp /c/dev/ndsrecomp
git -C /c/dev/ndsrecomp checkout 79efa88ad78ee46dd334b9fa21d1cea11b8ae388   # ndsrecomp.pin
git clone https://github.com/2002-source/InazumaElevenRecomp /c/dev/ie1recomp-src
```

recomp-ui must be at `C:/dev/recomp-ui`, at the commit in `recomp-ui.pin`.

Apply the port's runner changes (exact diff against the pinned commits):

```
git -C /c/dev/ndsrecomp apply /c/dev/ie1recomp-src/runner-patches/ndsrecomp.diff
git -C /c/dev/recomp-ui apply /c/dev/ie1recomp-src/runner-patches/recomp-ui.diff
```

The individual `runner-patches/*.py` scripts are the same changes as
step-by-step patch scripts (kept for reference and for porting to newer
ndsrecomp versions).

## 3. Project folder

```
mkdir -p /c/dev/ie1recomp/{games,scripts,run,configs,lanzador,mods,plugin}
cp -r /c/dev/ie1recomp-src/tools/.      /c/dev/ie1recomp/scripts/
cp -r /c/dev/ie1recomp-src/plugin/.     /c/dev/ie1recomp/scripts/
cp -r /c/dev/ie1recomp-src/launcher/.   /c/dev/ie1recomp/lanzador/
cp -r /c/dev/ie1recomp-src/mods/.       /c/dev/ie1recomp/mods/
cp -r /c/dev/ie1recomp-src/config/*.toml /c/dev/ie1recomp/configs/
cp /c/dev/ie1recomp-src/config/game.toml /c/dev/ie1recomp/run/
cp /c/dev/ie1recomp-src/coverage/*.json  /c/dev/ie1recomp/run/
cp -r /c/dev/ie1recomp-src/packaging/textos_port /c/dev/ie1recomp/scripts/
cp /c/dev/ie1recomp-src/packaging/*.sh  /c/dev/ie1recomp/scripts/
cp YOUR_ROM.nds /c/dev/ie1recomp/games/ie1_eur.nds
```

## 4. Recompile and build

```
cd /c/dev/ie1recomp
python scripts/extraer_rom.py games/ie1_eur.nds images
bash scripts/ronda.sh            # recompiles using the shipped coverage
bash scripts/perf.sh             # performance (flat) banks
bash scripts/paso_mingw.sh       # runner for your CPU
bash scripts/compilar_mods.sh    # mods plugin
bash scripts/compilar_lanzador.sh
bash scripts/jugar.sh --execution-model performance
```

Optional: Spanish language pack from your Spanish ROM
(`crear_paquete_idioma.py`, `analizar_cadenas.py`, `crear_parche_textos.py es`)
and the mods (`crear_npc_entrenador.py`, `crear_mod_niveles.py`).

## 5. Release ZIP

```
bash scripts/paso_port.sh        # runner compatible with any x86-64 CPU
bash scripts/crear_distribucion.sh
```

It builds a ZIP without any ROM or game data; players create everything with
the drag-and-drop preparer.

---

## Resumen en español

1. Instala MSYS2 (terminal CLANG64) y los paquetes del paso 1.
2. Clona ndsrecomp en `C:\dev\ndsrecomp` y pon el commit de `ndsrecomp.pin`;
   recomp-ui en `C:\dev\recomp-ui` con el de `recomp-ui.pin`. Aplica los
   `.diff` de `runner-patches/`.
3. Monta `C:\dev\ie1recomp` con las carpetas del paso 3 y tu ROM en
   `games\ie1_eur.nds`.
4. Recompila y compila con los comandos del paso 4.
5. Para el ZIP para jugadores: `paso_port.sh` y `crear_distribucion.sh`.
