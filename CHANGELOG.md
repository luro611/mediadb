# Änderungen

## MediaDB 1.17.0 – Bereiche ein- und ausschalten
- **Neuer Abschnitt „Bereiche“ in den Einstellungen:** Musik, Filme, Serien und Bücher lassen sich einzeln ausschalten, z. B. für alle, die nur Bücher oder nur Filme und Serien verwalten.
- **Ausgeschaltet heißt ausgeblendet:** Der Bereich verschwindet aus der Leiste, der Startseite, der Suche und aus „Hinzufügen“. Seine Hintergrundarbeiten ruhen, etwa die tägliche Serien-Aktualisierung. Einstellungen, die nur diesen Bereich betreffen (z. B. der TMDB-Schlüssel), treten zurück. Alte Lesezeichen zeigen einen freundlichen Hinweis.
- **Es geht nichts verloren:** Die Datenbank des Bereichs wird nicht angefasst. Nach dem Einschalten ist alles sofort wieder da, samt gesehen, Bewertungen und Listen. Mindestens ein Bereich bleibt an.
- Die Merkliste erscheint, solange Filme oder Serien an sind; „Verliehen“ zeigt weiterhin alles, was verliehen ist.
- **Willkommensseite:** Bei einer neuen, leeren Installation fragt MediaDB beim ersten Start nach der Sprache und danach, was verwaltet werden soll. Bestehende Installationen sehen diese Seite nicht; dort bleiben alle Bereiche an.
- Anleitung und Bildschirmfotos ergänzt.

## MediaDB 1.16.0 – Anleitung mit Bildschirmfotos
- **15 Bildschirmfotos in der Anleitung:** Startseite, Musik, Filme, Serien, „Was fehlt?“, Bücher, Buchreihen, Merkliste, Verliehen, Hinzufügen und die Einstellungen für Sprache und Farben. Jedes Bild hat eine Unterschrift; ein Klick öffnet es in voller Größe.
- Die Fotos zeigen eine **erfundene Beispiel-Sammlung** mit farbigen Platzhaltern statt echter Cover, also nichts Privates und keine fremden Bilder.
- **Hilfe in eigenem Fenster:** Das ? oben, „Anleitung“ unten und der Link in den Einstellungen öffnen die Hilfe in einem eigenen Fenster. So kannst du MediaDB bedienen und gleichzeitig nachlesen. Ein weiterer Klick holt dasselbe Fenster wieder nach vorn.
- Die Anleitung erklärt jetzt auch die **Farben** in den Einstellungen.
- Für Betreuer: `tools/demo_data.py` legt die Beispiel-Sammlung an, `tools/screenshots.py` macht alle Fotos neu (siehe „Betrieb im Homelab“).

## MediaDB 1.15.0 – Hilfe in der App
- **Die Anleitung ist jetzt in MediaDB selbst:** über das neue **?** oben in der Leiste, den Link „Anleitung“ unten auf jeder Seite oder „Was die einzelnen Einstellungen bedeuten …“ in den Einstellungen. Sie passt immer zur installierten Version und funktioniert auch ohne Internet.
- Neben der Anleitung gibt es **Betrieb im Homelab**, **Datenquellen und Rechtliches** und **Änderungen** (diese Liste) als eigene Reiter. Links zwischen den Texten bleiben in der App.
- Das **Inhaltsverzeichnis** der Anleitung ist anklickbar.
- Die Hilfe gibt es bisher nur auf Deutsch; in den anderen Sprachen steht ein Hinweis darüber.

## MediaDB 1.14.0 – Eigene Farben
- **Neuer Bereich „Farben“ in den Einstellungen:** Hintergrund, Kästen und Eingabefelder, Schrift, Nebentext, Akzent (Überschriften, Knöpfe) und Links lassen sich frei wählen, getrennt für das helle und das dunkle Farbschema. Jede Änderung ist sofort als Vorschau zu sehen; gespeichert wird erst mit „Farben speichern“. Geänderte Farben sind markiert.
- **„Auf Ursprung zurücksetzen“** stellt mit einem Klick alle ursprünglichen Farben wieder her. Die Vorgaben stehen fest im Programm (static/style.css) und werden nie überschrieben; gespeichert werden nur deine Abweichungen (data/settings.json).

## MediaDB 1.13.2 – Anleitung auf dem neuesten Stand
- **Anleitung überarbeitet** (`docs/ANLEITUNG.md`): mit allen Funktionen bis 1.13, also Startseite, Als Nächstes, Ansichten Kacheln/Liste/Text, Statusanzeige, Merkliste, NAS-Freigaben, Musik vom Mac, Sichern und Updates mit Dockhand. Veraltetes korrigiert: Installation im Homelab, Einstellungen in der App statt in `.env`, Fehlersuche.
- **Link „Anleitung“** unten auf jeder Seite neben der Versionsnummer und in den Einstellungen. Er öffnet die Anleitung auf Codeberg.

## MediaDB 1.13.1 – Sprache gut sichtbar in den Einstellungen
- **Eigener Bereich „Sprache der Oberfläche“** ganz oben in den Einstellungen. Bisher steckte er klein in einer schmalen Kachel weit unten, und die Häkchen waren kaum zu sehen.
- **Zwei getrennte Teile:** links die **Hauptsprache** mit eigenem Speichern-Knopf, rechts der **Umschalter oben in der Leiste** mit großen Knöpfen zum Anhaken und eigenem Speichern-Knopf.
- **Website:** fünf Sprachen, dazu neue Abschnitte zu „Als Nächstes“, den Ansichten Kacheln/Liste/Text und der neuen Startseite.

## MediaDB 1.13.0 – Italienisch und Spracheinstellungen
- **Italienisch:** Die ganze Oberfläche gibt es jetzt auch auf Italiano. Als Datensprache für Filme und Serien stehen Italienisch (Italien) und Italienisch (Schweiz) zur Auswahl.
- **Sprache in den Einstellungen:** Unter „Sprache der Oberfläche“ wählst du die Hauptsprache. Dort hakst du auch die Sprachen an, die oben in der Leiste zum Umschalten erscheinen sollen. Das ist praktisch, wenn im Haushalt mehrere Sprachen gesprochen werden.
- **Umschalter oben nur noch auf Wunsch:** Ohne Auswahl (oder mit nur einer Sprache) ist die Leiste oben aufgeräumt und zeigt keine DE/EN/FR/ES-Knöpfe mehr.
- **Handy:** In der Serienliste ist das Auswahlfeld für Streamingdienste nicht mehr breiter als der Bildschirm.

## MediaDB 1.12.0 – Aufgeräumte Startseite und Text-Ansicht
- **Startseite aufgeräumt:** Statt acht Auswahllisten gibt es drei Reihen, in denen alle Bereiche gemischt sind: **„Als Nächstes“** (ist offen, in der Reihenfolge des Vormerkens), **„Gerade dabei“** (angefangene Serien und Bücher, die du gerade liest) und **„Zuletzt hinzugefügt“**. Ein kleines Schild zeigt, ob es eine CD, ein Film, eine Serie oder ein Buch ist.
- „Top 10: Muss ich sehen“ und „Zuletzt gesehen“ findest du weiterhin als Reiter unter **Filme**.
- **Dritte Ansicht „Text“** im Umschalter: eine Zeile pro Eintrag, ganz ohne Bilder. Bei Musik zeigen Tabelle und Interpretenliste dann keine Cover. Die Wahl merkt sich der Browser wie bisher für jeden Bereich.
- **Größeres Zahnrad** für die Einstellungen oben in der Leiste.

## MediaDB 1.11.0 – Als Nächstes
- **Neuer Knopf „☆ Als Nächstes vormerken“** auf jeder CD-, Film-, Serien- und Buchseite: für das, was du als Nächstes hören, sehen oder lesen möchtest. Ein zweiter Klick nimmt es wieder herunter.
- **Neuer Reiter „Als Nächstes“** in Musik, Filme, Serien und Bücher, mit Anzahl. Die Einträge stehen in der Reihenfolge, in der du sie vorgemerkt hast. Ein ★ auf Kacheln und Zeilen zeigt vorgemerkte Einträge auch in den anderen Listen.
- **Räumt sich selbst auf:** Ein Film fällt heraus, sobald du ihn als gesehen markierst, ein Buch, sobald es gelesen ist, und eine Serie, sobald keine ausgestrahlte Folge mehr offen ist. CDs nimmst du selbst herunter.
- Auf der Serienseite heißt die nächste ungesehene Folge jetzt „Weiter mit:“ statt „Als Nächstes:“, damit nichts verwechselt wird.

## MediaDB 1.10.0 – Kacheln oder Liste
- **Umschalter „Kacheln / Liste“** oben rechts über jeder Liste: Musik, Filme, Serien und Bücher, dazu Personen-, Autoren- und Buchreihen-Seiten.
- **Listenansicht** für Filme, Serien und Bücher: eine schmale Zeile pro Eintrag mit kleinem Bild, Titel, Jahr, Format, Bewertung, Gesehen/Gelesen und Fortschritt. So passt viel mehr auf eine Seite.
- **Kachelansicht für Musik:** Interpreten und CDs als Cover-Raster. Die bisherige Tabelle bleibt die Voreinstellung.
- Die Wahl merkt sich der Browser für jeden Bereich getrennt.

## MediaDB 1.9.4 – Update-Hinweis und NAS-Status in den Einstellungen
- **Neue Version?** In den Einstellungen steht jetzt, welche Version läuft, welche die neueste auf Codeberg ist und wann zuletzt nachgesehen wurde, dazu der Knopf **„Jetzt nach neuer Version suchen“**.
- MediaDB sieht **alle sechs Stunden** nach (bisher einmal am Tag). Der Hinweis „Neue Version … verfügbar“ unten auf der Seite kam deshalb bisher bis zu einen Tag zu spät.
- **NAS-Freigaben in den Einstellungen:** Neben jeder NAS steht wie in der Ordnerauswahl, ob sie gerade erreichbar ist.
- **Verbindung prüfen** nennt die NAS: „NAS: Musik · Verbindung klappt: …“.

## MediaDB 1.9.3 – NAS, die nicht immer an ist
- **Punkt in der Ordnerauswahl:** Neben jeder „NAS: …“ steht, ob sie gerade erreichbar ist (grün) oder aus (orange). Die Liste erscheint sofort, die NAS werden danach im Hintergrund gefragt.
- **Klare Meldung:** Wer eine ausgeschaltete NAS öffnet, liest jetzt „Die NAS … ist gerade nicht erreichbar. Ist sie eingeschaltet?“ statt „Ordner nicht gefunden oder nicht freigegeben“.
- **Hinweis nach dem Einlesen:** Konnten Ordner nicht gelesen werden (NAS zwischendurch aus, fehlende Leserechte), steht über der Vorschau, wie viele und welche. Bisher fehlten sie stillschweigend. Gilt für Musik, Filme, Serien und Bücher.
- **Schneller wieder da:** Ist eine NAS nach dem Ausschalten wieder an, nutzt MediaDB sie sofort, statt bis zu einer Minute weiter „nicht erreichbar“ zu melden.
- Bereits eingelesene Einträge bleiben wie bisher erhalten, wenn die NAS aus ist.

## MediaDB 1.9.2 – NAS-Verbindung prüfen
- **„Verbindung prüfen“ direkt im Formular:** prüft die eingetragenen Angaben, ohne sie zu speichern. Die Prüfung geht Schritt für Schritt vor und sagt genau, woran es hängt: Name der NAS nicht gefunden (Namen mit `.local` funktionieren im Docker-Container nicht, dann die IP-Adresse eintragen), NAS antwortet nicht, SMB ausgeschaltet, nur das alte SMB1, Benutzer unbekannt, Passwort falsch, Freigabe oder Unterordner falsch. Darunter steht eine technische Angabe für die Fehlersuche.
- **Zugang übernehmen:** Bei einer weiteren Freigabe lässt sich eine schon eingerichtete NAS auswählen; Adresse, Benutzer und Passwort werden übernommen.
- Die ganze Adresse (`smb://192.168.1.20/Musik/Alben` oder `\\192.168.1.20\Musik\Alben`) darf ins Feld NAS-Adresse; „Musik/Alben“ im Feld Freigabe wird in Freigabe und Unterordner aufgeteilt (bisher ging der Unterordner verloren).
- Benutzer und Passwort sind jetzt Pflicht: Ein Gastzugang ohne Passwort scheiterte bisher immer mit der irreführenden Meldung „Anmeldung abgelehnt“.
- Nach einem Neustart der NAS wird die alte Verbindung verworfen und neu verbunden.

## MediaDB 1.9.1 – Hinweis auf neue Versionen
- **Neue Version verfügbar:** MediaDB schaut einmal am Tag bei Codeberg nach dem neuesten Release. Gibt es ein neueres, steht unten auf jeder Seite neben der Versionsnummer „Neue Version … verfügbar“, mit Link zu den Neuerungen. Aktualisieren wie gewohnt in Dockhand mit *Pull* und *Redeploy*.
- Abgefragt wird nur die öffentliche Release-Liste, ohne Angaben zu dir oder deiner Sammlung. Abschaltbar unter Einstellungen → „Dienste und Automatik“ (`UPDATE_CHECK=0`).

## MediaDB 1.9.0 – NAS-Freigaben direkt lesen
- **Einstellungen → NAS-Freigaben:** MediaDB liest Musik, Filme, Serien und Bücher direkt von der NAS über SMB (wie Finder oder Windows-Explorer). Eintragen: Name, NAS-Adresse, Freigabe, optional Unterordner, Benutzer und Passwort; „Verbindung prüfen“ sagt verständlich, was nicht stimmt (Anmeldung, Name der Freigabe, Unterordner, NAS nicht erreichbar).
- **Kein Einhängen mehr nötig**, auch nicht im Proxmox-LXC: Dort lassen sich Netzwerkfreigaben weder im LXC noch im Container einhängen; der Umweg über den Proxmox-Host entfällt.
- Jede Freigabe erscheint in der Ordnerauswahl von Audio-, Film-, Serien- und Bücher-Import als **„NAS: Name“**. Tags, Cover, .nfo-Dateien, E-Books und Technikdaten (ffprobe) werden direkt von der NAS gelesen; bei Filmen nur die Teile, die ffprobe braucht, nicht die ganze Datei.
- Es wird nur gelesen. Ist die NAS aus, wartet MediaDB höchstens einmal kurz und versucht es nach einer Minute wieder.
- Das Passwort steht in `data/settings.json` (nur für den Besitzer lesbar) und wird auf der Seite nie angezeigt. Empfehlung: eigener NAS-Benutzer mit Leserechten.

## MediaDB 1.8.2 – Version und TMDB-Logo
- **Versionsnummer** unten auf jeder Seite („MediaDB 1.8.2“), damit man sieht, welcher Stand läuft (z. B. nach einem Update im LXC).
- **Offizielles TMDB-Logo** vor dem Quellenhinweis bei Filmen, Serien und Merkliste (Pflicht laut TMDB). Alle Logo-Varianten liegen in `static/tmdb/`.

## MediaDB 1.8.1 – Betrieb im Proxmox-LXC
- **Fertiges Docker-Image** von Codeberg: `codeberg.org/luro61/mediadb` (für amd64 und arm64). `docker-compose.homelab.yml` nutzt es direkt und lässt sich unverändert als Stack in Dockhand oder Portainer einfügen; Updates dort mit „Pull“ und „Redeploy“.
- **Alles in einem Ordner** auf dem Server: `/opt/mediadb/data` für die Daten, `/opt/mediadb/medien/musik`, `…/filme`, `…/serien`, `…/buecher` für Mediendateien (nur lesend). Keine `.env` mehr nötig; die Zugriffseinstellungen stehen in der Compose-Datei.
- **Bücher-Import:** neuer Ordner `/books` im Homelab.
- Zeitzone im Container (`TZ`, Paket tzdata), damit Daten und Uhrzeiten stimmen.
- `tools/publish.sh`: baut das Image auf dem Mac und lädt es zu Codeberg hoch.
- `docs/BETRIEB.md`: Größe des LXC, Einrichtung mit Dockhand, Umzug des Ordners `data` vom Mac in den LXC.

## MediaDB 1.8.0 – Mediatheken
- **In der Mediathek:** Auf jeder Serien- und Filmseite sucht MediaDB in den Mediatheken der öffentlich-rechtlichen Sender (ARD, ZDF, Arte, 3sat, ORF, SRF und weitere) und zeigt, was dort gerade abrufbar ist: Sender, Sendedatum, Länge und ein Link zur Sendung in der Mediathek. Die Suche läuft im Hintergrund, die Seite wartet nicht darauf.
- **Bei Serien** werden die Folgen dem Episodenführer zugeordnet (z. B. „S05E08“, auch aus Angaben wie „(3/8)“ mit „Staffel 2“ im Thema) und markiert: **„fehlt dir“** oder „vorhanden“. Oben steht, wie viele fehlende Folgen es gerade in einer Mediathek gibt.
- **Merkliste:** Abschnitt „Jetzt in der Mediathek“ für vorgemerkte Filme und Serien.
- Fassungen mit Audiodeskription, Gebärdensprache usw. werden zusammengefasst; Trailer, Making-of und kurze Clips weggelassen. Bei Filmen zählt nur ein genau passender Titel ab 45 Minuten, und das Jahr muss passen (keine Neuverfilmung).
- Quelle ist MediathekViewWeb (freie Software rund um MediathekView). MediaDB zeigt nur Links; heruntergeladen wird nichts. Abschaltbar unter Einstellungen → „Dienste und Automatik“ (`MEDIATHEK=0`).

## MediaDB 1.7.0 – Verliehen an …
- Neue Seite **Verliehen** (Menü „Verliehen“) für alle Bereiche gemeinsam, mit eigener kleiner Datenbank (`data/verleih.db`).
- **Nur Physisches** lässt sich verleihen: CDs (Besitz „CD“ oder „CD + digital“), DVDs, Blu-rays und 4K-Discs von Filmen, Serien-Boxen, gedruckte Bücher und Hörbuch-CDs. Dateien, rein digitale Alben und E-Books bekommen den Hinweis „Nur digital vorhanden“.
- Auf jeder Detailseite (CD, Film, Serie, Buch) ein Kasten **„Verleihen …“**: an wen (bekannte Namen werden vorgeschlagen), wann (heute vorbelegt; Feld leeren, wenn unbekannt, oder nur das Jahr), optional „zurück bis“ und Notiz, bei mehreren Exemplaren die Auswahl (z. B. DVD oder Blu-ray). Ist etwas verliehen, steht dort „Verliehen an Peter am 01.03.2019 (seit 7 Jahren)“ mit dem Knopf **Zurückbekommen**.
- **Viele alte Verleihungen schnell nachtragen:** Auf der Seite „Verliehen“ einen Namen eintragen, in der ganzen Sammlung suchen und bei jedem Treffer „An … verleihen“ klicken.
- Übersicht nach Personen mit Filter nach Bereich, überfällige Rückgaben hervorgehoben, „Zurückbekommen“ mit Verlauf, **Als Text zum Kopieren** (z. B. für eine Nachricht). Personenseite mit allem, was jemand gerade hat und früher hatte, „Alles zurückbekommen“ und Umbenennen (gleiche Namen werden zusammengeführt).
- In den Übersichten von Musik, Filmen, Serien und Büchern sind verliehene Einträge markiert; auf der Startseite steht „Verliehen: x Sachen bei y Personen“; die Suche findet auch Namen.

## MediaDB 1.6.1 – Zusammenfassungen und Bewertungen bei Büchern
- **Inhalt:** Zu vielen neueren deutschen Büchern holt die App den **Verlagstext (Klappentext)**, den die Deutsche Nationalbibliothek bereitstellt; sonst die Beschreibung von Open Library. Unter dem Text steht die Quelle. Ein Link führt zum **Inhaltsverzeichnis (PDF)** der DNB, wenn es eines gibt.
- **Wikipedia:** Gibt es zum Buch einen Wikipedia-Artikel, steht dessen Einleitung auf der Buchseite, mit Link „Weiterlesen bei Wikipedia“ und Lizenzhinweis (CC BY-SA 4.0). Gesucht wird in der Datensprache, sonst in der englischen Wikipedia. Passt ein Artikel nicht, lässt er sich entfernen.
- **Bewertungen und Rezensionen:** Durchschnitt der Bewertungen bei Open Library (z. B. „4,2 von 5 Sternen (12 Stimmen)“) und Links zur Suche nach Rezensionen bei Perlentaucher, Goodreads und im Web.
- Wird nach dem Speichern und nach einem Import automatisch im Hintergrund geladen (sichtbar in der Statusanzeige), für schon vorhandene Bücher kurz nach dem Start. Auf der Buchseite: „Zusammenfassung und Bewertungen neu laden“.
- Projektseite: neuer Abschnitt „Willkommen“ mit der Geschichte des Projekts.

## MediaDB 1.6.0 – Bücher
- Neuer Bereich **Bücher** mit eigener Datenbank (`data/buecher.db`), im Menü und als vierte Kachel auf der Startseite.
- **Hinzufügen:** per **ISBN** (Strichcode scannen oder eintippen, 10 oder 13 Stellen), über **Titel und Autor** oder **von Hand**. Die Daten kommen von der **Deutschen Nationalbibliothek** (kostenlos, ohne Anmeldung) und von **Open Library** (Ergänzungen, Beschreibung, Cover). Je nach Datensprache wird zuerst die eine oder die andere Quelle gefragt.
- **Bücher-Import:** Ordner mit **E-Books** (EPUB, PDF, MOBI/AZW3, Calibre-Bibliotheken) und **Hörbüchern** (M4B, Ordner mit MP3/M4A, auch mit CD-Unterordnern) einlesen; Titel, Autor, Sprecher, ISBN und Cover werden aus den Dateien gelesen. Für viele gedruckte Bücher auf einmal: eine **ISBN-Liste** (z. B. nacheinander gescannt) oder eine **CSV-/Excel-Tabelle** mit Spalten wie ISBN, Titel, Autor, Format, Gelesen, Bewertung, Notiz. Vorschau wie bei Filmen und Serien, gespeichert wird erst mit „Übernehmen“.
- **Exemplare:** gebunden, Taschenbuch, E-Book, Hörbuch oder anderes; ein Buch kann mehrere haben (z. B. Taschenbuch und Hörbuch).
- **Lesen:** „Lese ich gerade“, „Gelesen“ mit Datum (oder nur Jahr), eigene Bewertung 1–10, Notiz. Startseite: „Lese ich gerade“ und „Zuletzt hinzugefügt: Bücher“.
- **Übersicht:** nach Autor, Titel, Jahr, Bewertung oder Hinzufügedatum, A–Z-Leiste, Filter für Genre, Format und Sprache; Ansichten Ungelesen, Lese ich gerade, Gelesen, Lieblinge, Zuletzt gelesen, Zuletzt hinzugefügt, E-Books, Hörbücher.
- **Autoren** mit eigener Seite (alle Bücher in der Sammlung), Übersetzer, Illustratoren und Sprecher werden mit angezeigt. **Buchreihen** mit Bandnummern und Lücken („Band 3 fehlt“).
- **Titelbild ändern:** aus Open Library, eigenes Bild hochladen (z. B. Foto des Umschlags) oder entfernen. Cover werden lokal gespeichert.
- Die gemeinsame Suche auf der Startseite findet jetzt auch Bücher und Autoren.

## MediaDB 1.5.0 – Einstellungen und Datensprache
- Neue Seite **Einstellungen** (Zahnrad ⚙ oben): TMDB-Schlüssel (mit „Jetzt prüfen“), Sprache der Daten mit Land, E-Mail-Adresse für MusicBrainz, Discogs-Token und die Schalter für Barcode-Dienst, iTunes-/Deezer-Cover und die tägliche Aktualisierung. Gilt sofort, gespeichert in `data/settings.json`, Vorrang vor `.env`. Zugriffsschutz (Passwort, Internetzugang) bleibt aus Sicherheitsgründen in `.env`.
- **Datensprache** getrennt von der Oberflächensprache: Deutsch, Englisch, Französisch, Spanisch mit Land (z. B. Österreich, Schweiz, Kanada, Mexiko). Bei der ersten Einrichtung passt sie sich der gewählten Oberflächensprache an. „Alles in der Datensprache neu laden“ lädt Filme, Serien und Merkliste im Hintergrund neu (sichtbar in der Statusanzeige).
- Französische und spanische Namen: Platzhalter-Titel wie „Épisode 3“ oder „Episodio 3“ werden durch den englischen Titel ersetzt; Kennungen wie FRENCH, TRUEFRENCH, VOSTFR, MULTi, CASTELLANO, LATINO werden aus Datei- und Ordnernamen entfernt, ebenso spanische Staffelkürzel (T2).
- **Fehler behoben:** Bei Filmen schnitten Wörter wie „English“ den Titel ab („The.English.Patient.1996…“ wurde zu „The“). Zusätze werden jetzt bei Filmen und Serien nur noch am Ende des Namens entfernt.

## MediaDB 1.4.2
- **Statusanzeige für Hintergrundaufgaben** oben in der Navigation, auf jeder Seite: Läuft etwas, erscheint „1 Aufgabe läuft“ (bzw. „§ Aufgaben laufen“) mit blinkendem Punkt. Ein Klick zeigt, was genau läuft, mit Fortschritt und Link zur Seite: Ordner-Import (Musik, Filme, Serien), Poster, Cover und Genres laden, Besetzung nachladen, tägliche Aktualisierung von Serien und Merkliste. Markiert ist, ob die App gerade **Dateien liest** (orange) oder nur **Internet**-Daten lädt (grün).

## MediaDB 1.4.1
- Merkliste: „Vorgemerkt“ mit Suchfeld steht jetzt oben, „Neu bei deinen Serien“ darunter.

## MediaDB 1.4.0 – Merkliste und Streamingdienste
- Neue Seite **Merkliste** (Menü „Merkliste“):
  - **Neu bei deinen Serien:** demnächst startende Staffeln und Folgen mit Datum und Streamingdienst („Tulsa King · Staffel 4 startet · 16.10.2026 · Paramount+“), gerade erschienene Folgen der letzten 30 Tage und angekündigte Staffeln ohne Termin.
  - **Vorgemerkt:** Filme und Serien per TMDB-Suche (oder ohne TMDB) vormerken, mit Notiz („Tipp von …“). Angezeigt werden Kinostart bzw. Digitalstart, Start der nächsten Staffel, Streamingdienst und ob der Titel schon in der Sammlung ist; „In die Sammlung“, „erledigt“, „entfernen“.
- **Automatische Aktualisierung** einmal am Tag im Hintergrund (und per Knopf „Jetzt aktualisieren“): laufende Serien bekommen neue Folgen und Staffeln, beendete Serien alle 30 Tage; geladen werden nur die letzte und neue Staffeln. Danach werden die Einträge der Merkliste aufgefrischt.
- **Streamingdienst bei Serien** (Daten von JustWatch über TMDB): auf der Serienseite mit „Wo ansehen?“ und der nächsten Folge, als Filter in der Serienübersicht und durchsuchbar. Eine eigene Angabe unter „Bearbeiten“ ersetzt die von TMDB.
- Serien-Import: Zusätze von Streamingdiensten am Ende von Ordnernamen werden entfernt (`Almost_Paradise_AmazonHD` → „Almost Paradise“; ebenso AMZN, NF, Netflix, DSNP, ATVP, HMAX, Joyn, HD …).

## MediaDB 1.3.9
- Serien-Import: Titel in anderer Schrift (z. B. kyrillisch) werden beim Vergleich nicht mehr fälschlich als passend gewertet. „10 историй о любви и смерти“ schrumpfte beim Vereinfachen auf „10“ und passte damit zu jedem Namen „10“. Genau gleiche Titel wie „24“ oder „1883“ gelten weiter als Treffer.
- Serienseite: Unter „Staffeln und Folgen“ steht der Ordner, aus dem die Dateien stammen; beim Zeigen auf „1080p“ usw. erscheint der Dateipfad.

## MediaDB 1.3.8
- Film- und Serien-Import: Alle Knöpfe stehen in einer Leiste, die beim Blättern unten am Bildschirm stehen bleibt: „Bei ‚Bitte prüfen‘: überall den ersten Vorschlag“, „… alle überspringen“, „Übernehmen“ und „Verwerfen“. Dazu eine laufende Zählung (x übernehmen · y ohne TMDB · z überspringen) und eine Bestätigung, bei wie vielen Einträgen ein Knopf etwas geändert hat.
- Die Gruppen der Vorschau sind einklappbar. „Bitte prüfen“ steht zuerst, danach „Nicht gefunden“; große Gruppen „Erkannt“ und „Schon vorhanden“ (mehr als 30) sind zugeklappt, zählen beim Übernehmen aber mit.

## MediaDB 1.3.7
- Serien-Import: Wörter wie „English“, „German“ oder „Complete“ im Seriennamen schneiden den Namen nicht mehr ab („A.Very.English.Scandal.S01E01.GERMAN.720P…“ wurde zu „A Very“). Szene-Zusätze werden nur noch am Ende entfernt; ist der Name aus der Datei nur der Anfang des Ordnernamens, gilt der Ordnername.
- Serien-Import: Bei „Bitte prüfen“ ist jetzt der beste Vorschlag vorgewählt, wenn er halbwegs passt; nur bei schwachen Treffern steht „Überspringen“.

## MediaDB 1.3.6
- Serien-Import: Der Fortschritt zeigt jetzt drei Schritte (Ordner durchsuchen mit laufender Zahl gefundener Videodateien und dem aktuellen Ordner, Dateinamen auswerten, Serien bei TMDB suchen mit dem Namen der aktuellen Serie). Vorher stand beim Durchsuchen großer NAS-Ordner minutenlang „0 von …“.

## MediaDB 1.3.5
- Film- und Serien-Import: Im Abschnitt „Bitte prüfen“ erklärt ein Hinweis, was „Überspringen“ bedeutet, und zwei Knöpfe setzen die Auswahl für alle Einträge auf einmal: „Überall den ersten Vorschlag wählen“ oder „Überall überspringen“. Einzelne Einträge lassen sich danach noch umstellen.

## MediaDB 1.3.4
- Startseite: Tausendertrennung je nach Sprache mit Punkt (5.783), im Englischen mit Komma, im Französischen mit Leerzeichen; vorher war der Abstand zu breit.

## MediaDB 1.3.3
- Startseite: Die Musikkachel zeigt jetzt „5 783 Alben, davon … CDs und … digital, insgesamt … Lieder von … Interpreten“. Gezählt werden die Titellisten, bei reinen Dateialben ohne Titelliste die Audiodateien. 

## MediaDB 1.3.2
- Serienseite: „Staffeln und Folgen“ steht jetzt direkt unter Handlung und Angaben, die Besetzung folgt danach.

## MediaDB 1.3.1
- **Fehler behoben:** Die Serienübersicht brach mit einem Serverfehler ab, sobald eine Serie eingetragen war.
- Serienseite: Die Folgen sind sofort sichtbar. Aufgeklappt sind Staffeln mit fehlenden Folgen, die Staffel mit der nächsten ungesehenen Folge und bei bis zu zwei Staffeln alle; dazu „Alle Staffeln aufklappen“ und „Alle zuklappen“.
- Folgen, die nur als Datei bekannt sind (Serie ohne TMDB oder Folge fehlt im Episodenführer), stehen jetzt ebenfalls in der Folgenliste, mit dem Titel aus dem Dateinamen und dem Hinweis „nur Datei“; „gesehen“ funktioniert auch für sie.
- Hat eine Serie eine TMDB-Zuordnung, aber noch keinen Episodenführer, gibt es den Knopf „Episodenführer jetzt laden“.

## MediaDB 1.3.0 – Serien
- Neuer Bereich **Serien** mit eigener Datenbank `data/serien.db` (Menü „Serien“).
- **Hinzufügen** per Barcode einer DVD-/Blu-ray-Box (Staffelangaben wie „Staffel 1-3“ oder „Die komplette Serie“ werden aus dem Produktnamen übernommen), per Titelsuche oder von Hand.
- **Ordner-Import**, etwa vom NAS: erkennt `S01E01`, Doppelfolgen `S01E01E02`, `1x01`, `E01` ohne Staffel, Staffelordner und `tvshow.nfo`; gruppiert die Folgen nach Serie und sucht jede Serie einmal bei TMDB. Beispiele wie `Sacrifice.S01E01.GERMAN.DL.1080P.WEB.H264.mkv` und `Stephen.Hawkings.Grosser.Entwurf.E01.Wie.das.Universum.entstand….mkv` werden richtig zugeordnet.
- **Episodenführer** von TMDB mit den richtigen Folgentiteln, auch wenn der Dateiname keinen enthält (fehlt der deutsche Titel, der englische).
- **Was fehlt?** Vergleich der vorhandenen Dateien und Boxen mit den tatsächlich ausgestrahlten Folgen: auf jeder Serienseite pro Folge (vorhanden, fehlt, kommt) und als Gesamtliste aller fehlenden Staffeln und Folgen, auch als Text zum Kopieren.
- **Videoformat** jeder Folge (Auflösung, Codec, HDR, Ton, Untertitel); die beste Auflösung steht in der Übersicht.
- Alle Angaben wie bei den Filmen: Handlung, Sender, Status, FSK, Genres, Idee, Besetzung mit Rollen und Anzahl Folgen, Trailer, Poster und Hintergrundbild (änderbar).
- **Gesehen** pro Folge oder ganze Staffel, „Als Nächstes“ mit einem Klick, Fortschrittsbalken, Bewertung 1–10, Notiz. Ansichten: Unvollständig, Angefangen, Noch nicht angefangen, Ganz gesehen, Läuft noch, Zuletzt hinzugefügt.
- **Personen** sind mit der Personen-Datenbank der Filme verknüpft: Die Personenseite zeigt Filme und Serien aus der Sammlung, weitere Serien laut TMDB lassen sich direkt hinzufügen.
- Startseite mit Serienkachel (Serien, Folgendateien, fehlende Folgen) und den Bereichen „Serien, die ich gerade schaue“ und „Zuletzt hinzugefügt: Serien“; die gemeinsame Suche findet Serien.
- Homelab: optionaler Einhängepunkt `/host/series` (im Import als `/series`).

## MediaDB 1.2.2
- Startseite aufgeräumt: oben Suche und drei schlichte Kacheln (Musik, Filme, Serien), darunter einklappbar „Top 10: Muss ich sehen“, „Zuletzt gesehen“, „Zuletzt hinzugefügt: Filme“ und „Zuletzt hinzugefügt: Musik“. Ab Werk zugeklappt; der Browser merkt sich, was du aufklappst. Am Handy stehen die Kacheln kompakt nebeneinander.

## MediaDB 1.2.1
- Musik: Hat ein Interpret nur einen Eintrag, öffnet ein Klick in der Interpreten-Übersicht direkt diesen Eintrag; bei mehreren erscheint wie bisher die Auswahl.
- Musik: Auf der Detailseite führt „← Interpreten X“ zurück zur Übersicht beim Anfangsbuchstaben des Interpreten.

## MediaDB 1.2.0 – Startseite und Bedienung
- Neue **Startseite** (Logo oben links und Neuladen führen dorthin): Suche über alle Bereiche, Kacheln für Musik, Filme und Serien (folgt) mit Zahlen und den zuletzt hinzugefügten Covern, dazu „Top 10: Muss ich sehen“, „Zuletzt gesehen“ und die neuesten Musik-Einträge.
- **Gemeinsame Suche** (`/search`): findet Musik (auch Songtitel), Filme und Personen auf einer Seite.
- **Musik:** Die Interpreten-Übersicht zeigt jeweils einen Anfangsbuchstaben statt der ganzen Liste; Auswahl über die Buchstabenleiste, „Alle“ zeigt weiterhin alles. **# (Zahlen) steht jetzt vorne.** „← Alle Interpreten“ führt zurück zum Buchstaben des Interpreten.
- **Filme:** dieselbe Buchstabenleiste (Sortiertitel ohne Artikel, „Der Pate“ unter P).

## MediaDB 1.1.4 – Poster aus mehreren Quellen
- Knopf **„Fehlende Poster laden“** in der Filmübersicht (läuft im Hintergrund mit Fortschritt). Reihenfolge: Bild neben der Filmdatei (poster.jpg, folder.jpg, cover.jpg, <Dateiname>-poster.jpg … wie von Jellyfin, Kodi oder Plex abgelegt), in MKV/MP4 eingebettetes Cover, alle Poster von TMDB (Deutsch, dann ohne Text, dann Englisch). Hintergrundbilder entsprechend (fanart.jpg, backdrop.jpg).
- Am Ende eine Liste der Filme ohne TMDB-Zuordnung (mit „zuordnen“) und der Filme, für die es nirgends ein Poster gibt (mit „eigenes Bild hochladen“).
- Neue Seite **„Poster ändern“** auf jeder Filmseite: Poster und Hintergrundbild aus allen TMDB-Bildern auswählen, ein Bild neben der Datei oder das eingebettete Cover nehmen, ein eigenes Bild hochladen (JPG, PNG, WebP bis 15 MB) oder das Bild entfernen.
- Beim Import und beim Speichern greifen dieselben Ausweichquellen automatisch, wenn TMDB kein Standardposter liefert; Bilddownloads werden einmal wiederholt.

## MediaDB 1.1.3 – Personen
- Besetzung, Regie und Drehbuch sind verlinkt. Die **Personenseite** zeigt Foto, Geburtsdatum und -ort, Kurzbiografie (Deutsch, sonst Englisch), alle Filme dieser Person **in deiner Sammlung** und darunter ihre **weiteren Filme und Serien** laut TMDB (neueste zuerst, mit „Hinzufügen“). Talkshow- und Nachrichtenauftritte werden ausgeblendet.
- Die Filmsuche zeigt passende Personen aus deiner Sammlung als eigene Treffer („Personen: Liam Neeson 3“).
- Für schon erfasste Filme lädt die App die Personen einmal im Hintergrund von TMDB nach. Personenangaben werden zwei Wochen zwischengespeichert, Fotos lokal in `data/film_images/`.

## MediaDB 1.1.2
- Filme: Das Datum bei „gesehen“ lässt sich ändern oder beim Eintragen angeben; es reicht auch Monat und Jahr oder nur das Jahr (z. B. 1999). Leer gespeichert heißt „Datum unbekannt“.
- Filme: Die Auflösung (z. B. 1080p, 2160p) steht in der Übersicht. Kann ffprobe sie nicht lesen, wird sie aus dem Dateinamen genommen (z. B. „11.Rebels.2024.German.1080p.BluRay.x264.mkv“), sonst bleibt das Feld leer.
- Erfolgsmeldungen auf der Filmseite erscheinen jetzt auch nach Aktionen mit Sprung zum Abschnitt.

## MediaDB 1.1.1
- Barcode-Suche bei Filmen verbessert: Produktnamen wie „David Tattersall - Star Wars I: Phantom Menace (2 Dvd) - Pal“ werden in Teile zerlegt; Formatangaben (Pal, Region 2, Extended Edition, 2 DVDs …) fallen weg, und die App probiert mehrere Schreibweisen, bis TMDB etwas findet.

## MediaDB 1.1.0 – Filme
- Neuer Bereich **Filme** mit eigener Datenbank `data/filme.db`; oben im Menü Musik · Filme.
- Hinzufügen per **Barcode** (DVD, Blu-ray, 4K UHD; Produktname über UPCitemdb, dann TMDB), per **Titelsuche**, **von Hand** oder per **Ordner-Import** (MKV, MP4, AVI, ISO, DVD- und Blu-ray-Ordner; Jellyfin-/Kodi-.nfo, Namen wie „Titel (Jahr)“ oder „[tmdbid-…]“; Fassungen wie Director’s Cut werden erkannt).
- Filmdaten von **TMDB** auf Deutsch: Handlung, Originaltitel, Laufzeit, Genres, Regie, Drehbuch, Besetzung, FSK, Filmreihe, Trailer-Link, Stichworte, Poster und Hintergrundbild.
- Ein Film, mehrere **Exemplare** (DVD, Blu-ray, 4K UHD, Datei) mit Barcode und Fassung; bei Dateien Auflösung, HDR, Codec, Tonspuren und Untertitel per ffprobe.
- **Gesehen** (mit Datum und Anzahl) und **eigene Bewertung 1–10** (1 = 5× löschen, 10 = Unbedingt sehen).
- **Listen:** Noch nicht gesehen, Top 10: Muss ich sehen, Lieblingsfilme, Zuletzt gesehen, Zuletzt hinzugefügt, Filmreihen und **eigene Listen**; Suche über Titel, Regie, Darsteller und Barcode, Filter nach Genre, Jahrzehnt und Format.
- „Anderen Film zuordnen“ korrigiert falsche Treffer; „Von TMDB ergänzen“ füllt nur leere Felder.
- Neue Einstellungen: `TMDB_API_KEY`, `TMDB_LANGUAGE`, `BARCODE_LOOKUP`; Filmordner im Homelab als `/movies`. Das Docker-Image enthält jetzt ffmpeg/ffprobe.

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
