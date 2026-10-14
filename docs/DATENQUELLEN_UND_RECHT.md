# Datenquellen und Rechtliches

> **Wichtiger Hinweis:** Dies ist eine sorgfältige Zusammenstellung der Bedingungen, wie sie bei der Erstellung (Oktober 2026) auf den Webseiten der Anbieter standen. Es ist **keine Rechtsberatung**. Bedingungen ändern sich; vor einer Veröffentlichung bitte die verlinkten Originale prüfen.

## Kurzfassung

| Quelle | Wofür | Wie genutzt | Privat OK? | Bei Weitergabe der Software |
|---|---|---|---|---|
| MusicBrainz (Kerndaten) | Titel, Künstler, Barcodes, Tracklisten | Web-API, max. 1 Anfrage/s, eigener User-Agent | Ja (CC0) | Ja, kein Problem |
| MusicBrainz (Tags/Genres, Annotationen) | Genre-Feld | Web-API | Ja | Nur nicht-kommerziell, mit Namensnennung (CC BY-NC-SA 3.0) |
| Cover Art Archive | Cover | Bilder werden einzeln geladen und lokal gespeichert | Ja, Rechte liegen bei Künstlern/Labels | Keine Bilder weitergeben |
| Discogs (optional) | Titel, Label, Tracklisten, Cover | API, nur auf Knopfdruck, mit Bestätigung | Ja | Namensnennung nötig; Software nicht im Namen von Discogs |
| iTunes Search API (optional) | Cover-Ausweichquelle | Suche, Bild wird gespeichert | Grauzone | Abschaltbar (`COVER_WEB=0`) |
| Deezer API (optional) | Cover-Ausweichquelle | Suche, Bild wird gespeichert | Grauzone (Nutzung „nicht-kommerziell, privat“) | Abschaltbar (`COVER_WEB=0`) |
| Eigene Musikdateien | Tags, eingebettete Cover | Lokal gelesen, nichts wird übertragen | Ja | – |

## Was die App nach außen sendet

Nur **Suchbegriffe** (Interpret, Albumtitel, Barcode, ggf. MusicBrainz-/Discogs-Nummern) an die genannten Dienste. Die Datenbank, deine Dateinamen und deine Musikdateien verlassen den Rechner nicht. Außerdem wird die IP-Adresse deines Internetanschlusses von den Diensten wie bei jedem Webzugriff gesehen.

## Die Dienste im Einzelnen

### MusicBrainz (Hauptquelle)
- Die **Kerndaten** (Künstler, Alben, Ausgaben, Barcodes, Titel) stehen unter **CC0**, sind also frei nutzbar, auch kommerziell und ohne Namensnennung.
- **Ergänzende Daten** (nutzererzeugte Annotationen, **Tags und damit auch Genre-Zuordnungen**, Bewertungen) stehen unter **CC BY-NC-SA 3.0**: nicht-kommerzielle Nutzung mit Nennung von MusicBrainz; abgeleitete Werke unter gleicher Lizenz.
- Für die Web-API verlangt MusicBrainz höchstens **eine Anfrage pro Sekunde** und einen **aussagekräftigen User-Agent** mit Kontaktadresse. Die App hält beides ein; die Adresse steht in der Datei `.env` bei `MB_USER_AGENT`. **Jeder Nutzer muss dort seine eigene E-Mail-Adresse eintragen.**
- Für Erreichbarkeit, Zuverlässigkeit und Wartung gibt MusicBrainz keine Garantie. Für kommerziellen Einsatz bietet die MetaBrainz Foundation Lizenzen an.
- Quelle: [MusicBrainz Database](https://musicbrainz.readthedocs.io/en/latest/musicbrainz_database/index.html)

### Cover Art Archive
- Betrieben von MusicBrainz und dem Internet Archive. Die Bilder sind meist Fotos/Scans der Originalhüllen und bleiben **urheberrechtlich geschützt** (Rechte bei Künstlern bzw. Labels). Die Seite bittet: „Be respectful of the rights of the artists and labels.“
- Die App lädt Cover nur für Einträge, die **du** angelegt hast, und speichert sie lokal in `data/covers/` zur Anzeige in deiner eigenen Sammlung. Das entspricht der üblichen privaten Nutzung (Vergleich: Cover im eigenen Musikprogramm).
- **Cover nicht öffentlich ins Internet stellen und nicht im Repository (z. B. Codeberg) ablegen.** Der Ordner `data/` ist deshalb in `.gitignore`.
- Quelle: [Cover Art Archive](https://musicbrainz.org/doc/Cover_Art_Archive)

### Discogs (optional)
- Nur wenn du auf „Ähnliche Ausgabe suchen“ gehst und einen Discogs-Link einfügst (oder, mit Token, die Suche nutzt). Nichts passiert automatisch.
- Laut den [API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593): Die „CC0 Data“ (z. B. Titel, Tracklisten, Künstler-/Labelangaben) ist gemeinfrei; „Restricted Data“ (u. a. Nutzerdaten, Marketplace-Daten, bestimmte Bilder) darf nur eingeschränkt genutzt werden. Kommerzielle Nutzung ist „generally permitted“, Discogs kann sie aber untersagen.
- **Pflichttexte** (stehen auf der Vorschauseite): „Data provided by Discogs.“ mit Link auf die Release-Seite sowie „This application uses Discogs’ API but is not affiliated with, sponsored or endorsed by Discogs.“
- Es gibt Rate-Limits (ohne Token deutlich enger). Limits dürfen nicht durch zusätzliche API-Schlüssel umgangen werden.
- Die Bedingungen sagen auch, Inhalte dürften nur so lange gespeichert werden, wie es für den Dienst nötig ist. Die App übernimmt nur die frei nutzbaren Stammdaten (Titel, Label, Jahr, Tracklisten) dauerhaft in deine eigene Datenbank; **Discogs-Bilder werden nur auf deine ausdrückliche Bestätigung** und nur zur privaten Anzeige gespeichert. Ohne diesen Aufruf bleibt die Discogs-Anbindung ungenutzt.
- Der persönliche Token gehört in die `.env` und **nie** ins Repository.

### iTunes Search API / Apple (optional, Cover-Ausweichquelle)
- Apple beschreibt die Suche als Hilfe, um Inhalte des Stores zu bewerben. Album-Artwork gilt als „Promotional Content“ und darf nach Apples Bedingungen nur **zur Bewerbung von Store-Inhalten** (mit Badge) verwendet werden, nicht „for entertainment purposes“. Das Limit liegt bei etwa 20 Anfragen pro Minute.
- Die private Archivnutzung für die eigene CD-Sammlung ist davon streng genommen **nicht gedeckt** (Grauzone, geringes praktisches Risiko, aber nicht gesichert).
- Quelle: [Search API Dokumentation](https://performance-partners.apple.com/resources/documentation/itunes-store-web-service-search-api/)

### Deezer API (optional, Cover-Ausweichquelle)
- Die [Nutzungsbedingungen](https://developers.deezer.com/termsofuse) erlauben die Nutzung „strictly limited for a non-commercial purpose and in a non-commercial environment“, Inhalte nur für „strictly private use within a family scope“. Eine ausdrückliche Regel zum Speichern von Bildern gibt es nicht. Deezer darf Zugänge jederzeit ändern.
- Privat und unkommerziell also im Rahmen; **für Weitergabe oder Gewerbliches ungeeignet**.

### Eigene Musikdateien
- Die Tags (Interpret, Album, Titel, Genre, Jahr) und eingebettete Cover werden **nur lokal** gelesen. Die Bibliothek `mutagen` ist freie Software.

## Darf ich das alles privat nutzen?
Für die **eigene, private Sammlung** (Katalog deiner CDs und Dateien, lokal auf deinem Rechner, nicht öffentlich im Netz): im Rahmen der Bedingungen ja. Abfragen einzelner Daten und ihre Speicherung in der eigenen Datenbank sind üblich, die Hauptquelle MusicBrainz ist weitgehend gemeinfrei. Ausnahmen sind Grauzonen bei iTunes/Deezer-Covern (siehe oben); wer sie meiden will, setzt `COVER_WEB=0`.

## Darf ich die Software auf Codeberg anbieten?
Die **Software** (dein Quellcode) darfst du unter einer freien Lizenz weitergeben. Dabei beachten:

1. **Keine Daten mitliefern:** keine Datenbank, keine Cover, keine `.env`, keinen Token. (`.gitignore` ist vorbereitet; vor dem Hochladen mit `git status` prüfen.)
2. **Jeder Nutzer ruft die Dienste selbst ab**, mit eigenem User-Agent und ggf. eigenem Token. Das ist die saubere Arbeitsteilung.
3. **Kein Betrieb als öffentlicher Dienst** mit fremden Nutzern auf einem Server ohne Rücksprache mit den Anbietern: die API-Bedingungen von Discogs, Deezer und Apple sind darauf nicht ausgelegt. Die App ist als lokales Einzelnutzer-Programm gedacht.
4. **Namen und Logos:** Die App nennt die Quellen und behauptet keine Verbindung zu ihnen (siehe Texte in der App). Keine Logos der Dienste verwenden.
5. **Lizenz der App:** Im Projekt liegt die GPL-3.0 als Vorschlag. Grund: Die Bibliothek `mutagen` steht unter GPL-2.0-oder-später; wer sie zusammen mit eigenem Code ausliefert (zum Beispiel in einem Docker-Image), sollte den eigenen Code ebenfalls unter einer kompatiblen GPL-Lizenz veröffentlichen. Du kannst eine andere Lizenz wählen, solltest dann aber `mutagen` ersetzen oder prüfen lassen.
6. **Schriftarten** in `static/fonts/` (Inter, Archivo, Geist Mono, Instrument Serif): nach meinem Kenntnisstand unter der SIL Open Font License 1.1. Vor der Veröffentlichung bitte die jeweiligen Lizenztexte beilegen oder die Schriften durch Systemschriften ersetzen.
7. Im Repository sollten **keine echten Daten aus deiner Sammlung** (Beispiel-Excel, Screenshots mit Covern) liegen.

## Verwendete Programmbibliotheken
Alle werden beim Bau des Docker-Images per `pip` installiert und nicht mitgeliefert (Lizenzangaben nach meinem Kenntnisstand, bitte vor Veröffentlichung gegenprüfen):

| Bibliothek | Zweck | Lizenz |
|---|---|---|
| FastAPI | Web-Framework | MIT |
| Uvicorn | Webserver | BSD-3-Clause |
| python-multipart | Datei-/Formular-Upload | Apache-2.0 |
| Jinja2 | Seitenvorlagen | BSD-3-Clause |
| SQLAlchemy | Datenbank | MIT |
| openpyxl | Excel lesen/schreiben | MIT |
| requests | Web-Abfragen | Apache-2.0 |
| mutagen | Audio-Tags | GPL-2.0-oder-später |

Dazu kommen Python selbst (PSF-Lizenz), Docker und SQLite (gemeinfrei).

## Datenschutz (DSGVO)
Die Sammlung ist eine private Liste. Die App überträgt keine persönlichen Daten außer Suchbegriffen und der IP-Adresse an die genannten Dienste. Erfasst du Daten Dritter (z. B. Leihgeber), gilt die übliche Zurückhaltung. Wer die App anderen anbietet, sollte in seiner README darauf hinweisen, dass die Dienste vom eigenen Rechner aus angesprochen werden.
