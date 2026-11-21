#!/usr/bin/env python3
"""
Volumen del juego en el menu de Esc: Sistema > Volumen (0 a 100, de 10 en 10).
Se aplica al momento y se recuerda en datos/ie1_menu.cfg (volumen=...).
El texto sale en el idioma del menu (ingles, espanol, frances, aleman, italiano).

Toca runner/src/frontend.cpp. Requiere parche_menu_extra.py y
parche_menu_5idiomas.py (ya aplicados). Se puede ejecutar varias veces.
Despues: bash scripts/paso_mingw.sh
"""
import sys

FRONTEND = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
MARCA = "IE1_VOLUMEN"
DESC_ES = "Volumen del juego (0 = sin sonido, 100 = normal). Se guarda para la proxima vez."
DESC_EN = "Game volume (0 = no sound, 100 = normal). It is kept for next time."
DESC_FR = "Volume du jeu (0 = sans son, 100 = normal). Il est garde pour la prochaine fois."
DESC_DE = "Lautstaerke des Spiels (0 = kein Ton, 100 = normal). Wird fuer das naechste Mal gespeichert."
DESC_IT = "Volume del gioco (0 = senza audio, 100 = normale). Viene ricordato per la prossima volta."

# (ancla, texto que se pone, donde: "antes" o "despues" del ancla)
CAMBIOS = [
    # variables
    ('constexpr const char* kIe1RestartKey = "ie1.restart";\n',
     'constexpr const char* kIe1VolumeKey = "ie1.volume";  // IE1_VOLUMEN\n'
     'int g_ie1_volumen = 100;              // 0..100\n'
     'bool g_ie1_req_volumen = true;        // aplicarlo al stream de audio\n', "despues"),
    # leer el valor
    ('    if (ie1_key(item, kIe1SlotKey)) { *value = g_ie1_state_slot; return 1; }\n',
     '    if (ie1_key(item, kIe1VolumeKey)) { *value = g_ie1_volumen; return 1; }  // IE1_VOLUMEN\n', "antes"),
    # cambiar el valor
    ('    if (ie1_key(item, kIe1SlotKey)) {\n        if (value < 1 || value > 10) return 0;\n',
     '    if (ie1_key(item, kIe1VolumeKey)) {  // IE1_VOLUMEN\n'
     '        if (value < 0 || value > 100) return 0;\n'
     '        g_ie1_volumen = value; g_ie1_req_volumen = true; return 1;\n'
     '    }\n', "antes"),
    # elemento del menu (System, antes de Reiniciar)
    ('        {kIe1RestartKey, "System", "Reiniciar",  // IE1_MENU_EXTRA\n',
     '        {kIe1VolumeKey, "System", "Volume",  // IE1_VOLUMEN\n'
     '         "' + DESC_ES + '",\n'
     '         RECOMP_RUNTIME_UI_INT, 0, 100, 10, nullptr, 0, nullptr},\n', "antes"),
    # traducciones (original, es, en) y (en, fr, de, it)
    ('        {"Volume", "Volumen", "Volume"},\n',
     '        {"' + DESC_ES + '", "' + DESC_ES + '", "' + DESC_EN + '"},  // IE1_VOLUMEN\n', "despues"),
    ('        {"Volume", "Volume", "Lautstaerke", "Volume"},\n',
     '        {"' + DESC_EN + '", "' + DESC_FR + '", "' + DESC_DE + '", "' + DESC_IT + '"},  // IE1_VOLUMEN\n', "despues"),
    # recordarlo en ie1_menu.cfg: leer
    ('        else if (!std::strcmp(k, "ranura")) slot = v;\n',
     '        else if (!std::strcmp(k, "volumen") && v >= 0 && v <= 100) { g_ie1_volumen = v; g_ie1_req_volumen = true; }  // IE1_VOLUMEN\n',
     "despues"),
    # aplicarlo en el bucle principal
    ('        ie1_cfg_guardar_si_cambia();  // IE1_MENU_EXTRA\n',
     '        if (g_ie1_req_volumen) {  // IE1_VOLUMEN\n'
     '            g_ie1_req_volumen = false;\n'
     '#if defined(NDS_HAVE_SDL3)\n'
     '            if (audio && !audio_queue.output_muted)\n'
     '                SDL_SetAudioStreamGain(audio.stream, static_cast<float>(g_ie1_volumen) / 100.0f);\n'
     '#endif\n'
     '        }\n', "antes"),
]

# recordarlo en ie1_menu.cfg: guardar (se cambian estas lineas enteras)
REEMPLAZOS = [
    ('    static int ult[5] = {-1, -1, -1, -1, -1};\n'
     '    const int cur[5] = {g_ie1_fullscreen ? 1 : 0, g_ie1_window_size, g_ie1_horizontal ? 1 : 0,\n'
     '                        g_ie1_fill_scale ? 1 : 0, g_ie1_state_slot};\n',
     '    static int ult[6] = {-1, -1, -1, -1, -1, -1};  // IE1_VOLUMEN\n'
     '    const int cur[6] = {g_ie1_fullscreen ? 1 : 0, g_ie1_window_size, g_ie1_horizontal ? 1 : 0,\n'
     '                        g_ie1_fill_scale ? 1 : 0, g_ie1_state_slot, g_ie1_volumen};\n'),
    ('        std::fprintf(f, "pantalla_completa=%d\\ntamano=%d\\nhorizontal=%d\\nllenar=%d\\nranura=%d\\n",\n'
     '                     cur[0], cur[1], cur[2], cur[3], cur[4]);\n',
     '        std::fprintf(f, "pantalla_completa=%d\\ntamano=%d\\nhorizontal=%d\\nllenar=%d\\nranura=%d\\nvolumen=%d\\n",\n'
     '                     cur[0], cur[1], cur[2], cur[3], cur[4], cur[5]);\n'),
]


def main():
    try:
        s = open(FRONTEND, encoding="utf-8", newline="").read()
    except OSError:
        sys.exit("No encuentro %s. No toco nada." % FRONTEND)
    if MARCA in s:
        print("frontend.cpp: el volumen ya estaba en el menu.")
        return
    nl = "\r\n" if "\r\n" in s else "\n"
    f = lambda t: t.replace("\n", nl)
    for ancla, _, _ in CAMBIOS:
        if s.count(f(ancla)) != 1:
            sys.exit("frontend.cpp no tiene la forma esperada (falta: %s). No toco nada." % ancla.strip()[:70])
    for viejo, _ in REEMPLAZOS:
        if s.count(f(viejo)) != 1:
            sys.exit("frontend.cpp no tiene la forma esperada (ie1_menu.cfg). No toco nada.")
    for ancla, texto, donde in CAMBIOS:
        a, t = f(ancla), f(texto)
        s = s.replace(a, t + a if donde == "antes" else a + t)
    for viejo, nuevo in REEMPLAZOS:
        s = s.replace(f(viejo), f(nuevo))
    open(FRONTEND, "w", encoding="utf-8", newline="").write(s)
    print("frontend.cpp: Sistema > Volumen anadido (se guarda en ie1_menu.cfg).")
    print("Compila el runner con: bash scripts/paso_mingw.sh")


if __name__ == "__main__":
    main()
