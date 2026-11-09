# runner-patches license

The scripts in this directory modify files of the ndsrecomp runner that are
licensed GPL-3.0-or-later (for example `runner/src/frontend.cpp`, which derives
from melonDS, and `runner/src/wifi_net.cpp`), and the runner-side code they
generate (for example `runner/src/ie1_idiomas.cpp`, `runner/src/hle_ie1_card.cpp`).

These patches and the code they produce are licensed
**GPL-3.0-or-later**. The `nds_runner` executable distributed in the releases
is a GPL-3.0-or-later combined work: its corresponding source is
ndsrecomp at the commit in `../ndsrecomp.pin`, recomp-ui at the commit in
`../recomp-ui.pin`, plus the patches in this directory, applied as described in
`../docs/BUILDING.md`. The full GPL-3.0 text ships as `LICENSE-GPL` with
ndsrecomp and with every release ZIP.

`parche_menu_barra.py` also edits `recomp-ui/src/common/recomp_runtime_ui.c`;
that change follows recomp-ui's own license.
