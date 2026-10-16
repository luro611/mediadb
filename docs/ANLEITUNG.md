# MediaDB – Ausführliche Anleitung

MediaDB ist eine **private Mediendatenbank für den eigenen Rechner** mit vier Bereichen: Musik, Filme, Serien und Bücher, dazu Merkliste und „Verliehen an …“. Für die Musik erfasst du deine CDs (per Barcode, Künstlersuche, Tabelle oder von Hand) und deine Musikdateien (MP3, M4A, FLAC …). Die App ergänzt Titellisten, Cover und Genres aus freien Internetquellen und zeigt alles in einer Weboberfläche im Browser. Die Daten bleiben bei dir.

## 1. Was die App kann

**Erfassen**
- **Barcode:** Scanner oder Eingabe. Zu einem Barcode werden bei MusicBrainz die passenden Ausgaben gesucht (offizielle zuerst, dann die älteste; Bootlegs eingeklappt). Unvollständige Barcodes (10/11 Ziffern) werden ergänzt, Striche und Leerzeichen ignoriert.
- **Diskografie-Suche ohne Scanner:** Interpret wählen, dann alle seine CDs als Liste (nach Albumtitel, mit A–Z-Leiste und Barcode), Ausgabe wählen, „Das ist meine CD“.
- **Von Hand:** Alle Felder frei eintragbar.
- **Tabelle importieren (Excel, ODS, CSV):** Interpret und Albumtitel genügen, den Rest holt die App von MusicBrainz. Mit Probelauf und Vorschau.
- **Audio-Import:** Musikordner (z. B. auf einer externen Platte oder direkt von der NAS, siehe Einstellungen → NAS-Freigaben) einlesen. Abgleich mit vorhandenen CDs über die Titellisten, Cover und Genre werden ergänzt.
- **Ähnliche Ausgabe suchen:** Wird bei MusicBrainz nichts Eindeutiges gefunden, zeigt die App ähnliche Ausgaben zur Auswahl. Zusätzlich kann ein **Discogs-Link** eingefügt werden (Vorschau, dann bestätigen).

**Verwalten und ansehen**
- Startseite: Sammlung als **Interpreten-Übersicht** mit A–Z-Leiste, Klick zeigt die CDs; Reiter „Alle CDs“.
- **Besitz** je Eintrag: Physische CD, Nur digital, CD + digital; Dateiformate (MP3, M4A, FLAC …).
- **Suche** über ein Feld (Künstler, Album, Genre, Label, Songtitel, Notizen; mehrere Wörter = alle müssen passen) plus Filter für Künstler, Genre und Jahr. Sortieren per Klick.
- **Compilations** sind ein einziger Eintrag („Various Artists“), gefunden werden sie auch über die Interpreten der einzelnen Titel.
- Cover, Titellisten mit Laufzeiten, Label, Katalognummer, Land, Jahr der CD **und** Erscheinungsdatum des Albums, Genre und Styles.
- Sammelaktionen mit Fortschrittsanzeige: **Fehlende Cover laden**, **Fehlende Genres laden**, **Alle aus MusicBrainz aktualisieren** (füllt nur Leeres, überschreibt nichts).

**Sprachen**
- Die Oberfläche gibt es auf **Deutsch, Englisch, Französisch, Spanisch und Italienisch**. Die Hauptsprache stellst du unter **Einstellungen → Sprache der Oberfläche** ein. Wird im Haushalt mehr als eine Sprache gesprochen, hakst du dort die Sprachen an, die oben in der Leiste als Umschalter (z. B. DE · IT) erscheinen sollen. Die Wahl wird im Browser (Cookie) und zusätzlich im Ordner `data/` (Datei `settings.json`) gespeichert und bleibt auch nach einem Neustart erhalten. Ohne Auswahl gilt Deutsch.
- Was nicht übersetzt wird: Namen von Künstlern, Alben und Labels, die Inhalte aus MusicBrainz/Discogs sowie technische Fehlermeldungen. Die Spaltenüberschriften der Exportdateien (xlsx, ods, csv) bleiben englische Feldnamen, damit Sicherungen in jeder Sprache wieder importierbar sind.

**Sichern und mitnehmen**
- **Export** als xlsx (Excel), ods (LibreOffice), csv (Semikolon, UTF-8 mit BOM, öffnet in Excel richtig) oder Markdown; wahlweise alles, nur CDs oder nur Digitales. Die Excel-Datei dient zugleich als Sicherung: Beim Import wird sie erkannt und vollständig wiederhergestellt.

## 2. Installation (Mac, Windows, Linux)

Voraussetzung: **Docker**, auf dem Mac z. B. **OrbStack** oder Docker Desktop.

1. Projektordner entpacken oder von Codeberg laden.
2. Im Terminal in den Projektordner wechseln.
3. `cp .env.example .env` und die Datei `.env` bearbeiten: bei `MB_USER_AGENT` **deine eigene E-Mail-Adresse** eintragen (MusicBrainz verlangt eine Kontaktmöglichkeit).
4. `docker compose up --build`
5. Im Browser `http://localhost:8000` öffnen.

**Proxmox-LXC, Linux-Server, NAS:** eigene Anleitung in [BETRIEB.md](BETRIEB.md) (mit `docker-compose.homelab.yml`, Updates, Sicherung, Zugriffsschutz).

Stoppen: `docker compose down`. Neu bauen nach einem Update: `docker compose up --build`. Fehler ansehen: `docker compose logs --tail 60`.

**Daten:** Datenbank (`musik.db`) und Cover liegen im Ordner `data/`. Das sind **deine Daten**: sichern, bei Updates nie überschreiben.

**Update einspielen:** neue Dateien über das Projekt kopieren (`app`, `static`, `docker-compose.yml`, `Dockerfile`, `requirements.txt`), `data/` und `.env` nicht anfassen, dann `docker compose down` und `docker compose up --build`, im Browser Cmd+Shift+R (Windows/Linux Strg+Shift+R).

**Musikordner sichtbar machen:** `docker-compose.yml` bindet auf dem Mac `/Volumes` (externe Laufwerke) und den Benutzerordner nur lesend ein. Beim ersten Zugriff muss macOS ggf. erlauben: Systemeinstellungen → Datenschutz & Sicherheit → Dateien und Ordner bzw. Vollständiger Festplattenzugriff für OrbStack. Unter Linux/Windows die Pfade in `docker-compose.yml` anpassen.

## 3. Einstellungen

**In der App (Zahnrad ⚙ oben):** TMDB-Schlüssel, Sprache der Daten (mit Land), E-Mail-Adresse für MusicBrainz, Discogs-Token und die Schalter für Barcode-Dienst, Cover von iTunes/Deezer und die tägliche Aktualisierung. Änderungen gelten sofort, gespeichert wird in `data/settings.json`. Diese Werte haben Vorrang vor der Datei `.env`.

**Sprache der Oberfläche und Sprache der Daten** sind zwei verschiedene Dinge: Die Oberfläche (Menüs, Knöpfe) stellst du unter Einstellungen → „Sprache der Oberfläche“ um. In der **Datensprache** kommen Titel, Inhaltsangaben, Genres und Episodennamen von TMDB in die Datenbank; das Land dazu bestimmt Altersfreigabe, Kinostart und Streamingdienste. Wer bei der ersten Einrichtung die Oberfläche auf Englisch, Französisch, Spanisch oder Italienisch stellt, bekommt die passende Datensprache voreingestellt. Wird die Datensprache später geändert, lädt „Alles in der Datensprache neu laden“ die schon gespeicherten Filme und Serien im Hintergrund neu. Musik bleibt immer im Original (MusicBrainz übersetzt keine Titel).

**In der Datei `.env`** stehen weiterhin die Zugriffseinstellungen und können dort auch alle anderen Werte stehen (z. B. bei einer automatischen Einrichtung):
| Eintrag | Bedeutung |
|---|---|
| `MB_USER_AGENT` | Pflicht. Name und E-Mail, z. B. `MediaDB/1.0 (du@example.com)` |
| `DISCOGS_TOKEN` | Optional. Kostenloser Token (discogs.com → Einstellungen → Entwickler). Schaltet die Discogs-Suche frei. |
| `COVER_WEB` | `1` (Standard) oder `0`. Bei `0` werden keine Cover von iTunes/Deezer geholt (siehe Rechtliches). |
| `APP_PASSWORD` | Optional. Passwort für die Anmeldung; leer = keine Anmeldung. |
| `ALLOW_PUBLIC` | `0` (Standard): nur Heimnetz. `1` erlaubt Zugriffe aus dem Internet (nicht empfohlen). |
| `BASE_PATH` | Nur hinter einem Reverse Proxy mit Unteradresse. Details in [BETRIEB.md](BETRIEB.md). |
| `TMDB_API_KEY` | Für Filme nötig. Kostenloser Schlüssel von themoviedb.org (Einstellungen → API). |
| `TMDB_LANGUAGE` | Sprache der Filmdaten, Standard `de-DE`. |
| `BARCODE_LOOKUP` | `1` (Standard): DVD-/Blu-ray-Barcodes bei UPCitemdb nachschlagen; `0`: aus. |

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

## 5. Filme

**Voraussetzung:** ein kostenloser TMDB-Schlüssel. Konto auf themoviedb.org anlegen, unter Einstellungen → API einen Schlüssel beantragen (Zweck: privat/nicht kommerziell) und in `.env` bei `TMDB_API_KEY` eintragen, dann neu starten. Ohne Schlüssel lassen sich Filme nur von Hand anlegen.

**Hinzufügen** (Menü Filme → Hinzufügen):
- **Barcode:** scannen, Format wählen oder automatisch erkennen lassen. Die App fragt den Produktnamen ab („Der Pate [Blu-ray] Steelbook“ wird zu „Der Pate“) und zeigt die passenden Filme von TMDB. Treffer wählen, ggf. Fassung eintragen, „Das ist mein Film“.
- **Titelsuche:** Titel und optional Jahr eingeben.
- **Ordner-Import:** Ordner wählen → Einlesen und erkennen → Vorschau prüfen → Übernehmen. Am sichersten sind Jellyfin-/Kodi-`.nfo`-Dateien oder Namen wie `Titel (Jahr)/Titel (Jahr).mkv` bzw. `Titel (Jahr) [tmdbid-123]`. Szene-Namen wie `Titel.2010.German.1080p.BluRay` werden bereinigt. Trailer, Samples und Extras-Ordner werden übersprungen, DVD-/Blu-ray-Ordner (VIDEO_TS, BDMV) zählen als ein Film. Aus den Dateien werden Auflösung, HDR, Codec, Laufzeit, Tonspuren und Untertitel gelesen.
- **Von Hand:** für Filme, die TMDB nicht kennt.

**Ein Film, mehrere Exemplare:** Hast du „Alien“ als DVD, Blu-ray und Datei, ist das ein Film mit drei Exemplaren. Ein weiteres Exemplar fügst du auf der Filmseite hinzu oder einfach per Barcode-Scan des zweiten Datenträgers.

**Gesehen und Bewertung:** Auf der Filmseite „Heute gesehen“ klicken oder ein Datum eintragen; es reicht auch das Jahr (z. B. 1999, wenn du den Film damals im Kino gesehen hast). Das Datum lässt sich jederzeit ändern, leer heißt „unbekannt“. „Heute nochmal gesehen“ zählt hoch. Die eigene Bewertung reicht von 1 (5× löschen) bis 10 (Unbedingt sehen) und gilt für gesehene und ungesehene Filme: Bei ungesehenen bedeutet sie, wie dringend du ihn sehen willst.

**Listen:** Alle · Noch nicht gesehen · Top 10: Muss ich sehen (die 10 ungesehenen mit der höchsten Bewertung) · Lieblingsfilme (gesehen, 9–10) · Zuletzt gesehen · Zuletzt hinzugefügt · Filmreihen (von TMDB, z. B. alle Teile einer Trilogie) · Eigene Listen (anlegen unter „Eigene Listen“ oder direkt auf der Filmseite). Die Suche findet Titel, Originaltitel, Regie, Darsteller, Stichworte und Barcodes; dazu Filter nach Genre, Jahrzehnt und Format.

**Poster:** Fehlt ein Poster, in der Filmübersicht auf „Fehlende Poster laden“ klicken. Die App sucht zuerst Bilder neben der Filmdatei (z. B. `poster.jpg`, `folder.jpg`, `cover.jpg`), dann in der Datei eingebettete Cover, dann alle Poster bei TMDB. Für einen einzelnen Film: auf der Filmseite unter dem Poster „Poster ändern“. Dort kannst du aus allen TMDB-Postern wählen oder ein eigenes Bild hochladen, etwa einen Scan der DVD-Hülle. Zeigt ein Film ein völlig falsches Bild, ist meist der Film falsch zugeordnet: dann „Anderen Film zuordnen“.

**Personen:** Namen in Besetzung, Regie und Drehbuch sind anklickbar. Die Personenseite zeigt Foto und Kurzbiografie, alle Filme mit dieser Person in deiner Sammlung und darunter ihre weiteren Filme und Serien laut TMDB, jeweils mit „Hinzufügen“. Tippst du in der Filmsuche einen Namen ein (z. B. „Neeson“), erscheint die Person zusätzlich als Treffer.

**Falscher Treffer?** Auf der Filmseite „Anderen Film zuordnen“. Exemplare, gesehen, Bewertung, Listen und Notiz bleiben erhalten. Gibt es den richtigen Film schon, werden die Exemplare dorthin verschoben.

## 6. Serien

**Voraussetzung:** derselbe TMDB-Schlüssel wie für die Filme. Serien haben eine eigene Datenbank (`data/serien.db`).

**Hinzufügen** (Menü Serien → Hinzufügen):
- **Barcode einer Box:** scannen, die App sucht über den Produktnamen. Steht darin z. B. „Staffel 1-3“ oder „Die komplette Serie“, wird das als Inhalt der Box vorgeschlagen.
- **Titelsuche:** Titel und optional das Jahr der ersten Ausstrahlung. Eine Box anzugeben ist freiwillig.
- **Ordner-Import (z. B. vom NAS):** Ordner wählen, in dem die Serienordner liegen → Einlesen und erkennen → Vorschau prüfen → Übernehmen. Die Folgen werden nach Serie gruppiert, jede Serie wird einmal bei TMDB gesucht. Erkannt werden `Serie.S01E01`, `S01E02E03` (Doppelfolge), `1x01`, `E01` ohne Staffel (dann Staffel 1, bei Dokus nach Folgentitel) und Staffelordner wie `Season 1` oder `Staffel 1`. Eine `tvshow.nfo` von Jellyfin oder Kodi macht die Zuordnung sicher. Beispiele: `Sacrifice.S01E01.GERMAN.DL.1080P.WEB.H264.mkv` und `Stephen.Hawkings.Grosser.Entwurf.E01.Wie.das.Universum.entstand…mkv`. Schon erfasste Dateien werden beim nächsten Lauf übersprungen, neue Folgen kommen einfach dazu.
- **Von Hand:** für Serien, die TMDB nicht kennt (dann ohne Episodenführer).

**Episodenführer und Episodennamen:** Für jede Serie lädt die App alle Staffeln und Folgen mit Titel, Inhalt und Ausstrahlungsdatum von TMDB. Die Folgennamen kommen von dort, auch wenn der Dateiname keinen enthält; fehlt ein deutscher Titel, wird der englische genommen. „Episodenführer aktualisieren“ auf der Serienseite holt neue Folgen und Staffeln.

**Was fehlt?** Auf der Serienseite steht bei jeder Folge „vorhanden“ (mit Auflösung oder „Box“), „fehlt“ oder „kommt“ (noch nicht ausgestrahlt). Eine Box zählt für die angegebenen Staffeln. Die Seite **Was fehlt?** listet alle Serien mit Lücken: ganze Staffeln oder einzelne Folgen mit Titel. Über „Als Text zum Kopieren“ gibt es die Liste als einfachen Text. Gezählt werden nur ausgestrahlte Folgen, Specials (Staffel 0) nicht.

**Videoformat:** Aus jeder Datei liest die App Auflösung, Codec, HDR, Laufzeit, Tonspuren und Untertitel (ffprobe). In der Übersicht steht die beste vorhandene Auflösung.

**Gesehen und Bewertung:** Pro Folge ein Haken, „Ganze Staffel als gesehen“, oder oben bei „Als Nächstes“ auf „Gesehen“ klicken. Die Bewertung 1–10 gilt wie bei den Filmen.

**Übersicht:** Alle · Unvollständig (es fehlen Folgen) · Angefangen · Noch nicht angefangen · Ganz gesehen · Läuft noch · Zuletzt hinzugefügt · Was fehlt?. Die Suche findet Titel, Darsteller, Sender und Barcodes.

**Personen:** Besetzung und Idee sind mit derselben Personenseite verknüpft wie bei den Filmen. Dort stehen jetzt Filme **und** Serien aus deiner Sammlung, darunter die weiteren laut TMDB mit „Hinzufügen“.

**Dateien ohne passende Folge:** Kann eine Datei keiner Folge zugeordnet werden, steht sie auf der Serienseite unten; dort lassen sich Staffel und Folge von Hand eintragen. Falsche Serie erkannt: „Andere Serie zuordnen“ (Dateien, Boxen und gesehen bleiben).

**Streamingdienst:** Auf der Serienseite steht, bei welchem Dienst die Serie im Abo läuft (laut JustWatch über TMDB), mit „Wo ansehen?“ und dem Termin der nächsten Folge. Stimmt die Angabe nicht oder fehlt sie, unter „Bearbeiten“ eine eigene eintragen. In der Serienübersicht lässt sich nach Dienst filtern.

**Merkliste** (Menü „Merkliste“): Oben stehen die Neuigkeiten deiner eigenen Serien: was demnächst startet (z. B. „Staffel 4 startet am 16.10.“ mit Dienst), was in den letzten 30 Tagen erschienen ist und welche Staffeln angekündigt sind. Darunter deine vorgemerkten Filme und Serien: Titel suchen, „Vormerken“, eine Notiz dazuschreiben (etwa „Tipp von …“). Die App zeigt Kinostart, Digitalstart oder Staffelstart und den Streamingdienst. „In die Sammlung“ führt zur Suche im passenden Bereich, „erledigt“ nimmt den Eintrag von der Liste (wiederherstellbar unter „Erledigte Einträge“).

**Aktualisierung:** Einmal am Tag frischt die App im Hintergrund auf: laufende Serien täglich, beendete alle 30 Tage, dazu die Merkliste. Beim ersten Mal kann das bei vielen Serien einige Minuten dauern. „Jetzt aktualisieren“ auf der Merkliste startet es sofort.

## 7. Bücher

Bücher haben eine eigene Datenbank (`data/buecher.db`). Ein Schlüssel ist nicht nötig.

**Hinzufügen** (Menü Bücher → Hinzufügen):
- **Mit ISBN:** den Strichcode auf der Rückseite scannen oder die ISBN eintippen (10 oder 13 Stellen, Striche und Leerzeichen sind egal). Die App fragt die **Deutsche Nationalbibliothek** und **Open Library** und zeigt die Ausgabe zur Bestätigung. Ist die ISBN schon in der Sammlung, zeigt die App das vorhandene Buch an.
- **Nach Titel und Autor:** ohne Scanner den Titel und am besten den Nachnamen eingeben, dann die richtige Ausgabe wählen.
- **Von Hand:** für Bücher, die keine Datenbank kennt (Selbstverlegtes, sehr alte Ausgaben).
- **Viele Bücher auf einmal** (Bücher-Import): Eine **ISBN-Liste** ist am einfachsten: eine ISBN pro Zeile, z. B. mit dem Scanner nacheinander in eine Textdatei gescannt. Oder eine **CSV- oder Excel-Tabelle** mit Spalten wie ISBN, Titel, Autor, Format, Gelesen, Bewertung, Notiz (die Kopfzeile wird erkannt). Die Suche dauert etwa eine Sekunde pro Buch; 300 Bücher brauchen also rund fünf Minuten, die Statusanzeige oben zeigt den Fortschritt.
- **E-Books und Hörbücher aus Ordnern:** EPUB, PDF, MOBI/AZW3, Calibre-Bibliotheken (dann werden die Angaben aus `metadata.opf` übernommen), M4B-Dateien und Ordner mit MP3/M4A (ein Ordner = ein Hörbuch, auch mit Unterordnern „CD 1“, „CD 2“). Für Hörbücher nur den Hörbuch-Ordner wählen, nicht die Musiksammlung. Schon erfasste Dateien werden beim nächsten Lauf übersprungen.
- Danach wie bei Filmen und Serien: Vorschau mit „Erkannt“, „Bitte prüfen“, „Nicht gefunden“ und „Buch schon vorhanden“, Knöpfe in der Leiste unten, gespeichert wird erst mit **Übernehmen**.

**Exemplare:** Ein Buch kann mehrere Exemplare haben (gebunden, Taschenbuch, E-Book, Hörbuch), etwa das Taschenbuch und das Hörbuch desselben Titels.

**Lesen und Bewerten:** „Lese ich gerade“, „Gelesen“ mit Datum. Ist das genaue Datum unbekannt, reicht das Jahr (z. B. 1999). Bewertung 1–10 und eine Notiz wie bei den Filmen.

**Übersicht:** sortierbar nach Autor (Nachname), Titel (ohne „Der/Die/Das“), Jahr, Bewertung und Hinzufügedatum, mit A–Z-Leiste und Filtern für Genre, Format und Sprache. Ansichten: Ungelesen, Lese ich gerade, Gelesen, Lieblinge, Zuletzt gelesen, Zuletzt hinzugefügt, E-Books, Hörbücher.

**Autoren und Reihen:** Autorennamen sind anklickbar und zeigen alle Bücher dieses Autors in der Sammlung. Unter **Buchreihen** stehen alle Reihen mit Bandnummern; fehlende Bände werden genannt.

**Zusammenfassung und Bewertungen:** Auf der Buchseite steht unter „Inhalt“ der Verlagstext (über die Deutsche Nationalbibliothek) oder die Beschreibung von Open Library, darunter die Einleitung des **Wikipedia**-Artikels zum Buch, falls es einen gibt, und die **Bewertung bei Open Library**. Die Links unter „Rezensionen suchen“ öffnen eine Suche bei Perlentaucher (Zusammenfassungen von Zeitungskritiken), Goodreads oder im Web. Geladen wird das automatisch im Hintergrund, nach dem Speichern bzw. Import. Passt der Wikipedia-Artikel nicht zum Buch, „Entfernen“ klicken. Eigene Gedanken zum Buch gehören in die **Notiz**.

**Korrigieren:** „Bearbeiten“ für alle Angaben, „Leere Felder ergänzen“ lädt fehlende Angaben nach (überschreibt nichts), „Anderes Buch zuordnen“ bei falschem Treffer (Exemplare, gelesen und Bewertung bleiben), „Titelbild ändern“ für ein anderes Cover oder ein eigenes Foto.

**Gut zu wissen:** Bei der Nationalbibliothek ist die Reihe oft nur die Verlagsreihe („dtv 21412“); solche Angaben übernimmt die App nicht. Die Reihe kannst du unter „Bearbeiten“ selbst eintragen. Cover gibt es bei Open Library nicht für jede deutsche Ausgabe; dann hilft ein Foto des Umschlags.

## 8. Verliehen an …

Für alle Bereiche gemeinsam gibt es die Seite **Verliehen** (Menü). Die Angaben liegen in einer eigenen kleinen Datenbank (`data/verleih.db`); die Datenbanken von Musik, Filmen, Serien und Büchern werden dabei nicht verändert.

**Was sich verleihen lässt:** nur, was du in der Hand hast: CDs (Besitz „CD“ oder „CD + digital“), DVDs, Blu-rays und 4K-Discs, Serien-Boxen, gedruckte Bücher und Hörbuch-CDs. Dateien, rein digitale Alben und E-Books nicht; dort steht „Nur digital vorhanden“.

**Verleihen auf der Detailseite:** Unten bei CD, Film, Serie oder Buch „Verleihen …“ öffnen, den Namen eintragen (bekannte Namen werden vorgeschlagen), Datum prüfen und „Als verliehen eintragen“. Das Datum ist mit heute vorbelegt. Weißt du es nicht mehr, Feld leeren oder nur das Jahr eintragen (z. B. 2015). „Zurück bis“ und eine Notiz sind freiwillig. Hat ein Film mehrere Exemplare (DVD und Blu-ray), wählst du, welches.

**Viele alte Verleihungen nachtragen:** Auf der Seite „Verliehen“ oben den Namen eintragen und nach Titel, Interpret oder Autor suchen. Bei jedem Treffer steht „An … verleihen“. So sind die CDs, DVDs und Bücher bei einem Freund schnell erfasst.

**Zurückbekommen:** auf der Detailseite, in der Übersicht oder auf der Seite der Person „Zurückbekommen“ (Datum vorbelegt mit heute). Auf der Personenseite gibt es „Alles zurückbekommen“. Was zurück ist, steht unter „Zurückbekommen“ bzw. „Früher geliehen“. Ein versehentlicher Eintrag lässt sich löschen.

**Überblick:** Die Seite zeigt alles nach Personen sortiert, mit Filter nach Bereich; überfällige Rückgaben sind rot. „Als Text zum Kopieren“ liefert die Liste als einfachen Text, etwa für eine Nachricht an Freunde. In den Übersichten der Bereiche sind verliehene Einträge markiert, die Startseite nennt die Zahl, und die Suche oben findet auch Namen.

## 9. Mediatheken

Auf jeder Serien- und Filmseite steht der Abschnitt **In der Mediathek**. MediaDB sucht dort in den Mediatheken der öffentlich-rechtlichen Sender (ARD, ZDF, Arte, 3sat, ORF, SRF und weitere) und zeigt Sender, Sendedatum, Länge und einen Link. Der Link öffnet die Sendung in der Mediathek des Senders im Browser. Die Suche läuft nach dem Laden der Seite; das dauert meist ein, zwei Sekunden.

**Bei Serien** ordnet MediaDB die Folgen dem Episodenführer zu und markiert sie mit **„fehlt dir“** oder „vorhanden“. So siehst du sofort, ob eine fehlende Folge gerade irgendwo läuft. Folgen, die sich nicht zuordnen lassen (Dokus, Specials), stehen ohne Markierung dabei.

**Merkliste:** Unter „Jetzt in der Mediathek“ stehen vorgemerkte Filme und Serien, die gerade abrufbar sind.

**Gut zu wissen:** Sendungen stehen nur eine begrenzte Zeit in den Mediatheken; manche sind nur in Deutschland, Österreich oder der Schweiz abrufbar. Fassungen mit Audiodeskription oder Gebärdensprache werden zu einem Eintrag zusammengefasst. MediaDB lädt nichts herunter. Die Suche lässt sich unter Einstellungen → „Dienste und Automatik“ abschalten.

## 10. Woher kommen die Daten?
Hauptquelle ist **MusicBrainz** (Daten) mit dem **Cover Art Archive** (Bilder). Optional **Discogs**, als Cover-Ausweichquelle **iTunes** und **Deezer**, außerdem die Tags in deinen Musikdateien. Für Filme und Serien ist es **TMDB** (Daten, Episodenführer und Bilder, Streamingdienste von JustWatch über TMDB) und für DVD-/Blu-ray-Barcodes **UPCitemdb**. Bücher kommen von der **Deutschen Nationalbibliothek** und von **Open Library**, die Mediathek-Treffer von **MediathekViewWeb**. Zusammengefasst: Es werden nur Suchbegriffe gesendet, deine Daten bleiben lokal. Genaueres, auch zur Frage „Darf ich das?“, steht in **DATENQUELLEN_UND_RECHT.md**.

## 11. Grenzen
- Keine getrennten Konten: ein gemeinsames Passwort (optional), „gesehen“ und Bewertungen gelten für den ganzen Haushalt. Nicht ins offene Internet stellen.
- Barcodes von DVDs und Blu-rays werden über einen freien Dienst nachgeschlagen, der deutsche Ausgaben nur lückenhaft kennt. Dann hilft die Titelsuche; der Barcode wird trotzdem gespeichert und beim nächsten Mal erkannt.
- Gelöschte oder verschobene Audiodateien werden nicht automatisch bereinigt.
- Cover von iTunes/Deezer sind rechtlich eine Grauzone und lassen sich mit `COVER_WEB=0` abschalten.
- Sehr alte, seltene oder nur lokal veröffentlichte Alben fehlen manchmal bei MusicBrainz; dann hilft Discogs oder die Handerfassung.
- Die Software wurde ohne automatisierte Tests entwickelt und von einem Nutzer im Alltag geprüft; Fehler bitte mit der Ausgabe von `docker compose logs --tail 60` melden.

## 12. Fehlersuche
| Problem | Lösung |
|---|---|
| Seite nicht erreichbar | `docker compose ps` prüfen, `docker compose up -d`, notfalls `docker compose logs --tail 60` |
| Container startet in Dauerschleife | Im Log die erste Zeile mit `Traceback` lesen; meist ein Fehler in einer frisch eingespielten Datei |
| Musikordner leer oder „Zugriff verweigert“ | macOS-Zugriff für OrbStack/Docker erlauben (siehe 2.) |
| MusicBrainz antwortet nicht | Später erneut versuchen; die App hält 1 Anfrage/s ein |
| Barcode findet nichts | Vollständigkeit prüfen (12/13 Ziffern), sonst „Ähnliche Ausgabe suchen“ |
| Ordner auf dem NAS lässt sich nicht umbenennen | Oben in der Navigation nachsehen, ob eine Aufgabe „liest Dateien“ läuft (orange Punkt). Nach dem Ende geht es wieder. Aufgaben nur mit „Internet“ greifen nicht auf deine Dateien zu. |
| Cover nicht gefunden | Siehe 4., letzter Absatz |
