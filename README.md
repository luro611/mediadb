# MediaDB

Private Mediendatenbank für den eigenen Rechner: CDs, Musikdateien, DVDs, Blu-rays, Filme, Serien und Bücher verwalten; Titellisten, Cover, Filmdaten, Episodenführer, Poster und Buchdaten kommen automatisch aus MusicBrainz, TMDB, der Deutschen Nationalbibliothek und Open Library. Läuft lokal im Docker-Container (Mac, Linux, Proxmox-LXC), Bedienung im Browser. Die Daten bleiben bei dir.

*English: a small self-hosted catalogue for your CDs, music files and films, TV shows and books (FastAPI, SQLite). Looks up music on MusicBrainz, films on TMDB, books at the German National Library and Open Library. UI in German, English, French and Spanish; docs in German.*

## Funktionen
Oberfläche in Deutsch, Englisch, Französisch und Spanisch (Auswahl oben neben „Theme“) · **Filme:** Barcode, Titelsuche, Ordner-Import mit Jellyfin-.nfo, gesehen, eigene Bewertung 1–10, eigene Listen, Filmreihen · **Serien:** Barcode von Boxen, Ordner-Import vom NAS (S01E01, 1x01, Staffelordner, tvshow.nfo), Episodenführer von TMDB, Liste fehlender Staffeln und Folgen, Videoformat, gesehen pro Folge, Streamingdienste, Merkliste mit neuen Staffeln · **Bücher:** ISBN scannen, Titelsuche, E-Books und Hörbücher aus Ordnern (EPUB, Calibre, M4B, MP3), ISBN-Listen und Tabellen, gelesen, Bewertung, Autoren, Buchreihen · **Mediatheken:** zeigt, welche Serienfolgen und Filme gerade bei ARD, ZDF, Arte & Co. abrufbar sind („fehlt dir“) · **Verliehen an …:** CDs, DVDs, Blu-rays und Bücher an Freunde verleihen und zurückbekommen, mit Übersicht nach Personen · Barcode- und Diskografie-Suche · Import aus Excel/ODS/CSV · Audio-Import (MP3, M4A, FLAC …) mit Abgleich gegen vorhandene CDs · Cover und Genres · Suche, A–Z-Leiste, Interpreten-Übersicht · Export (xlsx, ods, csv, Markdown) · Discogs als Zweitquelle.

## Schnellstart
```
cp .env.example .env     # MB_USER_AGENT mit eigener E-Mail-Adresse anpassen
docker compose up --build
```
Dann `http://localhost:8000` öffnen. Daten liegen in `data/` (Datenbank und Cover).

## Dokumentation
- [Ausführliche Anleitung](docs/ANLEITUNG.md): Funktionen, Installation, Abläufe, Fehlersuche
- [Datenquellen und Rechtliches](docs/DATENQUELLEN_UND_RECHT.md): welche Dienste genutzt werden, Bedingungen, was bei Weitergabe zu beachten ist
- [Betrieb im Homelab](docs/BETRIEB.md): Proxmox-LXC (auch mit Dockhand), Umzug vom Mac, Updates, Sicherung, Zugriffsschutz
- [Roadmap](docs/ROADMAP.md): nächste Versionen
- [Übersetzungen](docs/SPRACHEN.md): Sprachen ergänzen oder verbessern
- [Projektanleitung](PROJEKTANLEITUNG.md): technische Entscheidungen und Stand, für die Weiterentwicklung
- [Änderungen](CHANGELOG.md)

## Hinweise
Nur für den lokalen Einzelnutzerbetrieb gedacht, nicht öffentlich ins Internet stellen. Keine Verbindung zu und keine Unterstützung durch MusicBrainz, Discogs, Apple, Deezer, TMDB, die Deutsche Nationalbibliothek oder Open Library. Cover bleiben Eigentum der Rechteinhaber und gehören nicht ins Repository.

## Lizenz
GNU GPL v3 oder später, siehe [LICENSE](LICENSE) (Vorschlag, vor der Veröffentlichung bestätigen; Begründung in den Rechtshinweisen).
