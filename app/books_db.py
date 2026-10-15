"""Buecherdatenbank (data/buecher.db), eigene Datei wie Filme und Serien.

Tabellen:
  books        ein Eintrag pro Buch (Werk in einer Ausgabe; Daten von DNB, Open Library oder von Hand), dazu gelesen/Bewertung
  copies       Exemplare: Hardcover, Taschenbuch, E-Book (Datei), Hoerbuch (CD oder Datei), sonstiges
  authors      Personen (Autor, Uebersetzer, Illustrator, Sprecher);  book_authors  wer an welchem Buch mitgewirkt hat
  isbn_cache   Ergebnisse von ISBN-Abfragen (spart Anfragen bei Wiederholungen)
Volltextsuche search_books_v1 per Trigger."""
import re, sqlite3, threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from .films_db import sort_key, now, parse_date  # gemeinsame Hilfsfunktionen

DB_PATH = None
KINDS = {'hardcover': 'Hardcover', 'paperback': 'Taschenbuch', 'ebook': 'E-Book', 'audiobook': 'Hörbuch', 'other': 'Sonstiges'}
FILE_KINDS = ('ebook', 'audiobook')
ROLES = {'aut': 'Autor', 'trl': 'Übersetzung', 'ill': 'Illustration', 'nrr': 'Sprecher', 'edt': 'Herausgeber'}
STATUS = {'': 'Ungelesen', 'reading': 'Lese ich gerade', 'read': 'Gelesen'}
RATING_LABELS = {1: '5× löschen', 10: 'Unbedingt lesen'}
FTS = 'search_books_v1'
_init_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS books(
  id INTEGER PRIMARY KEY, isbn TEXT, title TEXT NOT NULL, subtitle TEXT, sort_title TEXT, original_title TEXT,
  authors TEXT, sort_author TEXT, publisher TEXT, place TEXT, year INTEGER, edition TEXT, pages INTEGER, duration_s INTEGER,
  language TEXT, series TEXT, series_no TEXT, series_sort REAL, genres TEXT, subjects TEXT, description TEXT,
  cover TEXT, dnb_id TEXT, ol_key TEXT, source TEXT,
  status TEXT NOT NULL DEFAULT '', read_at TEXT, read_count INTEGER NOT NULL DEFAULT 0,
  rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 10), notes TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS copies(
  id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, kind TEXT NOT NULL,
  isbn TEXT, edition TEXT, notes TEXT, path TEXT UNIQUE, file_format TEXT, size_bytes INTEGER, duration_s INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS authors(id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort_name TEXT, gnd TEXT, ol_key TEXT, UNIQUE(name));
CREATE TABLE IF NOT EXISTS book_authors(
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, author_id INTEGER NOT NULL REFERENCES authors(id),
  role TEXT NOT NULL DEFAULT 'aut', ord INTEGER, PRIMARY KEY(book_id, author_id, role));
CREATE TABLE IF NOT EXISTS isbn_cache(isbn TEXT PRIMARY KEY, data TEXT, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_books_isbn ON books(isbn);
CREATE INDEX IF NOT EXISTS ix_books_sort ON books(sort_title);
CREATE INDEX IF NOT EXISTS ix_books_author ON books(sort_author);
CREATE INDEX IF NOT EXISTS ix_books_series ON books(series);
CREATE INDEX IF NOT EXISTS ix_bcopies_book ON copies(book_id);
CREATE INDEX IF NOT EXISTS ix_bcopies_isbn ON copies(isbn);
CREATE INDEX IF NOT EXISTS ix_ba_author ON book_authors(author_id);
"""
_BODY = ("coalesce(b.title,'')||' | '||coalesce(b.subtitle,'')||' | '||coalesce(b.original_title,'')||' | '||coalesce(b.authors,'')"
         "||' | '||coalesce(b.publisher,'')||' | '||coalesce(b.year,'')||' | '||coalesce(b.series,'')||' | '||coalesce(b.genres,'')"
         "||' | '||coalesce(b.subjects,'')||' | '||coalesce(b.isbn,'')||' | '||coalesce(b.notes,'')"
         "||' | '||coalesce((SELECT group_concat(a.name,' ') FROM book_authors ba JOIN authors a ON a.id=ba.author_id WHERE ba.book_id=b.id),'')"
         "||' | '||coalesce((SELECT group_concat(coalesce(k.isbn,''),' ') FROM copies k WHERE k.book_id=b.id),'')")
_REFRESH = f"DELETE FROM {FTS} WHERE rowid=X; INSERT INTO {FTS}(rowid, body) SELECT b.id, {_BODY} FROM books b WHERE b.id=X;"
TRIGGERS = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS} USING fts5(body, tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS books_ai AFTER INSERT ON books BEGIN {_REFRESH.replace('X', 'NEW.id')} END;
CREATE TRIGGER IF NOT EXISTS books_au AFTER UPDATE ON books BEGIN {_REFRESH.replace('X', 'NEW.id')} END;
CREATE TRIGGER IF NOT EXISTS books_ad AFTER DELETE ON books BEGIN DELETE FROM {FTS} WHERE rowid=OLD.id; END;
CREATE TRIGGER IF NOT EXISTS ba_ai AFTER INSERT ON book_authors BEGIN {_REFRESH.replace('X', 'NEW.book_id')} END;
CREATE TRIGGER IF NOT EXISTS bcopies_ai AFTER INSERT ON copies BEGIN {_REFRESH.replace('X', 'NEW.book_id')} END;
CREATE TRIGGER IF NOT EXISTS bcopies_ad AFTER DELETE ON copies BEGIN {_REFRESH.replace('X', 'OLD.book_id')} END;
"""
BOOK_FIELDS = ['isbn', 'title', 'subtitle', 'original_title', 'authors', 'publisher', 'place', 'year', 'edition', 'pages',
               'duration_s', 'language', 'series', 'series_no', 'genres', 'subjects', 'description', 'cover', 'dnb_id', 'ol_key',
               'source', 'notes', 'description_src', 'blurb_url', 'toc_url', 'ol_work']
# seit 1.6.1: Inhaltstext-Quelle, Wikipedia und Bewertung bei Open Library (in bestehenden Datenbanken per ALTER TABLE ergaenzt)
NEW_COLUMNS = {'description_src': 'TEXT', 'blurb_url': 'TEXT', 'toc_url': 'TEXT', 'ol_work': 'TEXT', 'wiki_extract': 'TEXT',
               'wiki_url': 'TEXT', 'wiki_title': 'TEXT', 'wiki_lang': 'TEXT', 'ol_rating': 'REAL', 'ol_rating_count': 'INTEGER',
               'extras_at': 'TEXT'}
LANG_NAMES = {'ger': 'Deutsch', 'deu': 'Deutsch', 'de': 'Deutsch', 'eng': 'Englisch', 'en': 'Englisch', 'fre': 'Französisch',
              'fra': 'Französisch', 'fr': 'Französisch', 'spa': 'Spanisch', 'es': 'Spanisch', 'ita': 'Italienisch', 'it': 'Italienisch',
              'dut': 'Niederländisch', 'nld': 'Niederländisch', 'nl': 'Niederländisch'}


def init(path):
    global DB_PATH
    DB_PATH = Path(path)
    with _init_lock, db() as c:
        c.executescript(SCHEMA)
        have = {r[1] for r in c.execute('PRAGMA table_info(books)')}
        for col, typ in NEW_COLUMNS.items():
            if col not in have:
                c.execute(f'ALTER TABLE books ADD COLUMN {col} {typ}')
        c.executescript(TRIGGERS)
        if c.execute(f'SELECT count(*) FROM {FTS}').fetchone()[0] != c.execute('SELECT count(*) FROM books').fetchone()[0]:
            c.execute(f'DELETE FROM {FTS}')
            c.execute(f'INSERT INTO {FTS}(rowid, body) SELECT b.id, {_BODY} FROM books b')


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


# ---------------------------------------------------------------- ISBN
def isbn_digits(s):
    return re.sub(r'[^0-9Xx]', '', s or '').upper()


def isbn10_to_13(i10):
    core = '978' + i10[:9]
    s = sum(int(d) * (1 if n % 2 == 0 else 3) for n, d in enumerate(core))
    return core + str((10 - s % 10) % 10)


def valid13(i):
    if not re.fullmatch(r'\d{13}', i or ''):
        return False
    s = sum(int(d) * (1 if n % 2 == 0 else 3) for n, d in enumerate(i[:12]))
    return (10 - s % 10) % 10 == int(i[12])


def valid10(i):
    if not re.fullmatch(r'\d{9}[\dX]', i or ''):
        return False
    s = sum((10 - n) * (10 if d == 'X' else int(d)) for n, d in enumerate(i))
    return s % 11 == 0


def norm_isbn(s):
    """Beliebige Schreibweise -> ISBN-13 ohne Striche, oder '' wenn ungueltig. EAN 978/979 = ISBN."""
    d = isbn_digits(s)
    if len(d) == 10 and valid10(d):
        return isbn10_to_13(d)
    if len(d) == 13 and valid13(d) and d[:3] in ('978', '979'):
        return d
    return ''


def isbn_pretty(i):
    """9783423214124 -> 978-3-423-21412-4 (vereinfachte Gruppierung fuer den deutschsprachigen Raum, sonst Bloecke)."""
    if not i or len(i) != 13:
        return i or ''
    if i[3] == '3':  # Deutschland, Oesterreich, Schweiz: Verlagsnummer 2-7 Stellen
        pub = i[4:6]
        n = 2 if pub < '20' else 3 if pub < '70' else 4 if pub < '85' else 5 if pub < '90' else 6 if pub < '95' else 7
        return f'{i[:3]}-3-{i[4:4 + n]}-{i[4 + n:12]}-{i[12]}'
    return f'{i[:3]}-{i[3:12]}-{i[12]}'


# ---------------------------------------------------------------- Buecher
def series_sort(no):
    m = re.search(r'\d+(?:[.,]\d+)?', no or '')
    return float(m.group().replace(',', '.')) if m else None


def author_sort(authors):
    """'J. R. R. Tolkien; Walter Scherf' -> 'tolkien j r r' (Nachname zuerst) fuer die Sortierung."""
    first = (authors or '').split(';')[0].strip()
    if not first:
        return ''
    if ',' in first:
        return sort_key(first)
    parts = first.split()
    return sort_key(' '.join(parts[-1:] + parts[:-1]))


def get(c, bid):
    return c.execute('SELECT * FROM books WHERE id=?', (bid,)).fetchone()


def by_isbn(c, isbn):
    i = norm_isbn(isbn)
    if not i:
        return []
    return c.execute('SELECT DISTINCT b.* FROM books b LEFT JOIN copies k ON k.book_id=b.id WHERE b.isbn=? OR k.isbn=?', (i, i)).fetchall()


def insert(c, data):
    d = {k: data.get(k) for k in BOOK_FIELDS if data.get(k) not in (None, '')}
    d['title'] = (data.get('title') or 'Ohne Titel').strip()
    d['sort_title'] = sort_key(d['title'])
    d['sort_author'] = author_sort(d.get('authors'))
    d['series_sort'] = series_sort(d.get('series_no'))
    d['created_at'] = d['updated_at'] = now()
    bid = c.execute(f'INSERT INTO books({",".join(d)}) VALUES({",".join("?" * len(d))})', tuple(d.values())).lastrowid
    if data.get('_people'):
        set_people(c, bid, data['_people'])
    return bid


def update(c, bid, data, only_empty=False):
    cur = get(c, bid)
    if not cur:
        return False
    d = {}
    for k in BOOK_FIELDS:
        if k in data and not (only_empty and cur[k] not in (None, '')):
            d[k] = data[k] if data[k] != '' else None
    if 'title' in d:
        if d['title']:
            d['sort_title'] = sort_key(d['title'])
        else:
            d.pop('title')
    if 'authors' in d:
        d['sort_author'] = author_sort(d['authors'])
    if 'series_no' in d:
        d['series_sort'] = series_sort(d['series_no'])
    if d:
        d['updated_at'] = now()
        c.execute(f'UPDATE books SET {",".join(k + "=?" for k in d)} WHERE id=?', (*d.values(), bid))
    if data.get('_people') and (not only_empty or not people_of(c, bid)['aut']):
        set_people(c, bid, data['_people'])
    return True


def delete(c, bid):
    c.execute('DELETE FROM books WHERE id=?', (bid,))


def set_status(c, bid, status, when=None):
    """status '' (ungelesen), 'reading' oder 'read' (Anzahl +1, Datum heute oder 'when')."""
    if status == 'read':
        c.execute('UPDATE books SET status=?, read_count=read_count+1, read_at=?, updated_at=? WHERE id=?',
                  ('read', when if when is not None else date.today().isoformat(), now(), bid))
    else:
        c.execute('UPDATE books SET status=?, updated_at=? WHERE id=?', (status if status in STATUS else '', now(), bid))


def set_read_date(c, bid, when):
    c.execute("UPDATE books SET status='read', read_count=max(read_count,1), read_at=?, updated_at=? WHERE id=?", (when or None, now(), bid))


def set_rating(c, bid, rating):
    r = int(rating) if str(rating or '').isdigit() and 1 <= int(rating) <= 10 else None
    c.execute('UPDATE books SET rating=?, updated_at=? WHERE id=?', (r, now(), bid))
    return r


# ---------------------------------------------------------------- Exemplare
def add_copy(c, bid, data):
    kind = data.get('kind') if data.get('kind') in KINDS else 'paperback'
    return c.execute('INSERT INTO copies(book_id, kind, isbn, edition, notes, path, file_format, size_bytes, duration_s, created_at) '
                     'VALUES(?,?,?,?,?,?,?,?,?,?)',
                     (bid, kind, norm_isbn(data.get('isbn')) or None, data.get('edition') or None, data.get('notes') or None,
                      data.get('path') or None, data.get('file_format') or None, data.get('size_bytes'), data.get('duration_s'), now())).lastrowid


def copies_of(c, bid):
    return c.execute('SELECT * FROM copies WHERE book_id=? ORDER BY id', (bid,)).fetchall()


def known_paths(c):
    return {r[0] for r in c.execute('SELECT path FROM copies WHERE path IS NOT NULL')}


# ---------------------------------------------------------------- Personen
def set_people(c, bid, people):
    """people: [{'name', 'role', 'gnd'?, 'ol_key'?}] in Reihenfolge."""
    c.execute('DELETE FROM book_authors WHERE book_id=?', (bid,))
    for i, p in enumerate(people or []):
        name = re.sub(r'\s+', ' ', (p.get('name') or '').strip())
        if not name:
            continue
        role = p.get('role') if p.get('role') in ROLES else 'aut'
        r = c.execute('SELECT id FROM authors WHERE name=?', (name,)).fetchone()
        aid = r[0] if r else c.execute('INSERT INTO authors(name, sort_name, gnd, ol_key) VALUES(?,?,?,?)',
                                        (name, author_sort(name), p.get('gnd'), p.get('ol_key'))).lastrowid
        if r and (p.get('gnd') or p.get('ol_key')):
            c.execute('UPDATE authors SET gnd=coalesce(gnd,?), ol_key=coalesce(ol_key,?) WHERE id=?', (p.get('gnd'), p.get('ol_key'), aid))
        c.execute('INSERT OR IGNORE INTO book_authors(book_id, author_id, role, ord) VALUES(?,?,?,?)', (bid, aid, role, i))


def people_of(c, bid):
    out = {r: [] for r in ROLES}
    for r in c.execute('''SELECT ba.role, a.id, a.name FROM book_authors ba JOIN authors a ON a.id=ba.author_id
                          WHERE ba.book_id=? ORDER BY ba.ord''', (bid,)):
        out.setdefault(r['role'], []).append({'id': r['id'], 'name': r['name']})
    return out


def get_author(c, aid):
    return c.execute('SELECT * FROM authors WHERE id=?', (aid,)).fetchone()


def books_by_author(c, aid):
    return c.execute('''SELECT b.*, group_concat(DISTINCT ba.role) AS roles,
                        (SELECT group_concat(DISTINCT k.kind) FROM copies k WHERE k.book_id=b.id) AS kinds
                        FROM books b JOIN book_authors ba ON ba.book_id=b.id WHERE ba.author_id=?
                        GROUP BY b.id ORDER BY b.series, b.series_sort, b.year, b.sort_title''', (aid,)).fetchall()


def find_authors(c, q, limit=8):
    toks = [t for t in (q or '').split() if t]
    if not toks:
        return []
    where = ' AND '.join('a.name LIKE ?' for _ in toks)
    return c.execute(f"""SELECT a.id, a.name, count(DISTINCT ba.book_id) AS n FROM authors a JOIN book_authors ba ON ba.author_id=a.id
                         WHERE {where} GROUP BY a.id ORDER BY n DESC, a.name LIMIT ?""", (*[f'%{t}%' for t in toks], limit)).fetchall()


# ---------------------------------------------------------------- Reihen
def series_list(c):
    return c.execute('''SELECT series, count(*) AS n, min(series_sort) AS first, max(series_sort) AS last,
                        group_concat(series_sort) AS nos, max(authors) AS authors
                        FROM books WHERE coalesce(series,'')<>'' GROUP BY series ORDER BY lower(series)''').fetchall()


def series_books(c, name):
    return c.execute('SELECT * FROM books WHERE series=? ORDER BY series_sort IS NULL, series_sort, year', (name,)).fetchall()


def series_gaps(nos):
    """Fehlende ganze Bandnummern zwischen 1 und dem hoechsten vorhandenen Band."""
    have = {int(x) for x in nos if x is not None and float(x).is_integer()}
    if not have:
        return []
    return [n for n in range(1, max(have) + 1) if n not in have]


# ---------------------------------------------------------------- Uebersicht
VIEW_RULES = {
    'unread': ("b.status=''", None, None),
    'reading': ("b.status='reading'", 'b.updated_at DESC', None),
    'read': ("b.status='read'", None, None),
    'favorites': ('b.rating>=9', 'b.rating DESC, b.sort_title', None),
    'recent_read': ("b.status='read' AND b.read_at IS NOT NULL", 'b.read_at DESC, b.updated_at DESC', 50),
    'recent_added': ('1=1', 'b.created_at DESC, b.id DESC', 50),
    'ebooks': ("EXISTS (SELECT 1 FROM copies k WHERE k.book_id=b.id AND k.kind='ebook')", None, None),
    'audiobooks': ("EXISTS (SELECT 1 FROM copies k WHERE k.book_id=b.id AND k.kind='audiobook')", None, None),
}
SORTS = {'title': 'b.sort_title {d}', 'author': "b.sort_author='' , b.sort_author {d}, b.series, b.series_sort, b.sort_title",
         'year': 'b.year IS NULL, b.year {d}, b.sort_title', 'rating': 'b.rating IS NULL, b.rating {d}, b.sort_title',
         'added': 'b.created_at {d}, b.id {d}'}
LETTER_SQL = {'title': "CASE WHEN substr(b.sort_title,1,1) BETWEEN 'a' AND 'z' THEN upper(substr(b.sort_title,1,1)) ELSE '#' END",
              'author': "CASE WHEN substr(b.sort_author,1,1) BETWEEN 'a' AND 'z' THEN upper(substr(b.sort_author,1,1)) ELSE '#' END"}


def query(c, view='all', q='', genre='', kind='', lang='', sort='author', direction='asc', limit=120, offset=0, letter=''):
    where, args = [], []
    lkey = 'author' if sort == 'author' else 'title'
    if letter and (letter == '#' or (len(letter) == 1 and 'A' <= letter <= 'Z')):
        where.append(f'{LETTER_SQL[lkey]}=?')
        args.append(letter)
    order = SORTS.get(sort, SORTS['author']).format(d='DESC' if direction == 'desc' else 'ASC')
    fixed = None
    if view in VIEW_RULES:
        cond, vorder, fixed = VIEW_RULES[view]
        where.append(cond)
        order = vorder or order
    toks = [t for t in (q or '').split() if t]
    long, short = [t for t in toks if len(t) >= 3], [t for t in toks if len(t) < 3]
    if long:
        where.append(f'b.id IN (SELECT rowid FROM {FTS} WHERE {FTS} MATCH ?)')
        args.append(' AND '.join('"' + t.replace('"', '""') + '"' for t in long))
    for t in short:
        where.append('(b.title LIKE ? OR b.authors LIKE ?)')
        args += [f'%{t}%', f'%{t}%']
    d = norm_isbn(q)
    if d:  # ISBN in der Suche: auch Exemplare
        where = [w for w in where if 'MATCH' not in w]
        args = [a for a in args if not (isinstance(a, str) and a.startswith('"'))]
        where.append('(b.isbn=? OR EXISTS (SELECT 1 FROM copies k WHERE k.book_id=b.id AND k.isbn=?))')
        args += [d, d]
    if genre:
        where.append("(', '||coalesce(b.genres,'')||',') LIKE ?")
        args.append(f'%, {genre},%')
    if kind in KINDS:
        where.append('EXISTS (SELECT 1 FROM copies k WHERE k.book_id=b.id AND k.kind=?)')
        args.append(kind)
    if lang:
        where.append('b.language=?')
        args.append(lang)
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    total = c.execute(f'SELECT count(*) FROM books b {w}', args).fetchone()[0]
    lim, off = (fixed, 0) if fixed else (limit, offset)
    if fixed:
        total = min(total, fixed)
    rows = c.execute(f"""SELECT b.*, (SELECT group_concat(DISTINCT k.kind) FROM copies k WHERE k.book_id=b.id) AS kinds
                         FROM books b {w} ORDER BY {order} LIMIT ? OFFSET ?""", (*args, lim, off)).fetchall()
    return rows, total


def view_counts(c):
    out = {'all': c.execute('SELECT count(*) FROM books').fetchone()[0]}
    for v, (cond, _, lim) in VIEW_RULES.items():
        n = c.execute(f'SELECT count(*) FROM books b WHERE {cond}').fetchone()[0]
        out[v] = min(n, lim) if lim else n
    return out


def letter_counts(c, sort='author'):
    return dict(c.execute(f"SELECT {LETTER_SQL['author' if sort == 'author' else 'title']}, count(*) FROM books b GROUP BY 1").fetchall())


def genres(c):
    seen = {}
    for (g,) in c.execute("SELECT genres FROM books WHERE coalesce(genres,'')<>''"):
        for x in g.split(','):
            x = x.strip()
            if x:
                seen[x] = seen.get(x, 0) + 1
    return sorted(seen.items(), key=lambda kv: kv[0].lower())


def languages(c):
    return c.execute("SELECT language, count(*) FROM books WHERE coalesce(language,'')<>'' GROUP BY 1 ORDER BY 2 DESC").fetchall()


def stats(c):
    n = c.execute('SELECT count(*) FROM books').fetchone()[0]
    kinds = dict(c.execute('SELECT kind, count(DISTINCT book_id) FROM copies GROUP BY kind').fetchall())
    read = c.execute("SELECT count(*) FROM books WHERE status='read'").fetchone()[0]
    pages = c.execute("SELECT coalesce(sum(pages),0) FROM books WHERE status='read'").fetchone()[0]
    authors = c.execute("SELECT count(DISTINCT author_id) FROM book_authors WHERE role='aut'").fetchone()[0]
    return {'books': n, 'read': read, 'pages_read': pages, 'authors': authors, 'ebooks': kinds.get('ebook', 0),
            'audiobooks': kinds.get('audiobook', 0), 'print': kinds.get('hardcover', 0) + kinds.get('paperback', 0)}


# ---------------------------------------------------------------- Zusammenfassung und Bewertungen aus anderen Quellen
EXTRA_FIELDS = ('description', 'description_src', 'blurb_url', 'toc_url', 'ol_key', 'ol_work', 'wiki_extract', 'wiki_url',
                'wiki_title', 'wiki_lang', 'ol_rating', 'ol_rating_count')


def set_extras(c, bid, data):
    d = {k: data[k] for k in EXTRA_FIELDS if k in data}
    d['extras_at'] = now()
    c.execute(f"UPDATE books SET {', '.join(k + '=?' for k in d)} WHERE id=?", (*d.values(), bid))


def missing_extras(c, limit=None):
    sql = 'SELECT id FROM books WHERE extras_at IS NULL ORDER BY id'
    return [r[0] for r in c.execute(sql + (f' LIMIT {int(limit)}' if limit else ''))]
