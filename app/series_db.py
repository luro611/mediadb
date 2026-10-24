"""Seriendatenbank (data/serien.db), eigene Datei wie Musik und Filme. Eingebautes sqlite3, ohne Zusatzpakete testbar.

Tabellen:
  series       eine Serie (Daten von TMDB oder von Hand), eigene Bewertung, Notiz
  seasons      Staffeln laut TMDB (Name, Ausstrahlung, Anzahl Folgen)
  episodes     Episodenfuehrer laut TMDB: jede Folge mit Titel, Inhalt, Ausstrahlungsdatum
  ep_files     vorhandene Videodateien, je Datei Staffel/Folge (auch Doppelfolgen) und Technikdaten
  copies       DVD-/Blu-ray-Boxen mit Barcode und den enthaltenen Staffeln
  watched      gesehene Folgen (pro Haushalt)
  series_people, people  Besetzung und Serienschoepfer (TMDB-Personennummern, wie bei den Filmen)
Volltextsuche search_series_v1 per Trigger.
"""
import json, re, sqlite3, threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from .films_db import sort_key, now, parse_date  # gemeinsame Hilfsfunktionen
from . import users as U

DB_PATH = None
KINDS = {'dvd': 'DVD', 'bluray': 'Blu-ray', 'uhd': '4K UHD'}
STATUS = {'Returning Series': 'Läuft noch', 'Ended': 'Beendet', 'Canceled': 'Abgesetzt', 'In Production': 'In Produktion',
          'Planned': 'Geplant', 'Pilot': 'Pilot'}
FTS = 'search_series_v1'
_init_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS series(
  id INTEGER PRIMARY KEY, tmdb_id INTEGER UNIQUE, imdb_id TEXT, tvdb_id INTEGER, title TEXT NOT NULL, sort_title TEXT,
  original_title TEXT, year INTEGER, first_air_date TEXT, last_air_date TEXT, status TEXT, networks TEXT, genres TEXT,
  creators TEXT, overview TEXT, tagline TEXT, countries TEXT, original_language TEXT, certification TEXT, episode_runtime INTEGER,
  number_of_seasons INTEGER, number_of_episodes INTEGER, poster TEXT, backdrop TEXT, trailer_url TEXT, tmdb_rating REAL,
  tmdb_votes INTEGER, keywords TEXT, rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 10), notes TEXT, source TEXT,
  guide_at TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS seasons(
  id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE, season INTEGER NOT NULL,
  name TEXT, overview TEXT, air_date TEXT, episode_count INTEGER, poster_path TEXT, UNIQUE(series_id, season));
CREATE TABLE IF NOT EXISTS episodes(
  id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE, season INTEGER NOT NULL,
  episode INTEGER NOT NULL, name TEXT, overview TEXT, air_date TEXT, runtime INTEGER, UNIQUE(series_id, season, episode));
CREATE TABLE IF NOT EXISTS ep_files(
  id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE, season INTEGER, episode INTEGER,
  episode_end INTEGER, title_hint TEXT, path TEXT UNIQUE, container TEXT, resolution TEXT, video_codec TEXT, hdr TEXT,
  duration_s INTEGER, audio TEXT, subtitles TEXT, size_bytes INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS copies(
  id INTEGER PRIMARY KEY, series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE, kind TEXT NOT NULL,
  barcode TEXT, edition TEXT, seasons TEXT, notes TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS watched(
  series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE, season INTEGER NOT NULL, episode INTEGER NOT NULL,
  watched_at TEXT, PRIMARY KEY(series_id, season, episode));
CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT NOT NULL, profile_path TEXT);
CREATE TABLE IF NOT EXISTS series_people(
  series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE, person_id INTEGER NOT NULL REFERENCES people(id),
  role TEXT NOT NULL, character TEXT, episodes INTEGER, ord INTEGER, PRIMARY KEY(series_id, person_id, role));
CREATE TABLE IF NOT EXISTS barcode_cache(barcode TEXT PRIMARY KEY, title TEXT, fetched_at TEXT);
CREATE INDEX IF NOT EXISTS ix_ep_series ON episodes(series_id, season);
CREATE INDEX IF NOT EXISTS ix_files_series ON ep_files(series_id, season, episode);
CREATE INDEX IF NOT EXISTS ix_copies_series ON copies(series_id);
CREATE INDEX IF NOT EXISTS ix_copies_barcode ON copies(barcode);
CREATE INDEX IF NOT EXISTS ix_series_sort ON series(sort_title);
CREATE INDEX IF NOT EXISTS ix_sp_person ON series_people(person_id);
"""
_BODY = ("coalesce(s.title,'')||' | '||coalesce(s.original_title,'')||' | '||coalesce(s.year,'')||' | '||coalesce(s.genres,'')"
         "||' | '||coalesce(s.creators,'')||' | '||coalesce(s.networks,'')||' | '||coalesce(s.keywords,'')||' | '||coalesce(s.notes,'')"
         "||' | '||coalesce(s.providers,'')||' | '||coalesce(s.providers_own,'')"
         "||' | '||coalesce((SELECT group_concat(p.name||' '||coalesce(sp.character,''),' ') FROM series_people sp JOIN people p ON p.id=sp.person_id WHERE sp.series_id=s.id),'')"
         "||' | '||coalesce((SELECT group_concat(coalesce(c.barcode,''),' ') FROM copies c WHERE c.series_id=s.id),'')")
_REFRESH = f"DELETE FROM {FTS} WHERE rowid=X; INSERT INTO {FTS}(rowid, body) SELECT s.id, {_BODY} FROM series s WHERE s.id=X;"
TRIGGERS = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS} USING fts5(body, tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS series_ai AFTER INSERT ON series BEGIN {_REFRESH.replace('X', 'NEW.id')} END;
CREATE TRIGGER IF NOT EXISTS series_au AFTER UPDATE ON series BEGIN {_REFRESH.replace('X', 'NEW.id')} END;
CREATE TRIGGER IF NOT EXISTS series_ad AFTER DELETE ON series BEGIN DELETE FROM {FTS} WHERE rowid=OLD.id; END;
CREATE TRIGGER IF NOT EXISTS sp_ai AFTER INSERT ON series_people BEGIN {_REFRESH.replace('X', 'NEW.series_id')} END;
CREATE TRIGGER IF NOT EXISTS scopies_ai AFTER INSERT ON copies BEGIN {_REFRESH.replace('X', 'NEW.series_id')} END;
CREATE TRIGGER IF NOT EXISTS scopies_ad AFTER DELETE ON copies BEGIN {_REFRESH.replace('X', 'OLD.series_id')} END;
"""
SERIES_FIELDS = ['tmdb_id', 'imdb_id', 'tvdb_id', 'title', 'original_title', 'year', 'first_air_date', 'last_air_date', 'status',
                 'networks', 'genres', 'creators', 'overview', 'tagline', 'countries', 'original_language', 'certification',
                 'episode_runtime', 'number_of_seasons', 'number_of_episodes', 'poster', 'backdrop', 'trailer_url', 'tmdb_rating',
                 'tmdb_votes', 'keywords', 'notes', 'source', 'guide_at', 'providers', 'providers_buy', 'providers_link',
                 'providers_at', 'providers_own', 'next_air_date', 'next_season', 'next_episode']
NEW_COLUMNS = {'providers': 'TEXT', 'providers_buy': 'TEXT', 'providers_link': 'TEXT', 'providers_at': 'TEXT',
               'providers_own': 'TEXT', 'next_air_date': 'TEXT', 'next_season': 'INTEGER', 'next_episode': 'INTEGER', 'next_at': 'TEXT'}
SCHEMA_VERSION = 2  # 2: Streamingdienste und naechste Folge (1.4)
FILE_FIELDS = ['season', 'episode', 'episode_end', 'title_hint', 'path', 'container', 'resolution', 'video_codec', 'hdr',
               'duration_s', 'audio', 'subtitles', 'size_bytes']


def init(path):
    global DB_PATH, _ready
    DB_PATH, _ready = Path(path), False
    with _init_lock, db() as c:
        c.executescript(SCHEMA)
        have = {r[1] for r in c.execute('PRAGMA table_info(series)')}
        for col, typ in NEW_COLUMNS.items():
            if col not in have:
                c.execute(f'ALTER TABLE series ADD COLUMN {col} {typ}')
        U.add_owner_column(c, 'copies')  # seit 1.21: Besitzer
        U.personal_table(c, 'series', 'series_user', 'series_id', PERSONAL)  # seit 1.22: Bewertung, Als Naechstes und gesehene Folgen pro Person
        c.execute('CREATE TABLE IF NOT EXISTS watched_user(user_id INTEGER NOT NULL, series_id INTEGER NOT NULL, season INTEGER NOT NULL, '
                  'episode INTEGER NOT NULL, watched_at TEXT, PRIMARY KEY(user_id, series_id, season, episode))')
        old = c.execute('PRAGMA user_version').fetchone()[0]
        if old < SCHEMA_VERSION:  # Suchtext hat sich geaendert: Trigger neu anlegen, Index neu fuellen
            for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
                c.execute(f'DROP TRIGGER IF EXISTS "{name}"')
            c.execute(f'DROP TABLE IF EXISTS {FTS}')
            c.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        c.executescript(TRIGGERS)
        if c.execute(f'SELECT count(*) FROM {FTS}').fetchone()[0] != c.execute('SELECT count(*) FROM series').fetchone()[0]:
            c.execute(f'DELETE FROM {FTS}')
            c.execute(f'INSERT INTO {FTS}(rowid, body) SELECT s.id, {_BODY} FROM series s')
    _ready = True


# seit 1.22: persoenliche Werte (siehe users.personalize)
PERSONAL = {'rating': 'NULL', 'next_at': 'NULL'}
SPECS = [('personal', 'series', 'series_user', 'series_id', PERSONAL, [('watched_user', 'series_id')]),
         ('set', 'watched', 'watched_user', ['series_id', 'season', 'episode'], ['watched_at']), ('rows', 'watch')]
_ready = False


@contextmanager
def db(plain=False):
    """plain=True: ohne persoenliche Sichten (Aufbau der Tabellen beim Start)."""
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    if _ready and not plain:
        U.personalize(c, 'series', SPECS)
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def today():
    return date.today().isoformat()


# ---------------------------------------------------------------- Serien
def get(c, sid):
    return c.execute('SELECT * FROM series WHERE id=?', (sid,)).fetchone()


def by_tmdb(c, tmdb_id):
    return c.execute('SELECT * FROM series WHERE tmdb_id=?', (tmdb_id,)).fetchone() if tmdb_id else None


def insert(c, data):
    d = {k: data.get(k) for k in SERIES_FIELDS if data.get(k) not in (None, '')}
    d['title'] = (data.get('title') or 'Ohne Titel').strip()
    d['sort_title'] = sort_key(d['title'])
    d['created_at'] = d['updated_at'] = now()
    return c.execute(f'INSERT INTO main.series({",".join(d)}) VALUES({",".join("?" * len(d))})', tuple(d.values())).lastrowid


def update(c, sid, data, only_empty=False):
    cur = get(c, sid)
    if not cur:
        return False
    d = {}
    for k in SERIES_FIELDS:
        if k in data and not (only_empty and cur[k] not in (None, '')):
            d[k] = data[k] if data[k] != '' else None
    if d.get('title'):
        d['sort_title'] = sort_key(d['title'])
    elif 'title' in d:
        d.pop('title')
    if d:
        d['updated_at'] = now()
        c.execute(f'UPDATE series SET {",".join(k + "=?" for k in d)} WHERE id=?', (*d.values(), sid))
    return True


def delete(c, sid):
    c.execute('DELETE FROM series WHERE id=?', (sid,))


def set_rating(c, sid, rating):
    r = int(rating) if str(rating or '').isdigit() and 1 <= int(rating) <= 10 else None
    c.execute('UPDATE series SET rating=?, updated_at=? WHERE id=?', (r, now(), sid))


# ---------------------------------------------------------------- Episodenfuehrer
def set_guide(c, sid, seasons, episodes):
    """Staffeln und Folgen laut TMDB neu setzen (gesehen und Dateien bleiben, sie haengen an Staffel/Folge-Nummern)."""
    c.execute('DELETE FROM seasons WHERE series_id=?', (sid,))
    c.execute('DELETE FROM episodes WHERE series_id=?', (sid,))
    for s in seasons:
        c.execute('INSERT INTO seasons(series_id, season, name, overview, air_date, episode_count, poster_path) VALUES(?,?,?,?,?,?,?)',
                  (sid, s['season'], s.get('name'), s.get('overview'), s.get('air_date'), s.get('episode_count'), s.get('poster_path')))
    for e in episodes:
        c.execute('INSERT OR REPLACE INTO episodes(series_id, season, episode, name, overview, air_date, runtime) VALUES(?,?,?,?,?,?,?)',
                  (sid, e['season'], e['episode'], e.get('name'), e.get('overview'), e.get('air_date'), e.get('runtime')))
    c.execute('UPDATE series SET guide_at=? WHERE id=?', (now(), sid))


def upsert_guide(c, sid, seasons, episodes, only_seasons):
    """Nur die angegebenen Staffeln neu setzen (fuer die regelmaessige Aktualisierung laufender Serien).
    Staffel-Kopfzeilen werden alle aktualisiert, damit neu angekuendigte Staffeln erscheinen."""
    for s in seasons:
        c.execute('''INSERT INTO seasons(series_id, season, name, overview, air_date, episode_count, poster_path) VALUES(?,?,?,?,?,?,?)
                     ON CONFLICT(series_id, season) DO UPDATE SET name=excluded.name, overview=excluded.overview, air_date=excluded.air_date,
                     episode_count=excluded.episode_count, poster_path=excluded.poster_path''',
                  (sid, s['season'], s.get('name'), s.get('overview'), s.get('air_date'), s.get('episode_count'), s.get('poster_path')))
    for se in only_seasons:
        c.execute('DELETE FROM episodes WHERE series_id=? AND season=?', (sid, se))
    for e in episodes:
        if e['season'] in only_seasons:
            c.execute('INSERT OR REPLACE INTO episodes(series_id, season, episode, name, overview, air_date, runtime) VALUES(?,?,?,?,?,?,?)',
                      (sid, e['season'], e['episode'], e.get('name'), e.get('overview'), e.get('air_date'), e.get('runtime')))
    c.execute('UPDATE series SET guide_at=? WHERE id=?', (now(), sid))


def upcoming(c, days=120, recent=30):
    """Neue Folgen und Staffeln der eigenen Serien: (demnaechst, gerade erschienen, angekuendigt ohne Termin)."""
    t = today()
    from datetime import date as _d, timedelta
    until = (_d.fromisoformat(t) + timedelta(days=days)).isoformat()
    since = (_d.fromisoformat(t) - timedelta(days=recent)).isoformat()
    cols = 's.id, s.title, s.year, s.poster, s.status, s.networks, s.providers, s.providers_own'
    soon = [dict(r) for r in c.execute(f'''SELECT {cols}, e.season, e.episode, e.name AS ep_name, e.air_date,
              (SELECT count(*) FROM episodes x WHERE x.series_id=s.id AND x.season=e.season) AS n_eps,
              (SELECT min(x.episode) FROM episodes x WHERE x.series_id=s.id AND x.season=e.season) AS first_ep
              FROM episodes e JOIN series s ON s.id=e.series_id
              WHERE e.season>0 AND e.air_date>? AND e.air_date<=? AND e.air_date=(SELECT min(y.air_date) FROM episodes y
                    WHERE y.series_id=e.series_id AND y.season>0 AND y.air_date>?)
              GROUP BY s.id ORDER BY e.air_date, s.sort_title''', (t, until, t))]
    new = [dict(r) for r in c.execute(f'''SELECT {cols}, e.season, min(e.episode) AS episode, max(e.air_date) AS air_date, count(*) AS n_new,
              (SELECT count(*) FROM episodes x WHERE x.series_id=s.id AND x.season=e.season) AS n_eps
              FROM episodes e JOIN series s ON s.id=e.series_id
              WHERE e.season>0 AND e.air_date>=? AND e.air_date<=? GROUP BY s.id, e.season ORDER BY max(e.air_date) DESC''', (since, t))]
    announced = [dict(r) for r in c.execute(f'''SELECT {cols}, se.season, se.air_date, se.name AS season_name FROM seasons se JOIN series s ON s.id=se.series_id
              WHERE se.season>0 AND (se.air_date IS NULL OR se.air_date>?) AND NOT EXISTS (SELECT 1 FROM episodes e WHERE e.series_id=se.series_id
                    AND e.season=se.season AND e.air_date IS NOT NULL AND e.air_date<=?)
                AND NOT EXISTS (SELECT 1 FROM episodes e WHERE e.series_id=se.series_id AND e.season=se.season AND e.air_date>? AND e.air_date<=?)
              ORDER BY se.air_date IS NULL, se.air_date, s.sort_title''', (t, t, t, until))]
    return soon, new, announced


def providers_all(c):
    """Alle vorkommenden Streamingdienste mit Anzahl Serien (fuer den Filter)."""
    seen = {}
    for (p,) in c.execute("SELECT coalesce(nullif(providers_own,''), providers) FROM series WHERE coalesce(nullif(providers_own,''), providers) IS NOT NULL"):
        for x in p.split(','):
            x = x.strip()
            if x:
                seen[x] = seen.get(x, 0) + 1
    return sorted(seen.items(), key=lambda kv: (-kv[1], kv[0].lower()))


def parse_seasons(text):
    """'1-3', '1, 2, 4', 'komplett' -> Menge der Staffeln ({-1} = alle)."""
    t = (text or '').strip().lower()
    if not t:
        return set()
    if re.search(r'komplett|complete|gesamt|alle|all', t):
        return {-1}
    out = set()
    for a, b in re.findall(r'(\d+)\s*(?:-|–|bis|to)\s*(\d+)', t):
        out |= set(range(int(a), int(b) + 1))
    t = re.sub(r'(\d+)\s*(?:-|–|bis|to)\s*(\d+)', ' ', t)
    out |= {int(x) for x in re.findall(r'\d+', t)}
    return out


def have_map(c, sid):
    """{(staffel, folge): {'files': [...], 'disc': True/False}} fuer alles, was vorhanden ist."""
    have = {}
    for f in c.execute('SELECT * FROM ep_files WHERE series_id=? AND season IS NOT NULL AND episode IS NOT NULL', (sid,)):
        for e in range(f['episode'], (f['episode_end'] or f['episode']) + 1):
            have.setdefault((f['season'], e), {'files': [], 'disc': False})['files'].append(dict(f))
    disc_seasons = set()
    for k in c.execute('SELECT seasons FROM copies WHERE series_id=?', (sid,)):
        disc_seasons |= parse_seasons(k['seasons'])
    if disc_seasons:
        for e in c.execute('SELECT season, episode FROM episodes WHERE series_id=?', (sid,)):
            if -1 in disc_seasons or e['season'] in disc_seasons:
                have.setdefault((e['season'], e['episode']), {'files': [], 'disc': False})['disc'] = True
    return have


def overview(c, sid, specials=False, upto=None):
    """Staffeln mit Folgen und Zustand: vorhanden (Datei/Disc), fehlt, noch nicht ausgestrahlt, gesehen.
    Gibt (staffeln, summen) zurueck. Specials (Staffel 0) zaehlen nur mit specials=True zu 'fehlt'."""
    upto = upto or today()
    have = have_map(c, sid)
    seen = {(r['season'], r['episode']): r['watched_at'] for r in c.execute('SELECT * FROM watched WHERE series_id=?', (sid,))}
    seasons = {r['season']: dict(r, episodes=[]) for r in c.execute('SELECT * FROM seasons WHERE series_id=? ORDER BY season', (sid,))}
    tot = {'aired': 0, 'have': 0, 'missing': 0, 'upcoming': 0, 'seen': 0, 'extra': 0}
    for e in c.execute('SELECT * FROM episodes WHERE series_id=? ORDER BY season, episode', (sid,)):
        key = (e['season'], e['episode'])
        h = have.get(key)
        aired = bool(e['air_date']) and e['air_date'] <= upto
        if h and not aired and not h.get('files'):  # eine Box kann keine noch nicht ausgestrahlte Folge enthalten
            h = None
        state = 'have' if h else ('missing' if aired else 'upcoming')
        item = dict(e, state=state, files=(h or {}).get('files', []), disc=(h or {}).get('disc', False), seen=key in seen,
                    seen_at=seen.get(key), aired=aired)
        seasons.setdefault(e['season'], {'season': e['season'], 'name': None, 'episodes': []})['episodes'].append(item)
        if e['season'] == 0 and not specials:
            continue
        if aired or h:
            tot['aired'] += 1 if aired else 0
            tot['have'] += 1 if h and aired else 0
            tot['missing'] += 1 if state == 'missing' else 0
        else:
            tot['upcoming'] += 1
        tot['seen'] += 1 if key in seen else 0
    known = {(e['season'], e['episode']) for s in seasons.values() for e in s['episodes']}
    extra = sorted(k for k in have if k not in known)  # Dateien zu Folgen, die TMDB nicht kennt
    tot['extra'] = len(extra)
    for key in extra:  # trotzdem als Folge anzeigen (Serie ohne TMDB, Folge fehlt im Episodenfuehrer)
        h = have[key]
        if not h['files']:
            continue
        hint = next((f['title_hint'] for f in h['files'] if f.get('title_hint')), None)
        item = {'series_id': sid, 'season': key[0], 'episode': key[1], 'name': hint, 'overview': None, 'air_date': None, 'runtime': None,
                'state': 'have', 'files': h['files'], 'disc': False, 'seen': key in seen, 'seen_at': seen.get(key), 'aired': False, 'unlisted': True}
        s = seasons.setdefault(key[0], {'season': key[0], 'name': None, 'episodes': []})
        s['episodes'].append(item)
        s['episodes'].sort(key=lambda x: x['episode'])
        if key[0] != 0 or specials:
            tot['seen'] += 1 if key in seen else 0
    for s in seasons.values():
        eps = s['episodes']
        s['n_aired'] = sum(1 for e in eps if e['aired'])
        s['n_have'] = sum(1 for e in eps if e['state'] == 'have' and e['aired'])
        s['n_files'] = sum(1 for e in eps if e['files'])
        s['n_unlisted'] = sum(1 for e in eps if e.get('unlisted'))
        s['n_missing'] = sum(1 for e in eps if e['state'] == 'missing')
        s['n_seen'] = sum(1 for e in eps if e['seen'])
        s['complete'] = s['n_aired'] > 0 and s['n_missing'] == 0
        s['absent'] = s['n_aired'] > 0 and s['n_have'] == 0
    order = sorted(seasons.values(), key=lambda s: (s['season'] == 0, s['season']))
    return order, dict(tot, extra_list=extra)


def next_up(c, sid):
    """Naechste ungesehene, schon ausgestrahlte Folge nach der zuletzt gesehenen."""
    last = c.execute('SELECT season, episode FROM watched WHERE series_id=? AND season>0 ORDER BY season DESC, episode DESC LIMIT 1', (sid,)).fetchone()
    q = 'SELECT * FROM episodes e WHERE series_id=? AND season>0 AND air_date<=? AND NOT EXISTS (SELECT 1 FROM watched w WHERE w.series_id=e.series_id AND w.season=e.season AND w.episode=e.episode)'
    args = [sid, today()]
    if last:
        q += ' AND (season>? OR (season=? AND episode>?))'
        args += [last['season'], last['season'], last['episode']]
    return c.execute(q + ' ORDER BY season, episode LIMIT 1', args).fetchone()


def set_watched(c, sid, season, episode, on, when=None):
    if on:
        c.execute('INSERT OR REPLACE INTO watched(series_id, season, episode, watched_at) VALUES(?,?,?,?)',
                  (sid, season, episode, when if when is not None else today()))
    else:
        c.execute('DELETE FROM watched WHERE series_id=? AND season=? AND episode=?', (sid, season, episode))


def set_next(c, sid, on):
    """Fuer "Als Naechstes" vormerken (on=True) oder davon herunternehmen."""
    c.execute('UPDATE series SET next_at=? WHERE id=?', (now() if on else None, sid))


def drop_next_if_caught_up(c, sid):
    """Nach "gesehen": Ist keine ausgestrahlte Folge mehr offen, faellt die Serie aus "Als Naechstes" heraus."""
    if not next_up(c, sid) and c.execute('SELECT 1 FROM watched WHERE series_id=? AND season>0 LIMIT 1', (sid,)).fetchone():
        set_next(c, sid, False)


def set_season_watched(c, sid, season, on, only_aired=True):
    eps = [dict(e) for e in c.execute('SELECT episode, air_date FROM episodes WHERE series_id=? AND season=?', (sid, season))]
    listed = {e['episode'] for e in eps}
    for (s, ep), h in have_map(c, sid).items():  # Folgen, die nur als Datei bekannt sind
        if s == season and ep not in listed and h['files']:
            eps.append({'episode': ep, 'air_date': '0000'})
    if not eps and not on:  # beim Zuruecksetzen alles der Staffel loeschen
        c.execute('DELETE FROM watched WHERE series_id=? AND season=?', (sid, season))
    for e in eps:
        if on and only_aired and not (e['air_date'] and e['air_date'] <= today()):
            continue
        if on:
            c.execute('INSERT OR IGNORE INTO watched(series_id, season, episode, watched_at) VALUES(?,?,?,?)', (sid, season, e['episode'], today()))
        else:
            c.execute('DELETE FROM watched WHERE series_id=? AND season=? AND episode=?', (sid, season, e['episode']))


# ---------------------------------------------------------------- Dateien und Boxen
def add_file(c, sid, data):
    d = {k: data.get(k) for k in FILE_FIELDS if data.get(k) not in (None, '')}
    d['series_id'] = sid
    d['created_at'] = now()
    return c.execute(f'INSERT OR IGNORE INTO ep_files({",".join(d)}) VALUES({",".join("?" * len(d))})', tuple(d.values())).lastrowid


def known_paths(c):
    return {r[0] for r in c.execute('SELECT path FROM ep_files')}


def add_copy(c, sid, data):
    kind = data.get('kind') if data.get('kind') in KINDS else 'dvd'
    return c.execute('INSERT INTO copies(series_id, kind, barcode, edition, seasons, notes, owner_id, created_at) VALUES(?,?,?,?,?,?,?,?)',
                     (sid, kind, data.get('barcode') or None, data.get('edition') or None, data.get('seasons') or None,
                      data.get('notes') or None, data['owner_id'] if 'owner_id' in data else U.current_id(), now())).lastrowid


def copies_of(c, sid):
    return c.execute('SELECT * FROM copies WHERE series_id=? ORDER BY id', (sid,)).fetchall()


def series_by_barcode(c, barcode):
    bc = re.sub(r'\D', '', barcode or '').lstrip('0')
    return c.execute("SELECT DISTINCT s.* FROM series s JOIN copies k ON k.series_id=s.id WHERE ltrim(k.barcode,'0')=?", (bc,)).fetchall() if bc else []


# ---------------------------------------------------------------- Personen
def set_people(c, sid, people):
    c.execute('DELETE FROM series_people WHERE series_id=?', (sid,))
    for p in people or []:
        if not p.get('id') or p.get('role') not in ('cast', 'creator'):
            continue
        c.execute('INSERT INTO people(id, name, profile_path) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name',
                  (p['id'], p.get('name') or '?', p.get('profile_path')))
        c.execute('INSERT OR IGNORE INTO series_people(series_id, person_id, role, character, episodes, ord) VALUES(?,?,?,?,?,?)',
                  (sid, p['id'], p['role'], p.get('character') or None, p.get('episodes'), p.get('ord')))


def people_of(c, sid):
    out = {'cast': [], 'creator': []}
    for r in c.execute("""SELECT sp.role, sp.character, sp.episodes, p.id, p.name FROM series_people sp JOIN people p ON p.id=sp.person_id
                          WHERE sp.series_id=? ORDER BY sp.role, coalesce(sp.ord, 999)""", (sid,)):
        out[r['role']].append({'id': r['id'], 'name': r['name'], 'character': r['character'] or '', 'episodes': r['episodes']})
    return out


def series_with_person(c, pid):
    return c.execute("""SELECT s.*, group_concat(DISTINCT sp.role) AS roles, max(sp.character) AS character FROM series s
                        JOIN series_people sp ON sp.series_id=s.id WHERE sp.person_id=? GROUP BY s.id ORDER BY s.year DESC""", (pid,)).fetchall()


def find_people(c, q, limit=8):
    toks = [t for t in (q or '').split() if t]
    if not toks:
        return []
    where = ' AND '.join('p.name LIKE ?' for _ in toks)
    return c.execute(f"""SELECT p.id, p.name, count(DISTINCT sp.series_id) AS n FROM people p JOIN series_people sp ON sp.person_id=p.id
                         WHERE {where} GROUP BY p.id ORDER BY n DESC LIMIT ?""", (*[f'%{t}%' for t in toks], limit)).fetchall()


# ---------------------------------------------------------------- Uebersicht
VIEWS = ['all', 'next', 'incomplete', 'watching', 'unstarted', 'finished', 'running', 'recent_added']
LETTER_SQL = "CASE WHEN substr(s.sort_title,1,1) BETWEEN 'a' AND 'z' THEN upper(substr(s.sort_title,1,1)) ELSE '#' END"
_AIRED = "(SELECT count(*) FROM episodes e WHERE e.series_id=s.id AND e.season>0 AND e.air_date<=:today)"
_HAVE_FILES = """(SELECT count(DISTINCT e.season||'x'||e.episode) FROM episodes e JOIN ep_files f ON f.series_id=e.series_id AND f.season=e.season
                 AND e.episode BETWEEN f.episode AND coalesce(f.episode_end, f.episode) WHERE e.series_id=s.id AND e.season>0 AND e.air_date<=:today)"""
_SEEN = "(SELECT count(*) FROM watched w WHERE w.series_id=s.id AND w.season>0)"


def query(c, view='all', q='', genre='', letter='', sort='title', direction='asc', limit=120, offset=0, provider='', owner=(False, None)):
    where, args = [], {'today': today()}
    if owner[0]:  # Besitzer (seit 1.21): mindestens eine Box gehoert ihm; None = Haushalt
        where.append('EXISTS (SELECT 1 FROM copies k WHERE k.series_id=s.id AND k.owner_id IS :owner)')
        args['owner'] = owner[1]
    if provider:
        where.append("(', '||coalesce(nullif(s.providers_own,''), s.providers, '')||',') LIKE :prov")
        args['prov'] = f'%, {provider},%'
    if letter and (letter == '#' or (len(letter) == 1 and 'A' <= letter <= 'Z')):
        where.append(f'{LETTER_SQL}=:letter')
        args['letter'] = letter
    toks = [t for t in (q or '').split() if t]
    long = [t for t in toks if len(t) >= 3]
    if long:
        where.append(f's.id IN (SELECT rowid FROM {FTS} WHERE {FTS} MATCH :fts)')
        args['fts'] = ' AND '.join('"' + t.replace('"', '""') + '"' for t in long)
    for i, t in enumerate(x for x in toks if len(x) < 3):
        where.append(f'(s.title LIKE :s{i} OR s.original_title LIKE :s{i})')
        args[f's{i}'] = f'%{t}%'
    if genre:
        where.append("(', '||coalesce(s.genres,'')||',') LIKE :genre")
        args['genre'] = f'%, {genre},%'
    if view == 'next':
        where.append('s.next_at IS NOT NULL')
    elif view == 'watching':
        where.append(f'{_SEEN}>0 AND {_SEEN}<{_AIRED}')
    elif view == 'unstarted':
        where.append(f'{_SEEN}=0')
    elif view == 'finished':
        where.append(f'{_SEEN}>0 AND {_SEEN}>={_AIRED}')
    elif view == 'running':
        where.append("s.status IN ('Returning Series','In Production')")
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    d = 'DESC' if direction == 'desc' else 'ASC'
    order = {'title': f's.sort_title {d}', 'year': f's.year IS NULL, s.year {d}', 'rating': f's.rating IS NULL, s.rating {d}, s.sort_title',
             'added': f's.created_at {d}'}.get(sort, f's.sort_title {d}')
    if view == 'recent_added':
        order = 's.created_at DESC, s.id DESC'
    elif view == 'next':
        order = 's.next_at, s.sort_title'
    copies_all = "EXISTS (SELECT 1 FROM copies k WHERE k.series_id=s.id AND (lower(k.seasons) LIKE '%komplett%' OR lower(k.seasons) LIKE '%complete%'))"
    sql = f"""SELECT s.*, {_AIRED} AS n_aired, {_HAVE_FILES} AS n_files, {_SEEN} AS n_seen,
              (SELECT group_concat(DISTINCT k.kind) FROM copies k WHERE k.series_id=s.id) AS kinds,
              (SELECT count(*) FROM ep_files f WHERE f.series_id=s.id) AS n_filecount,
              (SELECT f.resolution FROM ep_files f WHERE f.series_id=s.id AND f.resolution IS NOT NULL
               ORDER BY CAST(rtrim(f.resolution,'pi') AS INTEGER) DESC LIMIT 1) AS res, {copies_all} AS disc_all
              FROM series s {w} ORDER BY {order}"""
    rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    if view == 'recent_added':
        rows = rows[:50]

    def fill(rs):  # fehlende Folgen genau ausrechnen (Dateien und Boxen mit Staffelangaben)
        for r in rs:
            if 'n_missing' not in r:
                _, tot = overview(c, r['id'])
                r['n_missing'], r['n_have'] = tot['missing'], tot['have']
        return rs
    if view == 'incomplete' or limit >= 10**6:
        rows = fill(rows)
        if view == 'incomplete':
            rows = [r for r in rows if r['n_missing'] > 0]
        return rows[offset:offset + limit], len(rows)
    return fill(rows[offset:offset + limit]), len(rows)


def view_counts(c):
    rows, n = query(c, 'all', limit=10**6)
    running = ('Returning Series', 'In Production')
    return {'all': n, 'next': sum(1 for r in rows if r['next_at']), 'incomplete': sum(1 for r in rows if r['n_missing'] > 0),
            'watching': sum(1 for r in rows if 0 < r['n_seen'] < r['n_aired']),
            'unstarted': sum(1 for r in rows if r['n_seen'] == 0),
            'finished': sum(1 for r in rows if r['n_seen'] > 0 and r['n_seen'] >= r['n_aired']),
            'running': sum(1 for r in rows if r['status'] in running), 'recent_added': min(n, 50)}


def letter_counts(c):
    return dict(c.execute(f'SELECT {LETTER_SQL}, count(*) FROM series s GROUP BY 1').fetchall())


def genres(c):
    seen = {}
    for (g,) in c.execute("SELECT genres FROM series WHERE coalesce(genres,'')<>''"):
        for x in g.split(','):
            x = x.strip()
            if x:
                seen[x] = seen.get(x, 0) + 1
    return sorted(seen.items(), key=lambda kv: kv[0].lower())


def stats(c):
    r = c.execute('SELECT count(*) FROM series').fetchone()[0]
    e = c.execute('SELECT count(*) FROM ep_files').fetchone()[0]
    w = c.execute('SELECT count(*) FROM watched').fetchone()[0]
    rows, _ = query(c, 'all', limit=10**6)
    return {'series': r, 'files': e, 'watched': w, 'missing': sum(x['n_missing'] for x in rows),
            'incomplete': sum(1 for x in rows if x['n_missing'] > 0), 'aired': sum(x['n_aired'] for x in rows)}


def missing_all(c):
    """Fuer die Seite 'Was fehlt?': alle Serien mit fehlenden, schon ausgestrahlten Folgen."""
    out = []
    for s in c.execute('SELECT id, title, year, poster, status FROM series WHERE tmdb_id IS NOT NULL ORDER BY sort_title').fetchall():
        seasons, tot = overview(c, s['id'])
        if tot['missing']:
            gaps = []
            for se in seasons:
                if se['season'] == 0 or not se['n_missing']:
                    continue
                gaps.append({'season': se['season'], 'name': se.get('name'), 'absent': se['absent'], 'n_aired': se['n_aired'],
                             'episodes': [e for e in se['episodes'] if e['state'] == 'missing']})
            out.append(dict(s, missing=tot['missing'], have=tot['have'], aired=tot['aired'], gaps=gaps))
    return out
