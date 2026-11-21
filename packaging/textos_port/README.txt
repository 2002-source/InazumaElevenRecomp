INAZUMA ELEVEN RECOMP - PC PORT  v1.1.1
=======================================
A native PC version of Inazuma Eleven (Nintendo DS), made by static
recompilation: the game's code was translated to PC code, so it runs at full
speed without an emulator.
Other languages: LEEME.txt (Español), LISEZMOI.txt (Français),
LIESMICH.txt (Deutsch), LEGGIMI.txt (Italiano).

This package does NOT include the game. You need your own ROM (a dump of your
own cartridge).


WHAT'S NEW IN v1.1.1
--------------------
Mod fixes only:
- Total power in moves: the panel now follows each special move's own
  animation. It no longer stays on screen after a save, no longer vanishes
  when the screen flickers (Spinning Cut), shows up when a keeper uses a
  special move against a normal shot, and no longer shows "calculating" on
  normal shots that get blocked or on shots that go wide.
- IE2 mechanics (move levels): the move's banner shows the level it had when
  it was used; the "Lv +" notice comes afterwards, as in IE2.
- Japanese voices: shot blocks have sound again. If you use this mod, drag
  the Japanese ROM onto PREPARAR again.


WHAT'S NEW IN v1.1
------------------
- Performance: the heaviest special moves (Multi-dribble, Lightning Burst,
  Triangle Z...) went from 46-50 FPS to 57-60 FPS. The fast "performance"
  mode is now really used, and the 3D drawing commands are sent much faster.
- French, German and Italian: drag the French, German or Italian ROM onto the
  PREPARAR file and that language is added (game text and menus, and its voices if that
  version has its own). The
  Esc menu and the launcher are also in these languages.
- Esc > System > Volume: turn the game volume up or down (it is remembered).
- Esc > System > Restart now works every time: the game reopens by itself
  with the language and mods you chose (it used to close after the third
  restart).
- The window is called "Inazuma Eleven Recomp" and shows the version; the
  launcher and the game have the game's own DS icon.
- New mods: IE2 mechanics (special move levels, IE2 shooting, shot blocks,
  talents, Mark can leave the team after the story, double EXP), total power
  shown in special move scenes, instant scouting, special move filters and
  affinity colours. See mods\README.txt.
- Free training: Y levels a player up paying Passion; X sends a player back
  to level 1 for free.


1. WHAT YOU NEED
----------------
REQUIRED
  Inazuma Eleven (Europe, English)      code YEEP
  SHA-1: d55169c0b93d26b4037379d3b81a61b5404945e5

OPTIONAL (each one adds a language or a mod)
  Inazuma Eleven (Europe, Spanish)      code YEES  -> Spanish (text and voices)
  SHA-1: 1977bf71a45a9ab654427f359eb7fbaa62d97ebe
  Inazuma Eleven (Europe, French)       code YEEF  -> French
  Inazuma Eleven (Europe, German)       code YEED  -> German
  Inazuma Eleven (Europe, Italian)      code YEEI  -> Italian
  Inazuma Eleven (Japan)                code YEEJ  -> "Japanese voices" mod
Tested with these French, German and Italian ROMs (SHA-1):
  French   7fd6dfbd3821b17e0f8dbbf0bcea151c659d2b52
  German   d3764abd90a5b69fd375e8d190e8e83a9e329e69
  Italian  1244e4f4f527202d937d9ff92538bd675f2c6999

Windows 10 or 11 (64-bit). A gamepad is optional (PS4/PS5/Xbox controllers work).


2. INSTALL (first time only)
----------------------------
1. Unzip this folder anywhere (for example D:\Games\Inazuma Eleven).
2. Drag your ROM onto  "PREPARAR - arrastra aqui tus ROM.bat"
   You can drop several ROMs at once (English + other languages + Japanese).
3. Wait until it says "Done". It recognises each ROM by itself and creates
   everything inside this folder. Your ROMs are never modified.

You can run it again at any time to add another ROM (for example, French
later on). The first extra language you add becomes the game language; you
can change it in Options or in the Esc menu.


3. PLAY
-------
Double-click "Inazuma Eleven.exe" (the launcher):
  Play                start the game
  Play over network   play with another PC (see section 5)
  Mods                turn mods on or off (Tab or right-click on a mod: what
                      it does)
  Options             language, voices, window/fullscreen, size, layout,
                      scaling, mode, VSync and controls
  Quit

"Inazuma Eleven.bat" starts the game directly, without the launcher.

Default keys
  Arrows = D-pad    Z = A    X = B    A = Y    S = X    Q = L    W = R
  Enter = Start     Backspace = Select
  Mouse on the bottom screen = touch screen
  Esc = in-game menu
A gamepad works out of the box. Keys can be changed in Options > Controls or
in the Esc menu.


4. THE ESC MENU (in game)
-------------------------
Press Esc at any time. It follows the language chosen for the game text.
  Mods       turn each mod on/off (selecting one shows what it does and how
             to get it). Changes apply after restarting.
  System     Volume (0-100, remembered), Restart (the game reopens by
             itself, e.g. to apply a language or mods), Resume game, Quit.
  Language   Text and Voices language (applied after restarting).
  States     Slot, Save state, Load state (quick saves, 10 slots).
  Display    Window/fullscreen, window size (480p/720p/1080p), layout
             (screens stacked or side by side), scaling (fill or sharp
             integer scaling), VSync.
  Controls   the key for every DS button.
  Input      mouse sensitivity.
Your normal save (the in-game save) is datos\ie1_eur.sav.


5. PLAY OVER NETWORK (local wireless between two PCs) - experimental
---------------------------------------------------------------------
The game's local wireless mode (matches against a friend) works between two
PCs: on the same home network, or over the internet with a free "virtual LAN"
program such as Radmin VPN or ZeroTier (both players join the same network).
1. Launcher > Play over network.
2. One player chooses Player 1 (host), the other Player 2 (guest).
3. "Other PC's IP": type the IP of the OTHER computer (home network: see
   ipconfig, "IPv4 Address"; Radmin VPN: the IP it shows, starting with 26.).
   Port: 7030 on both (only change it if something else uses it).
4. Both press "Connect and play". If Windows asks about the firewall, click
   Allow (private networks).
5. In the game, enter the wireless mode: one creates the room, the other
   joins it.
Over the internet it works best with low ping (same country).


6. MODS
-------
Read mods\README.txt. Short version:
  Free training          a trainer on top of the Tower (after the story)
                         trains your players, levels them up (Y) or sends
                         them back to level 1 (X).
  IE2 mechanics          move levels, IE2 shooting and long shots, shot
                         blocks, talents, Mark can leave the team after the
                         story, double EXP in random encounters.
  Total power in moves   both players' power during special move scenes.
  Instant scouting       Celia's and Nelly's searches finish at once.
  Special move filters   filter and sort the special move manuals (X).
  Affinity colours       move names in the colour of their element.
  Japanese voices        original Japanese voices (needs the Japanese ROM).


7. IF SOMETHING DOESN'T WORK
----------------------------
- "The ROM is missing" / the game does not start: drag your English ROM onto
  the PREPARAR file again. It must be exactly the version above (same SHA-1).
- A language is missing: drag that language's ROM onto the PREPARAR file.
- A mod is missing or does nothing: see mods\README.txt (it says which ROM to
  drag for each one).
- Anything else: send datos\ultima_sesion.log to whoever helps you.


8. FILES
--------
  datos\ie1_eur.sav        your save
  datos\estados\           save states
  datos\ultima_sesion.log  log of the last session
  mods\                    mods and mods.cfg (active mods)
  idiomas\                 language packs created from your ROMs
  licencias\               licenses and where the source code is

This port contains no ROM. Inazuma Eleven is a trademark of LEVEL-5 Inc.
This is a non-commercial fan project.
Created by Dosmildos (github.com/2002-source/InazumaElevenRecomp), developed
with the help of Claude (Anthropic). Built on ndsrecomp (mstan /
RetroPortingToolkit) and melonDS.
