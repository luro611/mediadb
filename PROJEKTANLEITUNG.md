# MediaDB – Projektanleitung

Diese Datei ist das Gedächtnis des Projekts. Wenn ein Chat abbricht oder neu begonnen wird:
**diese Datei und `mediadb.zip` hochladen**, mehr braucht es nicht.

## Worum es geht
Private Medien-Datenbank **MediaDB** (Hobbyprojekt, bis Oktober 2026 „MusikDB“). Bereiche, jeder mit eigener Datenbank: Musik (CDs und Audiodateien, seit 1.0), Filme (seit 1.1), Serien (seit 1.3) und Bücher (seit 1.6); dazu Merkliste (1.4) und Einstellungen (1.5). Dazu Verliehen (1.7) über alle Bereiche und Mediatheken (1.8). Läuft auf dem Mac (OrbStack) und im Homelab (Proxmox-LXC), Projektseite online unter https://lurohome.de/mediadb/ (seit Oktober 2026 im eigenen Projekt `lurohome`, vorher https://mediadb.lurohome.de mit Quelle im Ordner `website/`). Code öffentlich auf GitHub: https://github.com/luro611/mediadb (bis 1.17.x auf Codeberg, luro61/mediadb).
Lief bis 1.8 unter OrbStack/Docker auf dem Mac (http://localhost:8000); ab 1.8.1 im Proxmox-LXC (http://<IP-des-LXC>:8000).

## Entscheidungen (nicht neu diskutieren)
- SQLite bleibt, auch bei 500.000–1 Mio. Einträgen und für Familien mit mehreren Nutzern (Lasttest Okt. 2026: 1 Mio. Titel, Volltextsuche unter 1 ms, Filter wenige ms). Voraussetzung: Indizes und Volltextindex (FTS5). Zugriff nur über SQLAlchemy, damit ein späterer Wechsel zu PostgreSQL möglich bleibt.
- **Getrennte Datenbanken und Bereiche, nicht vermischen:** `musik.db`, `filme.db`, `serien.db`, `buecher.db`; dazu `verleih.db` für das Verleihen über alle Bereiche.
- Zielgruppe: Homelab. Eigener Betrieb unter Proxmox im LXC (Docker), Updates von GitHub. Verteilung als Docker-Image über die GitHub-Registry ghcr.io (amd64 + arm64), später ein Home-Assistant-Add-on.
- Nicht für den öffentlichen Internetbetrieb gedacht: sichere Voreinstellungen, optionale Anmeldung (aus für Einzelnutzer, an für Familien, unnötig unter Home Assistant), deutliche Hinweise in README und Rechtsdokument.
- Digitale Dateien sind formatoffen (MP3, M4A, FLAC und künftig weitere); „digital“ ist der Oberbegriff.
- Die **physisch vorhandene CD hat Vorrang**. Es gibt eine eigene Ansicht „Vorhandene CDs“.
- Eine Neuauflage/Remaster mit Zusatztiteln ist eine **eigene Ausgabe** (eigener Eintrag).
- Name: **MediaDB** (international; früher MusikDB). Versionszählung neu ab 1.0.0.
- GitHub statt Codeberg (seit 1.18.0): Codeberg verbietet seit 2026 überwiegend KI-geschriebene Projekte. Quellcode ohne Daten, siehe `docs/DATENQUELLEN_UND_RECHT.md`.
- Datenquellen: MusicBrainz (Barcode-Suche), Cover vom Cover Art Archive; optional Discogs; iTunes/Deezer nur als Cover-Ausweichquelle (abschaltbar mit `COVER_WEB=0`).

## Technik
Python, FastAPI, Jinja2-Vorlagen, SQLAlchemy, SQLite, openpyxl (Excel), requests.

## Dateien
- `app/audio.py` – Audio-Import ohne Datenbank (Ordner, Tags, Abgleich); `app/main.py` – übrige Logik: Datenmodell, Routen, MusicBrainz, Cover, Import/Export
- `app/templates/` – `base`, `scan`, `candidates` (Trefferauswahl), `manual` (Erfassen + Bearbeiten), `list` (Sammlung), `detail`, `import`, `audio`
- `static/style.css`, `static/fonts/` – Aussehen
- `data/musik.db` – die Datenbank (bis MusikDB 1.1 `musikdb.db`, wird automatisch umbenannt, Kopie in `data/backup/`), `data/covers/` – die Cover-Bilder (**das sind deine Daten**); `data/secret.key` – Schlüssel für die Anmeldung
- `app/films_*.py`, `app/templates/films_*.html` – Bereich Filme (siehe unten)
- `app/storage.py` – Datenbankdateien (musik/filme/serien) und Umbenennung; `app/search.py` – Volltextsuche; `app/security.py` – Unterpfad, Heimnetz-Sperre, Anmeldung
- `docker-compose.homelab.yml`, `docs/BETRIEB.md` – Betrieb unter Proxmox/Linux (auch als Dockhand-Stack), Image von GitHub, Umzug vom Mac, Zugriffsschutz; `tools/publish.sh` – Image bauen und zu GitHub (ghcr.io) hochladen, Tag und Release anlegen
- `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `.env` (aus `.env.example` kopiert; dort die eigene E-Mail bei `MB_USER_AGENT` eintragen)

## Starten, stoppen, neu bauen
Im Projektordner im Terminal:
- Starten/neu bauen: `docker compose up --build`
- Stoppen: `docker compose down`
- Fehler ansehen: `docker compose logs --tail 60`

## Neue Version einspielen
Zip entpacken, die geänderten Ordner und Dateien (meist `app`, manchmal `static`, `docs`, `Dockerfile`, `docker-compose*.yml`) über die Projektdateien kopieren, den Ordner `data` und die Datei `.env` **nie** überschreiben. Unter Proxmox/Linux mit Git: siehe `docs/BETRIEB.md`. Dann `docker compose down` und `docker compose up --build`, im Browser `Cmd + Shift + R`.

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

## Mehrsprachigkeit (seit MusikDB 1.1.0)
- Quellsprache ist Deutsch. In den Vorlagen steht jeder sichtbare Text als `{{ _("Deutscher Text") }}`; ein `§` ist ein Platzhalter für eingesetzte Werte (`{{ _("§ Titel", n) }}`); `*Wort*` wird zu `<em>Wort</em>` (nur Überschriften). Für JavaScript-Texte `_t(...)|tojson`.
- Übersetzungen: `app/locales/en.json`, `fr.json`, `es.json`, `it.json` (seit 1.13; Schlüssel = deutscher Text). Fehlt ein Eintrag, erscheint der deutsche Text. Python-Meldungen werden in der Vorlage mit `{{ _(message) }}` übersetzt.
- Auswahl: Cookie `mediadb_lang`, sonst `lang` in `data/settings.json`, sonst die Sprache des Browsers (Accept-Language), sonst Deutsch (`get_lang` in `main.py`). Seit 1.13 in den Einstellungen: Hauptsprache (`/lang-settings/main`) und getrennt die Sprachen für den Umschalter oben (`/lang-settings/nav`, `nav_langs`; unter zwei Sprachen kein Umschalter). `/lang/<code>` bleibt für den Umschalter und die Willkommensseite.
- Nach jeder Textänderung: `python3 tools/check_translations.py` (prüft en, fr, es, it). Neue Python-Meldungen und Texte, die nur über Variablen in `_()` landen, zusätzlich in `EXTRA` dieses Skripts und in alle vier JSON-Dateien eintragen.

## Fundament (seit MediaDB 1.0)
- **Suche:** Volltextindex `search_media_v1` (SQLite FTS5, Trigramme): ein Suchtext pro Eintrag aus Albumfeldern, Titeln und Titel-Interpreten. Wird bei jeder Änderung über ein SQLAlchemy-Ereignis (`after_flush`) in derselben Transaktion nachgezogen; beim Start neu aufgebaut, wenn die Anzahl nicht passt. Suchwörter ab 3 Zeichen gehen über den Index (auch Teilwörter), kürzere per LIKE. Neue durchsuchbare Felder: in `search.FIELDS` eintragen und den Tabellennamen hochzählen (`search_media_v2`), dann wird neu aufgebaut. Massenänderungen mit `query.update()`/`delete()` umgehen das Ereignis.
- **Indizes:** Liste `INDEXES` in `main.py`, werden beim Start angelegt.
- **Unterpfad:** Alle Links in Vorlagen beginnen mit `{{ base }}`; Weiterleitungen (`RedirectResponse('/…')`) ergänzt die Middleware selbst. In Vorlagen also nie `href="/…"` ohne `{{ base }}` schreiben; Python-Code schreibt Pfade weiterhin ohne Unterpfad.
- **Zugriff:** `security.Gate` prüft zuerst die IP (öffentlich = 403, außer `ALLOW_PUBLIC=1`), dann bei gesetztem `APP_PASSWORD` das Cookie (HMAC, 30 Tage). Frei: `/login`, `/static/`, `/healthz`.
- Gemeinsame Konten für Familien (mehrere Nutzer) sind noch nicht gebaut; bisher ein gemeinsames Passwort.

## Filme (seit MediaDB 1.1)
- Eigene Datenbank `data/filme.db`, Bilder in `data/film_images/` (`<id>-poster.jpg` 342 px, `<id>-backdrop.jpg` 780 px), ausgeliefert unter `/film-images`.
- **Bewusst ohne SQLAlchemy und FastAPI-Decorators:** `app/films_db.py` nutzt das eingebaute `sqlite3`, `app/films_web.py` ist eine Starlette-App, in `main.py` unter `/films` eingehängt (plus `app.add_route('/films', …)`, damit `/films` ohne Schrägstrich nicht umgeleitet wird). Grund: So lassen sich Datenbank, Seiten und Abläufe in Claudes Sandbox vollständig testen (Starlette, Jinja2, sqlite3 und ffprobe sind dort vorhanden, FastAPI/SQLAlchemy nicht). Für die Serien genauso vorgehen.
- Module: `films_db.py` (Tabellen films, copies, lists, list_items, barcode_cache; Volltextsuche `search_films_v1` per **Trigger** aktuell), `films_tmdb.py` (TMDB-Abfragen, einzige Netzwerkfunktion `_http_get`, in Tests ersetzbar; Barcode über UPCitemdb, Titelbereinigung), `films_files.py` (Ordner-Import: Dateien finden, .nfo/Dateinamen auswerten, ffprobe, Probelauf `JOB` und Übernahme), `films_web.py` (Routen), Vorlagen `films_*.html`, `_films_nav.html`, `_films_foot.html`.
- **Entscheidungen:** ein Eintrag pro Film, mehrere Exemplare (dvd/bluray/uhd/file) mit Barcode und Fassung. Gesehen (Datum, Anzahl) und Bewertung 1–10 (1 = 5× löschen, 10 = Unbedingt sehen) gelten vorerst für den Haushalt; später pro Person. Eine Skala für gesehene und ungesehene Filme; „Top 10: Muss ich sehen“ = ungesehen, höchste Bewertung. Eingebaute Listen siehe `films_db.VIEW_RULES`, dazu eigene Listen und Filmreihen (TMDB-Collections). Poster und ein Hintergrundbild lokal, Darsteller ohne Fotos.
- **Bilder (seit 1.1.4):** `app/films_art.py`. Dateinamen `<id>-poster-<zeit>.<ext>` bzw. `-backdrop-` (Zeitstempel gegen Browser-Cache; alte Varianten werden per glob gelöscht). Endung nach Dateiinhalt (JPG/PNG/WebP), nicht nach Name. Quellen in `fill_missing`: lokale Bilddateien → eingebettetes Cover (ffprobe/ffmpeg: MKV-Anhang oder MP4 attached_pic) → TMDB `/movie/<id>/images`. Sammellauf `JOB`, Seite `/films/<id>/poster`, Upload über `request.form(max_part_size=…)`.
- **Personen (seit 1.1.3):** Tabellen `people` (TMDB-Personennummer als id, Foto `person-<id>.jpg`, Biografie, Filmografie als JSON, `fetched_at`, 14 Tage gültig) und `film_people` (Film, Person, Rolle cast/director/writer, Figur, Reihenfolge). Gesetzt beim Speichern aus den TMDB-Credits (erste 20 der Besetzung, Regie, bis zu 5 Drehbuch); `films_files.backfill_people()` lädt beim Start im Hintergrund für ältere Filme nach (Platzhalter-Person 0 mit Rolle `none`, wenn TMDB nichts liefert). Seite `/films/person/<id>`; die Filmografie markiert eigene Filme über `tmdb_id`. Seit 1.3 zeigt „In deiner Sammlung“ auch Serien.
- „Von TMDB ergänzen“ füllt nur leere Felder; „Anderen Film zuordnen“ ersetzt alle TMDB-Felder (Notiz, Exemplare, gesehen, Bewertung, Listen bleiben; gibt es den Zielfilm schon, wird zusammengeführt).
- Ordner-Import: Erkennung .nfo (uniqueid tmdb/imdb) → `[tmdbid-…]`/`{imdb-tt…}` im Namen → Titel/Jahr aus Ordner- oder Dateiname → TMDB-Suche (sicher ab Ähnlichkeit 0,86 und passendem Jahr ±1). Nicht gefunden: mit Jahr im Namen wird „ohne TMDB anlegen“ vorgeschlagen, sonst „überspringen“ (eigene Videos).
- Tests (in der Sandbox, Skripte nicht im Repository): Datenbank, TMDB-Auswertung mit Beispieldaten, Ordner-Import mit per ffmpeg erzeugten Testvideos und .nfo, alle Seiten und Formulare über einen ASGI-Testaufruf inklusive Unterpfad.

## Startseite und Bedienung (seit 1.2)
- `app/home.py` (Starlette-Endpunkte, in `main.py` per `app.add_route('/')` und `'/search'`): liest die Musikdatenbank nur lesend per `sqlite3` (Zahlen, neueste Einträge, Suche über den Volltextindex `search_media_v1`), Filme über `films_db`. Vorlagen `home.html`, `search.html`. Serien sind dritte Kachel und Teil der Suche (seit 1.3).
- Buchstabenauswahl: Musik `/media?l=X` (Interpreten-Ansicht; ohne `l` der erste belegte Buchstabe, `l=all` alles), Filme `/films?l=X` (`films_db.LETTER_SQL` auf `sort_title`). Reihenfolge immer `#`, A–Z.
- Navigation: `area` im Vorlagen-Kontext (`home`, `films`, `series`, `books`, `watch`, `lend`, `settings`, `help`, `welcome`, sonst Musik) steuert die Hervorhebung; das Ziel von „Hinzufügen“ liefert `add_url(area)` (aktueller Bereich, sonst der erste eingeschaltete).

## Serien (seit 1.3)
- Eigene Datenbank `data/serien.db`, Bilder ebenfalls in `data/film_images/` mit Präfix `s<id>-` (Poster, Hintergrund). Gleiches Muster wie Filme: `series_db.py` (sqlite3), `series_files.py` (Ordner-Import), `series_web.py` (Starlette, in `main.py` unter `/series` eingehängt), TMDB-Funktionen `tv_*` in `films_tmdb.py`, Vorlagen `series_*.html`, `_series_nav.html`.
- Tabellen: `series`, `seasons`, `episodes` (Episodenführer von TMDB, je Staffel `/tv/<id>/season/<n>`; fehlende deutsche Titel englisch nachgeladen), `ep_files` (eine Zeile pro Datei mit Staffel, Folge, `episode_end` für Doppelfolgen, `title_hint` aus dem Dateinamen und Technikdaten aus ffprobe), `copies` (Boxen mit Freitext `seasons`: „1-3“, „2, 4“, „komplett“), `watched` (pro Folge), `people`/`series_people` (Rolle cast oder creator, TMDB-Personennummer wie bei den Filmen), `barcode_cache`. Volltextsuche `search_series_v1` per Trigger.
- **Vergleich:** `series_db.overview()` baut pro Folge den Zustand `have` (Datei oder Box), `missing` (ausgestrahlt, nicht vorhanden) oder `upcoming`; eine Box zählt nur für ausgestrahlte Folgen, Staffel 0 zählt nicht. `missing_all()` für „Was fehlt?“ (`/series/missing`, `?format=txt`).
- **Dateinamen** (`series_files.parse_episode`): `S01E01`, `S01E01E02`/`S01E01-E02`, `1x01`, `E01`/`Folge 01` ohne Staffel, Staffelordner (`Season 1`, `Staffel 01`, `S01`), Serienname aus Dateiname, sonst aus dem Ordner; `tvshow.nfo` (uniqueid tmdb/tvdb/imdb, `[tmdbid-…]` im Ordnernamen). Bei `E01` ohne Staffel sucht `place_file` die Folge über den Titel im Dateinamen, sonst Staffel 1. Namensvarianten (Grosser → Großer, ae → ä) für die TMDB-Suche.
- Personenseite `/films/person/<id>` (in `films_web.py`) zeigt Filme und Serien der Sammlung; kennt die Filmdatenbank eine Person nicht und TMDB ist nicht erreichbar, reicht der Name aus `serien.db`.
- Startseite: dritte Kachel mit Zahl der Serien, Folgendateien und fehlenden Folgen, aufklappbar „Serien, die ich gerade schaue“ und „Zuletzt hinzugefügt: Serien“; die Suche zeigt Serien und Personen aus beiden Datenbanken.

## Merkliste und Aktualisierung (seit 1.4)
- `app/watchlist.py`: Tabelle `watch` in **beiden** Datenbanken (Filme in `filme.db`, Serien in `serien.db`, gleicher Aufbau), Tabelle `meta` in `serien.db` (Zeitpunkt der letzten Aktualisierung). Funktionen für Merkliste (`items`, `add`, `refresh_item`, `set_done` …) und der Aktualisierer `UPD`/`run`/`start`/`scheduler` (Thread: 90 s nach dem Start prüfen, dann stündlich; läuft, wenn die letzte Runde älter als 20 Stunden ist).
- `refresh_series`: TMDB-Details (mit `watch/providers`), Personen, dann nur die letzte bekannte und neue Staffeln (`series_db.upsert_guide`); fällig sind laufende Serien nach 20 Stunden, beendete nach 30 Tagen, Serien ohne Streamingangaben sofort.
- `app/watchlist_web.py` (Starlette, `/watchlist`), Vorlagen `watchlist.html`, `watchlist_done.html`. „Neu bei deinen Serien“ aus `series_db.upcoming()` (nächste Folge je Serie in 120 Tagen, erschienene der letzten 30 Tage, angekündigte Staffeln).
- TMDB: `providers_of` (Abo, kostenlos, mit Werbung für das Land aus `TMDB_LANGUAGE`; Kauf/Leihe getrennt), `next_of`, `multi_search`, `watch_status`. Neue Spalten in `series` werden beim Start per `ALTER TABLE` ergänzt (`NEW_COLUMNS`), `PRAGMA user_version` steuert den Neuaufbau des Suchindex.
- Pflicht: Hinweis „Streaming-Angaben: JustWatch (über TMDB)“, wo Dienste angezeigt werden.

## Einstellungen (seit 1.5)
- `app/config.py`: Werte aus `data/settings.json` (Schlüssel `config`) werden beim Start (`config.init`, ganz am Anfang von `main.py`) und beim Speichern in `os.environ` geschrieben; der übrige Code liest weiter `os.getenv`. Deshalb keine Modul-Konstanten aus Umgebungsvariablen mehr anlegen (Discogs-Token, User-Agent sind jetzt Funktionen). `MB_CONTACT` erzeugt `MB_USER_AGENT`. Zugriffseinstellungen bleiben bewusst nur in `.env`.
- `app/settings_web.py` (Starlette, `/settings`), Vorlage `settings.html`; `RELANG` lädt Filme (sprachabhängige Felder, optional Titel), Serien (`refresh_guide` plus Titel) und Merkliste in der Datensprache neu. Erste Einrichtung: `/lang/<code>` setzt die Datensprache, solange keine gespeichert ist und Film- und Seriendatenbank leer sind.
- Namen bereinigen: `films_files.strip_junk` (gemeinsam für Filme und Serien) entfernt Zusätze nur am Ende; `JUNK_TOKEN` enthält Qualitäts-, Sprach- und Streamingkennungen.

## Bücher (seit 1.6)
- Eigene Datenbank `data/buecher.db`, gleiches Muster wie Serien: `books_db.py` (sqlite3; Tabellen `books`, `copies` mit `kind` hardcover/paperback/ebook/audiobook/other und Dateipfad, `authors`/`book_authors` mit Rolle aut/trl/ill/nrr/edt, `isbn_cache`; Volltextsuche `search_books_v1` per Trigger), `books_api.py` (Netz), `books_files.py` (Ordner- und Tabellen-Import), `books_web.py` (Starlette, `/books`), Vorlagen `books_*.html`, `_books_nav.html`, `_books_foot.html` (Quellenhinweis DNB und Open Library).
- **Quellen:** DNB-SRU (`services.dnb.de/sru/dnb`, MARC21-xml, `parse_marc`), Open Library (`/api/books?bibkeys=ISBN:…&jscmd=data`, `/search.json`, Cover `covers.openlibrary.org/b/id/<id>-L.jpg?default=false`). `lookup_isbn`: zuerst DNB, Open Library ergänzt leere Felder; `search` fragt je nach Datensprache zuerst DNB (Deutsch) oder Open Library. Drosselung `GAP` (3,1 s) wegen der Cover-Grenze von Open Library (100 Abrufe / 5 Minuten). Verlagsreihen der DNB („dtv 21412“) verwirft `publisher_series`.
- **Dateien:** EPUB/OPF selbst ausgewertet, Calibre über `metadata.opf`, MOBI über den EXTH-Kopf, PDF über das Info-Feld, Hörbücher per `ffprobe` (M4B oder Ordner mit Audiodateien, CD-Unterordner zusammengefasst); Cover eingebettet oder aus dem Ordner. Bilder in `data/film_images/` mit Präfix `b<id>-`.
- **Tabellen:** `read_table` erkennt CSV/XLSX und reine ISBN-Listen samt Kopfzeile; Vorschau und Übernehmen wie beim Serien-Import (`table_scan_worker`, `table_apply_worker`). Ist dieselbe ISBN schon als Exemplar vorhanden, steht der Eintrag auf „Überspringen“.
- **Zusatzangaben (seit 1.6.1):** `books_extras.py` lädt im Hintergrund (Job `JOB`, `start()` nach Speichern/Import, `scheduler()` 120 s nach dem Start) für alle Bücher ohne `extras_at`: DNB-Inhaltstext (`856 $3 Inhaltstext` → `blurb_url`, `books_api.dnb_blurb`; Inhaltsverzeichnis → `toc_url`), Open-Library-Werk (`ol_work`) und Bewertung (`ol_rating`, `ol_rating_count`), Wikipedia (`wiki_find`: Suche, Artikelname muss zum Titel passen, Klammerzusätze wie „(Fernsehserie)“ ausgeschlossen, Autor im Text, Buchwort wie „Roman“ im Text). `wiki_url='-'` heißt: vom Nutzer entfernt, wird nur mit „neu laden“ wieder gesucht. `description_src`: dnb, openlibrary, manual. Neue Spalten per `NEW_COLUMNS`/`ALTER TABLE`.
- Startseite: vierte Kachel, „Lese ich gerade“, „Zuletzt hinzugefügt: Bücher“; die gemeinsame Suche findet Bücher und Autoren.

## Mediatheken (seit 1.8)
- `app/mediathek.py`: Suche über den RSS-Feed von MediathekViewWeb (`https://mediathekviewweb.de/feed?query=…&everywhere=false`, höchstens 50 Einträge; Selektoren `#thema` bzw. `+titel`, mehrere Wörter mit Komma: `#babylon,berlin`). Zwischenspeicher 6 h im Speicher, Abstand 0,5 s. `series_hits` (Thema passt genau oder „Titel Staffel n“, mindestens 10 Minuten; Folgen über `(S05/E08)`, `S05E08`, `Staffel 5, Folge 8`, `(3/8)` mit Staffel aus dem Thema, sonst über den Folgentitel; Nummern, die der Episodenführer nicht kennt, werden verworfen), `film_hits` (Titel genau, ab 45 Minuten, Jahr aus der Beschreibung ±1). Fassungen (Audiodeskription …) zusammengefasst, Trailer/Making-of und zukünftige Termine weg.
- `app/mediathek_web.py` (Starlette, `/mediathek/series/<id>`, `/film/<id>`, `/watchlist`) liefert HTML-Abschnitte (`_mediathek_hits.html`); die Detailseiten binden `_mediathek.html` ein, das per `fetch` nachlädt. Schalter `MEDIATHEK` (config, Einstellungen). Bewusst kein Download (Wunsch des Betreibers; erst auf Nachfrage).

## Verliehen (seit 1.7)
- `app/loans.py` (sqlite3, `data/verleih.db`): Tabellen `people` (Name, eindeutig ohne Groß/Klein) und `loans` (area music/film/series/book, `item_id` in der Bereichs-Datenbank, `copy_id` des Exemplars, Titel als Kopie, `detail` z. B. „DVD · Special Edition“, `lent_at`/`due_at`/`returned_at` als ISO-Datum, auch nur Jahr). Die Bereichs-Datenbanken werden nicht verändert.
- `app/loans_web.py` (Starlette, `/lend`): `physical(area, id)` bestimmt, was verleihbar ist (Musik: `ownership` cd/cd_digital; Filme: Exemplare ohne `file`/Pfad; Serien: Boxen; Bücher: Exemplare ohne Pfad und nicht `ebook`). Jinja-Globale `lend_info`, `lent_ids`, `lend_stats`, `lend_find`; Kasten als Makro `_lend.html` (`lend_box`) in `detail.html`, `films_detail.html`, `series_detail.html`, `books_detail.html`; Vorlagen `lend.html`, `lend_person.html`, `_lend_rows.html`. Vorlagen prüfen mit `is defined`, damit Tests ohne diesen Teil laufen.
- Die Suche auf der Seite nutzt `home._music_hits` und die `query`-Funktionen der Bereiche.

## Betrieb im LXC (seit 1.8.1)
- Eigener Betrieb: Proxmox-LXC mit Docker, verwaltet mit **Dockhand** (Agent Hawser im LXC). Stack „mediadb“ = Inhalt von `docker-compose.homelab.yml`, Image `ghcr.io/luro611/mediadb:latest` (GitHub-Benutzer `luro611`; bis 1.17.x `codeberg.org/luro61/mediadb`).
- Alles unter `/opt/mediadb` im LXC: `data` (Daten) und `medien/musik|filme|serien|buecher` (nur lesend, in der App `/music`, `/movies`, `/series`, `/books`; `audio.ROOTS`). Container läuft als root. Seit 1.9 liest MediaDB Medien auch direkt per SMB von der NAS (Einstellungen → NAS-Freigaben, `app/nas.py`), ohne Einhängen. Mediendateien braucht es nur zum Einlesen.
- LXC-Größe: 2 Kerne, 1024 MB RAM (+512 MB Swap), 16 GB Speicher (Ordner `data` beim Umzug ca. 2,2 GB).
- Neue Version: `VERSION` hochzählen, CHANGELOG-Abschnitt schreiben, committen und pushen, dann auf dem Mac `sh tools/publish.sh` (buildx, amd64 + arm64, Tags `<Version>` und `latest`, Git-Tag `v<Version>`, GitHub-Release mit Text aus dem CHANGELOG; Anmeldung über das GitHub-Programm `gh`), dann in Dockhand Pull und Redeploy.

## Ansichten und Startseite (seit 1.10)
- **Kacheln / Liste / Text:** Cookie `mediadb_layout_<bereich>` (music, films, series, books), Route `/layout/<bereich>/<modus>`, Vorlage `_layout.html` (Umschalter). Für Filme, Serien und Bücher setzt `layout_cls(bereich)` nur CSS-Klassen am Raster (`.posters.rows`, `.posters.rows.text`); Musik rendert Kacheln oder die bisherige Tabelle (`list.html`, `artists.html`). Voreinstellung: Musik Liste, sonst Kacheln.
- **Als Nächstes (1.11):** Spalte `next_at` in `films`, `series`, `books` und `media`; Knopf aus `_next.html` (POST `/next/<bereich>/<id>`), Reiter `view=next` in allen Listen, Stern `.pnext`. Fällt automatisch heraus: Film bei „gesehen“ (`films_db.set_watched`), Buch bei „gelesen“ (`books_db.set_status`), Serie, wenn keine ausgestrahlte Folge mehr offen ist (`series_db.drop_next_if_caught_up`).
- **Startseite (1.12):** drei gemischte Reihen aus allen eingeschalteten Bereichen (`home._card`, `_mixed`): Als Nächstes, Gerade dabei (angefangene Serien, Bücher „lese ich gerade“), Zuletzt hinzugefügt.

## Farben, Hilfe und Bildschirmfotos (seit 1.14)
- **Eigene Farben (1.14):** sechs CSS-Variablen je Farbschema (`COLOR_KEYS` in `main.py`). Die Vorgaben stehen fest in `static/style.css` und werden beim Start nur gelesen (`_css_defaults`); gespeichert werden nur Abweichungen (`settings.json` → `colors`), ausgegeben als `<style id="customcolors">` in `base.html`. „Auf Ursprung zurücksetzen“ löscht nur die Abweichungen.
- **Hilfe in der App (1.15):** `app/help.py`, Route `/hilfe[/betrieb|datenquellen|aenderungen]` zeigt `docs/ANLEITUNG.md` (seit 1.17.2 bei nicht-deutscher Oberfläche `docs/MANUAL.md`, die englische Fassung mit Bildern aus `docs/bilder/en/`), `docs/BETRIEB.md`, `docs/DATENQUELLEN_UND_RECHT.md` und `CHANGELOG.md` mit Python-Markdown; Sprungmarken wie auf GitHub (`slug`), Listen werden für Python-Markdown nachgebessert (`_commonmark_lists`). Links zur Hilfe öffnen das Fenster `mediadb-hilfe`. Die Texte werden ins Docker-Image kopiert (`.dockerignore` mit Ausnahmen).
- **Bildschirmfotos (1.16):** `docs/bilder/*.png` (deutsch) und `docs/bilder/en/*.png` (englisch, seit 1.17.2), eingebunden mit `![…](bilder/…png)`, in der App unter `/hilfe/bilder/<name>`. Immer aus der erfundenen Beispiel-Sammlung: `tools/demo_data.py` legt sie an (Platzhalter-Cover als SVG), `tools/screenshots.py` startet MediaDB damit und fotografiert mit Playwright und Google Chrome. Bei jeder Änderung der Oberfläche neu machen.

## Bereiche ein- und ausschalten (seit 1.17)
- `config.areas()` / `config.area_on(bereich)` (`settings.json` → `areas`; ohne Eintrag sind alle an; `watch` = Filme oder Serien). Ausgeschaltet heißt nur ausgeblendet: Datenbanken bleiben unberührt.
- `AreaGuard` in `main.py` (ASGI-Middleware, innen nach `security.Gate`): Pfade aus `AREA_PATHS` eines ausgeschalteten Bereichs zeigen `area_off.html` (404). Leiste, Startseite, Suche (`home.py`), Merkliste und Einstellungen fragen `area_on` ab; ausgeblendete Einstellungen bleiben im Formular (Attribut `hidden`), damit Speichern nichts verliert. Hintergrundarbeiten prüfen den Bereich (`watchlist.run`/`scheduler`, `books_extras.scheduler`, Personen-Nachladen in `films_web`).
- **Willkommensseite** `/willkommen`: nur bei einer neuen, leeren Installation (`is_fresh`: keine Wahl der Bereiche gespeichert und keine Einträge). Schritt 1 Begrüßung in allen Sprachen (Sprache des Browsers zuerst), Schritt 2 (`?schritt=2`) die Bereiche in der gewählten Sprache.

## Hintergrundaufgaben (seit 1.4.2)
- `app/activity.py`: Jeder Bereich meldet eine Funktion an (`register`), die den Stand seiner Aufgabe liefert (Text, `net`/`files`, Fortschritt, Link). `/activity?lang=..` gibt alle laufenden als JSON; `base.html` fragt alle 8 s (bei laufender Aufgabe alle 3 s) ab und zeigt die Anzeige in der Navigation. Musik meldet sich in `main.py` an (REFRESH, JOB, IMP), Filme/Serien/Merkliste in `activity.register_media()`. Neue Hintergrundaufgaben dort anmelden.

## Stand und nächste Schritte
- **MediaDB 1.18.1** (Git-Stand `v1.18.1`): Barcode-Namen mit „By …“ und Händlerangaben werden bereinigt (`films_tmdb.query_variants`); Meldungen nach einem Sprung erscheinen schwebend (`.toast`, Skript in `base.html`); Sicherheitsfrage vor „Alles in der Datensprache neu laden“; Staffel-Knopf nur bei Ungesehenem.
- **MediaDB 1.18.0** (Git-Stand `v1.18.0`): Umzug von Codeberg zu GitHub (Code https://github.com/luro611/mediadb, Image `ghcr.io/luro611/mediadb`, Update-Hinweis fragt GitHub, `tools/publish.sh` mit `gh`). Auf Codeberg gibt es als letzte Version 1.17.3, die nur auf den Umzug hinweist.
- **MediaDB 1.17.2** (Git-Stand `v1.17.2`): englische Anleitung (`docs/MANUAL.md`) für alle Sprachen außer Deutsch, englische Bildschirmfotos. **1.17.1** Willkommensseite in zwei Schritten (Sprache, dann Bereiche). **1.17.0** Bereiche ein- und ausschalten. **1.16.0** Bildschirmfotos in der Anleitung (Beispiel-Sammlung). **1.15.0** Hilfe in der App. **1.14.0** eigene Farben. **1.13.x** Italienisch, Spracheinstellungen, Website mit fünf Sprachen, Anleitung aktualisiert. **1.12.0** aufgeräumte Startseite, Ansicht „Text“. **1.11.0** „Als Nächstes“. **1.10.0** Umschalter Kacheln/Liste. **1.9.x** NAS-Freigaben, Update-Hinweis.
- Davor: **MediaDB 1.8.2** (Git-Stand `v1.8.2`): Versionsnummer unten auf jeder Seite (`app_version` aus der Datei `VERSION`), offizielles TMDB-Logo (`static/tmdb/`). **MediaDB 1.8.1** (Git-Stand `v1.8.1`): Betrieb im Proxmox-LXC mit Dockhand. **MediaDB 1.8.0** (Git-Stand `v1.8.0`): Mediatheken. **MediaDB 1.7.0** (Git-Stand `v1.7.0`): Verliehen an … über alle Bereiche. **MediaDB 1.6.1** (Git-Stand `v1.6.1`): Zusammenfassungen und Bewertungen bei Büchern, Willkommenstext auf der Projektseite. **MediaDB 1.6.0**: Bücher. Frühere Stände: `v1.5.0` Einstellungen, `v1.4.x` Merkliste, `v1.3.x` Serien, `v1.2.x` Startseite. **MediaDB 1.1.0** (Git-Stand `v1.1.0`): Filme. **MediaDB 1.0.0** (Git-Stand `v1.0.0`): Musik komplett plus Fundament (eigene Datenbankdatei, Volltextsuche, Unterpfad, Zugriffsschutz, Homelab-Betrieb). Vorgeschichte als MusikDB: Git-Stände `musikdb-v1.0.0`, `musikdb-v1.1.0` (Mehrsprachigkeit), `musikdb-v1.2.0`. Nutzer- und Rechtsdokumentation: `docs/ANLEITUNG.md`, `docs/DATENQUELLEN_UND_RECHT.md`.
- Als Nächstes: Rückmeldungen von Nutzern abwarten. Offen bleiben (siehe `docs/ROADMAP.md`): Übersetzung von Betrieb/Datenquellen ins Englische, Anleitung in weiteren Sprachen, Home-Assistant-Add-on, gemeinsame Konten für Familien. Hinweis zur Versionsnummer: Die Zählung ab 1.0 bleibt so; bei neuen Projekten vorher über das Schema (z. B. 0.x bis zur ersten öffentlichen Version) sprechen.
- Weitere Optionen in `.env`: `DISCOGS_TOKEN`, `COVER_WEB`, `TMDB_API_KEY`, `TMDB_LANGUAGE`, `BARCODE_LOOKUP`, `APP_PASSWORD`, `ALLOW_PUBLIC`, `BASE_PATH`.

## Erfahrungen (hilft einer neuen Sitzung)
- MusicBrainz: Mehrere Ausgaben können denselben Barcode haben (Bootlegs, Budget-Labels). Deshalb Status und Alter beachten.
- `TemplateResponse` nimmt `request` als ersten Parameter (neue Starlette-Version).
- Datenbank-Sitzung offen halten, bis die Seite gerendert ist (sonst „DetachedInstanceError“ bei den Tracks).
- Läuft der Container in einer Dauerschleife („exited with code 1 (restarting)“), steckt ein Fehler beim Start in `main.py`; die erste Fehlerzeile mit `Traceback` im Log nennt die Ursache. Mit Strg+C beenden, dann `docker compose down`.
- Claude kann die App inzwischen selbst starten und testen: eigene Python-Umgebung mit `requirements.txt`, eine Kopie von `data/` oder die Beispiel-Sammlung (`python3 tools/demo_data.py <leerer-ordner>`), Start mit `DATA_DIR=<ordner> uvicorn app.main:app`, Anschauen im eingebauten Browser. Den Server im LXC erreicht Claude nicht; dort bei Fehlern die letzten Zeilen des Container-Logs (Dockhand) mitschicken.

## Erste Nachricht in einem neuen Chat (Vorlage)
> Ich arbeite an meiner MediaDB (Anleitung und Zip hängen an). Stand: siehe Anleitung. Als Nächstes möchte ich: …
