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
| TMDB (Filme) | Filmdaten, Poster, Hintergrundbilder | API mit eigenem kostenlosem Schlüssel, Bilder lokal gespeichert | Ja (nicht kommerziell) | Jeder Nutzer braucht einen eigenen Schlüssel; Quellenhinweis Pflicht; keine Bilder weitergeben |
| UPCitemdb (optional) | Produktname zu DVD-/Blu-ray-Barcodes | Testschnittstelle ohne Schlüssel, ca. 100 Abfragen pro Tag | Ja | Abschaltbar (`BARCODE_LOOKUP=0`) |
| Deutsche Nationalbibliothek | Buchdaten zu ISBN, Titel, Autor | SRU-Schnittstelle, ohne Anmeldung | Ja (Metadaten CC0) | Ja, kein Problem |
| Open Library | Buchdaten, Beschreibung, Cover | API ohne Schlüssel, gedrosselt, Cover lokal gespeichert | Ja | Hinweis auf Open Library erwünscht; keine Cover weitergeben |
| DNB-Inhaltstexte (Verlagstexte) | Klappentext zum Buch | Abruf über den Verweis im DNB-Datensatz, lokal gespeichert | Ja, zur privaten Nutzung | Texte gehören den Verlagen: nicht weitergeben |
| Wikipedia | Einleitung des Artikels zum Buch | REST-Schnittstelle, mit Link und Lizenzhinweis | Ja (CC BY-SA 4.0) | Namensnennung und Lizenzhinweis nötig (steht dabei) |
| MediathekViewWeb (optional) | Sendungen in den Mediatheken von ARD, ZDF, Arte & Co. | Öffentlicher Such-Feed, nur Anzeige und Link | Ja | Abschaltbar (`MEDIATHEK=0`); keine Downloads |
| Eigene Filmdateien | Dateiname, Jellyfin-/Kodi-.nfo, Technikdaten per ffprobe | Lokal gelesen, nichts wird übertragen | Ja | – |
| GitHub (optional) | Nummer der neuesten MediaDB-Version | Alle sechs Stunden (und auf Knopfdruck) die öffentliche Release-Liste lesen | Ja | Abschaltbar (`UPDATE_CHECK=0`); es wird nichts über dich oder die Sammlung gesendet |

## Was die App nach außen sendet

Nur **Suchbegriffe** (Interpret, Albumtitel, Filmtitel und Jahr, Buchtitel und Autor, ISBN, Barcode, ggf. MusicBrainz-/Discogs-/TMDB-/IMDb-Nummern) an die genannten Dienste. Die Datenbank, deine Dateinamen und deine Musikdateien verlassen den Rechner nicht. Außerdem wird die IP-Adresse deines Internetanschlusses von den Diensten wie bei jedem Webzugriff gesehen.

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
- **Cover nicht öffentlich ins Internet stellen und nicht im Repository (z. B. GitHub) ablegen.** Der Ordner `data/` ist deshalb in `.gitignore`.
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

### TMDB – The Movie Database (Filme und Serien)
- Quelle für Titel, Originaltitel, Handlung, Laufzeit, Genres, Regie, Darsteller, Altersfreigabe, Filmreihen, Trailer-Links, Poster und Hintergrundbilder; bei Serien zusätzlich Sender, Staffeln und der Episodenführer (Folgentitel, Inhalt, Ausstrahlungsdatum).
- Die API ist für **nicht kommerzielle Projekte kostenlos**; nötig ist ein eigener API-Schlüssel (themoviedb.org → Einstellungen → API). Bei der Beantragung bestätigst du die Nutzungsbedingungen von TMDB. **Jeder Nutzer der Software beantragt seinen eigenen Schlüssel**; der Schlüssel gehört in die eigene `.env` und nie ins Repository.
- **Pflicht laut [TMDB-FAQ](https://developer.themoviedb.org/docs/faq):** der Hinweis „This product uses the TMDB API but is not endorsed or certified by TMDB.“ (steht unten auf jeder Filmseite der App) und ein TMDB-Logo, das weniger auffällt als das eigene Logo. Erledigt seit 1.8.2: das offizielle Logo (`static/tmdb/`, Variante „Alt short“, 11 Pixel hoch) steht vor dem Hinweis.
- Poster (342 Pixel breit) und ein Hintergrundbild (780 Pixel) werden lokal in `data/film_images/` gespeichert, damit nicht bei jedem Seitenaufruf neu geladen wird. Die Bilder bleiben urheberrechtlich geschützt (Studios, Verleiher): **nicht weitergeben, nicht ins Repository**. Die Regeln zum Zwischenspeichern stehen in den TMDB-Nutzungsbedingungen, die du beim Beantragen des Schlüssels bestätigst; sie ließen sich bei der Erstellung nicht automatisch abrufen und sollten vor der Veröffentlichung von Hand gelesen werden.
- Auf der Trefferauswahl lädt dein Browser kleine Vorschaubilder direkt von `image.tmdb.org`; dabei sieht TMDB die IP-Adresse deines Browsers.

### JustWatch (Streamingdienste, über TMDB)
- Welche Streamingdienste einen Film oder eine Serie anbieten, liefert TMDB über die Schnittstelle „Watch Providers“; die Daten stammen von [JustWatch](https://www.justwatch.com/). TMDB verlangt dafür einen Hinweis auf JustWatch; er steht auf der Merkliste („Streaming-Angaben: JustWatch (über TMDB)“). Die Links „Wo ansehen?“ führen zur TMDB-Seite mit den Anbietern.
- Übertragen wird dabei nichts Zusätzliches: Es ist dieselbe TMDB-Abfrage wie für die Serie selbst. Gespeichert werden nur die Namen der Dienste.

### UPCitemdb (optional, Barcode von DVD/Blu-ray)
- TMDB kennt keine Barcodes. Deshalb fragt die App beim Scannen den Produktnamen bei der kostenlosen Testschnittstelle von [UPCitemdb](https://www.upcitemdb.com/) ab (etwa 100 Abfragen pro Tag, ohne Anmeldung) und sucht mit dem bereinigten Namen bei TMDB. Ergebnisse werden in `filme.db` bzw. `serien.db` zwischengespeichert, jeder Barcode wird also nur einmal abgefragt.
- Übertragen wird nur die Barcode-Nummer. Abschaltbar mit `BARCODE_LOOKUP=0`; dann werden nur Barcodes erkannt, die schon in der eigenen Sammlung stehen.
- Deutsche Ausgaben sind dort lückenhaft erfasst. Ein weiterer Kandidat ist [Disq](https://docs.disqapis.com/) (rund 400.000 DVD-/Blu-ray-Barcodes, derzeit kostenlose Testphase); er ließe sich später zusätzlich anbinden, sobald die Schnittstelle vollständig dokumentiert ist.

### Deutsche Nationalbibliothek (Bücher)
- Die [SRU-Schnittstelle](https://www.dnb.de/sru) der DNB liefert zu einer ISBN oder zu Titel und Autor die Katalogdaten (Titel, Autoren mit Rolle, Verlag, Jahr, Seiten, Reihe, Sachgruppe, Originaltitel). Sie ist **kostenlos und ohne Anmeldung** nutzbar; die Metadaten stehen unter **CC0** (gemeinfrei).
- Übertragen wird nur die ISBN bzw. der Suchbegriff. Gespeichert werden die Angaben in `buecher.db`, jede ISBN wird zwischengespeichert und nur einmal abgefragt.

- **Inhaltstexte:** Zu vielen neueren Büchern verweist der DNB-Datensatz auf einen „Inhaltstext“. Das sind Klappentexte der Verlage, die die DNB über den Branchendienst MVB bekommt und in ihrem Katalog öffentlich zeigt. Die Metadaten der DNB sind CC0, diese Texte aber nicht: Sie bleiben urheberrechtlich geschützt (Verlage). Die App ruft sie wie ein Katalogbesucher ab und speichert sie für die eigene Sammlung; **nicht weitergeben, nicht ins Repository**.

### Wikipedia (Bücher)
- Zu Büchern mit eigenem Wikipedia-Artikel lädt die App die Einleitung über die [REST-Schnittstelle](https://www.mediawiki.org/wiki/API:REST_API) (`/api/rest_v1/page/summary`). Gesendet werden nur Titel und Autor. Die Texte stehen unter [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.de); verlangt sind Namensnennung, Link und Lizenzhinweis. Alle drei stehen auf der Buchseite.
- Rezensionen selbst lädt die App nicht (Zeitungskritiken und Goodreads-Texte sind geschützt, Goodreads hat keine offene Schnittstelle mehr). Sie bietet nur Links, die eine Suche bei Perlentaucher, Goodreads oder einer Suchmaschine öffnen.

### Open Library (Bücher)
- [Open Library](https://openlibrary.org/) (Internet Archive) ergänzt Beschreibung, Themen, die **Bewertung** der Open-Library-Nutzer (`/works/…/ratings.json`) und vor allem **Cover**; für englischsprachige Bücher ist sie oft die bessere Quelle. Die Schnittstelle braucht keinen Schlüssel, die Daten sind frei nutzbar. Open Library bittet um einen Hinweis auf die Quelle; er steht unten auf jeder Bücherseite.
- Cover-Abrufe über die ISBN sind auf **100 Abrufe in 5 Minuten** begrenzt. Die App hält deshalb mindestens drei Sekunden Abstand zwischen Abrufen; beim Import langer Listen dauert es entsprechend.
- Cover werden lokal in `data/` gespeichert. Die Umschläge sind urheberrechtlich geschützt (Verlage, Illustratoren): **nicht weitergeben, nicht ins Repository**. Auf der Trefferauswahl lädt dein Browser kleine Vorschaubilder direkt von `covers.openlibrary.org`.

### Eigene E-Books und Hörbücher
- Gelesen werden die Angaben in den Dateien (EPUB/OPF, Calibre-`metadata.opf`, MOBI-Kopf, PDF-Info, Audio-Tags per `ffprobe`) und eingebettete Cover. Nichts davon verlässt den Rechner; gesucht wird nur mit ISBN bzw. Titel und Autor. Die Dateien werden nie verändert.

### MediathekViewWeb (Mediatheken, optional)
- [MediathekViewWeb](https://mediathekviewweb.de/) ist der Web-Ableger von [MediathekView](https://mediathekview.de/), freie Software (GPL-3.0), betrieben von Freiwilligen. Es durchsucht die Mediatheken der öffentlich-rechtlichen Sender. MediaDB nutzt den öffentlichen RSS-Feed, den die Seite zu jeder Suche anbietet. Gesendet werden nur Serien- bzw. Filmtitel; Ergebnisse werden sechs Stunden zwischengespeichert, Abfragen mit Abstand gestellt.
- MediaDB zeigt nur Titel, Sender, Datum und Dauer und verlinkt auf die Seite der Sendung in der Mediathek des Senders. **Es wird nichts heruntergeladen oder gespeichert.** Die Sendungen gehören den Sendern bzw. Produzenten.
- Zum Herunterladen selbst (in MediaDB bewusst nicht eingebaut): Für den rein privaten Gebrauch in Deutschland gilt das Herunterladen frei zugänglicher Mediathek-Inhalte ohne Kopierschutz nach verbreiteter Ansicht als Privatkopie (§ 53 UrhG); gerichtlich geklärt ist das nicht. Weitergabe, Veröffentlichung und das Umgehen von Kopierschutz sind nicht erlaubt; in Österreich und der Schweiz gelten andere Regeln.
- Abschaltbar unter Einstellungen oder mit `MEDIATHEK=0`.

### Eigene Film- und Seriendateien
- Gelesen werden Ordner- und Dateinamen, `.nfo`- bzw. `tvshow.nfo`-Dateien von Jellyfin/Kodi und mit `ffprobe` die Technikdaten (Auflösung, Codec, HDR, Tonspuren, Untertitel). Nichts davon verlässt den Rechner; an TMDB gehen nur der erkannte Titel und das Jahr bzw. die TMDB-/IMDb-Nummer.
- Die Dateien selbst werden nie verändert, verschoben oder gelöscht.

## Darf ich das alles privat nutzen?
Für die **eigene, private Sammlung** (Katalog deiner CDs und Dateien, lokal auf deinem Rechner, nicht öffentlich im Netz): im Rahmen der Bedingungen ja. Abfragen einzelner Daten und ihre Speicherung in der eigenen Datenbank sind üblich, die Hauptquelle MusicBrainz ist weitgehend gemeinfrei. Ausnahmen sind Grauzonen bei iTunes/Deezer-Covern (siehe oben); wer sie meiden will, setzt `COVER_WEB=0`.

## Darf ich die Software auf GitHub anbieten?
Die **Software** (dein Quellcode) darfst du unter einer freien Lizenz weitergeben. Dabei beachten:

1. **Keine Daten mitliefern:** keine Datenbank, keine Cover, keine `.env`, keinen Token. (`.gitignore` ist vorbereitet; vor dem Hochladen mit `git status` prüfen.)
2. **Jeder Nutzer ruft die Dienste selbst ab**, mit eigenem User-Agent und ggf. eigenem Token. Das ist die saubere Arbeitsteilung.
3. **Kein Betrieb als öffentlicher Dienst** mit fremden Nutzern auf einem Server ohne Rücksprache mit den Anbietern: die API-Bedingungen von Discogs, Deezer und Apple sind darauf nicht ausgelegt. Die App ist als lokales Einzelnutzer-Programm gedacht.
4. **Namen und Logos:** Die App nennt die Quellen und behauptet keine Verbindung zu ihnen (siehe Texte in der App). Keine Logos der Dienste verwenden.
5. **Lizenz der App:** Im Projekt liegt die GPL-3.0 als Vorschlag. Grund: Die Bibliothek `mutagen` steht unter GPL-2.0-oder-später; wer sie zusammen mit eigenem Code ausliefert (zum Beispiel in einem Docker-Image), sollte den eigenen Code ebenfalls unter einer kompatiblen GPL-Lizenz veröffentlichen. Du kannst eine andere Lizenz wählen, solltest dann aber `mutagen` ersetzen oder prüfen lassen.
6. **Schriftarten** in `static/fonts/` (Inter, Archivo, Geist Mono, Instrument Serif): nach meinem Kenntnisstand unter der SIL Open Font License 1.1. Vor der Veröffentlichung bitte die jeweiligen Lizenztexte beilegen oder die Schriften durch Systemschriften ersetzen.
7. Im Repository sollten **keine echten Daten aus deiner Sammlung** (Beispiel-Excel, Screenshots mit Covern) liegen. Die Bildschirmfotos der Anleitung (`docs/bilder/`) zeigen deshalb eine erfundene Beispiel-Sammlung mit selbst erzeugten, schlichten Platzhaltern statt Covern und Postern (`tools/demo_data.py`, `tools/screenshots.py`).
8. **Mit KI geschrieben:** Der Code von MediaDB ist mit Claude Code (KI) entstanden. GitHub erlaubt solche Projekte. Codeberg verbietet seit 2026 in seinen Nutzungsbedingungen Projekte, die überwiegend aus KI-geschriebenem Code bestehen; deshalb ist MediaDB im Oktober 2026 von Codeberg zu GitHub umgezogen.

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
| smbprotocol | NAS-Freigaben (SMB) direkt lesen | MIT |
| Markdown (Python-Markdown) | Anleitung als Hilfe in der App anzeigen | BSD-3-Clause |
| ffmpeg / ffprobe | Technikdaten von Filmdateien lesen (nur im Docker-Image, als eigenes Programm aufgerufen) | LGPL-2.1 / GPL-2.0 (je nach Bau, Debian-Paket) |

Dazu kommen Python selbst (PSF-Lizenz), Docker und SQLite (gemeinfrei). Nur für Betreuer und nicht im Image: Playwright (Apache-2.0) für die Bildschirmfotos der Anleitung.

## Datenschutz (DSGVO)
Die Sammlung ist eine private Liste. Die App überträgt keine persönlichen Daten außer Suchbegriffen und der IP-Adresse an die genannten Dienste. Erfasst du Daten Dritter (z. B. Leihgeber), gilt die übliche Zurückhaltung. Wer die App anderen anbietet, sollte in seiner README darauf hinweisen, dass die Dienste vom eigenen Rechner aus angesprochen werden.
