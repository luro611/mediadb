# MusikDB – Ausführliche Anleitung (Version 1.0)

MusikDB ist eine **private Musikdatenbank für den eigenen Rechner**. Du erfasst deine CDs (per Barcode, Künstlersuche, Tabelle oder von Hand) und deine Musikdateien (MP3, M4A, FLAC …). Die App ergänzt Titellisten, Cover und Genres aus freien Internetquellen und zeigt alles in einer Weboberfläche im Browser. Die Daten bleiben bei dir.

## 1. Was die App kann

**Erfassen**
- **Barcode:** Scanner oder Eingabe. Zu einem Barcode werden bei MusicBrainz die passenden Ausgaben gesucht (offizielle zuerst, dann die älteste; Bootlegs eingeklappt). Unvollständige Barcodes (10/11 Ziffern) werden ergänzt, Striche und Leerzeichen ignoriert.
- **Diskografie-Suche ohne Scanner:** Interpret wählen, dann alle seine CDs als Liste (nach Albumtitel, mit A–Z-Leiste und Barcode), Ausgabe wählen, „Das ist meine CD“.
- **Von Hand:** Alle Felder frei eintragbar.
- **Tabelle importieren (Excel, ODS, CSV):** Interpret und Albumtitel genügen, den Rest holt die App von MusicBrainz. Mit Probelauf und Vorschau.
- **Audio-Import:** Musikordner (z. B. auf einer externen Platte) einlesen. Abgleich mit vorhandenen CDs über die Titellisten, Cover und Genre werden ergänzt.
- **Ähnliche Ausgabe suchen:** Wird bei MusicBrainz nichts Eindeutiges gefunden, zeigt die App ähnliche Ausgaben zur Auswahl. Zusätzlich kann ein **Discogs-Link** eingefügt werden (Vorschau, dann bestätigen).

**Verwalten und ansehen**
- Startseite: Sammlung als **Interpreten-Übersicht** mit A–Z-Leiste, Klick zeigt die CDs; Reiter „Alle CDs“.
- **Besitz** je Eintrag: Physische CD, Nur digital, CD + digital; Dateiformate (MP3, M4A, FLAC …).
- **Suche** über ein Feld (Künstler, Album, Genre, Label, Songtitel, Notizen; mehrere Wörter = alle müssen passen) plus Filter für Künstler, Genre und Jahr. Sortieren per Klick.
- **Compilations** sind ein einziger Eintrag („Various Artists“), gefunden werden sie auch über die Interpreten der einzelnen Titel.
- Cover, Titellisten mit Laufzeiten, Label, Katalognummer, Land, Jahr der CD **und** Erscheinungsdatum des Albums, Genre und Styles.
- Sammelaktionen mit Fortschrittsanzeige: **Fehlende Cover laden**, **Fehlende Genres laden**, **Alle aus MusicBrainz aktualisieren** (füllt nur Leeres, überschreibt nichts).

**Sichern und mitnehmen**
- **Export** als xlsx (Excel), ods (LibreOffice), csv (Semikolon, UTF-8 mit BOM, öffnet in Excel richtig) oder Markdown; wahlweise alles, nur CDs oder nur Digitales. Die Excel-Datei dient zugleich als Sicherung: Beim Import wird sie erkannt und vollständig wiederhergestellt.

## 2. Installation (Mac, Windows, Linux)

Voraussetzung: **Docker**, auf dem Mac z. B. **OrbStack** oder Docker Desktop.

1. Projektordner entpacken oder von Codeberg laden.
2. Im Terminal in den Projektordner wechseln.
3. `cp .env.example .env` und die Datei `.env` bearbeiten: bei `MB_USER_AGENT` **deine eigene E-Mail-Adresse** eintragen (MusicBrainz verlangt eine Kontaktmöglichkeit).
4. `docker compose up --build`
5. Im Browser `http://localhost:8000` öffnen.

Stoppen: `docker compose down`. Neu bauen nach einem Update: `docker compose up --build`. Fehler ansehen: `docker compose logs --tail 60`.

**Daten:** Datenbank und Cover liegen im Ordner `data/`. Das sind **deine Daten**: sichern, bei Updates nie überschreiben.

**Update einspielen:** neue Dateien über das Projekt kopieren (`app`, `static`, `docker-compose.yml`, `requirements.txt`), `data/` und `.env` nicht anfassen, dann `docker compose down` und `docker compose up --build`, im Browser Cmd+Shift+R (Windows/Linux Strg+Shift+R).

**Musikordner sichtbar machen:** `docker-compose.yml` bindet auf dem Mac `/Volumes` (externe Laufwerke) und den Benutzerordner nur lesend ein. Beim ersten Zugriff muss macOS ggf. erlauben: Systemeinstellungen → Datenschutz & Sicherheit → Dateien und Ordner bzw. Vollständiger Festplattenzugriff für OrbStack. Unter Linux/Windows die Pfade in `docker-compose.yml` anpassen.

## 3. Einstellungen in `.env`
| Eintrag | Bedeutung |
|---|---|
| `MB_USER_AGENT` | Pflicht. Name und E-Mail, z. B. `MusikDB/1.0 (du@example.com)` |
| `DISCOGS_TOKEN` | Optional. Kostenloser Token (discogs.com → Einstellungen → Entwickler). Schaltet die Discogs-Suche frei. |
| `COVER_WEB` | `1` (Standard) oder `0`. Bei `0` werden keine Cover von iTunes/Deezer geholt (siehe Rechtliches). |

## 4. Die wichtigsten Abläufe

**CD mit Barcode erfassen:** Hinzufügen → Barcode eingeben/scannen → Treffer wählen → „Diesen Treffer speichern“. Cover und Tracks kommen mit.

**Alles aus einer Tabelle:** Hinzufügen → Tabelle importieren → Datei hochladen → Spalten prüfen (Interpret, Titel, Barcode, Jahr) → Abgleichen. Die App sucht jede Zeile bei MusicBrainz (etwa eine pro Sekunde). In der Vorschau stehen die Gruppen *gefunden*, *bitte prüfen*, *nicht gefunden*, *schon vorhanden*. Standard: Vorhandenes wird übersprungen, nicht Gefundenes als einfacher Eintrag angelegt. Erst „Übernehmen“ speichert.

**Musikdateien einlesen:** Hinzufügen → Audio-Import → Ordner wählen → Einlesen. Regeln:
- Ein Ordner ist ein Album; mehrere Formate desselben Albums (MP3 + M4A) bleiben ein Eintrag; Disc-Ordner werden zusammengefasst.
- Abgleich über die **Titelliste**: gleiche Titel = dieselbe CD (dann nur „+ digital“ und Format vermerkt); abweichende Titel (Remaster mit Bonus) = eigener Eintrag.
- Sampler erkennt die App daran, dass die Titel von verschiedenen Interpreten sind.
- Erneut einlesen ist gefahrlos. Bekannte Dateien werden übersprungen.
- Bis zu „Übernehmen“ wird nichts gespeichert.

**Cover oder Daten fehlen:** Eintrag öffnen → „Ähnliche Ausgabe suchen“ → Treffer wählen oder Discogs-Link einfügen → bestätigen. Als letzte Möglichkeit: eine Datei `cover.jpg` in den Musikordner legen.

## 5. Woher kommen die Daten?
Hauptquelle ist **MusicBrainz** (Daten) mit dem **Cover Art Archive** (Bilder). Optional **Discogs**, als Cover-Ausweichquelle **iTunes** und **Deezer**, außerdem die Tags in deinen Musikdateien. Zusammengefasst: Es werden nur Suchbegriffe gesendet, deine Daten bleiben lokal. Genaueres, auch zur Frage „Darf ich das?“, steht in **DATENQUELLEN_UND_RECHT.md**.

## 6. Grenzen (Version 1.0)
- Kein Mehrbenutzerbetrieb, keine Anmeldung; gedacht für einen lokalen Rechner. Nicht ins offene Internet stellen.
- Nur Musik (CDs, Audiodateien). Filme und Serien folgen in Version 2 (siehe ROADMAP.md).
- Gelöschte oder verschobene Audiodateien werden nicht automatisch bereinigt.
- Cover von iTunes/Deezer sind rechtlich eine Grauzone und lassen sich mit `COVER_WEB=0` abschalten.
- Sehr alte, seltene oder nur lokal veröffentlichte Alben fehlen manchmal bei MusicBrainz; dann hilft Discogs oder die Handerfassung.
- Die Software wurde ohne automatisierte Tests entwickelt und von einem Nutzer im Alltag geprüft; Fehler bitte mit der Ausgabe von `docker compose logs --tail 60` melden.

## 7. Fehlersuche
| Problem | Lösung |
|---|---|
| Seite nicht erreichbar | `docker compose ps` prüfen, `docker compose up -d`, notfalls `docker compose logs --tail 60` |
| Container startet in Dauerschleife | Im Log die erste Zeile mit `Traceback` lesen; meist ein Fehler in einer frisch eingespielten Datei |
| Musikordner leer oder „Zugriff verweigert“ | macOS-Zugriff für OrbStack/Docker erlauben (siehe 2.) |
| MusicBrainz antwortet nicht | Später erneut versuchen; die App hält 1 Anfrage/s ein |
| Barcode findet nichts | Vollständigkeit prüfen (12/13 Ziffern), sonst „Ähnliche Ausgabe suchen“ |
| Cover nicht gefunden | Siehe 4., letzter Absatz |
