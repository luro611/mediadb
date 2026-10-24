# Konzept: mehrere Nutzer

Stand: 24.10.2026, abgestimmt mit Lutz. Umsetzung in drei Stufen, jede als eigene Version.

## Grundidee
Eine gemeinsame Sammlung für den ganzen Haushalt. Alle sehen alles. Dazu kommen Konten, ein Besitzer pro Exemplar und persönliche Angaben wie „gesehen“ und Bewertung. Getrennte Datenbanken pro Person gibt es bewusst nicht: Sie würden doppelte Einträge erzeugen und das gemeinsame Stöbern erschweren.

## Stufe 1: Konten und Anmeldung (fertig, 1.20.0)
- **Nutzer** liegen in einer eigenen kleinen Datenbank `data/nutzer.db`: Name, Rolle, Passwort oder PIN (nur als Prüfwert gespeichert, scrypt), letzte Anmeldung.
- **Rollen:**
  - **Verwalter:** alles, dazu Einstellungen, NAS-Freigaben, Nutzer anlegen, Updates.
  - **Mitglied:** alles ansehen, hinzufügen und bearbeiten; keine Einstellungen.
  - **Gast:** nur ansehen, nichts ändern (z. B. für Besuch).
- **Art der Anmeldung** (Einstellungen → Nutzer, umschaltbar):
  - **Aus:** wie bisher; ein gesetztes `APP_PASSWORD` gilt weiter.
  - **Profilwahl:** Beim Öffnen auf den eigenen Namen klicken, wahlweise mit PIN. Von öffentlichen Adressen (nur mit `ALLOW_PUBLIC=1` überhaupt erreichbar) ist die PIN immer nötig; Profile ohne PIN gehen dann nicht.
  - **Name und Passwort:** richtige Anmeldung, 30 Tage gültig.
- **Einrichten:** In den Einstellungen legt man sich selbst als ersten Verwalter an und wählt die Art der Anmeldung. Alle vorhandenen Daten gehören danach dem ersten Verwalter.
- Mindestens ein Verwalter bleibt immer. Ändert sich ein Passwort, sind alte Anmeldungen dieses Nutzers ungültig.
- Oben in der Leiste steht, wer angemeldet ist; „Wechseln“ bzw. „Abmelden“.

## Stufe 2: Besitzer (fertig, 1.21.0)
- Der Besitzer hängt am **Exemplar** (die DVD kann Lutz gehören, die Blu-ray Anna); bei Musik, die keine Exemplare hat, am Album.
- Wer etwas einträgt, wird Besitzer. Ändern lässt es sich auf der Seite, auch auf „Haushalt“ (gemeinsam).
- Filter in den Listen: „Alle · Meins · von …“.
- **Verleihen:** zeigt, wem das verliehene Exemplar gehört; Filter „meine verliehenen“.

## Stufe 3: persönliche Angaben (fertig, 1.22.0)
- **Pro Person:** gesehen (Datum, Anzahl), gesehene Folgen, eigene Bewertung, gelesen, „Als Nächstes“, Merkliste.
- **Gemeinsam:** eigene Listen und Notizen.
- Anzeige z. B. „Gesehen von: Lutz (12.09.), Anna“. Die bisherigen Werte gehören dem ersten Verwalter.
- Die Ansicht „Gesehen gesammelt abhaken“ (ROADMAP) baut auf dieser Stufe auf.

## Später
- Oberflächensprache und Darstellung pro Person.
