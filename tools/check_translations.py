#!/usr/bin/env python3
"""Prüft, ob alle Texte in den Vorlagen (app/templates) in app/locales/<sprache>.json übersetzt sind.
Aufruf im Projektordner:  python3 tools/check_translations.py
Texte stehen in den Vorlagen als {{ _("Deutscher Text") }}; ein § steht für eingesetzte Werte.
Dazu kommen Meldungen aus app/main.py, app/audio.py und app/importer.py (siehe EXTRA unten)."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = ['en', 'fr', 'es']
PAT = re.compile(r"""\b_t?\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""")
# Texte, die ohne _() im Quelltext stehen (Listen, Meldungen aus Python); bei neuen Meldungen hier ergänzen
EXTRA = [
    'Alle', 'Vorhandene CDs', 'Nur digital', 'Titel', 'Jahr (CD)', 'Dateiformate', 'Label', 'Katalognr.', 'Styles',
    'Physische CD', 'Nur digital (Audiodateien)', 'CD + digital', 'Digital', 'CD + Digital', 'Gespeichert.',
    'Eintrag nicht gefunden.', 'Kein gültiger Ordner ausgewählt.', 'Ordner nicht gefunden oder nicht freigegeben.',
]

def keys():
    out = {}
    for f in sorted((ROOT / 'app' / 'templates').glob('*.html')):
        for m in PAT.finditer(f.read_text(encoding='utf-8')):
            v = m.group(1) if m.group(1) is not None else m.group(2)
            v = json.loads('"' + v + '"') if m.group(1) is not None else v.replace("\\'", "'")
            out[' '.join(v.split())] = f.name
    for k in EXTRA:
        out.setdefault(k, 'EXTRA')
    return out

def main():
    ks = keys(); problems = 0
    for lang in LANGS:
        p = ROOT / 'app' / 'locales' / f'{lang}.json'
        t = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        miss = [k for k in ks if k not in t]
        bad = [k for k in t if k.count('§') != t[k].count('§')]
        for k in miss: print(f'[{lang}] fehlt ({ks[k]}): {k[:90]}')
        for k in bad: print(f'[{lang}] Platzhalter § passen nicht: {k[:90]}')
        problems += len(miss) + len(bad)
    print('OK: alles übersetzt' if not problems else f'{problems} Problem(e)')
    return 1 if problems else 0

if __name__ == '__main__':
    sys.exit(main())
