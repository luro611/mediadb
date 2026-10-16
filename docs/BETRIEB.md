# Betrieb im Homelab

MediaDB ist für das **eigene Heimnetz** gedacht: ein Haushalt, eine kleine Datenbank auf dem eigenen Rechner oder Server. Die App gehört nicht frei ins Internet (siehe unten).

## Varianten

| Wo | Datei | Bemerkung |
|---|---|---|
| Mac (OrbStack, Docker Desktop) | `docker-compose.yml` | liest Musik von `/Volumes` und aus dem Benutzerordner |
| Proxmox-LXC, Linux-Server, NAS, Dockhand | `docker-compose.homelab.yml` | fertiges Image von Codeberg, alles unter `/opt/mediadb` |
| Home Assistant | geplant | als Add-on, siehe Roadmap |

## Proxmox: LXC mit Docker

### Größe des LXC

MediaDB selbst ist sparsam. Richtwerte für eine Sammlung mit einigen tausend Alben, Filmen und Büchern:

| | Empfehlung | Bemerkung |
|---|---|---|
| CPU | 2 Kerne | 1 reicht im Alltag; der zweite hilft bei Importen und beim Neuaufbau des Suchindex |
| RAM | 1024 MB, dazu 512 MB Swap | die App braucht im Betrieb etwa 150–300 MB |
| Speicher | 16 GB | System ca. 1,5 GB, Docker-Image ca. 0,7 GB (beim Update kurz doppelt), dazu der Ordner `data` |

Der Ordner `data` wächst vor allem durch Cover und Poster (grob 50–150 KB pro Eintrag). Die **Mediendateien selbst** (MP3, Filme) brauchen viel mehr Platz und gehören auf Dauer auf ein NAS; für den Anfang müssen sie gar nicht im LXC liegen (siehe unten). Den Speicher kann man in Proxmox jederzeit vergrößern (*Ressourcen → Laufwerk → Größe ändern*), aber nicht verkleinern.

### Einrichten

1. In Proxmox einen LXC anlegen (z. B. Debian 12/13) mit den Werten oben. Unter *Optionen → Features* **nesting** und **keyctl** einschalten (nötig für Docker im LXC).
2. Im LXC Docker installieren (offizielle Anleitung: docs.docker.com → Install → Debian) oder fertig mit Dockhand/Hawser einrichten.
3. Den Ordner für MediaDB anlegen: `mkdir -p /opt/mediadb/data`
4. **Mit Dockhand:** neuen Stack „mediadb“ anlegen und den Inhalt von `docker-compose.homelab.yml` einfügen, dann *Deploy*.
   **Ohne Dockhand:** `docker-compose.homelab.yml` nach `/opt/mediadb/` kopieren und dort `docker compose -f docker-compose.homelab.yml up -d` ausführen.
5. Im Browser `http://<IP-des-LXC>:8000` öffnen und unter Einstellungen (Zahnrad) E-Mail, TMDB-Schlüssel usw. eintragen.

Alles liegt in **einem** Ordner, `/opt/mediadb`:

| Ordner im LXC | in der App | Inhalt |
|---|---|---|
| `/opt/mediadb/data` | – | Datenbanken, Cover, Einstellungen (**deine Daten**) |
| `/opt/mediadb/medien/musik` | `/music` | Musikdateien für den Audio-Import |
| `/opt/mediadb/medien/filme` | `/movies` | Filmdateien für den Film-Import |
| `/opt/mediadb/medien/serien` | `/series` | Serien für den Serien-Import |
| `/opt/mediadb/medien/buecher` | `/books` | E-Books und Hörbücher für den Bücher-Import |

Der Container läuft als root und liest die Medienordner nur. Solange die Dateien im LXC selbst liegen (und als root dorthin kopiert wurden), gibt es **keine Probleme mit Dateirechten**.

### Brauchen die Mediendateien Platz im LXC?

Nein. MediaDB spielt nichts ab; nach dem Import stehen Titel, Tags, Technikdaten und Cover in der Datenbank. Bereits erfasste Sammlungen (auch vom Mac übernommene) brauchen die Dateien also nicht.

### Musik und Filme von der NAS einlesen (ab 1.9)

Am einfachsten liest MediaDB die Dateien **direkt von der NAS**. In Proxmox muss dafür nichts eingerichtet werden.

1. In MediaDB: **Einstellungen (Zahnrad) → NAS-Freigaben → Freigabe hinzufügen**.
2. Eintragen: Name (z. B. „Musik“), NAS-Adresse (z. B. `192.168.1.20`), Freigabe (der Ordnername, den du auch im Finder unter `smb://192.168.1.20/…` siehst), optional ein Unterordner, Benutzer und Passwort der NAS. Die ganze Adresse `smb://192.168.1.20/Musik/Alben` ins Feld NAS-Adresse zu kopieren geht auch.
3. **Verbindung prüfen** (prüft, ohne zu speichern) und dann **Speichern und prüfen.** Die Meldung sagt, ob es klappt, und sonst, woran es hängt: Name nicht gefunden, NAS antwortet nicht, SMB aus, Anmeldung, Freigabe oder Unterordner falsch.
4. Für weitere Freigaben auf derselben NAS oben **„Zugang einer eingerichteten NAS übernehmen“** wählen: Adresse, Benutzer und Passwort sind dann schon eingetragen.
5. Beim Einlesen (Audio-Import, Filme, Serien, Bücher) erscheint die Freigabe in der Ordnerauswahl als **„NAS: Musik“**.

Die NAS muss **SMB2 oder SMB3** anbieten (bei Synology, QNAP, UGREEN, TrueNAS, Unraid, Fritzbox und Windows Standard). Es wird nur gelesen.

**Wenn es nicht klappt:**
- Die **IP-Adresse** der NAS eintragen, nicht ihren Namen. Namen wie `diskstation.local` findet der Docker-Container meist nicht.
- Ein **Benutzer mit Passwort** ist nötig; ein Gastzugang ohne Passwort geht nicht.
- Unter der Meldung steht eine **technische Angabe**. Die hilft bei der Fehlersuche.

**NAS, die nicht immer an ist:** Kein Problem. Was eingelesen ist, steht in der Datenbank von MediaDB und bleibt, auch wenn die NAS aus ist. In der Ordnerauswahl zeigt ein Punkt neben „NAS: …“, ob sie gerade erreichbar ist. Vor dem Einlesen die NAS einschalten und warten, bis der Punkt grün ist. Geht sie während des Einlesens aus, nennt MediaDB danach die Ordner, die fehlen; einfach später noch einmal einlesen. Am besten legst du auf der NAS einen eigenen Benutzer an, der die Freigaben nur lesen darf.


### Musik vom Mac (oder einem anderen Rechner) einlesen

MediaDB läuft im LXC und kann nicht auf die Festplatte des Rechners zugreifen, auf dem der Browser läuft (das lässt kein Browser zu). Ein Mac lässt sich aber **wie eine NAS freigeben**; dann erscheint sein Musikordner beim Einlesen als „NAS: …“.

**Am Mac den Ordner freigeben:**
1. **Systemeinstellungen → Allgemein → Teilen**, **Dateifreigabe** einschalten und daneben auf **ⓘ** klicken.
2. Unter **Geteilte Ordner** mit **+** den Musikordner hinzufügen (z. B. `Musik` im Benutzerordner).
3. **Optionen …**: Haken bei **„Dateien und Ordner über SMB teilen“**. Darunter bei **Windows-Dateifreigabe** den Haken beim eigenen Benutzer setzen und das Mac-Passwort eingeben. **Wichtig:** Ohne diesen Haken lehnt der Mac die Anmeldung ab, auch mit richtigem Passwort.
4. Oben im Fenster steht die Adresse, z. B. `smb://192.168.1.23`.

**In MediaDB eintragen** (Einstellungen → NAS-Freigaben → Freigabe hinzufügen):
- **Name:** z. B. `Mac Musik`
- **NAS-Adresse:** die IP von oben, z. B. `192.168.1.23` (nicht den Namen wie `Mein-MacBook.local`, den findet der Container nicht)
- **Freigabe:** der Ordnername, wie er unter „Geteilte Ordner“ steht, z. B. `Musik`
- **Benutzer und Passwort:** der Kurzname des Mac-Benutzers (wie in `/Users/…`) und das Mac-Passwort

Dann **Verbindung prüfen**. Beim Musik-Import erscheint der Mac als „NAS: Mac Musik“.

**Gut zu wissen:**
- **Ruhezustand:** Schläft der Mac, zeigt MediaDB „gerade aus“. Vor dem Einlesen den Mac wecken.
- **Feste IP:** Im Router dem Mac immer dieselbe Adresse geben (Fritzbox: *Heimnetz → Netzwerk → Gerät bearbeiten → „Diesem Netzwerkgerät immer die gleiche IPv4-Adresse zuweisen“*), sonst stimmt die Adresse irgendwann nicht mehr.
- **Apple-Musik-Mediathek:** Die Dateien liegen meist unter `Musik/Music/Media/Music`, bei älteren Macs unter `Musik/iTunes/iTunes Media/Music`. Im Import einfach dorthin durchklicken.
- **Eigener Benutzer:** Wer sein Mac-Passwort nicht in MediaDB speichern möchte, legt unter *Systemeinstellungen → Benutzer & Gruppen* einen Benutzer „Nur Teilen“ an und gibt ihm beim geteilten Ordner nur Leserechte.
- **Windows-PC:** geht genauso: Ordner im Explorer über *Eigenschaften → Freigabe* freigeben, dann IP, Ordnername, Windows-Benutzer und Passwort eintragen.

**Ohne NAS:** Neue Ordner in `/opt/mediadb/medien/…` kopieren, einlesen und danach wieder löschen.

Dateien vom Mac in den LXC kopieren (im Mac-Terminal; Ordnernamen anpassen):
```
rsync -av --progress "/Volumes/Musik/Neue Alben/" root@<IP-des-LXC>:/opt/mediadb/medien/musik/
```
Dafür muss im LXC die Anmeldung per SSH als root erlaubt sein. Geht das nicht, den Weg über den Proxmox-Host nehmen (wie beim Umzug unten).

### Umzug vom Mac in den LXC

Der Ordner `data` wird einmal komplett übernommen. Danach nur noch im LXC arbeiten, nicht mehr parallel auf dem Mac (sonst gibt es zwei verschiedene Datenbanken).

1. **Mac, Terminal, im Projektordner:** App stoppen und den Ordner `data` einpacken.
   ```
   docker compose down
   COPYFILE_DISABLE=1 tar -czf ~/Desktop/mediadb-data.tar.gz --exclude .DS_Store data
   ```
2. **Mac:** Das Paket auf den Proxmox-Host kopieren (Proxmox-IP und root-Passwort von Proxmox):
   ```
   scp ~/Desktop/mediadb-data.tar.gz root@<IP-von-Proxmox>:/tmp/
   ```
3. **Dockhand:** Läuft der Stack „mediadb“ schon, ihn jetzt **stoppen**.
4. **Proxmox-Weboberfläche → Knoten → Shell** (`<CTID>` ist die Nummer des LXC, z. B. 112):
   ```
   pct push <CTID> /tmp/mediadb-data.tar.gz /root/mediadb-data.tar.gz
   pct exec <CTID> -- mkdir -p /opt/mediadb
   pct exec <CTID> -- tar -xzf /root/mediadb-data.tar.gz -C /opt/mediadb --no-same-owner
   pct exec <CTID> -- rm /root/mediadb-data.tar.gz
   rm /tmp/mediadb-data.tar.gz
   ```
   Danach liegt alles in `/opt/mediadb/data`.
5. **Dockhand:** Stack starten. Der erste Start kann bei großen Sammlungen eine halbe Minute dauern.
6. Im Browser prüfen: Zahlen auf der Startseite, Cover, Einstellungen. Die Werte aus der Mac-Datei `.env` (z. B. E-Mail für MusicBrainz, Discogs-Token) unter Einstellungen eintragen, falls sie dort noch fehlen.

Die Datei `~/Desktop/mediadb-data.tar.gz` auf dem Mac ist zugleich eine Sicherung; aufheben, bis im LXC alles läuft.

## Neue Version einspielen

Gibt es eine neue Version, steht unten auf jeder Seite „Neue Version … verfügbar“ (alle sechs Stunden bei Codeberg nachgesehen, abschaltbar unter Einstellungen). Der Link führt zu den Neuerungen. Sofort nachsehen: Einstellungen → „Neue Version?“ → „Jetzt nach neuer Version suchen“.

**Mit Dockhand:** Stack „mediadb“ → *Pull* (lädt das neue Image von Codeberg) → *Redeploy*. Welche Version läuft, steht unten auf jeder Seite (z. B. „MediaDB 1.13.1“). Steht dort nach dem Redeploy noch die alte Nummer, war das *Pull* nicht erfolgreich: noch einmal *Pull*, dann *Redeploy*.

**Im Terminal des LXC:**
```
cd /opt/mediadb
docker compose -f docker-compose.homelab.yml pull
docker compose -f docker-compose.homelab.yml up -d
```

**Aus dem Quellcode** (wer selbst bauen will; in der Compose-Datei `build: .` statt `image:`):
```
git clone https://codeberg.org/luro61/mediadb.git   # beim ersten Mal, danach: git pull
docker compose -f docker-compose.homelab.yml up -d --build
```

Der Ordner `data` (Datenbank, Cover, Einstellungen) bleibt bei allen Wegen unberührt. Änderungen an der Datenbank (neue Spalten, Suchindex) macht die App beim Start selbst. Bei sehr großen Sammlungen kann der erste Start nach einem Update eine halbe Minute dauern, wenn der Suchindex neu aufgebaut wird.

## Sicherung

Alles Wichtige liegt in `data/`:
- `filme.db`: die Filmdatenbank, `film_images/`: Poster und Hintergrundbilder
- `serien.db`: die Seriendatenbank, `buecher.db`: die Bücherdatenbank (Titelbilder ebenfalls in `film_images/`)
- `verleih.db`: wer was geliehen hat (alle Bereiche)
- `musik.db`: die Musikdatenbank (früher `musikdb.db`, wird beim ersten Start automatisch umbenannt, eine Kopie landet in `data/backup/`)
- `covers/`: die Cover-Bilder
- `settings.json`, `secret.key`: Einstellungen und Schlüssel für die Anmeldung

Am sichersten: App kurz stoppen (`docker compose … down`), den Ordner `data` kopieren, wieder starten. Unter Proxmox reicht auch ein Backup/Snapshot des ganzen LXC.

## Zugriffsschutz

Ab Werk gilt:
- **Nur Heimnetz:** Anfragen von öffentlichen Internet-Adressen werden abgewiesen. Heimnetz (192.168.x.x, 10.x.x.x usw.), der eigene Rechner und VPNs wie Tailscale oder WireGuard mit privaten Adressen sind erlaubt.
- **Keine Anmeldung:** Für einen Nutzer im eigenen Heimnetz reicht das.

Diese Einstellungen stehen im Homelab in der Compose-Datei unter `environment:` (in Dockhand: Stack bearbeiten), auf dem Mac in `.env`. Danach neu starten (Dockhand: *Redeploy*):

| Einstellung | Wirkung |
|---|---|
| `APP_PASSWORD=…` | Anmeldung mit diesem Passwort. Empfohlen, sobald mehrere Personen oder Gäste im WLAN sind. Ein neues Passwort meldet alle ab. |
| `ALLOW_PUBLIC=1` | Auch Zugriffe aus dem Internet zulassen. **Nicht empfohlen.** Wenn überhaupt, nur mit Passwort und HTTPS über einen Reverse Proxy. |
| `BASE_PATH=/musik` | Nur hinter einem Reverse Proxy unter einer Unteradresse. Der Proxy muss die Unteradresse vor der Weitergabe entfernen (z. B. Traefik *StripPrefix*, der dann auch `X-Forwarded-Prefix` setzt; dann ist `BASE_PATH` gar nicht nötig). |
| `SECRET_KEY=…` | Optional. Sonst wird beim ersten Start `data/secret.key` angelegt. |

Wichtig: Hinter einem Reverse Proxy sieht die App nur die Adresse des Proxys, nicht die des Besuchers. Die Heimnetz-Sperre greift dann nicht. Wer die App über einen Proxy erreichbar macht, muss `APP_PASSWORD` setzen.

### Warum nicht ins Internet?

- Cover und Daten stammen von Diensten mit eigenen Bedingungen (siehe `DATENQUELLEN_UND_RECHT.md`). Eine öffentlich erreichbare Seite mit fremden Covern ist etwas anderes als die private Nutzung.
- Die App ist ein Hobbyprojekt ohne Sicherheitsprüfung.
- Wer die App trotzdem öffentlich betreibt, tut das auf eigene Verantwortung. Eine Gewährleistung wird nicht übernommen, soweit das gesetzlich zulässig ist (siehe Haftungshinweis im README).

## Docker-Image auf Codeberg veröffentlichen (für den Projektbetreuer)

Codeberg hat eine eigene Registry für Docker-Images. Das Image wird für normale PCs/Server (amd64) **und** für Raspberry Pi und ARM-Macs (arm64) gebaut.

Einmalig:
1. Auf codeberg.org anmelden → *Einstellungen → Anwendungen → Zugangstoken erstellen*. Name z. B. „docker“, Berechtigung **package: Lesen und Schreiben**. Den Token sofort kopieren (er wird nur einmal angezeigt).
2. Mac-Terminal: `docker login codeberg.org` → Benutzername `luro61`, als Passwort den Token einfügen.
3. Für die Releases nimmt `publish.sh` denselben Token aus dem Schlüsselbund (von `docker login`). Er braucht dafür zusätzlich **repository: Lesen und Schreiben**. Hat er das nicht, einen zweiten Token mit dieser Berechtigung anlegen, kopieren und im Mac-Terminal speichern (liest ihn aus der Zwischenablage, er erscheint nirgends auf dem Bildschirm):
   ```
   mkdir -p ~/.config/mediadb && pbpaste > ~/.config/mediadb/codeberg-token && chmod 600 ~/.config/mediadb/codeberg-token
   ```
4. Im Projekt auf Codeberg die Releases einschalten: *mediadb → Einstellungen → Einheiten* (bei älteren Codeberg-Versionen: *Einstellungen → Repository*), Haken bei **Releases**, speichern.

Jede neue Version: `VERSION` hochzählen, in `CHANGELOG.md` einen Abschnitt `## MediaDB <Version> – …` schreiben, committen und pushen. Dann im Mac-Terminal, im Projektordner:
```
sh tools/publish.sh
```
Das Skript
- baut beide Plattformen und lädt `codeberg.org/luro61/mediadb:<Version>` und `:latest` hoch,
- legt den Tag `v<Version>` an und pusht ihn,
- legt das Release auf Codeberg an: Titel und Text aus `CHANGELOG.md`, `docker-compose.homelab.yml` als Anhang.

Es bricht vorher ab, wenn noch etwas nicht committet oder nicht gepusht ist. Nur Tag und Release nachholen (Image ist schon oben): `sh tools/publish.sh release`. Danach in Dockhand beim Stack „mediadb“ *Pull* und *Redeploy*. Das Release ist dafür nicht nötig; es sorgt für den Hinweis „Neue Version … verfügbar“ in der App und für die Download-Links.

Das Image erscheint im Codeberg-Profil unter *Pakete*. Ist das Profil öffentlich, kann jeder das Image laden; das ist für die Veröffentlichung so gewollt.

## Bildschirmfotos der Anleitung erneuern (für den Projektbetreuer)

Die Bilder in `docs/bilder/` zeigen eine **erfundene Beispiel-Sammlung** mit farbigen Platzhaltern statt echter Cover. So ist nichts Privates darauf und keine fremden Bilder. Nach Änderungen an der Oberfläche lassen sie sich mit einem Befehl neu machen.

Einmalig (Google Chrome muss installiert sein):
```
python3 -m pip install -r requirements.txt playwright
```
Dann im Projektordner:
```
python3 tools/screenshots.py
```
Das Skript legt mit `tools/demo_data.py` eine frische Beispiel-Sammlung in einem Zwischenordner an, startet MediaDB damit, fotografiert die Seiten mit Chrome (unsichtbar) und räumt danach auf. Nur einzelne Bilder: `python3 tools/screenshots.py film serie`. Welche Seiten fotografiert werden, steht oben in `tools/screenshots.py`; eingebunden werden die Bilder in `docs/ANLEITUNG.md` mit `![Beschreibung](bilder/name.png)`.

## Home Assistant (geplant)

Ein Add-on ist ein kleines eigenes Repository mit einer Beschreibungsdatei, die auf das Docker-Image verweist. Die App ist darauf vorbereitet:
- Home Assistant zeigt Add-ons unter einer eigenen Unteradresse (Ingress). Die App erkennt das am Kopf `X-Ingress-Path` und passt alle Links an.
- Home Assistant übernimmt die Anmeldung, `APP_PASSWORD` bleibt dort leer.
- Das arm64-Image läuft auf dem Raspberry Pi.
