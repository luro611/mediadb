# Roadmap

## MediaDB 1.0 (fertig, bisher MusikDB 1.0–1.2)
Musik und Fundament: CDs und Audiodateien, MusicBrainz, Cover, Genres, Import/Export, Audio-Import, Discogs als Zweitquelle.

## Festgelegte Reihenfolge
1. ✅ **Fundament (fertig, in MediaDB 1.0):** Datenbank in drei Dateien vorbereiten (`musik.db`, später `filme.db`, `serien.db`; bestehende `musikdb.db` wird automatisch übernommen), Volltextsuche (FTS5) mit Index, Einstellungen für Datenordner, Port und Unterpfad (für Home Assistant Ingress), sichere Voreinstellung (nur lokal/Heimnetz), optionale Anmeldung vorbereitet, Docker-Image für amd64 und arm64. Noch offen daraus: Konten für mehrere Personen (bisher ein gemeinsames Passwort).
2. ✅ **1.1 Filme (fertig):** eigener Bereich mit eigener Datenbank (`filme.db`): Barcode, Titelsuche, Ordner-Import mit .nfo/ffprobe, Exemplare, gesehen, Bewertung 1–10, eingebaute und eigene Listen, Filmreihen.
3. ✅ **1.2 Startseite und Bedienung (fertig):** Startseite, gemeinsame Suche, Buchstabenauswahl.
4. ✅ **1.3 Serien (fertig):** eigener Bereich mit eigener Datenbank (`serien.db`): Barcode von Boxen, Titelsuche, Ordner-Import, Episodenführer von TMDB, Vergleich „Was fehlt?“, Videoformat, gesehen pro Folge, Personen gemeinsam mit den Filmen.
5. ✅ **1.4 Merkliste, 1.5 Einstellungen, 1.6 Bücher, 1.7 Verliehen, 1.8 Mediatheken (fertig).**
6. ✅ **Betrieb im Proxmox-LXC** (oberste Priorität für den Alltag, 1.8.1 vorbereitet: fertiges Image `codeberg.org/luro61/mediadb`, Stack für Dockhand, alles unter `/opt/mediadb`, Umzug vom Mac) und **Veröffentlichung auf Codeberg:** Quellcode und Docker-Image in der Codeberg-Registry; Update in Dockhand per Pull und Redeploy. Vor der Veröffentlichung noch: Codeberg-Links auf der Projektseite (TMDB-Logo erledigt in 1.8.2).
7. ✅ **1.9 NAS-Freigaben direkt in MediaDB (fertig):** siehe unten.
8. ✅ **1.10–1.17 Alltag und Bedienung (fertig):** Kacheln/Liste/Text, „Als Nächstes“, aufgeräumte Startseite, Italienisch und Spracheinstellungen, eigene Farben, Hilfe in der App mit Bildschirmfotos, Bereiche ein- und ausschalten, Willkommensseite beim ersten Start.
9. **Offen:** Anleitung in die anderen Sprachen übersetzen; gemeinsame Konten für Familien.
10. **Home-Assistant-Add-on:** eigenes kleines Repository, verweist auf das Docker-Image.

## NAS-Freigaben (1.9, fertig)
Problem: In einem Proxmox-LXC (unprivilegiert, Standard) lassen sich Netzwerkfreigaben weder im LXC noch im Docker-Container einhängen. Der Umweg über den Proxmox-Host (fstab, `pct set … -mp0`) ist niemandem zu erklären.
Lösung: MediaDB liest SMB-Freigaben selbst (Bibliothek smbprotocol, SMB 2/3), ganz ohne Einhängen. Funktioniert gleich im LXC, auf dem Mac, auf einem Raspberry Pi oder auf der NAS.
- **Einstellungen → NAS-Freigaben:** Name (z. B. „Musik“), NAS-Adresse, Freigabe, optional Unterordner, Benutzer, Passwort; „Verbindung prüfen“. Passwort wird nur maskiert angezeigt.
- **Import:** Jede Freigabe erscheint in der Ordnerauswahl von Musik, Filmen, Serien und Büchern als „NAS: Musik“ (intern `/nas/musik/…`), neben `/music`, `/movies` usw.
- **Technik:** eine Dateischicht (`app/fs.py`) für alle Importe: Ordner durchsuchen, Dateien lesen, Größen; für ffprobe/ffmpeg ein kleiner Vermittler nur auf 127.0.0.1, der die Datei per HTTP mit Range-Anfragen weiterreicht (es wird nur gelesen, was ffprobe braucht, nicht der ganze Film).
- Nur lesend. Empfehlung in der Anleitung: eigener NAS-Benutzer nur mit Leserechten.
Später: NFS, Anzeige „Datei auf dem NAS nicht mehr gefunden“, Hinweis auf eine neue Version direkt in MediaDB.

## Bücher (1.6, fertig)
Eigener Bereich mit eigener Datenbank (`buecher.db`): ISBN, Titelsuche, von Hand, E-Books und Hörbücher aus Ordnern, ISBN-Listen und Tabellen, Exemplare, gelesen, Bewertung, Autoren, Buchreihen. Daten von der Deutschen Nationalbibliothek und Open Library.
Später: Bücher auf die Merkliste (Wunschliste), Export als Tabelle, weitere Quelle für Cover deutscher Ausgaben.

## Mediatheken (1.8, fertig)
Suche in den Mediatheken von ARD, ZDF, Arte & Co. über MediathekViewWeb: Serien- und Filmseiten, Abgleich mit dem Episodenführer („fehlt dir“), Merkliste. Nur Links.
Später, nur wenn jemand danach fragt: Download einer Folge (in den Download-Ordner oder direkt in den Serienordner auf dem NAS).

## Verleihen (1.7, fertig)
Zentral für alle Bereiche (`verleih.db`): nur Physisches (CD, DVD, Blu-ray, 4K, Serien-Box, gedrucktes Buch, Hörbuch-CD), Person, Datum, zurück bis, Notiz; Übersicht, Personenseite, Markierung in den Listen, Text zum Kopieren.
Später: Erinnerung bei überfälligen Rückgaben (z. B. über Home Assistant).

## Merkliste (1.4, fertig)
Neue Staffeln der eigenen Serien, vorgemerkte Filme und Serien, Streamingdienste, tägliche Aktualisierung.
Später: Streamingdienst auch bei Filmen anzeigen; Benachrichtigung (z. B. Home Assistant) bei neuen Staffeln.

## Serien: Nachträge
- Eigene Listen und Merkliste wie bei den Filmen.
- Fehlende Poster gesammelt laden (wie bei den Filmen); bisher beim Speichern und über „Poster ändern“.
- Staffelposter und Bilder neben den Dateien (poster.jpg, season01-poster.jpg) nutzen.
- Aufräumen gelöschter oder verschobener Folgendateien.
- Absolute Folgennummern (Anime) und Folgen nach Ausstrahlungsdatum (Talkshows).

## Filme: Nachträge
- Zweite Barcode-Quelle (z. B. Disq), sobald dokumentiert; bisher UPCitemdb.
- Export/Sicherung der Filmliste als Tabelle (Datenbankdatei `filme.db` ist bis dahin die Sicherung).
- Gesehen und Bewertung pro Person, sobald es Konten gibt.
- Aufräumen gelöschter oder verschobener Filmdateien.

## Weitere Ideen
- Desktop-Version für Mac und Linux (ohne Docker), später.
- Aufräumen gelöschter/verschobener Audiodateien.
- Automatische Tests und eine kleine Demo-Datenbank ohne echte Cover.
- Weitere Sprachen (siehe SPRACHEN.md) und Verbesserung der vorhandenen Übersetzungen durch Muttersprachler.
- Codeberg: Repository mit README, Lizenz, Issues; Releases als Tags.
