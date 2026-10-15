# Projektseite

Statische Seite ohne Cookies, Tracking oder externe Schriften.

- Quellen: `src/index.src.html` (Startseite, Deutsch und Englisch nebeneinander), `src/impressum.src.html` (Impressum und Datenschutz)
- Bauen: `python3 website/src/build.py` erzeugt `dist/` (zum Hochladen), `mediadb-website-<Version>.zip` und `preview.html` (nur zur Vorschau, lädt Google Fonts; nicht hochladen)
- Hochladen: den Inhalt von `dist/` (bzw. der Zip) per FTP in das Hauptverzeichnis der Subdomain
- Impressum und Datenschutz sind fest in `src/impressum.src.html` eingetragen; die ganze Seite (`dist/` bzw. die Zip) kann also immer komplett hochgeladen werden. Codeberg: https://codeberg.org/luro61/mediadb
