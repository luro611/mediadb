# Roadmap

## Version 1.0 (fertig)
Musik: CDs und Audiodateien, MusicBrainz, Cover, Genres, Import/Export, Audio-Import, Discogs als Zweitquelle.

## Version 2: Filme und Serien (Ideen, noch nichts entschieden)
Offene Entscheidungen vor dem Start:
1. **Ein Programm für alle Medien** (Tabelle `media` um einen Medientyp erweitern) oder getrennte Bereiche? Vorschlag: eine Datenbank, Feld `media_type` (music / film / series), gemeinsame Sammlungsansicht mit Reitern.
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
