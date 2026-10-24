"""Filmdatenbank (data/filme.db), eigene Datei, getrennt von der Musik.

Bewusst mit dem eingebauten sqlite3 statt SQLAlchemy: klein, schnell, ohne Zusatzpakete testbar.
Tabellen:
  films       ein Eintrag pro Film (Daten von TMDB oder von Hand), dazu gesehen/Bewertung/Notizen
  copies      Exemplare eines Films: DVD, Blu-ray, 4K-UHD oder Datei (mit Technikdaten)
  lists       eigene Listen;  list_items  welche Filme in welcher Liste
  barcode_cache  Ergebnisse der Barcode-Abfrage (spart Anfragen)
Die Volltextsuche (search_films_v1) wird per Trigger automatisch aktuell gehalten."""
import json, re, sqlite3, threading, unicodedata
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from . import users as U

DB_PATH = None
KINDS = {'dvd': 'DVD', 'bluray': 'Blu-ray', 'uhd': '4K UHD', 'file': 'Datei'}
RATING_LABELS = {1: '5× löschen', 10: 'Unbedingt sehen'}
FTS = 'search_films_v1'
_init_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS films(
  id INTEGER PRIMARY KEY, tmdb_id INTEGER UNIQUE, imdb_id TEXT, title TEXT NOT NULL, sort_title TEXT, original_title TEXT,
  year INTEGER, release_date TEXT, runtime INTEGER, overview TEXT, tagline TEXT, genres TEXT, directors TEXT, writers TEXT,
  cast_json TEXT, countries TEXT, original_language TEXT, studios TEXT, certification TEXT, collection_id INTEGER,
  collection_name TEXT, poster TEXT, backdrop TEXT, trailer_url TEXT, tmdb_rating REAL, tmdb_votes INTEGER, keywords TEXT,
  watched INTEGER NOT NULL DEFAULT 0, watched_at TEXT, watch_count INTEGER NOT NULL DEFAULT 0,
  rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 10), notes TEXT, source TEXT,
  created_at TEXT, updated_at TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS copies(
  id INTEGER PRIMARY KEY, film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE, kind TEXT NOT NULL,
  barcode TEXT, edition TEXT, region TEXT, notes TEXT, path TEXT UNIQUE, container TEXT, resolution TEXT, video_codec TEXT,
  hdr TEXT, duration_s INTEGER, audio TEXT, subtitles TEXT, size_bytes INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS lists(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT);
CREATE TABLE IF NOT EXISTS list_items(
  list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE, film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE,
  added_at TEXT, PRIMARY KEY(list_id, film_id));
CREATE TABLE IF NOT EXISTS barcode_cache(barcode TEXT PRIMARY KEY, title TEXT, raw TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS people(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, profile_path TEXT, profile TEXT, biography TEXT, birthday TEXT, deathday TEXT,
  place TEXT, department TEXT, imdb_id TEXT, credits_json TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS film_people(
  film_id INTEGER NOT NULL REFERENCES films(id) ON DELETE CASCADE, person_id INTEGER NOT NULL REFERENCES people(id),
  role TEXT NOT NULL, character TEXT, ord INTEGER, PRIMARY KEY(film_id, person_id, role));
CREATE INDEX IF NOT EXISTS ix_film_people_person ON film_people(person_id);
CREATE INDEX IF NOT EXISTS ix_people_name ON people(name);
CREATE INDEX IF NOT EXISTS ix_copies_film ON copies(film_id);
CREATE INDEX IF NOT EXISTS ix_copies_barcode ON copies(barcode);
CREATE INDEX IF NOT EXISTS ix_films_sort ON films(sort_title);
CREATE INDEX IF NOT EXISTS ix_films_year ON films(year);
CREATE INDEX IF NOT EXISTS ix_films_watched ON films(watched, rating);
CREATE INDEX IF NOT EXISTS ix_films_collection ON films(collection_id);
CREATE INDEX IF NOT EXISTS ix_list_items_film ON list_items(film_id);
"""
_BODY = ("coalesce(f.title,'')||' | '||coalesce(f.original_title,'')||' | '||coalesce(f.year,'')||' | '||coalesce(f.genres,'')"
         "||' | '||coalesce(f.directors,'')||' | '||coalesce(f.writers,'')||' | '||coalesce(f.cast_json,'')||' | '||coalesce(f.collection_name,'')"
         "||' | '||coalesce(f.keywords,'')||' | '||coalesce(f.studios,'')||' | '||coalesce(f.notes,'')"
         "||' | '||coalesce((SELECT group_concat(coalesce(c.barcode,'')||' '||coalesce(c.edition,''),' ') FROM copies c WHERE c.film_id=f.id),'')")
TRIGGERS = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS} USING fts5(body, tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS films_ai AFTER INSERT ON films BEGIN
  INSERT INTO {FTS}(rowid, body) SELECT f.id, {_BODY} FROM films f WHERE f.id=NEW.id; END;
CREATE TRIGGER IF NOT EXISTS films_au AFTER UPDATE ON films BEGIN
  DELETE FROM {FTS} WHERE rowid=NEW.id; INSERT INTO {FTS}(rowid, body) SELECT f.id, {_BODY} FROM films f WHERE f.id=NEW.id; END;
CREATE TRIGGER IF NOT EXISTS films_ad AFTER DELETE ON films BEGIN DELETE FROM {FTS} WHERE rowid=OLD.id; END;
CREATE TRIGGER IF NOT EXISTS copies_ai AFTER INSERT ON copies BEGIN
  DELETE FROM {FTS} WHERE rowid=NEW.film_id; INSERT INTO {FTS}(rowid, body) SELECT f.id, {_BODY} FROM films f WHERE f.id=NEW.film_id; END;
CREATE TRIGGER IF NOT EXISTS copies_au AFTER UPDATE ON copies BEGIN
  DELETE FROM {FTS} WHERE rowid=NEW.film_id; INSERT INTO {FTS}(rowid, body) SELECT f.id, {_BODY} FROM films f WHERE f.id=NEW.film_id; END;
CREATE TRIGGER IF NOT EXISTS copies_ad AFTER DELETE ON copies BEGIN
  DELETE FROM {FTS} WHERE rowid=OLD.film_id; INSERT INTO {FTS}(rowid, body) SELECT f.id, {_BODY} FROM films f WHERE f.id=OLD.film_id; END;
"""

FILM_FIELDS = ['tmdb_id', 'imdb_id', 'title', 'original_title', 'year', 'release_date', 'runtime', 'overview', 'tagline', 'genres',
               'directors', 'writers', 'cast_json', 'countries', 'original_language', 'studios', 'certification', 'collection_id',
               'collection_name', 'poster', 'backdrop', 'trailer_url', 'tmdb_rating', 'tmdb_votes', 'keywords', 'notes', 'source', 'raw_json']
COPY_FIELDS = ['kind', 'barcode', 'edition', 'region', 'notes', 'path', 'container', 'resolution', 'video_codec', 'hdr',
               'duration_s', 'audio', 'subtitles', 'size_bytes', 'owner_id']


def now():
    return datetime.now().isoformat(timespec='seconds')


def sort_key(title):
    """Sortiertitel: ohne fuehrenden Artikel und Akzente ('Der Pate' -> 'pate', 'The Matrix' -> 'matrix')."""
    t = unicodedata.normalize('NFKD', str(title or '')).encode('ascii', 'ignore').decode().lower().strip()
    t = re.sub(r'^(the|a|an|der|die|das|ein|eine|le|la|les|l\'|el|los|las)\s+', '', t)
    return re.sub(r'[^a-z0-9 ]+', '', t).strip()


def init(path):
    global DB_PATH, _ready
    DB_PATH, _ready = Path(path), False
    with _init_lock, db() as c:
        c.executescript(SCHEMA)
        if 'next_at' not in {r[1] for r in c.execute('PRAGMA table_info(films)')}:  # seit 1.11: "Als Naechstes"
            c.execute('ALTER TABLE films ADD COLUMN next_at TEXT')
        U.add_owner_column(c, 'copies')  # seit 1.21: Besitzer
        U.personal_table(c, 'films', 'film_user', 'film_id', PERSONAL)  # seit 1.22: gesehen und Bewertung pro Person
        c.executescript(TRIGGERS)
        if c.execute(f'SELECT count(*) FROM {FTS}').fetchone()[0] != c.execute('SELECT count(*) FROM films').fetchone()[0]:
            c.execute(f'DELETE FROM {FTS}')
            c.execute(f'INSERT INTO {FTS}(rowid, body) SELECT f.id, {_BODY} FROM films f')
    _ready = True


# seit 1.22: persoenliche Werte (siehe users.personalize); SQL-Ausdruck fuer den Wert ohne Eintrag
PERSONAL = {'watched': '0', 'watched_at': 'NULL', 'watch_count': '0', 'rating': 'NULL', 'next_at': 'NULL'}
SPECS = [('personal', 'films', 'film_user', 'film_id', PERSONAL), ('rows', 'watch')]
_ready = False


@contextmanager
def db(plain=False):
    """plain=True: ohne persoenliche Sichten (Aufbau der Tabellen beim Start)."""
    c = sqlite3.connect(DB_PATH, timeout=15, factory=U.Conn)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    if _ready and not plain:
        U.personalize(c, 'films', SPECS)
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


# ---------------------------------------------------------------- Filme
def get_film(c, fid):
    return c.execute('SELECT * FROM films WHERE id=?', (fid,)).fetchone()


def film_by_tmdb(c, tmdb_id):
    return c.execute('SELECT * FROM films WHERE tmdb_id=?', (tmdb_id,)).fetchone() if tmdb_id else None


def insert_film(c, data):
    d = {k: data.get(k) for k in FILM_FIELDS if data.get(k) not in (None, '')}
    d['title'] = (data.get('title') or 'Ohne Titel').strip()
    d['sort_title'] = sort_key(d['title'])
    d['created_at'] = d['updated_at'] = now()
    cols = ','.join(d)
    cur = c.execute(f'INSERT INTO main.films({cols}) VALUES({",".join("?" * len(d))})', tuple(d.values()))
    return cur.lastrowid


def update_film(c, fid, data, only_empty=False):
    """Felder setzen. only_empty=True: nur leere Felder fuellen (Aktualisieren von TMDB ueberschreibt nichts Eigenes)."""
    cur = get_film(c, fid)
    if not cur:
        return False
    d = {}
    for k in FILM_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if only_empty and cur[k] not in (None, ''):
            continue
        d[k] = v if v != '' else None
    if 'title' in d:
        if not d['title']:
            d.pop('title')
        else:
            d['sort_title'] = sort_key(d['title'])
    if not d:
        return True
    d['updated_at'] = now()
    c.execute(f'UPDATE films SET {",".join(k + "=?" for k in d)} WHERE id=?', (*d.values(), fid))
    return True


def delete_film(c, fid):
    c.execute('DELETE FROM films WHERE id=?', (fid,))


def parse_date(text):
    """'19.05.1999', '5.1999', '1999', '1999-05-19' -> '1999-05-19' / '1999-05' / '1999'. Leer -> ''. Unlesbar -> None."""
    t = (text or '').strip()
    if not t:
        return ''
    m = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', t) or re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', t)
    if m:
        g = m.groups()
        y, mo, d = (int(g[2]), int(g[1]), int(g[0])) if '.' in t else (int(g[0]), int(g[1]), int(g[2]))
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r'(\d{1,2})[./](\d{4})', t) or re.fullmatch(r'(\d{4})-(\d{1,2})', t)
    if m:
        a, b = m.groups()
        y, mo = (int(b), int(a)) if len(a) <= 2 else (int(a), int(b))
        return f'{y:04d}-{mo:02d}' if 1 <= mo <= 12 and 1900 <= y <= 2100 else None
    if re.fullmatch(r'\d{4}', t) and 1900 <= int(t) <= 2100:
        return t
    return None


def set_watched(c, fid, watched, when=None):
    """watched=True: (noch einmal) gesehen, Anzahl +1, Datum heute oder 'when'; faellt aus "Als Naechstes" heraus.
    False: als ungesehen markieren."""
    if watched:
        c.execute('UPDATE films SET watched=1, watch_count=watch_count+1, watched_at=?, next_at=NULL, updated_at=? WHERE id=?',
                  (when if when is not None else date.today().isoformat(), now(), fid))
    else:
        c.execute('UPDATE films SET watched=0, updated_at=? WHERE id=?', (now(), fid))


def set_next(c, fid, on):
    """Fuer "Als Naechstes" vormerken (on=True) oder davon herunternehmen."""
    c.execute('UPDATE films SET next_at=? WHERE id=?', (now() if on else None, fid))


def set_watched_date(c, fid, when):
    """Nur das Datum aendern (leer = unbekannt); der Film gilt dann als gesehen."""
    c.execute('UPDATE films SET watched=1, watch_count=max(watch_count,1), watched_at=?, next_at=NULL, updated_at=? WHERE id=?',
              (when or None, now(), fid))


def set_rating(c, fid, rating):
    r = int(rating) if str(rating or '').isdigit() and 1 <= int(rating) <= 10 else None
    c.execute('UPDATE films SET rating=?, updated_at=? WHERE id=?', (r, now(), fid))
    return r


def cast_list(row, n=None):
    try:
        cast = json.loads(row['cast_json'] or '[]')
    except Exception:
        cast = []
    return cast[:n] if n else cast


# ---------------------------------------------------------------- Exemplare
def add_copy(c, fid, data):
    d = {k: data.get(k) for k in COPY_FIELDS if data.get(k) not in (None, '')}
    if 'owner_id' not in data:  # Besitzer nur bei physischen Exemplaren, Dateien gehoeren dem Haushalt
        d['owner_id'] = U.current_id() if U.physical_copy(d['kind'], d.get('path')) else None
    d['kind'] = d.get('kind') if d.get('kind') in KINDS else 'dvd'
    d['film_id'] = fid
    d['created_at'] = now()
    cur = c.execute(f'INSERT INTO copies({",".join(d)}) VALUES({",".join("?" * len(d))})', tuple(d.values()))
    return cur.lastrowid


def copies_of(c, fid):
    order = "CASE kind WHEN 'uhd' THEN 0 WHEN 'bluray' THEN 1 WHEN 'dvd' THEN 2 ELSE 3 END"
    return c.execute(f'SELECT * FROM copies WHERE film_id=? ORDER BY {order}, id', (fid,)).fetchall()


def delete_copy(c, cid):
    c.execute('DELETE FROM copies WHERE id=?', (cid,))


def films_by_barcode(c, barcode):
    bc = re.sub(r'\D', '', barcode or '').lstrip('0')
    if not bc:
        return []
    return c.execute("SELECT DISTINCT f.* FROM films f JOIN copies k ON k.film_id=f.id WHERE ltrim(k.barcode,'0')=?", (bc,)).fetchall()


def known_paths(c):
    return {r[0] for r in c.execute('SELECT path FROM copies WHERE path IS NOT NULL')}


# ---------------------------------------------------------------- Listen
def lists_all(c):
    return c.execute('SELECT l.*, (SELECT count(*) FROM list_items i WHERE i.list_id=l.id) AS n FROM lists l ORDER BY l.name COLLATE NOCASE').fetchall()


def create_list(c, name):
    name = (name or '').strip()[:80]
    if not name:
        return None
    row = c.execute('SELECT id FROM lists WHERE name=?', (name,)).fetchone()
    if row:
        return row['id']
    return c.execute('INSERT INTO lists(name, created_at) VALUES(?,?)', (name, now())).lastrowid


def rename_list(c, lid, name):
    name = (name or '').strip()[:80]
    if name and not c.execute('SELECT 1 FROM lists WHERE name=? AND id<>?', (name, lid)).fetchone():
        c.execute('UPDATE lists SET name=? WHERE id=?', (name, lid))
        return True
    return False


def delete_list(c, lid):
    c.execute('DELETE FROM lists WHERE id=?', (lid,))


def set_in_list(c, lid, fid, on):
    if on:
        c.execute('INSERT OR IGNORE INTO list_items(list_id, film_id, added_at) VALUES(?,?,?)', (lid, fid, now()))
    else:
        c.execute('DELETE FROM list_items WHERE list_id=? AND film_id=?', (lid, fid))


def lists_of(c, fid):
    return {r[0] for r in c.execute('SELECT list_id FROM list_items WHERE film_id=?', (fid,))}


# ---------------------------------------------------------------- Ansichten / Suche
VIEWS = ['all', 'next', 'unseen', 'mustsee', 'favorites', 'recent_watched', 'recent_added']
SORTS = {
    'title': 'f.sort_title {d}, f.year',
    'year': 'f.year IS NULL, f.year {d}, f.sort_title',
    'rating': 'f.rating IS NULL, f.rating {d}, f.sort_title',
    'added': 'f.created_at {d}',
    'watched_at': 'f.watched_at IS NULL, f.watched_at {d}, f.sort_title',
    'runtime': 'f.runtime IS NULL, f.runtime {d}, f.sort_title',
}
# feste Reihenfolge und Grenze fuer bestimmte Ansichten
VIEW_RULES = {
    'next': ('f.next_at IS NOT NULL', 'f.next_at, f.sort_title', None),
    'unseen': ('f.watched=0', None, None),
    'mustsee': ('f.watched=0 AND f.rating IS NOT NULL', 'f.rating DESC, f.sort_title', 10),
    'favorites': ('f.watched=1 AND f.rating>=9', 'f.rating DESC, f.sort_title', None),
    'recent_watched': ('f.watched=1 AND f.watched_at IS NOT NULL', 'f.watched_at DESC, f.updated_at DESC', 50),
    'recent_added': ('1=1', 'f.created_at DESC, f.id DESC', 50),
}


def fts_expr(q):
    toks = [t for t in (q or '').split() if t]
    long = [t for t in toks if len(t) >= 3]
    short = [t for t in toks if len(t) < 3]
    return (' AND '.join('"' + t.replace('"', '""') + '"' for t in long) if long else ''), short


LETTER_SQL = "CASE WHEN substr(f.sort_title,1,1) BETWEEN 'a' AND 'z' THEN upper(substr(f.sort_title,1,1)) ELSE '#' END"


def query(c, view='all', q='', genre='', decade='', kind='', sort='title', direction='asc', list_id=None,
          collection_id=None, limit=120, offset=0, letter='', owner=(False, None)):
    where, args = [], []
    if owner[0]:  # Besitzer (seit 1.21): mindestens ein Exemplar gehoert ihm; None = Haushalt
        where.append('EXISTS (SELECT 1 FROM copies k WHERE k.film_id=f.id AND k.owner_id IS ?)')
        args.append(owner[1])
    if letter and (letter == '#' or (len(letter) == 1 and 'A' <= letter <= 'Z')):
        where.append(f'{LETTER_SQL}=?')
        args.append(letter)
    order = SORTS.get(sort, SORTS['title']).format(d='DESC' if direction == 'desc' else 'ASC')
    fixed_limit = None
    if view in VIEW_RULES:
        cond, vorder, fixed_limit = VIEW_RULES[view]
        where.append(cond)
        if vorder:
            order = vorder
    if list_id:
        where.append('f.id IN (SELECT film_id FROM list_items WHERE list_id=?)')
        args.append(list_id)
    if collection_id:
        where.append('f.collection_id=?')
        args.append(collection_id)
        if sort == 'title':
            order = 'f.release_date IS NULL, f.release_date, f.year'
    expr, short = fts_expr(q)
    if expr:
        where.append(f'f.id IN (SELECT rowid FROM {FTS} WHERE {FTS} MATCH ?)')
        args.append(expr)
    for t in short:
        where.append("(f.title LIKE ? OR f.original_title LIKE ?)")
        args += [f'%{t}%', f'%{t}%']
    if genre:
        where.append("(', '||coalesce(f.genres,'')||',') LIKE ?")
        args.append(f'%, {genre},%')
    if decade and str(decade).isdigit():
        d0 = int(decade)
        where.append('f.year BETWEEN ? AND ?')
        args += [d0, d0 + 9]
    if kind in KINDS:
        where.append('EXISTS (SELECT 1 FROM copies k WHERE k.film_id=f.id AND k.kind=?)')
        args.append(kind)
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    total = c.execute(f'SELECT count(*) FROM films f {w}', args).fetchone()[0]
    if fixed_limit:
        total = min(total, fixed_limit)
        lim, off = fixed_limit, 0
    else:
        lim, off = limit, offset
    rows = c.execute(f"""SELECT f.*, (SELECT group_concat(DISTINCT k.kind) FROM copies k WHERE k.film_id=f.id) AS kinds,
                         (SELECT k.resolution FROM copies k WHERE k.film_id=f.id AND k.resolution IS NOT NULL
                          ORDER BY CAST(rtrim(k.resolution,'pi') AS INTEGER) DESC LIMIT 1) AS res
                         FROM films f {w} ORDER BY {order} LIMIT ? OFFSET ?""", (*args, lim, off)).fetchall()
    return rows, total


def view_counts(c):
    out = {'all': c.execute('SELECT count(*) FROM films').fetchone()[0]}
    for v, (cond, _, lim) in VIEW_RULES.items():
        n = c.execute(f'SELECT count(*) FROM films f WHERE {cond}').fetchone()[0]
        out[v] = min(n, lim) if lim else n
    return out


def genres(c):
    seen = {}
    for (g,) in c.execute("SELECT genres FROM films WHERE genres IS NOT NULL AND genres<>''"):
        for x in g.split(','):
            x = x.strip()
            if x:
                seen[x] = seen.get(x, 0) + 1
    return sorted(seen.items(), key=lambda kv: kv[0].lower())


def decades(c):
    return [r[0] for r in c.execute('SELECT DISTINCT (year/10)*10 FROM films WHERE year IS NOT NULL ORDER BY 1 DESC')]


def collections(c):
    return c.execute("""SELECT collection_id AS id, collection_name AS name, count(*) AS n, min(year) AS first,
                        sum(watched) AS seen, max(poster) AS poster FROM films WHERE collection_id IS NOT NULL
                        GROUP BY collection_id ORDER BY collection_name COLLATE NOCASE""").fetchall()


def stats(c):
    r = c.execute('SELECT count(*), sum(watched), sum(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) FROM films').fetchone()
    k = dict(c.execute('SELECT kind, count(*) FROM copies GROUP BY kind').fetchall())
    return {'films': r[0] or 0, 'watched': r[1] or 0, 'rated': r[2] or 0, 'kinds': k}


# ---------------------------------------------------------------- Personen (Besetzung, Regie, Drehbuch)
ROLES = ('cast', 'director', 'writer')


def set_film_people(c, fid, people):
    """Personen eines Films neu setzen. people: [{'id','name','profile_path','role','character','ord'}] (von TMDB)."""
    c.execute('DELETE FROM film_people WHERE film_id=?', (fid,))
    for p in people or []:
        if not p.get('id') or p.get('role') not in ROLES:
            continue
        c.execute('INSERT INTO people(id, name, profile_path) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, '
                  'profile_path=coalesce(excluded.profile_path, people.profile_path)', (p['id'], p.get('name') or '?', p.get('profile_path')))
        c.execute('INSERT OR IGNORE INTO film_people(film_id, person_id, role, character, ord) VALUES(?,?,?,?,?)',
                  (fid, p['id'], p['role'], p.get('character') or None, p.get('ord')))


def people_of(c, fid):
    """{'cast': [...], 'director': [...], 'writer': [...]} mit id, name, character."""
    out = {r: [] for r in ROLES}
    for r in c.execute("""SELECT fp.role, fp.character, p.id, p.name FROM film_people fp JOIN people p ON p.id=fp.person_id
                          WHERE fp.film_id=? AND fp.role IN ('cast','director','writer') ORDER BY fp.role, coalesce(fp.ord, 999), p.name""", (fid,)):
        out[r['role']].append({'id': r['id'], 'name': r['name'], 'character': r['character'] or ''})
    return out


def films_without_people(c, limit=None):
    q = 'SELECT id, tmdb_id FROM films f WHERE tmdb_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM film_people fp WHERE fp.film_id=f.id)'
    return c.execute(q + (f' LIMIT {int(limit)}' if limit else '')).fetchall()


def get_person(c, pid):
    return c.execute('SELECT * FROM people WHERE id=?', (pid,)).fetchone()


def save_person(c, pid, d):
    c.execute("""INSERT INTO people(id, name) VALUES(?, ?) ON CONFLICT(id) DO NOTHING""", (pid, d.get('name') or '?'))
    c.execute("""UPDATE people SET name=?, profile_path=?, biography=?, birthday=?, deathday=?, place=?, department=?, imdb_id=?,
                 credits_json=?, fetched_at=? WHERE id=?""",
              (d.get('name') or '?', d.get('profile_path'), d.get('biography'), d.get('birthday'), d.get('deathday'), d.get('place'),
               d.get('department'), d.get('imdb_id'), json.dumps(d.get('credits') or [], ensure_ascii=False), now(), pid))


def films_with_person(c, pid):
    return c.execute("""SELECT f.*, group_concat(DISTINCT fp.role) AS roles, max(fp.character) AS character,
                        (SELECT group_concat(DISTINCT k.kind) FROM copies k WHERE k.film_id=f.id) AS kinds
                        FROM films f JOIN film_people fp ON fp.film_id=f.id WHERE fp.person_id=? AND fp.role<>'none'
                        GROUP BY f.id ORDER BY f.year IS NULL, f.year DESC, f.sort_title""", (pid,)).fetchall()


def find_people(c, q, limit=8):
    """Personen aus der eigenen Sammlung, deren Name passt (fuer die Suche), mit Anzahl Filme."""
    toks = [t for t in (q or '').split() if t]
    if not toks:
        return []
    where = ' AND '.join('p.name LIKE ?' for _ in toks)
    return c.execute(f"""SELECT p.id, p.name, p.profile, count(DISTINCT fp.film_id) AS n FROM people p
                         JOIN film_people fp ON fp.person_id=p.id WHERE p.id>0 AND {where}
                         GROUP BY p.id ORDER BY n DESC, p.name LIMIT ?""", (*[f'%{t}%' for t in toks], limit)).fetchall()


def letter_counts(c):
    """Anzahl Filme je Anfangsbuchstabe (ohne Artikel), '#' fuer Zahlen und Sonderzeichen."""
    return dict(c.execute(f'SELECT {LETTER_SQL}, count(*) FROM films f GROUP BY 1').fetchall())
