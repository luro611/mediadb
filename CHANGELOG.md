# Änderungen

## MediaDB 1.0.0 – Neuer Name, Fundament
Das Projekt hieß bisher **MusikDB** (Versionen 1.0 bis 1.2, siehe unten). Mit der Erweiterung auf Filme und Serien heißt es **MediaDB**, die Zählung beginnt neu. Deine Daten bleiben unverändert erhalten.
- Neuer Name in Oberfläche, Dokumentation und Docker (Dienst `mediadb`). Sprachwahl und Farbschema werden übernommen; nach einer gesetzten Anmeldung muss man sich einmal neu anmelden.
- Exportdateien heißen `mediadb-musik.xlsx` usw.
- Datenbank heißt jetzt `data/musik.db` (Vorbereitung für eigene Datenbanken für Filme und Serien). Eine vorhandene `musikdb.db` wird beim ersten Start automatisch umbenannt, vorher wird eine Kopie in `data/backup/` gelegt.
- Schnelle Volltextsuche mit Index (SQLite FTS5): findet auch Teilwörter und Umlaute unabhängig von Groß-/Kleinschreibung, getestet mit 1 Million Titeln (unter 1 ms je Suche). Zusätzliche Indizes für Listen und Filter.
- Zugriffsschutz: Zugriffe aus dem Internet werden ab Werk abgewiesen (`ALLOW_PUBLIC`), optionale Anmeldung mit Passwort (`APP_PASSWORD`).
- Läuft auch unter einer Unteradresse (Home Assistant Ingress, Reverse Proxy mit `X-Forwarded-Prefix` oder `BASE_PATH`).
- Homelab: `docker-compose.homelab.yml` (Proxmox-LXC, Linux, NAS) mit Musikordner `/music`, Healthcheck, `.dockerignore`, neue Anleitung `docs/BETRIEB.md` inkl. Veröffentlichung des Images auf Codeberg (amd64 + arm64).
- `DATABASE_URL` muss nicht mehr in `.env` stehen.

(Die Punkte oben waren als MusikDB 1.2.0 entwickelt und sind Teil von MediaDB 1.0.0.)

---

# Vorgeschichte: MusikDB

## MusikDB 1.1.0 – Mehrsprachigkeit
- Oberfläche in Deutsch, Englisch, Französisch und Spanisch; Auswahl oben neben „Theme“, bleibt nach Neustart erhalten (Cookie und `data/settings.json`).
- Alle Seiten, Meldungen, Fortschrittsanzeigen und die Markdown-Exportüberschriften sind übersetzt.
- Hilfsprogramm `tools/check_translations.py` prüft, ob alle Texte übersetzt sind.
- Neu: `docs/SPRACHEN.md`.

## MusikDB 1.0.0 – Version 1 (Musik)
- CDs erfassen per Barcode, Diskografie-Suche, Handerfassung, Tabellen-Import (xlsx/ods/csv).
- Audio-Import mit Titellisten-Abgleich, Ordnerbaum, mehreren Formaten, Compilations.
- Cover (lokal, MusicBrainz/Cover Art Archive, iTunes, Deezer), Genres, Erscheinungsdatum.
- Ähnliche Ausgabe suchen; Discogs-Link als Zweitquelle; unvollständige Barcodes werden ergänzt.
- Sammlung als Interpreten-Übersicht, Suche, A–Z-Leiste, Besitz (CD/digital/beides).
- Export (xlsx, ods, csv, Markdown), Sicherung/Wiederherstellung.
- Fortschrittsanzeigen ohne Neuladen der Seite.
- Option `COVER_WEB=0`, Dokumentation inkl. Datenquellen und Rechtliches.
