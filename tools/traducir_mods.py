#!/usr/bin/env python3
"""
Anade a la ficha (mod.txt) de cada mod sus textos en frances, aleman e italiano:
nombre_fr, descripcion_fr, desbloqueo_fr (y lo mismo con _de y _it). El lanzador y el
menu de Esc los usan cuando el idioma de los textos es ese; si falta alguno, sale en ingles.

Solo toca los mods que conoce (los de este proyecto) y solo esas claves: lo demas de cada
mod.txt se queda igual. Se puede ejecutar varias veces (por ejemplo, despues de volver a
crear un mod con su script).
   python scripts/traducir_mods.py            (carpeta mods de C:/dev/ie1recomp)
   python scripts/traducir_mods.py RUTA/mods

Los nombres van sin tildes porque el menu de Esc solo tiene letras sin tilde; las
descripciones (que solo se ven en el lanzador) si las llevan.
"""
import os
import sys

MODS = "C:/dev/ie1recomp/mods"

T = {
    "filtros_supertecnicas": {
        "fr": ("Filtres des techniques",
               "Ajoute le bouton X \"Filtres\" à la liste des carnets de techniques (Inventaire > Techniques > "
               "Apprendre) : filtre par type (tir, dribble, défense, arrêt, talent) et par élément, et trie par PT "
               "(dans les deux sens) ou par nom (A-Z ou Z-A). Il s'ouvre aussi en touchant le bouton.",
               "Toujours actif."),
        "de": ("Filter fuer Spezialtechniken",
               "Fügt der Liste der Technik-Notizbücher (Inventar > Techniken > Lernen) die X-Taste \"Filter\" hinzu: "
               "filtert nach Typ (Schuss, Dribbling, Abwehr, Parade, Talent) und Element und sortiert nach TP "
               "(in beide Richtungen) oder nach Name (A-Z oder Z-A). Öffnet sich auch durch Antippen der Taste.",
               "Immer aktiv."),
        "it": ("Filtri delle tecniche",
               "Aggiunge il pulsante X \"Filtri\" all'elenco dei quaderni delle tecniche (Inventario > Tecniche > "
               "Impara): filtra per tipo (tiro, dribbling, difesa, parata, abilità) ed elemento, e ordina per PT "
               "(in entrambi i sensi) o per nome (A-Z o Z-A). Si apre anche toccando il pulsante.",
               "Sempre attivo."),
    },
    "talentos_ie2": {
        "fr": ("Talents facon IE2",
               "Active les talents pendant les matchs, comme dans Inazuma Eleven 2. Les talents sont les techniques de "
               "type Talent de certains joueurs : le jeu avait déjà tous leurs effets, mais ils n'étaient jamais "
               "appliqués. Au début de chaque match, chaque talent donne son effet au joueur qui l'a, aux coéquipiers "
               "de son poste ou à toute l'équipe. Rien ne change dans ta sauvegarde.",
               "Toujours actif : tu le remarques dès qu'un match commence avec des joueurs qui ont des talents."),
        "de": ("Talente wie in IE2",
               "Aktiviert die Talente in den Spielen, wie in Inazuma Eleven 2. Talente sind die Techniken vom Typ "
               "Talent mancher Spieler: Das Spiel hatte schon alle ihre Effekte, aber sie wurden nie angewendet. Zu "
               "Beginn jedes Spiels gibt jedes Talent seinen Effekt dem Spieler, der es hat, den Mitspielern auf seiner "
               "Position oder dem ganzen Team. An deinem Spielstand ändert sich nichts.",
               "Immer aktiv: Du merkst es, sobald ein Spiel mit Spielern beginnt, die Talente haben."),
        "it": ("Talenti come in IE2",
               "Attiva i talenti nelle partite, come in Inazuma Eleven 2. I talenti sono le tecniche di tipo Talento "
               "di alcuni giocatori: il gioco aveva già tutti i loro effetti, ma non venivano mai applicati. All'inizio "
               "di ogni partita, ogni talento dà il suo effetto al giocatore che lo possiede, ai compagni del suo ruolo "
               "o a tutta la squadra. Nel salvataggio non cambia nulla.",
               "Sempre attivo: lo noti appena inizia una partita con giocatori che hanno talenti."),
    },
    "tiro_ie2": {
        "fr": ("Tir facon IE2",
               "Apporte le système de tir d'Inazuma Eleven 2 aux matchs : le bouton S apparaît sur l'écran tactile "
               "(tu peux le déplacer où tu veux) et, en le touchant avec le ballon, ton joueur tire au but d'où il est. "
               "Il permet aussi les tirs lointains (Tir comète, Arc-en-ciel...) hors de la surface. Il utilise le code "
               "du jeu lui-même, qui était désactivé ; rien ne change dans ta sauvegarde. Au choix de la technique, les tirs lointains portent un T et les blocages un B à côté du nom.",
               "Toujours actif : tu le remarques dès qu'un match commence."),
        "de": ("Schuss wie in IE2",
               "Bringt das Schusssystem von Inazuma Eleven 2 in die Spiele: Auf dem Touchscreen erscheint die S-Taste "
               "(du kannst sie beliebig verschieben), und wenn du sie mit Ball berührst, schießt dein Spieler von dort "
               "aufs Tor, wo er gerade ist. Außerdem sind Fernschüsse (Kometenschuss, Regenbogen...) von außerhalb des "
               "Strafraums möglich. Es nutzt den eigenen Code des Spiels, der abgeschaltet war; an deinem Spielstand "
               "ändert sich nichts. Bei der Technikwahl tragen Fernschüsse ein L und Blocktechniken ein B neben dem Namen.",
               "Immer aktiv: Du merkst es, sobald ein Spiel beginnt."),
        "it": ("Tiro come in IE2",
               "Porta nelle partite il sistema di tiro di Inazuma Eleven 2: sul touch screen compare il pulsante S "
               "(puoi spostarlo dove vuoi) e, toccandolo con la palla, il tuo giocatore tira in porta da dove si trova. "
               "Permette anche i tiri da lontano (Tiro cometa, Arcobaleno...) da fuori area. Usa il codice del gioco "
               "stesso, che era disattivato; nel salvataggio non cambia nulla. Nella scelta della tecnica, i tiri da lontano hanno una T e i blocchi una B accanto al nome.",
               "Sempre attivo: lo noti appena inizia una partita."),
    },
    "ojeo_instantaneo": {
        "fr": ("Recrutement instantane",
               "Les recherches de Celia et de Nelly sont prêtes tout de suite, comme dans Inazuma Eleven 2 : sans "
               "scène, attente ni appel ; reparle-leur pour voir les candidats. Si une recherche était déjà en cours, "
               "l'appel arrive immédiatement. Les candidats et les recrutements sont ceux du jeu.",
               "Toujours actif : tu le remarques en demandant une recherche à Celia ou à Nelly."),
        "de": ("Sofortige Spielersuche",
               "Die Suchen von Celia und Nelly sind sofort fertig, wie in Inazuma Eleven 2: ohne Zwischensequenz, "
               "Wartezeit oder Anruf; sprich sie noch einmal an, um die Kandidaten zu sehen. Lief schon eine Suche, "
               "kommt der Anruf sofort. Kandidaten und Anwerbungen sind die des Spiels.",
               "Immer aktiv: Du merkst es, wenn du Celia oder Nelly um eine Suche bittest."),
        "it": ("Osservazione istantanea",
               "Le ricerche di Celia e Nelly sono pronte subito, come in Inazuma Eleven 2: senza scene, attese né "
               "chiamate; parla di nuovo con loro per vedere i candidati. Se una ricerca era già in corso, la "
               "chiamata arriva subito. Candidati e reclutamenti sono quelli del gioco.",
               "Sempre attivo: lo noti quando chiedi una ricerca a Celia o a Nelly."),
    },
    "valor_escenas": {
        "fr": ("Puissance dans les techniques",
               "Affiche la puissance totale de chaque joueur pendant les scènes des techniques : les deux valeurs "
               "dans les duels de dribble, de défense et tir-contre, celle du tir pendant son calcul et, quand il "
               "arrive au gardien, la puissance avec laquelle il arrive (distance comprise) et celle de l'arrêt. "
               "Le gagnant s'affiche en rouge. Dans les duels et les arrêts, la barre de PT passe au centre.",
               "Toujours actif : visible dans n'importe quel match quand une technique est utilisée."),
        "de": ("Kraft bei Spezialtechniken",
               "Zeigt die Gesamtkraft jedes Spielers in den Szenen der Spezialtechniken: beide Werte bei Dribbling-, "
               "Abwehr- und Schuss-Block-Duellen, den Wert des Schusses während der Berechnung und, wenn er den "
               "Torwart erreicht, mit wie viel Kraft er ankommt (mit Entfernung) und die der Parade. Der Sieger "
               "erscheint rot. Bei Duellen und Paraden wandert die TP-Leiste in die Mitte.",
               "Immer aktiv: in jedem Spiel zu sehen, wenn eine Spezialtechnik eingesetzt wird."),
        "it": ("Potenza nelle tecniche",
               "Mostra la potenza totale di ogni giocatore nelle scene delle tecniche: i due valori nei duelli di "
               "dribbling, difesa e tiro-blocco, quello del tiro mentre viene calcolato e, quando arriva al portiere, "
               "con quanta potenza arriva (distanza compresa) e quella della parata. Il vincitore appare in rosso. "
               "Nei duelli e nelle parate la barra dei PT passa al centro.",
               "Sempre attivo: si vede in qualsiasi partita quando si usa una tecnica."),
    },
    "niveles_supertecnicas": {
        "fr": ("Niveaux des techniques",
               "Les techniques montent de niveau à force d'être utilisées, comme dans Inazuma Eleven 2 : elles "
               "gagnent en puissance et leur marque (+, ++, N2...) s'affiche à côté du nom. L'annonce de montée "
               "de niveau n'apparaît que si tu as donné la ROM d'IE2 dans cette langue.",
               "Toujours actif : utilise tes techniques en match (selon le type, elles montent après 6 à 100 utilisations)."),
        "de": ("Technik-Stufen",
               "Spezialtechniken steigen durch Benutzung auf, wie in Inazuma Eleven 2: Sie werden stärker und ihr "
               "Zeichen (+, ++, S2...) erscheint neben dem Namen. Die Aufstiegsanzeige erscheint nur, wenn die "
               "IE2-ROM in dieser Sprache angegeben wurde.",
               "Immer aktiv: Setze deine Techniken in Spielen ein (je nach Typ steigen sie nach 6 bis 100 Einsätzen auf)."),
        "it": ("Livelli delle tecniche",
               "Le tecniche salgono di livello con l'uso, come in Inazuma Eleven 2: guadagnano potenza e il loro "
               "segno (+, ++, L2...) appare accanto al nome. L'avviso di salita di livello appare solo se hai dato "
               "la ROM di IE2 in questa lingua.",
               "Sempre attivo: usa le tecniche nelle partite (a seconda del tipo, salgono dopo 6-100 utilizzi)."),
    },
    "entrenamiento_libre": {
        "fr": ("Entrainement libre",
               "Un entraîneur en haut de la Tour ouvre un menu pour entraîner tes joueurs : PE, PT et statistiques "
               "en échange de Passion (450 par point). Avec X, le joueur revient gratuitement au niveau 1 : il garde "
               "ses techniques et perd tout l'entraînement (avec le mod des niveaux, ses techniques reviennent à 0 "
               "utilisation).",
               "Termine l'histoire (gagne le Football Frontier) et monte en haut de la Tour."),
        "de": ("Freies Training",
               "Ein Trainer oben auf dem Turm öffnet ein Menü zum Trainieren deiner Spieler: GP, TP und Werte gegen "
               "Leidenschaft (450 pro Punkt). Mit X kehrt der Spieler kostenlos auf Level 1 zurück: Er behält seine "
               "Techniken und verliert alles Trainierte (mit dem Technik-Stufen-Mod gehen seine Techniken auf 0 "
               "Einsätze zurück).",
               "Beende die Geschichte (gewinne den Football Frontier) und geh ganz nach oben auf den Turm."),
        "it": ("Allenamento libero",
               "Un allenatore in cima alla Torre apre un menu per allenare i tuoi giocatori: PE, PT e statistiche in "
               "cambio di Passione (450 per punto). Con X il giocatore torna gratis al livello 1: conserva le sue "
               "tecniche e perde tutto l'allenamento (con il mod dei livelli, le sue tecniche tornano a 0 usi).",
               "Completa la storia (vinci il Football Frontier) e sali in cima alla Torre."),
    },
    "colores_afinidad": {
        "fr": ("Couleurs par affinite",
               "Les noms des techniques s'affichent dans la couleur de leur affinité, comme dans Victory Road : "
               "feu en rouge, air en bleu, forêt en vert et montagne en marron. Sur la bannière de la technique "
               "et sur les boutons de techniques pendant les matchs.",
               "Toujours actif."),
        "de": ("Farben nach Element",
               "Die Namen der Spezialtechniken erscheinen in der Farbe ihres Elements, wie in Victory Road: "
               "Feuer rot, Wind blau, Wald grün und Berg braun. Auf dem Banner der Technik und auf den "
               "Technik-Tasten im Spiel.",
               "Immer aktiv."),
        "it": ("Colori per affinita",
               "I nomi delle tecniche appaiono nel colore della loro affinità, come in Victory Road: fuoco "
               "rosso, aria blu, bosco verde e montagna marrone. Sul cartello della tecnica e sui pulsanti "
               "delle tecniche durante le partite.",
               "Sempre attivo."),
    },
    "pasion_amistad_max": {
        "fr": ("Passion et Amitie au max",
               "Garde la Passion et l'Amitié à 999999.",
               "Toujours actif."),
        "de": ("Leidenschaft und Freundschaft max",
               "Hält Leidenschaft und Freundschaft auf 999999.",
               "Immer aktiv."),
        "it": ("Passione e Amicizia al massimo",
               "Mantiene Passione e Amicizia a 999999.",
               "Sempre attivo."),
    },
    "voces_jp": {
        "fr": ("Voix japonaises",
               "Les cinématiques utilisent les voix japonaises originales et l'opening est le japonais, avec sa "
               "chanson et sa vidéo.",
               "Toujours actif : on l'entend dans l'opening et les cinématiques."),
        "de": ("Japanische Stimmen",
               "Die Zwischensequenzen laufen mit den japanischen Originalstimmen und das Opening ist das "
               "japanische, mit seinem Lied und seinem Video.",
               "Immer aktiv: zu hören im Opening und in den Zwischensequenzen."),
        "it": ("Voci giapponesi",
               "I filmati usano le voci originali giapponesi e l'opening è quello giapponese, con la sua canzone "
               "e il suo video.",
               "Sempre attivo: si sente nell'opening e nei filmati."),
    },
}


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else MODS
    if not os.path.isdir(carpeta):
        sys.exit(f"No encuentro la carpeta de mods: {carpeta}")
    hechos = 0
    for mod in sorted(os.listdir(carpeta)):
        ruta = os.path.join(carpeta, mod, "mod.txt")
        if mod not in T or not os.path.isfile(ruta):
            continue
        lineas = open(ruta, encoding="utf-8", errors="replace").read().splitlines()
        claves = {}
        for lang, (nombre, desc, desb) in T[mod].items():
            claves[f"nombre_{lang}"] = nombre
            claves[f"descripcion_{lang}"] = desc
            claves[f"desbloqueo_{lang}"] = desb
        nuevas = [l for l in lineas if l.split("=", 1)[0] not in claves]
        nuevas += [f"{k}={v}" for k, v in claves.items()]
        open(ruta, "w", encoding="utf-8", newline="\n").write("\n".join(nuevas) + "\n")
        hechos += 1
        print(f"  {mod}: fr, de, it")
    sin = [m for m in sorted(os.listdir(carpeta)) if os.path.isfile(os.path.join(carpeta, m, "mod.txt")) and m not in T]
    print(f"{hechos} mods traducidos." + (f" Sin traduccion (saldran en ingles): {', '.join(sin)}" if sin else ""))


if __name__ == "__main__":
    main()
