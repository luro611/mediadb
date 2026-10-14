# Betrieb im Homelab

MediaDB ist für das **eigene Heimnetz** gedacht: ein Haushalt, eine kleine Datenbank auf dem eigenen Rechner oder Server. Die App gehört nicht frei ins Internet (siehe unten).

## Varianten

| Wo | Datei | Bemerkung |
|---|---|---|
| Mac (OrbStack, Docker Desktop) | `docker-compose.yml` | liest Musik von `/Volumes` und aus dem Benutzerordner |
| Proxmox-LXC, Linux-Server, NAS | `docker-compose.homelab.yml` | Musikordner optional als `/music` |
| Home Assistant | geplant | als Add-on, siehe Roadmap |

## Proxmox: LXC mit Docker

1. In Proxmox einen LXC-Container anlegen, z. B. Debian 12, 1 CPU-Kern, 1 GB RAM, 8 GB Speicher (mehr bei vielen Covern).
   Unter *Optionen → Features* **nesting** und **keyctl** einschalten (nötig für Docker im LXC).
2. Im Container Docker installieren (offizielle Anleitung: docs.docker.com → Install → Debian) und `git` installieren:
   `apt install git`
3. Projekt holen und starten:
   ```
   git clone https://codeberg.org/BENUTZERNAME/mediadb.git
   cd mediadb
   cp .env.example .env        # MB_USER_AGENT mit eigener E-Mail-Adresse eintragen
   docker compose -f docker-compose.homelab.yml up -d --build
   ```
4. Im Browser `http://<IP-des-Containers>:8000` öffnen.

Musik einbinden: Den Musikordner (z. B. vom NAS) zuerst in den LXC einhängen (Proxmox: *Ressourcen → Hinzufügen → Einhängepunkt*), dann in `docker-compose.homelab.yml` die Zeile `- /pfad/zur/musik:/host/music:ro` aktivieren. Im Audio-Import erscheint er als `/music`.

## Neue Version einspielen

Mit Git (Quellcode von Codeberg):
```
cd mediadb
git pull
docker compose -f docker-compose.homelab.yml up -d --build
```

Mit fertigem Image (sobald es veröffentlicht ist; in `docker-compose.homelab.yml` die Zeile `image:` statt `build: .` verwenden):
```
docker compose -f docker-compose.homelab.yml pull
docker compose -f docker-compose.homelab.yml up -d
```

Der Ordner `data` (Datenbank, Cover, Einstellungen) bleibt bei beiden Wegen unberührt. Änderungen an der Datenbank (neue Spalten, Suchindex) macht die App beim Start selbst. Bei sehr großen Sammlungen kann der erste Start nach einem Update eine halbe Minute dauern, wenn der Suchindex neu aufgebaut wird.

## Sicherung

Alles Wichtige liegt in `data/`:
- `musik.db`: die Datenbank (früher `musikdb.db`, wird beim ersten Start automatisch umbenannt, eine Kopie landet in `data/backup/`)
- `covers/`: die Cover-Bilder
- `settings.json`, `secret.key`: Einstellungen und Schlüssel für die Anmeldung

Am sichersten: App kurz stoppen (`docker compose … down`), den Ordner `data` kopieren, wieder starten. Unter Proxmox reicht auch ein Backup/Snapshot des ganzen LXC.

## Zugriffsschutz

Ab Werk gilt:
- **Nur Heimnetz:** Anfragen von öffentlichen Internet-Adressen werden abgewiesen. Heimnetz (192.168.x.x, 10.x.x.x usw.), der eigene Rechner und VPNs wie Tailscale oder WireGuard mit privaten Adressen sind erlaubt.
- **Keine Anmeldung:** Für einen Nutzer im eigenen Heimnetz reicht das.

Einstellungen in `.env` (danach neu starten):

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
- Wer die App trotzdem öffentlich betreibt, tut das auf eigene Verantwortung. Die Lizenz schließt jede Gewährleistung und Haftung aus.

## Docker-Image auf Codeberg veröffentlichen (für den Projektbetreuer)

Codeberg hat eine eigene Registry für Docker-Images. Das Image wird für normale PCs/Server (amd64) **und** für Raspberry Pi und ARM-Macs (arm64) gebaut:

```
# einmalig: Zugangstoken in Codeberg anlegen (Einstellungen → Anwendungen, Recht "package: write")
docker login codeberg.org

# bauen und hochladen (Version aus der Datei VERSION)
V=$(cat VERSION)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t codeberg.org/BENUTZERNAME/mediadb:$V \
  -t codeberg.org/BENUTZERNAME/mediadb:latest \
  --push .
```

Danach erscheint das Image im Codeberg-Profil unter *Pakete*. Nutzer tragen in `docker-compose.homelab.yml` die Zeile `image: codeberg.org/BENUTZERNAME/mediadb:latest` ein.

## Home Assistant (geplant)

Ein Add-on ist ein kleines eigenes Repository mit einer Beschreibungsdatei, die auf das Docker-Image verweist. Die App ist darauf vorbereitet:
- Home Assistant zeigt Add-ons unter einer eigenen Unteradresse (Ingress). Die App erkennt das am Kopf `X-Ingress-Path` und passt alle Links an.
- Home Assistant übernimmt die Anmeldung, `APP_PASSWORD` bleibt dort leer.
- Das arm64-Image läuft auf dem Raspberry Pi.
