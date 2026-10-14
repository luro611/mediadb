# MusikDB – Projektanleitung

Diese Datei ist das Gedächtnis des Projekts. Wenn ein Chat abbricht oder neu begonnen wird:
**diese Datei und `musikdb.zip` hochladen**, mehr braucht es nicht.

## Worum es geht
Private Medien-Datenbank (Hobbyprojekt, ein Nutzer, Mac). Im Moment: CD- und Musikdateien-Verwaltung (Version 1).
Läuft unter OrbStack/Docker auf dem Mac, Oberfläche im Browser unter http://localhost:8000.

## Entscheidungen (nicht neu diskutieren)
- SQLite bleibt. Postgres ist für ca. 400 CDs und einen Nutzer nicht nötig.
- Digitale Dateien sind formatoffen (MP3, M4A, FLAC und künftig weitere); „digital“ ist der Oberbegriff.
- Die **physisch vorhandene CD hat Vorrang**. Es gibt eine eigene Ansicht „Vorhandene CDs“.
- Eine Neuauflage/Remaster mit Zusatztiteln ist eine **eigene Ausgabe** (eigener Eintrag).
- Kein GitHub. Codeberg: Veröffentlichung geplant (Quellcode ohne Daten, siehe `docs/DATENQUELLEN_UND_RECHT.md`).
- Datenquellen: MusicBrainz (Barcode-Suche), Cover vom Cover Art Archive; optional Discogs; iTunes/Deezer nur als Cover-Ausweichquelle (abschaltbar mit `COVER_WEB=0`).

## Technik
Python, FastAPI, Jinja2-Vorlagen, SQLAlchemy, SQLite, openpyxl (Excel), requests.

## Dateien
- `app/audio.py` – Audio-Import ohne Datenbank (Ordner, Tags, Abgleich); `app/main.py` – übrige Logik: Datenmodell, Routen, MusicBrainz, Cover, Import/Export
- `app/templates/` – `base`, `scan`, `candidates` (Trefferauswahl), `manual` (Erfassen + Bearbeiten), `list` (Sammlung), `detail`, `import`, `audio`
- `static/style.css`, `static/fonts/` – Aussehen
- `data/musikdb.db` – die Datenbank, `data/covers/` – die Cover-Bilder (**das sind deine Daten**)
- `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `.env` (aus `.env.example` kopiert; dort die eigene E-Mail bei `MB_USER_AGENT` eintragen)

## Starten, stoppen, neu bauen
Im Projektordner im Terminal:
- Starten/neu bauen: `docker compose up --build`
- Stoppen: `docker compose down`
- Fehler ansehen: `docker compose logs --tail 60`

## Neue Version einspielen
Zip entpacken, die geänderten Ordner (meist `app`, manchmal `static`) über die Projektdateien kopieren, den Ordner `data` **nie** überschreiben. Dann `docker compose down` und `docker compose up --build`, im Browser `Cmd + Shift + R`.

## Sicherung
Den ganzen Ordner `data` regelmäßig kopieren (Datenbank + Cover). Vor größeren Änderungen den gesamten Projektordner als Zip sichern.

## Was funktioniert
- Barcode-Scan mit MusicBrainz-Suche und Trefferauswahl (offizielle Ausgaben zuerst, dann älteste; Bootlegs eingeklappt)
- Manuelle Erfassung, Bearbeiten, Löschen
- Cover automatisch laden (mit Ausweichsuche), Tracks mit Laufzeiten
- Felder: Jahr auf der CD **und** Erscheinungsdatum (erstes Erscheinen des Albums)
- Sammlung: Sortieren per Klick (auf-/absteigend), gruppiert nach Künstler (CDs eines Künstlers nach Erscheinungsdatum), Suche
- Besitz je CD: Physische CD / Nur digital / CD + digital, dazu das Feld Dateiformate (MP3, M4A, FLAC, … frei eintragbar). Ansichten „Alle · Vorhandene CDs · Nur digital“
- „Alle Einträge aus MusicBrainz aktualisieren“: füllt nur leere Felder, Tracks und Cover nach
- Excel-Import (mit Probelauf) und -Export

- Suche in der Sammlung: ein Feld für Stichworte (Künstler, Album, Genre, Label, Songtitel, Notizen …; mehrere Wörter = alle müssen vorkommen); A–Z-Leiste springt zum Buchstaben (bei Sortierung nach Künstler oder Titel); Spalte Genre, sortierbar.
- Genre: aus MusicBrainz (Release → Release-Group → Künstler, erst Genres, dann Tags); Knopf „Fehlende Genres laden“; beim Audio-Import aus den Datei-Tags.

- Compilations: ein Sampler ist EIN Eintrag (Interpret „Various Artists“, Typ Compilation, Badge in der Liste); die Interpreten der Einzeltitel stehen an den Tracks. Die Suche (Stichwort und Feld „Künstler“) findet Compilations auch über die Titel-Interpreten.

- Cover: Quellen in dieser Reihenfolge – bei Audio-Einträgen erst Bild im Ordner (cover/folder/front.jpg) oder eingebettetes Bild, dann MusicBrainz/Cover Art Archive, dann iTunes und Deezer (nur bei passendem Albumtitel und Interpret); bei CDs MusicBrainz zuerst. Knopf „Fehlende Cover laden“ (Hintergrund, mit Fortschritt) und automatisch nach jedem Audio-Import. Amazon hat keine freie Cover-Schnittstelle.

- Startseite ist die Sammlung als **Interpreten-Übersicht** (alphabetisch mit A–Z-Leiste, ohne führendes „The“); Klick auf einen Interpreten zeigt seine CDs und Dateien, der Reiter „Alle CDs“ die frühere Gesamtliste. Suche und Filter zeigen direkt Alben. Menü: Sammlung · Hinzufügen (Excel-Import und Audio-Import liegen als Karten dort). Der Excel-Export ist kein Menüpunkt, sondern nur eine Kachel auf „Hinzufügen"; er fragt zuerst nach Format (xlsx, ods, csv mit Semikolon und UTF-8-BOM, Markdown) und Umfang (alles / nur CDs / nur digital). Außerdem eine Karte auf „Hinzufügen". „Hinzufügen" bietet Barcode (Scanner/Eingabe) und **Diskografie-Suche** ohne Scanner: Interpret → Interpret wählen → Album wählen → Ausgaben mit Barcode, Label, Katalognummer, Land vergleichen → „Das ist meine CD". Die Diskografie zeigt direkt alle CDs des Interpreten als flache Liste nach Albumtitel sortiert (mit A–Z-Leiste, max. 1500, durchsuchbar nach Barcode, Label, Katalognummer, 1 Stunde im Speicher gemerkt). Interpreten mit genau gleichem Namen stehen oben, ähnliche Namen eingeklappt. Handerfassung weiterhin über einen Link dort.

## Ähnliche Ausgabe suchen
- Wenn bei MusicBrainz nichts Eindeutiges gefunden wurde (z. B. Cover fehlt): auf der Detailseite „Ähnliche Ausgabe suchen" oder in der Liste „Welche?" nach dem Cover-Lauf anklicken. Die App zeigt ähnliche Ausgaben, du wählst eine aus und bestätigst. Dann werden Cover, Titelliste, Genre und leere Felder ergänzt; Vorhandenes bleibt.

- Steht ein Album nur bei Discogs: auf derselben Seite den Link der Discogs-Release-Seite einfügen, Vorschau ansehen und bestätigen. Übernommen werden leere Felder, Titelliste und Cover. Mit einem kostenlosen Token (`DISCOGS_TOKEN=…` in der Datei `.env`) sucht die App auch selbst bei Discogs.

## Tabellen-Import (Karte unter Hinzufügen)
- Formate: .xlsx, .ods, .csv (Trennzeichen und Zeichensatz werden erkannt). Nötig sind nur Interpret + Albumtitel (oder Barcode); Jahr optional. Spalten werden an den Überschriften erkannt und lassen sich zuordnen.
- Ablauf wie beim Audio-Import: hochladen → Spalten prüfen → Probelauf (Abgleich mit MusicBrainz, ca. 1 Anfrage/Sekunde) → Vorschau → „Übernehmen" → Cover und Genre werden im Hintergrund nachgeladen.
- Schon vorhanden = gleicher Barcode oder gleicher Interpret + Titel. Mit Barcode wird genau diese Ausgabe gesucht; ohne Barcode die älteste offizielle CD-Ausgabe (andere zur Auswahl). Nicht Gefundenes wird als einfacher Eintrag (nur Interpret/Titel) angelegt oder übersprungen.
- Eine Sicherungsdatei aus dem eigenen Export (viele Feldnamen als Überschriften) wird erkannt und mit allen Feldern samt Titellisten wiederhergestellt; Cover werden neu geladen.

## Audio-Import (Seite „Audio“)
- Ordnerauswahl im Browser (mehrere Orte möglich) oder Pfad eintippen, z. B. `/Volumes/Name/Music`. Der Container sieht `/Volumes` und den Benutzerordner nur lesend (`docker-compose.yml`).
- Tags per `mutagen` (MP3, M4A, FLAC, OGG, OPUS, WAV, AAC, AIFF, WMA, APE, WV); fehlen Tags, gelten Ordner-/Dateinamen (`Interpret/Album/Titel.ext`).
- Zuerst Probelauf: Liste „Bitte prüfen“, „Passt zu vorhandenen CDs“, „Neu“. Gespeichert wird erst bei „Übernehmen“.
- Abgleich über die **Titellisten**, streng: gleicher Interpret und identische Titel = dieselbe CD (dann nur „+ digital“ und Format bei der CD ergänzt); bei mehr, weniger oder anderen Titeln entsteht ein eigener Eintrag (ähnliche CDs werden nur optional angeboten). Dieselben Titel in mehreren Formaten zählen einmal.
- Gruppierung: ein Ordner = ein Album (Disc-Unterordner „CD 1/Disc 2“ und Geschwisterordner „Album (Disc 1/2)“ mit gleichem Album-Tag werden zusammengefasst). Dasselbe Album in mehreren Formaten (MP3 + M4A) bleibt EIN Eintrag mit allen Formaten, auch bei leicht abweichenden Tags (Titellisten ≥ 80 % gleich). Nur Ordner mit deutlich mehreren Alben werden nach Album-Tag getrennt. Album-Interpret: Tag „Album Artist", sonst Hauptinterpret (Gäste wie „feat. X" zählen nicht) bei ≥ 70 % der Titel, sonst „Various Artists"; Ordner „Various Artists/Sampler/Verschiedene" gelten als Sammlung.
- Reihenfolge egal: Wird eine CD später angelegt (Scan/manuell) und gibt es schon einen passenden digitalen Eintrag, übernimmt die CD dessen Dateien (Besitz „CD + digital“) und der digitale Eintrag verschwindet.
- Erneut einlesen ist gefahrlos: bekannte Dateien (nach Pfad) werden übersprungen; neue Dateien in einem schon erfassten Ordner gehen zum selben Eintrag (bei rein digitalen Einträgen kommen neue Titel zur Titelliste dazu). Gelöschte oder verschobene Dateien werden nicht bereinigt.
- Erfasste Dateien stehen in der Tabelle `audio_files`; ein erneuter Lauf zeigt nur neue Dateien.
- macOS: Beim ersten Zugriff auf das externe Laufwerk ggf. in Systemeinstellungen → Datenschutz & Sicherheit → Dateien und Ordner bzw. Vollständiger Festplattenzugriff OrbStack erlauben.

## Mehrsprachigkeit (seit 1.1.0)
- Quellsprache ist Deutsch. In den Vorlagen steht jeder sichtbare Text als `{{ _("Deutscher Text") }}`; ein `§` ist ein Platzhalter für eingesetzte Werte (`{{ _("§ Titel", n) }}`); `*Wort*` wird zu `<em>Wort</em>` (nur Überschriften). Für JavaScript-Texte `_t(...)|tojson`.
- Übersetzungen: `app/locales/en.json`, `fr.json`, `es.json` (Schlüssel = deutscher Text). Fehlt ein Eintrag, erscheint der deutsche Text. Programm (Python)-Meldungen bleiben deutsche Sätze und werden in den Vorlagen mit `_(message)` übersetzt; Muster mit `§` erkennen auch zusammengesetzte Sätze.
- Auswahl: Cookie `musikdb_lang` und `data/settings.json` (Route `/lang/<code>`). `ctx(request, ...)` liefert `_`, `_t`, `lang` an jede Vorlage. Alle Seiten müssen über `ctx` gerendert werden.
- Nach jeder Textänderung: `python3 tools/check_translations.py`. Neue Python-Meldungen zusätzlich in `EXTRA` dieses Skripts und in die drei JSON-Dateien eintragen.

## Stand und nächste Schritte
- **Version 1.0 (Musik) ist fertig** (Git-Stand `v1.0.0`), **1.1.0** bringt die Mehrsprachigkeit (Deutsch, Englisch, Französisch, Spanisch). Nutzer- und Rechtsdokumentation: `docs/ANLEITUNG.md`, `docs/DATENQUELLEN_UND_RECHT.md`.
- Als Nächstes: Version 2 mit Filmen und Serien, Planung in `docs/ROADMAP.md`; außerdem Veröffentlichung auf Codeberg (Lizenz wählen, Schriftlizenzen beilegen, `git status` auf Daten prüfen).
- Weitere Optionen in `.env`: `DISCOGS_TOKEN`, `COVER_WEB`.

## Erfahrungen (hilft einer neuen Sitzung)
- MusicBrainz: Mehrere Ausgaben können denselben Barcode haben (Bootlegs, Budget-Labels). Deshalb Status und Alter beachten.
- `TemplateResponse` nimmt `request` als ersten Parameter (neue Starlette-Version).
- Datenbank-Sitzung offen halten, bis die Seite gerendert ist (sonst „DetachedInstanceError“ bei den Tracks).
- Läuft der Container in einer Dauerschleife („exited with code 1 (restarting)“), steckt ein Fehler beim Start in `main.py`; die erste Fehlerzeile mit `Traceback` im Log nennt die Ursache. Mit Strg+C beenden, dann `docker compose down`.
- Die Sandbox, in der Claude arbeitet, kann FastAPI/SQLAlchemy nicht installieren und die App deshalb nicht starten: Fehler zeigen sich erst bei dir. Bei einem Fehler immer die letzten Zeilen von `docker compose logs --tail 60` mitschicken.

## Erste Nachricht in einem neuen Chat (Vorlage)
> Ich arbeite an meiner MusikDB (Anleitung und Zip hängen an). Stand: siehe Anleitung. Als Nächstes möchte ich: …
