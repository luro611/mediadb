# Sprachen und Übersetzungen

MusikDB gibt es auf **Deutsch** (Quellsprache), **Englisch**, **Französisch** und **Spanisch**. Die Sprache wählst du oben rechts neben „Theme“.

## Wie es funktioniert
- Jeder sichtbare Text steht in den Vorlagen als `{{ _("Deutscher Text") }}`.
- Die Übersetzungen liegen in `app/locales/en.json`, `fr.json` und `es.json`. Der **Schlüssel** ist der deutsche Text, der **Wert** die Übersetzung.
- `§` ist ein Platzhalter für Zahlen oder Namen, die das Programm einsetzt. Er muss in der Übersetzung genauso oft vorkommen wie im Schlüssel, in der gleichen Reihenfolge.
- `*Wort*` in einer Überschrift wird hervorgehoben dargestellt (kursiv).
- Fehlt eine Übersetzung, zeigt die App den deutschen Text.

## Eine Übersetzung verbessern
1. Die passende Datei in `app/locales/` öffnen und den Wert ändern (Schlüssel nicht ändern).
2. Im Projektordner `python3 tools/check_translations.py` ausführen. Das Programm meldet fehlende Einträge und falsche Platzhalter.
3. `docker compose up --build`, im Browser neu laden.

## Eine neue Sprache ergänzen (z. B. Italienisch)
1. `app/locales/en.json` nach `app/locales/it.json` kopieren und alle Werte übersetzen.
2. In `app/i18n.py` bei `LANGS` die Zeile `'it': 'Italiano'` ergänzen.
3. In `tools/check_translations.py` die Liste `LANGS` um `'it'` erweitern und das Skript ausführen.
4. Die Datei `docs/SPRACHEN.md` und `README.md` anpassen.

## Neue Texte im Programm
- In Vorlagen: `{{ _("Neuer Text") }}` schreiben und den Text in alle JSON-Dateien aufnehmen.
- In JavaScript-Texten: `{{ _t("Neuer Text")|tojson }}`.
- Meldungen aus `main.py`: deutscher Satz, in der Vorlage mit `{{ _(message) }}` angezeigt; Text in `EXTRA` (tools/check_translations.py) und in die JSON-Dateien aufnehmen.

## Hinweis zur Qualität
Die Übersetzungen sind sorgfältig erstellt, aber nicht von Muttersprachlern geprüft. Verbesserungsvorschläge sind willkommen.
