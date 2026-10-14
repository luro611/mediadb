# Roadmap

## Version 1.0 (fertig)
Musik: CDs und Audiodateien, MusicBrainz, Cover, Genres, Import/Export, Audio-Import, Discogs als Zweitquelle.

## Festgelegte Reihenfolge
1. ✅ **1.2 Fundament (fertig):** Datenbank in drei Dateien vorbereiten (`musik.db`, später `filme.db`, `serien.db`; bestehende `musikdb.db` wird automatisch übernommen), Volltextsuche (FTS5) mit Index, Einstellungen für Datenordner, Port und Unterpfad (für Home Assistant Ingress), sichere Voreinstellung (nur lokal/Heimnetz), optionale Anmeldung vorbereitet, Docker-Image für amd64 und arm64. Noch offen daraus: Konten für mehrere Personen (bisher ein gemeinsames Passwort).
2. **2.0 Filme:** eigener Bereich mit eigener Datenbank.
3. **2.1 Serien:** eigener Bereich mit Staffeln und Folgen.
4. **Veröffentlichung auf Codeberg:** Quellcode und Docker-Image in der Codeberg-Registry; Update im LXC per `docker compose pull` und `docker compose up -d`.
5. **Home-Assistant-Add-on:** eigenes kleines Repository, verweist auf das Docker-Image.

## Version 2: Filme und Serien (offene Punkte)
Offene Entscheidungen vor dem Start:
1. ~~Ein Programm für alle Medien oder getrennte Bereiche?~~ **Entschieden:** getrennte Bereiche mit je eigener Datenbank (Musik, Filme, Serien).
2. **Datenquellen** für Filme/Serien, Bedingungen vorher lesen und in DATENQUELLEN_UND_RECHT.md aufnehmen. Kandidaten: TMDB (kostenloser API-Schlüssel, verlangt Quellenhinweis, Nutzung für nichtkommerzielle Zwecke), TheTVDB, OMDb, Wikidata. Bis dahin gilt: nichts davon ist geprüft.
3. **Barcode/EAN** bei DVD/Blu-ray: oft schlecht in freien Datenbanken; Alternative Titelsuche.
4. **Felder:** Titel, Originaltitel, Jahr, Regie, Darsteller, Laufzeit, Format (DVD, Blu-ray, 4K, Datei), Staffeln/Folgen bei Serien, Altersfreigabe, Cover/Poster.
5. **Dateiimport** für Videodateien (Ordner- und Dateinamen, Metadaten per `ffprobe`/MediaInfo).
6. **Lizenz/Technik:** Bei Hinzunahme weiterer Bibliotheken Lizenzen prüfen (siehe Rechtsdokument).

## Weitere Ideen
- Aufräumen gelöschter/verschobener Audiodateien.
- Automatische Tests und eine kleine Demo-Datenbank ohne echte Cover.
- Weitere Sprachen (siehe SPRACHEN.md) und Verbesserung der vorhandenen Übersetzungen durch Muttersprachler.
- Codeberg: Repository mit README, Lizenz, Issues; Releases als Tags.
