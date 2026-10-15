"""Verleihen ueber alle Bereiche (seit 1.7): eigene kleine Datenbank data/verleih.db.

Tabellen:
  people  an wen verliehen wird (nur der Name, optional eine Notiz)
  loans   eine Zeile pro Verleihvorgang: Bereich (music, film, series, book), Nummer des Eintrags in dessen Datenbank,
          optional das Exemplar (copy_id), Titel zum Zeitpunkt des Verleihens (bleibt lesbar, auch wenn der Eintrag
          spaeter geloescht wird), verliehen am, zurueck bis, zurueckbekommen am, Notiz.
Offen ist ein Vorgang, solange returned_at leer ist. Die Bereichs-Datenbanken werden nicht veraendert."""
import re, sqlite3, threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from .films_db import now, parse_date

DB_PATH = None
_init_lock = threading.Lock()
AREAS = {'music': ('Musik', '/media/'), 'film': ('Filme', '/films/'), 'series': ('Serien', '/series/'), 'book': ('Bücher', '/books/')}
AREA_ONE = {'music': 'CD', 'film': 'Film', 'series': 'Serie', 'book': 'Buch'}

SCHEMA = """
CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, note TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS loans(
  id INTEGER PRIMARY KEY, area TEXT NOT NULL, item_id INTEGER NOT NULL, copy_id INTEGER, title TEXT NOT NULL, subtitle TEXT,
  detail TEXT, person_id INTEGER NOT NULL REFERENCES people(id), lent_at TEXT, due_at TEXT, returned_at TEXT, note TEXT,
  created_at TEXT);
CREATE INDEX IF NOT EXISTS ix_loans_item ON loans(area, item_id);
CREATE INDEX IF NOT EXISTS ix_loans_person ON loans(person_id);
CREATE INDEX IF NOT EXISTS ix_loans_open ON loans(returned_at);
"""


def init(path):
    global DB_PATH
    DB_PATH = Path(path)
    with _init_lock, db() as c:
        c.executescript(SCHEMA)


@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def clean_name(name):
    return re.sub(r'\s+', ' ', name or '').strip()[:80]


def person_id(c, name, create=True):
    name = clean_name(name)
    if not name:
        return None
    r = c.execute('SELECT id FROM people WHERE name=?', (name,)).fetchone()
    if r:
        return r[0]
    if not create:
        return None
    return c.execute('INSERT INTO people(name, created_at) VALUES(?,?)', (name, now())).lastrowid


def lend(c, area, item_id, title, person, lent_at=None, due_at=None, note=None, copy_id=None, detail=None, subtitle=None):
    """Neuer Verleihvorgang. lent_at: ISO-Datum (auch nur Jahr) oder None fuer unbekannt. Gibt die Nummer zurueck."""
    if area not in AREAS:
        raise ValueError(area)
    pid = person_id(c, person)
    if not pid:
        raise ValueError('person')
    return c.execute('''INSERT INTO loans(area, item_id, copy_id, title, subtitle, detail, person_id, lent_at, due_at, note, created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                     (area, int(item_id), copy_id, (title or '?')[:300], subtitle or None, detail or None, pid, lent_at or None,
                      due_at or None, (note or '').strip() or None, now())).lastrowid


def give_back(c, lid, when=None):
    c.execute('UPDATE loans SET returned_at=? WHERE id=? AND returned_at IS NULL', (when or date.today().isoformat(), lid))


def delete(c, lid):
    c.execute('DELETE FROM loans WHERE id=?', (lid,))
    c.execute('DELETE FROM people WHERE id NOT IN (SELECT person_id FROM loans) AND note IS NULL')


_SELECT = '''SELECT l.*, p.name AS person FROM loans l JOIN people p ON p.id=l.person_id'''


def _rows(c, sql, args=()):
    today = date.today().isoformat()
    out = []
    for r in c.execute(sql, args):
        d = dict(r)
        d['url'] = AREAS[d['area']][1] + str(d['item_id'])
        d['overdue'] = bool(d['due_at'] and not d['returned_at'] and d['due_at'] < today)
        out.append(d)
    return out


def open_for(c, area, item_id):
    return _rows(c, _SELECT + ' WHERE l.area=? AND l.item_id=? AND l.returned_at IS NULL ORDER BY l.id', (area, item_id))


def get(c, lid):
    r = _rows(c, _SELECT + ' WHERE l.id=?', (lid,))
    return r[0] if r else None


def open_all(c, area=None):
    sql = _SELECT + ' WHERE l.returned_at IS NULL' + (' AND l.area=?' if area else '') + \
        " ORDER BY p.name COLLATE NOCASE, l.lent_at IS NULL, l.lent_at, l.id"
    return _rows(c, sql, (area,) if area else ())


def history(c, person=None, limit=100):
    sql = _SELECT + ' WHERE l.returned_at IS NOT NULL' + (' AND l.person_id=?' if person else '') + \
        ' ORDER BY l.returned_at DESC, l.id DESC LIMIT ?'
    return _rows(c, sql, ((person,) if person else ()) + (limit,))


def by_person(c, pid):
    return _rows(c, _SELECT + ' WHERE l.person_id=? AND l.returned_at IS NULL ORDER BY l.lent_at IS NULL, l.lent_at, l.id', (pid,))


def person(c, pid):
    r = c.execute('SELECT * FROM people WHERE id=?', (pid,)).fetchone()
    return dict(r) if r else None


def people(c):
    """Alle Personen mit Zahl der offenen und aller Vorgaenge, Personen mit offenen zuerst."""
    return [dict(r) for r in c.execute('''SELECT p.id, p.name, p.note,
          (SELECT count(*) FROM loans l WHERE l.person_id=p.id AND l.returned_at IS NULL) AS n_open,
          (SELECT count(*) FROM loans l WHERE l.person_id=p.id) AS n_all
          FROM people p ORDER BY n_open=0, p.name COLLATE NOCASE''')]


def find_people(c, q, limit=12):
    return [dict(r) for r in c.execute('''SELECT p.id, p.name,
          (SELECT count(*) FROM loans l WHERE l.person_id=p.id AND l.returned_at IS NULL) AS n_open
          FROM people p WHERE p.name LIKE ? ORDER BY p.name COLLATE NOCASE LIMIT ?''', (f'%{q}%', limit))]


def rename_person(c, pid, name, note=None):
    """Umbenennen; gibt es den neuen Namen schon, werden beide Personen zusammengefuehrt. Gibt die gueltige Nummer zurueck."""
    name = clean_name(name)
    if not name:
        return pid
    other = c.execute('SELECT id FROM people WHERE name=? AND id<>?', (name, pid)).fetchone()
    if other:
        c.execute('UPDATE loans SET person_id=? WHERE person_id=?', (other[0], pid))
        c.execute('DELETE FROM people WHERE id=?', (pid,))
        return other[0]
    c.execute('UPDATE people SET name=?, note=? WHERE id=?', (name, (note or '').strip() or None, pid))
    return pid


def open_ids(c, area):
    """Nummern aller zurzeit verliehenen Eintraege eines Bereichs (fuer die Markierung in den Uebersichten)."""
    return {r[0] for r in c.execute('SELECT DISTINCT item_id FROM loans WHERE area=? AND returned_at IS NULL', (area,))}


def stats(c):
    r = c.execute('''SELECT count(*), count(DISTINCT person_id), min(lent_at),
                     sum(CASE WHEN due_at IS NOT NULL AND due_at < ? THEN 1 ELSE 0 END)
                     FROM loans WHERE returned_at IS NULL''', (date.today().isoformat(),)).fetchone()
    by_area = dict(c.execute('SELECT area, count(*) FROM loans WHERE returned_at IS NULL GROUP BY area').fetchall())
    return {'n': r[0], 'people': r[1], 'oldest': r[2], 'overdue': r[3] or 0, 'by_area': by_area}


def since(iso, lang='de'):
    """'2019-03-12' -> Dauer bis heute als (zahl, einheit): (5, 'Jahre'), (3, 'Monate'), (12, 'Tage')."""
    if not iso:
        return None
    try:
        y = int(iso[:4]); m = int(iso[5:7]) if len(iso) >= 7 else 1; d = int(iso[8:10]) if len(iso) >= 10 else 1
        start = date(y, m, d)
    except ValueError:
        return None
    days = (date.today() - start).days
    if days < 0:
        return None
    if days < 60:
        return (days, 'Tag' if days == 1 else 'Tage')
    months = days // 30
    if months < 24:
        return (months, 'Monate')
    return (days // 365, 'Jahre')


def parse(text):
    """Datum aus dem Formular: leer -> None, sonst ISO (auch '1999' oder '05.1999'); unlesbar -> False."""
    p = parse_date(text)
    if p is None:
        return False
    return p or None
