# Konzept: mehrere Nutzer

Stand: 25.10.2026 (MediaDB 1.22.3), abgestimmt mit Lutz. Umgesetzt in drei Stufen, danach Feinschliff in 1.22.1 bis 1.22.3.

## Grundidee
Eine gemeinsame Sammlung für den ganzen Haushalt. Alle sehen alles. Dazu kommen Konten, ein Besitzer pro Exemplar und persönliche Angaben wie „gesehen“ und Bewertung. Getrennte Datenbanken pro Person gibt es bewusst nicht: Sie würden doppelte Einträge erzeugen und das gemeinsame Stöbern erschweren.

## Stufe 1: Konten und Anmeldung (fertig, 1.20.0)
- **Nutzer** liegen in einer eigenen kleinen Datenbank `data/nutzer.db`: Name, Rolle, Passwort oder PIN (nur als Prüfwert gespeichert, scrypt), letzte Anmeldung.
- **Rollen:**
  - **Verwalter:** alles, dazu Einstellungen, NAS-Freigaben, Nutzer anlegen, Updates.
  - **Mitglied:** alles ansehen, hinzufügen und bearbeiten; keine Einstellungen.
  - **Gast:** nur ansehen, nichts ändern, hinzufügen oder bewerten (z. B. für Besuch).
- **Eingebauter Gast** (seit 1.22.3): Mit Konten zeigt die Anmeldeseite von selbst „Gast“ (bei „Name und Passwort“ einen Knopf), ohne Passwort, nur im Heimnetz. Schalter unter Einstellungen → Nutzer und Anmeldung → Gastzugang; abgeschaltet ist ein angemeldeter Gast sofort abgemeldet. Eigene Personen mit der Rolle Gast gehen zusätzlich, auch ohne Passwort.
- **Art der Anmeldung** (Einstellungen → Nutzer, umschaltbar):
  - **Aus:** wie bisher; ein gesetztes `APP_PASSWORD` gilt weiter.
  - **Profilwahl:** Beim Öffnen auf den eigenen Namen klicken, wahlweise mit PIN. Von öffentlichen Adressen (nur mit `ALLOW_PUBLIC=1` überhaupt erreichbar) ist die PIN immer nötig; Profile ohne PIN gehen dann nicht.
  - **Name und Passwort:** richtige Anmeldung, 30 Tage gültig; Gäste brauchen kein Passwort.
- **Einrichten:** In den Einstellungen legt man sich selbst als ersten Verwalter an und wählt die Art der Anmeldung. Alle vorhandenen Daten gehören danach dem ersten Verwalter.
- Mindestens ein Verwalter bleibt immer. Ändert sich ein Passwort, sind alte Anmeldungen dieses Nutzers ungültig.
- Oben in der Leiste steht, wer angemeldet ist; „Wechseln“ bzw. „Abmelden“.

## Stufe 2: Besitzer (fertig, 1.21.0)
- Der Besitzer hängt am **Exemplar** (die DVD kann Lutz gehören, die Blu-ray Anna); bei Musik, die keine Exemplare hat, am Album.
- **Nur physische Exemplare** haben einen Besitzer (seit 1.22.2): CD (auch „CD + digital“), DVD, Blu-ray, 4K, Serienbox, gedrucktes Buch, auch ohne ISBN. Dateien, E-Books, Hörbücher aus Ordnern und rein digitale Alben gehören immer dem Haushalt.
- Wer etwas Physisches einträgt, wird Besitzer. Ändern lässt es sich auf der Seite, auch auf „Haushalt“ (gemeinsam). „Besitzer gesammelt setzen“ (Einstellungen → Nutzer und Anmeldung) gibt alle physischen Exemplare auf einmal einer Person.
- Filter in den Listen: „Alle Besitzer · Meine · Haushalt · von …“.
- **Verleihen:** zeigt, wem das verliehene Exemplar gehört; Filter „meine verliehenen“.

## Stufe 3: persönliche Angaben (fertig, 1.22.0)
- **Pro Person:** gesehen (Datum, Anzahl), gesehene Folgen, eigene Bewertung, gelesen, „Als Nächstes“, Merkliste.
- **Gemeinsam:** eigene Listen und Notizen.
- Anzeige z. B. „Gesehen von: Lutz (12.09.), Anna“. Die bisherigen Werte gehören dem ersten Verwalter.
- Die Ansicht „Gesehen gesammelt abhaken“ (ROADMAP) baut auf dieser Stufe auf.
- Technik: Die Werte liegen in eigenen Tabellen (`film_user`, `series_user`, `watched_user`, `book_user`, `media_next`, Merkliste mit `user_id`); Sichten und die Verbindungsklasse `users.Conn` leiten Lesen und Schreiben um (seit 1.22.1 ohne Trigger, weil SQLite 3.46 im Image sie nicht erlaubt).

## Später
- Oberflächensprache und Darstellung pro Person.
