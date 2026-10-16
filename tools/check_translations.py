#!/usr/bin/env python3
"""Prüft, ob alle Texte in den Vorlagen (app/templates) in app/locales/<sprache>.json übersetzt sind.
Aufruf im Projektordner:  python3 tools/check_translations.py
Texte stehen in den Vorlagen als {{ _("Deutscher Text") }}; ein § steht für eingesetzte Werte.
Dazu kommen Meldungen aus app/main.py, app/audio.py und app/importer.py (siehe EXTRA unten)."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ['en', 'fr', 'es', 'it']
PAT = re.compile(r"""\b_t?\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")
# Texte, die ohne _() im Quelltext stehen (Listen, Meldungen aus Python); bei neuen Meldungen hier ergänzen
EXTRA = [
    # Eigene Farben (1.14)
    "Farben gespeichert.", "Farben auf die Vorgaben zurückgesetzt.", "Hell", "Dunkel", "Hintergrund", "Kästen und Eingabefelder", "Schrift", "Nebentext", "Akzent (Überschriften, Knöpfe)", "Links",
    # Als Naechstes (1.11), Spracheinstellungen (1.13)
    "Für „Als Nächstes“ vorgemerkt.", "Von „Als Nächstes“ genommen.", "Hauptsprache gespeichert.", "Umschalter gespeichert.", "Buch",
    # Update-Knopf (1.9.4)
    "Neue Version § verfügbar.", "MediaDB § ist die neueste Version.", "Codeberg ist gerade nicht erreichbar. Bitte später noch einmal versuchen.",
    # NAS aus (1.9.3)
    "Die NAS „§“ ist gerade nicht erreichbar. Ist sie eingeschaltet? Nach dem Einschalten dauert es oft ein bis zwei Minuten, bis sie bereit ist.", "Ordner nicht gefunden oder nicht freigegeben.",
    # NAS-Verbindung pruefen (1.9.2)
    "Bitte Benutzer und Passwort der NAS eintragen. Ein Zugang als Gast ohne Passwort ist nicht möglich.", "Die NAS kennt diesen Benutzer nicht und würde nur einen Gastzugang erlauben. Bitte den Benutzernamen prüfen (genau so, wie er auf der NAS angelegt ist).", "Die NAS spricht wohl nur das alte SMB1. Bitte in der NAS-Oberfläche SMB2 oder SMB3 einschalten.", "Die NAS hat die Verbindung sofort beendet. Meist spricht sie nur das alte SMB1: Bitte in der NAS-Oberfläche SMB2 oder SMB3 einschalten.", "Den Namen „§“ findet MediaDB nicht: Namen mit .local funktionieren im Docker-Container nicht. Bitte die IP-Adresse der NAS eintragen (z. B. 192.168.1.20).", "Den Namen „§“ findet MediaDB im Netz nicht. Bitte die IP-Adresse der NAS eintragen (z. B. 192.168.1.20).", "Die NAS unter § antwortet, aber SMB ist dort nicht eingeschaltet (Port § ist zu). Bitte SMB in der NAS-Oberfläche einschalten.", "Unter § antwortet nichts. Stimmt die Adresse, und ist die NAS eingeschaltet? Läuft MediaDB in einem LXC oder einer VM: Ist die NAS von dort aus erreichbar (Firewall, anderes Netz)?",
    # NAS-Freigaben (1.9)
    "Bitte Name, NAS-Adresse und Freigabe eintragen.", "Die NAS-Adresse ist nicht lesbar (z. B. 192.168.1.20).", "Freigabe nicht gefunden.", "Anmeldung abgelehnt. Bitte Benutzer und Passwort prüfen.", "Die Freigabe gibt es auf der NAS nicht. Bitte den Namen der Freigabe prüfen.", "Den Unterordner gibt es auf der NAS nicht.", "Kein Zugriff: Der Benutzer darf diese Freigabe nicht lesen.", "Die NAS ist nicht erreichbar. Läuft sie, und stimmt die Adresse? SMB muss eingeschaltet sein.", "Fehler beim Zugriff auf die NAS: §", "Verbindung klappt: § Ordner und § Dateien gefunden.", "NAS-Freigabe nicht (mehr) eingerichtet", "NAS-Freigabe", "Freigabe entfernt. Schon eingelesene Einträge bleiben erhalten.",
    # Mediathek (1.8)
    'Die Mediatheken-Suche ist gerade nicht erreichbar.', 'Die Mediatheken-Suche lieferte keine lesbare Antwort.',
    # Verliehen (1.7)
    "Nichts ausgewählt.", "Bitte eintragen, an wen.", "Das Datum ist nicht lesbar (z. B. 24.12.2019 oder nur 2019).", "Nur digital vorhanden oder schon verliehen.", "Nur digital vorhanden – das lässt sich nicht verleihen.", "Dieses Exemplar ist schon verliehen.", "Als verliehen eingetragen.", "Nicht gefunden.", "Als zurückbekommen eingetragen.", "Eintrag gelöscht.", "Wieder als verliehen eingetragen.", "Alles als zurückbekommen eingetragen.", "Gespeichert.", "seit §", "DVD", "Blu-ray", "4K UHD", "CD", "Hardcover", "Taschenbuch", "Hörbuch", "Sonstiges",
    # Buecher: Zusammenfassung und Bewertungen (1.6.1)
    'Zusammenfassung und Bewertungen geladen.', 'Keine weiteren Angaben gefunden.', 'Wikipedia-Text entfernt.',
    'Bücher: Zusammenfassungen und Bewertungen laden',
    # Buecher
    'Hardcover', 'Taschenbuch', 'E-Book', 'Hörbuch', 'Sonstiges', 'Autor', 'Übersetzung', 'Illustration', 'Sprecher', 'Herausgeber', 'Ungelesen', 'Lese ich gerade', 'Gelesen', 'Alle', 'Lieblingsbücher', 'Zuletzt gelesen', 'Zuletzt hinzugefügt', 'E-Books', 'Hörbücher', 'Titel', 'Jahr', 'Bewertung', 'Hinzugefügt', 'Deutsch', 'Englisch', 'Französisch', 'Italienisch', 'Niederländisch', 'Spanisch', '5× löschen', 'Unbedingt lesen', 'Das ist keine gültige ISBN.', 'Kein Buch ausgewählt.', 'Exemplar zum vorhandenen Buch hinzugefügt.', 'Buch nicht gefunden.', 'Buch gelöscht.', 'Ohne ISBN lässt sich nichts nachladen. Bitte über „Anderes Buch zuordnen“ suchen.', 'Nichts gefunden.', 'Leere Felder ergänzt.', 'Neu zugeordnet und alle Angaben übernommen.', 'Das Buch war schon vorhanden; die Exemplare wurden dorthin verschoben.', 'Die Datei konnte nicht gelesen werden (CSV, Excel oder eine ISBN je Zeile).', 'Keine Bücher in der Liste gefunden.', 'Bücher: Ordner durchsuchen', 'Bücher: Dateien lesen', 'Bücher: bei DNB und Open Library suchen', 'Bücher: übernehmen und Titelbilder laden', 'Bücher: Import', '§ Bücher gefunden', 'ISBN aus der Datei', 'Nicht gefunden', 'Titel nur ähnlich', 'DNB nicht erreichbar.', 'DNB lieferte keine lesbare Antwort.', 'Open Library nicht erreichbar.', 'Open Library lieferte keine lesbare Antwort.', 'Originaltitel', 'ISBN', 'Verlag', 'Schlagworte',
    # Einstellungen
    'Filme und Serien in der Datensprache neu laden', 'Bitte eine gültige E-Mail-Adresse eintragen.', 'Die Einstellungen konnten nicht gespeichert werden.', 'Gespeichert. Die Datensprache wurde geändert.', 'Kein TMDB-Schlüssel eingetragen.', 'Der TMDB-Schlüssel funktioniert.', 'Deutsch (Deutschland)', 'Deutsch (Österreich)', 'Deutsch (Schweiz)', 'Englisch (USA)', 'Englisch (Großbritannien)', 'Englisch (Kanada)', 'Englisch (Australien)', 'Französisch (Frankreich)', 'Französisch (Belgien)', 'Französisch (Kanada)', 'Französisch (Schweiz)', 'Spanisch (Spanien)', 'Spanisch (Mexiko)', 'Spanisch (Argentinien)',
    # Hintergrundaufgaben
    'Filme: Ordner einlesen', 'Filme: übernehmen und Poster laden', 'Filme: fehlende Poster laden', 'Filme: Besetzung nachladen', 'Serien: Ordner einlesen', 'Serien: übernehmen, Episodenführer laden', 'Serien und Merkliste aktualisieren', 'Musik: Cover laden', 'Musik: Genres laden', 'Musik: Daten aktualisieren', 'Musik: Audiodateien einlesen', 'Musik: Audiodateien übernehmen', 'Musik: Tabellen-Import',
    # Merkliste
    'Vorgemerkt.', 'Stand schon auf der Merkliste.', 'Von der Merkliste entfernt.', 'Aktualisiert.', 'Nächste Folge', 'Kinostart', 'Digital ab',
    # Serien
    'Abgesetzt',
    'Angefangen',
    'Beendet',
    'Bewertung',
    'Bitte Jahr prüfen',
    'Box entfernt.',
    'Box hinzugefügt.',
    'Box zur vorhandenen Serie hinzugefügt.',
    'Datei neu zugeordnet.',
    'Datei-Eintrag entfernt. Die Datei selbst bleibt unberührt.',
    'Die Serie war schon vorhanden; Dateien und Boxen wurden dorthin verschoben.',
    'Diese Serie ist keinem TMDB-Eintrag zugeordnet.',
    'Episodenführer aktualisiert.',
    'Ganz gesehen',
    'Geplant',
    'Hinzugefügt',
    'In Produktion',
    'Jahr',
    'Keine Serie ausgewählt.',
    'Land',
    'Laufzeit',
    'Läuft noch',
    'Noch nicht angefangen',
    'Originalsprache',
    'Pilot',
    'Sender',
    'Serie gelöscht.',
    'Serie nicht gefunden.',
    'Speichern fehlgeschlagen.',
    'Stichworte',
    'TMDB lieferte keine Daten.',
    'TMDB-Nummer aus dem Namen',
    'TMDB-Nummer aus tvshow.nfo',
    'TMDB-Wertung',
    'Titel nur ähnlich',
    'Unvollständig',
    'Zuletzt hinzugefügt',
    'DVD',
    'Blu-ray',
    '4K UHD',
    'fehlt',
    'fehlen',
    'Alle', 'Vorhandene CDs', 'Nur digital', 'Titel', 'Jahr (CD)', 'Dateiformate', 'Label', 'Katalognr.', 'Styles',
    'Physische CD', 'Nur digital (Audiodateien)', 'CD + digital', 'Digital', 'CD + Digital', 'Gespeichert.',
    'Eintrag nicht gefunden.', 'Kein gültiger Ordner ausgewählt.', 'Ordner nicht gefunden oder nicht freigegeben.',
    # Filme
    'Bild entfernt.', 'Kein Bild gefunden.', 'Bild gespeichert.', 'Das ist keine Bilddatei (JPG, PNG oder WebP).', 'Die Datei ist zu groß (höchstens 15 MB).',
    'Person nicht gefunden.', 'Schauspiel', 'Regie', 'Drehbuch', 'Produktion', 'Musik', 'Kamera', 'Schnitt', 'Szenenbild', 'Kostüm und Maske', 'Visuelle Effekte', 'Filmstab', 'Licht',
    'Datum nicht erkannt. Bitte TT.MM.JJJJ, MM.JJJJ oder JJJJ eingeben.', 'Datum gespeichert.',
    'Bei TMDB nicht gefunden',
    'Bitte einen Barcode eingeben.',
    'Bitte einen Namen eingeben.',
    'Bitte einen Titel eingeben.',
    'Der Film war schon vorhanden; die Exemplare wurden dorthin verschoben.',
    'Dieser Film ist keinem TMDB-Eintrag zugeordnet. Bitte über „Anderen Film zuordnen“ suchen.',
    'Exemplar entfernt.',
    'Exemplar hinzugefügt.',
    'Film gelöscht.',
    'Film nicht gefunden.',
    'Kein Film ausgewählt.',
    'Kein TMDB-Schlüssel eingetragen (siehe Einstellungen).',
    'Kein Titel erkennbar',
    'Liste gelöscht. Die Filme bleiben erhalten.',
    'Listen gespeichert.',
    'Neu zugeordnet und alle Angaben von TMDB übernommen.',
    'Notiz gespeichert.',
    'TMDB lehnt den Schlüssel ab. Bitte TMDB_API_KEY prüfen.',
    'TMDB-Nummer aus .nfo',
    'TMDB-Nummer aus Dateiname',
    'Tageskontingent des Barcode-Dienstes erreicht. Bitte nach Titel suchen.',
    'Titel nur ähnlich',
    'Bitte Jahr prüfen',
    'Von TMDB ergänzt (nur leere Felder).',
    'Liste umbenannt.',
    'Name leer oder schon vergeben.',
    'Neues Exemplar zum vorhandenen Film hinzugefügt.',
    'Speichern fehlgeschlagen.',
    'TMDB lieferte keine Daten.',
    'TMDB nicht erreichbar (§).',
    'TMDB antwortet mit Fehler §.',
    'Barcode-Dienst nicht erreichbar (§).',
    'Alle',
    'Noch nicht gesehen',
    'Top 10: Muss ich sehen',
    'Lieblingsfilme',
    'Zuletzt gesehen',
    'Zuletzt hinzugefügt',
    'Titel',
    'Jahr',
    'Bewertung',
    'Hinzugefügt',
    'Laufzeit',
    'DVD',
    'Blu-ray',
    '4K UHD',
    'Datei',
    '5× löschen',
    'Unbedingt sehen',
    'Regie',
    'Drehbuch',
    'Produktion',
    'Land',
    'Originalsprache',
    'Erschienen',
    'TMDB-Wertung',
    'Stichworte',
]

def keys():
    out = {}
    for f in sorted((ROOT / 'app' / 'templates').glob('*.html')):
        for m in PAT.finditer(f.read_text(encoding='utf-8')):
            v = m.group(1) if m.group(1) is not None else m.group(2)
            v = json.loads('"' + v + '"') if m.group(1) is not None else v.replace("\\'", "'")
            out[' '.join(v.split())] = f.name
    for k in EXTRA:
        out.setdefault(k, 'EXTRA')
    return out

def main():
    ks = keys(); problems = 0
    for lang in LANGS:
        p = ROOT / 'app' / 'locales' / f'{lang}.json'
        t = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        miss = [k for k in ks if k not in t]
        bad = [k for k in t if k.count('§') != t[k].count('§')]
        for k in miss: print(f'[{lang}] fehlt ({ks[k]}): {k[:90]}')
        for k in bad: print(f'[{lang}] Platzhalter § passen nicht: {k[:90]}')
        problems += len(miss) + len(bad)
    print('OK: alles übersetzt' if not problems else f'{problems} Problem(e)')
    return 1 if problems else 0

if __name__ == '__main__':
    sys.exit(main())
