# Texte für lurohome.de/mediadb

Stand: MediaDB 1.22.2 (24.10.2026). Für den Homepage-Chat (Projekt `Webseiten/lurohome`): was sich auf der Projektseite `src/mediadb.html` und auf der Karte der Startseite (`PROJEKTE` in `src/build.py`) ändern soll. Die Version liest `build.py` selbst aus `VERSION`.

## Karte auf der Startseite

**DE:** Mediendatenbank fürs Heimnetz: CDs und Musikdateien, Filme, Serien und Bücher. Barcode scannen, Daten und Cover kommen von selbst. Für den ganzen Haushalt, mit eigenem Profil, eigener Bewertung und „gesehen“ für jede Person. Läuft im Docker-Container, Bedienung im Browser.

**EN:** A media database for your home network: CDs and music files, films, TV shows and books. Scan a barcode and the data and covers fill in. For the whole household, with a profile, ratings and “watched” for each person. Runs in a Docker container, used in the browser.

## Projektseite: neue Kacheln

Im Raster „Erfassen, ergänzen, wiederfinden“, gleicher Aufbau wie die vorhandenen Kacheln (Kicker, Überschrift, Text). Vorschlag: nach „Verliehen“ einfügen.

1. **Kicker:** Haushalt / Household
   **Überschrift:** Wer ist da? / Who’s there?
   **DE:** Mehrere Personen, eine Sammlung. Beim Öffnen auf den eigenen Namen klicken (PIN freiwillig) oder richtig mit Name und Passwort anmelden. Verwalter dürfen alles, Mitglieder ansehen und eintragen, Gäste stöbern ohne Passwort, ändern aber nichts. Die Konten liegen auf deinem Server, nicht in einer Cloud.
   **EN:** Several people, one collection. Click your own name when opening MediaDB (PIN optional) or sign in properly with name and password. Administrators may do everything, members view and add, guests browse without a password but change nothing. Accounts live on your server, not in a cloud.

2. **Kicker:** Jeder für sich / Everyone their own
   **Überschrift:** Gesehen von … / Watched by …
   **DE:** Gesehen, gelesen, eigene Bewertung, „Als Nächstes“ und die Merkliste hat jede Person für sich. Auf der Seite eines Films steht, wer ihn schon gesehen hat, bei Serien, wie viele Folgen jeder kennt.
   **EN:** Watched, read, your own rating, “Up next” and the watchlist belong to each person. A film’s page shows who has already watched it, a TV show how many episodes everyone has seen.

3. **Kicker:** Besitzer / Owner
   **Überschrift:** Wem gehört was? / Whose is it?
   **DE:** Jede CD, DVD, Blu-ray und jedes Buch hat einen Besitzer, oder es gehört dem ganzen Haushalt; Dateien und E-Books gehören immer allen. Die Listen filtern nach „Meine“ oder „von …“, beim Verleihen steht, wessen Exemplar unterwegs ist.
   **EN:** Every CD, DVD, Blu-ray and book has an owner, or belongs to the whole household; files and e-books always belong to everyone. Lists filter by “Mine” or “…’s”, and lending shows whose copy is out.

## Projektseite: geänderte Kacheln

- **Filme / Films**, Text ersetzen:
  **DE:** DVD, Blu-ray, 4K und Dateien per Barcode, Titelsuche oder Ordner-Import. Poster und Handlung von TMDB, „gesehen“ mit Datum, eigene Bewertung von 1 bis 10 und eigene Listen. Ist ein Film schon da, sagt MediaDB es deutlich; taucht er in besserer Auflösung auf, fragt es, ob die neue Datei die alte ersetzen soll.
  **EN:** DVD, Blu-ray, 4K and files by barcode, title search or folder import. Posters and plot from TMDB, watched with date, your own 1–10 rating and custom lists. If a film is already there, MediaDB says so clearly; if it turns up in a better resolution, it asks whether the new file should replace the old one.

- **Verliehen / Lent**, Satz anhängen:
  **DE:** Mit Konten steht dabei, wem das Exemplar gehört.
  **EN:** With accounts it also shows whose copy it is.

- **Als Nächstes / Up next**, Satz anhängen:
  **DE:** Mit Konten hat jede Person ihre eigene Reihe.
  **EN:** With accounts everyone has their own row.

## Projektseite: Fahrplan („Musik, Filme, Serien und Bücher“)

Nach 1.9 einfügen (alle „fertig / done“), vor „+ Home Assistant“:

| Version | DE | EN |
|---|---|---|
| 1.10 – 1.17 | Ansichten, Sprachen, Farben, Hilfe, Bereiche | Views, languages, colours, help, sections |
| 1.18 · 1.19 | GitHub, Hinzufügen verbessert | GitHub, better adding |
| 1.20 – 1.22 | Mehrere Nutzer | Several users |

## Projektseite: „Daten & Recht“

Satz ersetzen:
- **DE alt:** Es gibt kein Konto, keine Telemetrie und keine Werbung.
  **DE neu:** Es gibt kein Cloud-Konto, keine Telemetrie und keine Werbung; Konten für den Haushalt liegen nur auf deinem eigenen Server.
- **EN alt:** No account, no telemetry, no ads.
  **EN neu:** No cloud account, no telemetry, no ads; household accounts live only on your own server.

## Projektseite: „Für das Heimnetz gebaut“ (Homelab)

Satz anhängen:
- **DE:** Dazu kommt eine kleine Datei mit den Konten (`data/nutzer.db`), die mit in die Sicherung gehört.
- **EN:** Plus a small file with the accounts (`data/nutzer.db`) that belongs in your backup.

Falls dort oder bei der Installation der Zugriffsschutz erwähnt wird:
- **DE:** Mehrere Personen richtest du in der App ein (Einstellungen → Nutzer und Anmeldung). Für Filme und Serien brauchst du einen kostenlosen TMDB-Schlüssel (themoviedb.org → Einstellungen → API); MediaDB weist beim ersten Start darauf hin.
- **EN:** Set up several people in the app (Settings → Users and sign-in). Films and TV shows need a free TMDB key (themoviedb.org → Settings → API); MediaDB points this out on first start.

## Bildschirmfotos (optional)

Erfundene Beispiel-Sammlung, erfundene Namen (Maren, Jonas, Besuch). Deutsch in `docs/bilder/`, Englisch in `docs/bilder/en/`, gleicher Dateiname:

- `anmelden-profile.png`: Profilwahl „Wer ist da?“ / “Who’s there?”, passt zur Kachel „Haushalt“
- `gesehen-von.png`: gesehen und Bewertung mit „Gesehen von“, passt zu „Jeder für sich“
- `besitzer-exemplare.png`: Exemplare mit Besitzer, passt zu „Besitzer“
- `einstellungen-nutzer.png`: Einstellungen → Nutzer und Anmeldung
