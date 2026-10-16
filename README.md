# MediaDB

**Projektseite / Website: [lurohome.de/mediadb](https://lurohome.de/mediadb/)** · Docker-Image: `codeberg.org/luro61/mediadb` (amd64, arm64) · Lizenz / License: GPL-3.0

Private Mediendatenbank für das eigene Heimnetz: CDs, Musikdateien, DVDs, Blu-rays, Filme, Serien und Bücher verwalten. Titellisten, Cover, Filmdaten, Episodenführer, Poster und Buchdaten kommen automatisch aus MusicBrainz, TMDB, der Deutschen Nationalbibliothek und Open Library. Läuft im Docker-Container (Proxmox-LXC, Linux-Server, NAS, Mac), Bedienung im Browser. Die Daten bleiben bei dir.

## In English

MediaDB is a small self-hosted catalogue for your **CDs and music files, films, TV shows and books**, made for your home network (FastAPI, SQLite, one Docker container).

- **Music:** scan a barcode, track list, cover and genre fill in from MusicBrainz; import music folders (MP3, M4A, FLAC …) and match them against your CDs.
- **Films and TV shows:** data, posters and episode guides from TMDB (free API key), folder import with Jellyfin/Kodi `.nfo`, watched status, ratings, list of missing episodes, watchlist with streaming services.
- **Books:** ISBN scan, e-books and audiobooks from folders, data from the German National Library and Open Library.
- **Lending:** keep track of what you lent to whom. **NAS:** reads SMB shares directly, no mounting needed (also in a Proxmox LXC).
- The **user interface** is available in **English, German, French and Spanish** (switch at the top right). The documentation is in German; your browser's translate function works fine on these pages.

**Quick start:** create `/opt/mediadb/data`, copy [`docker-compose.homelab.yml`](docker-compose.homelab.yml) to the server (or paste the compose file from the German quick start below as a new stack into Dockhand or Portainer and click *Deploy*), run `docker compose -f docker-compose.homelab.yml up -d` and open `http://<server>:8000`. Then add your e-mail address (for MusicBrainz) and a TMDB key under Settings. Details (in German): [docs/BETRIEB.md](docs/BETRIEB.md).

## Funktionen
Oberfläche in Deutsch, Englisch, Französisch, Spanisch und Italienisch (Auswahl in den Einstellungen, auf Wunsch auch als Umschalter oben) · **Filme:** Barcode, Titelsuche, Ordner-Import mit Jellyfin-.nfo, gesehen, eigene Bewertung 1–10, eigene Listen, Filmreihen · **Serien:** Barcode von Boxen, Ordner-Import vom NAS (S01E01, 1x01, Staffelordner, tvshow.nfo), Episodenführer von TMDB, Liste fehlender Staffeln und Folgen, Videoformat, gesehen pro Folge, Streamingdienste, Merkliste mit neuen Staffeln · **Bücher:** ISBN scannen, Titelsuche, E-Books und Hörbücher aus Ordnern (EPUB, Calibre, M4B, MP3), ISBN-Listen und Tabellen, gelesen, Bewertung, Autoren, Buchreihen · **Mediatheken:** zeigt, welche Serienfolgen und Filme gerade bei ARD, ZDF, Arte & Co. abrufbar sind („fehlt dir“) · **Verliehen an …:** CDs, DVDs, Blu-rays und Bücher an Freunde verleihen und zurückbekommen, mit Übersicht nach Personen · **NAS-Freigaben:** liest Musik, Filme, Serien und Bücher direkt per SMB von der NAS, ohne Einhängen · Barcode- und Diskografie-Suche · Import aus Excel/ODS/CSV · Audio-Import (MP3, M4A, FLAC …) mit Abgleich gegen vorhandene CDs · Cover und Genres · Suche, A–Z-Leiste, Interpreten-Übersicht · Export (xlsx, ods, csv, Markdown) · Discogs als Zweitquelle.

## Schnellstart

**Homelab (Proxmox-LXC, Linux-Server, NAS)** mit dem fertigen Image von Codeberg:
```
mkdir -p /opt/mediadb/data && cd /opt/mediadb
curl -O https://codeberg.org/luro61/mediadb/raw/branch/main/docker-compose.homelab.yml
docker compose -f docker-compose.homelab.yml up -d
```
**Mit Dockhand oder Portainer:**
1. Auf dem Server einmal den Datenordner anlegen: `mkdir -p /opt/mediadb/data`
2. Neuen Stack „mediadb“ anlegen und diese Compose-Datei einfügen (dieselbe wie [`docker-compose.homelab.yml`](docker-compose.homelab.yml), nur ohne die langen Kommentare):
   ```yaml
   services:
     mediadb:
       image: codeberg.org/luro61/mediadb:latest
       container_name: mediadb
       ports:
         - "8000:8000"          # links: Port im Browser, z. B. "80:8000" für http://<server>
       environment:
         - APP_PASSWORD=        # Passwort für die Anmeldung, leer = keins
         - ALLOW_PUBLIC=0       # 0 = nur Heimnetz und VPN
         - BASE_PATH=
         - TZ=Europe/Berlin
       volumes:
         - /opt/mediadb/data:/app/data                     # deine Daten
         - /opt/mediadb/medien/musik:/host/music:ro        # optional, nur lesend;
         - /opt/mediadb/medien/filme:/host/movies:ro       # eine NAS lieber unter
         - /opt/mediadb/medien/serien:/host/series:ro      # Einstellungen → NAS-Freigaben
         - /opt/mediadb/medien/buecher:/host/books:ro      # eintragen
       restart: unless-stopped
   ```
3. *Deploy* klicken, `http://<server>:8000` öffnen und unter Einstellungen (Zahnrad) E-Mail-Adresse, TMDB-Schlüssel und NAS-Freigaben eintragen.
4. Neue Version: Stack öffnen, *Pull* und *Redeploy*. Welche Version läuft, steht unten auf jeder Seite.

Alles Weitere in [Betrieb im Homelab](docs/BETRIEB.md).

**Mac** (OrbStack oder Docker Desktop), aus dem Quellcode:
```
cp .env.example .env     # MB_USER_AGENT mit eigener E-Mail-Adresse anpassen
docker compose up --build
```
Dann `http://localhost:8000` öffnen. Daten liegen in `data/` (Datenbanken, Cover, Einstellungen).

## Dokumentation
- [Projektseite](https://lurohome.de/mediadb/): Überblick, Deutsch und Englisch (weitere Projekte auf [lurohome.de](https://lurohome.de))
- [Ausführliche Anleitung](docs/ANLEITUNG.md): Funktionen, Installation, Abläufe, Fehlersuche
- [Betrieb im Homelab](docs/BETRIEB.md): Proxmox-LXC (auch mit Dockhand), NAS-Freigaben, Umzug vom Mac, Updates, Sicherung, Zugriffsschutz
- [Datenquellen und Rechtliches](docs/DATENQUELLEN_UND_RECHT.md): welche Dienste genutzt werden, Bedingungen, was bei Weitergabe zu beachten ist
- [Roadmap](docs/ROADMAP.md): nächste Versionen
- [Übersetzungen](docs/SPRACHEN.md): Sprachen ergänzen oder verbessern
- [Projektanleitung](PROJEKTANLEITUNG.md): technische Entscheidungen und Stand, für die Weiterentwicklung
- [Änderungen](CHANGELOG.md)

## Hinweise
Für den privaten Betrieb im Heimnetz gedacht, nicht öffentlich ins Internet stellen. Keine Verbindung zu und keine Unterstützung durch MusicBrainz, Discogs, Apple, Deezer, TMDB, die Deutsche Nationalbibliothek oder Open Library. Cover bleiben Eigentum der Rechteinhaber und gehören nicht ins Repository.

Fehler gefunden oder eine Idee? Gern als [Issue auf Codeberg](https://codeberg.org/luro61/mediadb/issues).

## Haftungshinweis
MediaDB ist ein privates Hobbyprojekt und wird kostenlos unter der GNU GPL-3.0 bereitgestellt. Eine Gewährleistung wird nicht übernommen, soweit das gesetzlich zulässig ist. Die Nutzung erfolgt auf eigenes Risiko. Die Software ist nicht in allen Umgebungen getestet. Es besteht keine Verpflichtung zu Support, Fehlerbehebung oder Weiterentwicklung.

*In English:* MediaDB is a private hobby project, provided free of charge under the GNU GPL-3.0. To the extent permitted by law, no warranty is given. Use at your own risk. The software has not been tested in every environment. There is no obligation to provide support.

## Lizenz
GNU GPL v3 oder später, siehe [LICENSE](LICENSE).
