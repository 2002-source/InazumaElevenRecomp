#!/usr/bin/env python3
"""
Menu de Esc en cinco idiomas: ingles, espanol, frances, aleman e italiano (segun el idioma
de los textos de idiomas.cfg, o IE1_TEXTOS). Hasta ahora solo habia espanol, y el resto
salia en ingles.

  - Textos del menu: se anade una tabla con el frances, aleman e italiano de cada texto
    ingles de la tabla de traducciones (parche_menu_traduccion.py). Lo que no tenga
    traduccion sale en ingles, como antes.
  - Mods: el nombre de cada mod sale de nombre_fr / nombre_de / nombre_it de su mod.txt
    (traducir_mods.py los anade); si no lo tiene, de nombre_en.
  - La linea de ayuda de los mods, en los cinco idiomas.
Como la letra del menu de Esc no tiene tildes, los textos van sin ellas (ae, oe, ue en
aleman). Toca runner/src/frontend.cpp. Se puede ejecutar varias veces.
   python scripts/parche_menu_5idiomas.py   y despues   bash scripts/paso_mingw.sh
"""
import sys

PATH = "C:/dev/ndsrecomp/runner/src/frontend.cpp"
MARCA = "IE1_MENU_5IDIOMAS"

# texto ingles -> (frances, aleman, italiano)
T = {
    "UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT": (
        "HAUT/BAS CHOISIR  GAUCHE/DROITE CHANGER  ENTREE VALIDER",
        "HOCH/RUNTER WAEHLEN  LINKS/RECHTS AENDERN  ENTER OK",
        "SU/GIU SCEGLI  SIN/DES CAMBIA  INVIO CONFERMA"),
    "ENTER OPEN  ESC BACK": ("ENTREE OUVRIR  ECHAP RETOUR", "ENTER OEFFNEN  ESC ZURUECK", "INVIO APRI  ESC INDIETRO"),
    "Press again to confirm": ("Appuie encore pour confirmer", "Zum Bestaetigen erneut druecken",
                               "Premi di nuovo per confermare"),
    "Fill": ("Remplir", "Fuellen", "Riempi"),
    "Integer (sharp)": ("Entier (net)", "Ganzzahlig (scharf)", "Intero (nitido)"),
    "Off": ("Non", "Aus", "No"),
    "On": ("Oui", "An", "Si"),
    "Spanish": ("Espagnol", "Spanisch", "Spagnolo"),
    "English": ("Anglais", "Englisch", "Inglese"),
    "Japanese": ("Japonais", "Japanisch", "Giapponese"),
    "French": ("Francais", "Franzoesisch", "Francese"),
    "German": ("Allemand", "Deutsch", "Tedesco"),
    "Italian": ("Italien", "Italienisch", "Italiano"),
    "English (original)": ("Anglais (original)", "Englisch (Original)", "Inglese (originale)"),
    "Spanish (original)": ("Espagnol (original)", "Spanisch (Original)", "Spagnolo (originale)"),
    "Settings": ("Options", "Einstellungen", "Impostazioni"),
    "A / Enter": ("A / Entree", "A / Enter", "A / Invio"),
    "B / Backspace": ("B / Retour arriere", "B / Ruecktaste", "B / Backspace"),
    "Mouse sensitivity": ("Sensibilite de la souris", "Mausempfindlichkeit", "Sensibilita del mouse"),
    "Mouse speed.": ("Vitesse de la souris.", "Mausgeschwindigkeit.", "Velocita del mouse."),
    "Mouse": ("Souris", "Maus", "Mouse"),
    "Enter": ("Entree", "Enter", "Invio"),
    "Backspace": ("Retour arriere", "Ruecktaste", "Backspace"),
    "Space": ("Espace", "Leertaste", "Spazio"),
    "Tab": ("Tab", "Tab", "Tab"),
    "Up": ("Haut", "Hoch", "Su"),
    "Down": ("Bas", "Runter", "Giu"),
    "Left": ("Gauche", "Links", "Sinistra"),
    "Right": ("Droite", "Rechts", "Destra"),
    "Keypad Enter": ("Entree (pave num.)", "Enter (Ziffernblock)", "Invio (tast. num.)"),
    "Right Shift": ("Maj droite", "Umschalt rechts", "Maiusc destro"),
    "Right Ctrl": ("Ctrl droit", "Strg rechts", "Ctrl destro"),
    "Left Alt": ("Alt gauche", "Alt links", "Alt sinistro"),
    "Home": ("Debut", "Pos1", "Home"),
    "End": ("Fin", "Ende", "Fine"),
    "Page Up": ("Page prec.", "Bild hoch", "Pag su"),
    "Page Down": ("Page suiv.", "Bild runter", "Pag giu"),
    "Insert": ("Inser", "Einfg", "Ins"),
    "Delete": ("Suppr", "Entf", "Canc"),
    "Mods": ("Mods", "Mods", "Mod"),
    "Turns the mod on or off. Applied on restart (System > Restart).": (
        "Active ou desactive le mod. S'applique au redemarrage (Systeme > Redemarrer).",
        "Schaltet den Mod an oder aus. Gilt nach dem Neustart (System > Neustart).",
        "Attiva o disattiva la mod. Si applica al riavvio (Sistema > Riavvia)."),
    "System": ("Systeme", "System", "Sistema"),
    "Restart": ("Redemarrer", "Neustart", "Riavvia"),
    "Closes and reopens the game (for example, to apply the language).": (
        "Ferme et rouvre le jeu (par exemple, pour appliquer la langue).",
        "Schliesst das Spiel und startet es neu (z. B. um die Sprache anzuwenden).",
        "Chiude e riapre il gioco (per esempio, per applicare la lingua)."),
    "Language": ("Langue", "Sprache", "Lingua"),
    "Text": ("Textes", "Texte", "Testi"),
    "Language of texts and menus. Applied when the game restarts.": (
        "Langue des textes et des menus. S'applique au redemarrage du jeu.",
        "Sprache der Texte und Menues. Gilt nach dem Neustart des Spiels.",
        "Lingua di testi e menu. Si applica al riavvio del gioco."),
    "Voices": ("Voix", "Stimmen", "Voci"),
    "Language of the voices. Applied when the game restarts.": (
        "Langue des voix. S'applique au redemarrage du jeu.",
        "Sprache der Stimmen. Gilt nach dem Neustart des Spiels.",
        "Lingua delle voci. Si applica al riavvio del gioco."),
    "Save states": ("Sauvegardes rapides", "Speicherstaende", "Salvataggi rapidi"),
    "Slot": ("Emplacement", "Platz", "Slot"),
    "Slot used by Save and Load state.": ("Emplacement utilise pour sauvegarder et charger.",
                                          "Platz fuer Speichern und Laden.", "Slot usato da Salva e Carica stato."),
    "Save state": ("Sauvegarder", "Zustand speichern", "Salva stato"),
    "Saves the game to the selected slot.": ("Sauvegarde la partie dans l'emplacement choisi.",
                                             "Speichert das Spiel im gewaehlten Platz.",
                                             "Salva la partita nello slot scelto."),
    "Load state": ("Charger", "Zustand laden", "Carica stato"),
    "Loads the game from the selected slot.": ("Charge la partie de l'emplacement choisi.",
                                               "Laedt das Spiel aus dem gewaehlten Platz.",
                                               "Carica la partita dallo slot scelto."),
    "Display": ("Affichage", "Anzeige", "Schermo"),
    "Mode": ("Mode", "Modus", "Modalita"),
    "Window or fullscreen.": ("Fenetre ou plein ecran.", "Fenster oder Vollbild.", "Finestra o schermo intero."),
    "Window size": ("Taille de la fenetre", "Fenstergroesse", "Dimensione finestra"),
    "Size of the window in windowed mode.": ("Taille de la fenetre en mode fenetre.",
                                             "Groesse des Fensters im Fenstermodus.",
                                             "Dimensione della finestra in modalita finestra."),
    "Layout": ("Disposition", "Anordnung", "Disposizione"),
    "Screens stacked or side by side.": ("Ecrans l'un sur l'autre ou cote a cote.",
                                         "Bildschirme uebereinander oder nebeneinander.",
                                         "Schermi uno sopra l'altro o affiancati."),
    "Scaling": ("Mise a l'echelle", "Skalierung", "Scala"),
    "Fill the window, or integer scaling without distorting pixels.": (
        "Remplir la fenetre, ou echelle entiere sans deformer les pixels.",
        "Fenster fuellen oder ganzzahlig skalieren, ohne Pixel zu verzerren.",
        "Riempi la finestra, o scala intera senza deformare i pixel."),
    "VSync": ("VSync", "VSync", "VSync"),
    "Syncs the picture with the monitor (avoids tearing).": (
        "Synchronise l'image avec l'ecran (evite les dechirures).",
        "Synchronisiert das Bild mit dem Monitor (verhindert Tearing).",
        "Sincronizza l'immagine con il monitor (evita il tearing)."),
    "Controls": ("Commandes", "Steuerung", "Comandi"),
    "Input": ("Entree", "Eingabe", "Input"),
    "Resume game": ("Reprendre", "Weiterspielen", "Riprendi"),
    "Close settings and return to the game.": ("Ferme le menu et revient au jeu.",
                                               "Schliesst das Menue und kehrt zum Spiel zurueck.",
                                               "Chiude il menu e torna al gioco."),
    "Quit": ("Quitter", "Beenden", "Esci"),
    "Close the game.": ("Ferme le jeu.", "Beendet das Spiel.", "Chiude il gioco."),
    "Audio": ("Audio", "Audio", "Audio"),
    "Volume": ("Volume", "Lautstaerke", "Volume"),
    "Window": ("Fenetre", "Fenster", "Finestra"),
    "Fullscreen": ("Plein ecran", "Vollbild", "Schermo intero"),
    "Vertical": ("Vertical", "Vertikal", "Verticale"),
    "Horizontal": ("Horizontal", "Horizontal", "Orizzontale"),
}
for d in range(10):
    T[f"Keypad {d}"] = (f"{d} (pave num.)", f"{d} (Ziffernblock)", f"{d} (tast. num.)")
for b in ("A", "B", "X", "Y", "L", "R", "Start", "Select"):
    T[f"Key for the {b} button."] = (f"Touche du bouton {b}.", f"Taste fuer den {b}-Knopf.", f"Tasto del pulsante {b}.")
for en, fr, de, it in (("up", "haut", "hoch", "su"), ("down", "bas", "runter", "giu"),
                       ("left", "gauche", "links", "sinistra"), ("right", "droite", "rechts", "destra")):
    T[f"Key for D-pad {en}."] = (f"Touche de la croix : {fr}.", f"Taste fuer das Steuerkreuz: {de}.",
                                 f"Tasto della croce: {it}.")
for k, v in T.items():                  # la letra del menu no tiene tildes
    assert all(ord(c) < 128 for c in k + "".join(v)), k


def c(t):
    return t.replace("\\", "\\\\").replace('"', '\\"')


s = open(PATH, encoding="utf-8", newline="").read()
if MARCA in s:
    print("frontend.cpp: el parche ya estaba aplicado."); sys.exit(0)
if "IE1_MENU_TRADUCCION" not in s or "IE1_MENU_INFO_MODS" not in s:
    sys.exit("Faltan parches anteriores (parche_menu_traduccion.py y parche_menu_info_mods.py). No toco nada.")
nl = "\r\n" if "\r\n" in s else "\n"


def cambiar(viejo, nuevo, nombre):
    global s
    viejo, nuevo = viejo.replace("\n", nl), nuevo.replace("\n", nl)
    if s.count(viejo) != 1:
        sys.exit(f"No encontre exactamente una vez: {nombre}. No toco nada.")
    s = s.replace(viejo, nuevo)


# 1) idioma del menu (0 en, 1 es, 2 fr, 3 de, 4 it) y tabla de frances, aleman e italiano
tabla = "".join(f'        {{"{c(k)}", "{c(v[0])}", "{c(v[1])}", "{c(v[2])}"}},{nl}' for k, v in T.items())
cambiar('''bool ie1_menu_en_espanol() {
    static int es = -1;''', '''// IE1_MENU_5IDIOMAS: frances, aleman e italiano (parche_menu_5idiomas.py)
int g_ie1_menu_lang = 0;          // 0 en, 1 es, 2 fr, 3 de, 4 it
struct Ie1Traduccion3 { const char* en; const char* fr; const char* de; const char* it; };
const Ie1Traduccion3 kIe1Traducciones3[] = {
''' + tabla.replace(nl, "\n") + '''};
bool ie1_menu_en_espanol() {
    static int es = -1;''', "ie1_menu_en_espanol")
cambiar('''        es = idioma == "es" ? 1 : 0;
    }
    return es == 1;''', '''        es = idioma == "es" ? 1 : 0;
        g_ie1_menu_lang = idioma == "es" ? 1 : idioma == "fr" ? 2 : (idioma == "de" || idioma == "ge") ? 3 : idioma == "it" ? 4 : 0;
    }
    return es == 1;''', "idioma del menu")
cambiar('''const char* ie1_tr(const char* t) {
    if (!t) return t;
    const bool es = ie1_menu_en_espanol();
    for (const auto& x : kIe1Traducciones)
        if (!std::strcmp(t, x.original)) return es ? x.es : x.en;''', '''int ie1_menu_idioma() { ie1_menu_en_espanol(); return g_ie1_menu_lang; }
const char* ie1_tr3(const char* en) {        // ingles -> frances, aleman o italiano
    const int l = ie1_menu_idioma();
    if (l < 2 || !en) return en;
    for (const auto& x : kIe1Traducciones3)
        if (!std::strcmp(en, x.en)) return l == 2 ? x.fr : l == 3 ? x.de : x.it;
    return en;
}
const char* ie1_tr(const char* t) {
    if (!t) return t;
    const bool es = ie1_menu_en_espanol();
    for (const auto& x : kIe1Traducciones)
        if (!std::strcmp(t, x.original)) return es ? x.es : ie1_tr3(x.en);''', "ie1_tr")

# 2) nombre de los mods en su idioma (mod.txt: nombre_fr, nombre_de, nombre_it)
cambiar('''        const std::string k = clave, ken = k + "_en";''',
        '''        const std::string k = clave, ken = k + "_en";
        static const char* const kSufijo[5] = {"", "", "_fr", "_de", "_it"};  // IE1_MENU_5IDIOMAS
        const std::string kloc = k + kSufijo[ie1_menu_idioma()];
        std::string loc;''', "claves de mod.txt")
cambiar('''            if (l.compare(0, eq, ken) == 0 && eq == ken.size()) en = l.substr(eq + 1);''',
        '''            if (l.compare(0, eq, ken) == 0 && eq == ken.size()) en = l.substr(eq + 1);
            if (ie1_menu_idioma() >= 2 && l.compare(0, eq, kloc) == 0 && eq == kloc.size()) loc = l.substr(eq + 1);''',
        "leer nombre en su idioma")
cambiar('''        return (!ie1_menu_en_espanol() && !en.empty()) ? en : base;''',
        '''        if (!loc.empty()) return loc;
        return (!ie1_menu_en_espanol() && !en.empty()) ? en : base;''', "devolver nombre en su idioma")

# 3) linea de ayuda de los mods
i = s.find("const char* ie1_mod_descripcion(int i)")
j = s.find("}", i)
if i < 0 or j < 0:
    sys.exit("No encontre ie1_mod_descripcion. No toco nada.")
s = s[:i] + ('''const char* ie1_mod_descripcion(int i) {   // IE1_MENU_INFO_MODS2: una sola linea (IE1_MENU_5IDIOMAS)
    (void)i;
    static const char* const k[5] = {
        "Turn on or off (on restart). Info: launcher, Tab.",
        "Activar o desactivar (al reiniciar). Info: lanzador, Tab.",
        "Activer ou desactiver (au redemarrage). Infos : lanceur, Tab.",
        "An- oder ausschalten (nach Neustart). Infos: Starter, Tab.",
        "Attiva o disattiva (al riavvio). Info: launcher, Tab."};
    return k[ie1_menu_idioma()];
''').replace("\n", nl) + s[j:]

open(PATH, "w", encoding="utf-8", newline="").write(s)
print("frontend.cpp: menu de Esc en ingles, espanol, frances, aleman e italiano.")
print("Recompila con: bash scripts/paso_mingw.sh")
