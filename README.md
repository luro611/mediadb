# MusikDB

Private Musikdatenbank für den eigenen Rechner: CDs und Musikdateien verwalten, Titellisten, Cover und Genres automatisch aus MusicBrainz ergänzen. Läuft lokal im Docker-Container, Bedienung im Browser. Die Daten bleiben bei dir.

*English: a small self-hosted catalogue for your CDs and music files (FastAPI, SQLite). Looks up releases on MusicBrainz, optional Discogs. German UI and docs.*

## Funktionen
Barcode- und Diskografie-Suche · Import aus Excel/ODS/CSV · Audio-Import (MP3, M4A, FLAC …) mit Abgleich gegen vorhandene CDs · Cover und Genres · Suche, A–Z-Leiste, Interpreten-Übersicht · Export (xlsx, ods, csv, Markdown) · Discogs als Zweitquelle.

## Schnellstart
```
cp .env.example .env     # MB_USER_AGENT mit eigener E-Mail-Adresse anpassen
docker compose up --build
```
Dann `http://localhost:8000` öffnen. Daten liegen in `data/` (Datenbank und Cover).

## Dokumentation
- [Ausführliche Anleitung](docs/ANLEITUNG.md): Funktionen, Installation, Abläufe, Fehlersuche
- [Datenquellen und Rechtliches](docs/DATENQUELLEN_UND_RECHT.md): welche Dienste genutzt werden, Bedingungen, was bei Weitergabe zu beachten ist
- [Roadmap](docs/ROADMAP.md): Version 2 (Filme und Serien)
- [Projektanleitung](PROJEKTANLEITUNG.md): technische Entscheidungen und Stand, für die Weiterentwicklung
- [Änderungen](CHANGELOG.md)

## Hinweise
Nur für den lokalen Einzelnutzerbetrieb gedacht, nicht öffentlich ins Internet stellen. Keine Verbindung zu und keine Unterstützung durch MusicBrainz, Discogs, Apple oder Deezer. Cover bleiben Eigentum der Rechteinhaber und gehören nicht ins Repository.

## Lizenz
GNU GPL v3 oder später, siehe [LICENSE](LICENSE) (Vorschlag, vor der Veröffentlichung bestätigen; Begründung in den Rechtshinweisen).
