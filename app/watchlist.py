"""Merkliste und regelmaessige Aktualisierung (Bereich "Merkliste" unter /watchlist).

Die Merkliste haelt Filme und Serien fest, die man sich ansehen oder kaufen moechte (Tipps aus Videos, Zeitschriften ...).
Filme stehen in filme.db, Serien in serien.db (Tabelle 'watch', gleicher Aufbau), damit die Bereiche getrennt bleiben.

Der Aktualisierer (UPD) laeuft einmal am Tag im Hintergrund: laufende Serien der Sammlung bekommen neue Folgen und
Staffeln (nur die letzte und neue Staffeln werden geladen), Streamingdienste und die naechste Folge; beendete Serien
alle 30 Tage. Danach werden alle Eintraege der Merkliste aufgefrischt (Termin, Streamingdienst)."""
import logging, os, threading, time
from datetime import datetime, timedelta
from . import films_db as F
from . import series_db as S
from . import films_tmdb as T
from . import config as C
from . import users as U

SCHEMA = """
CREATE TABLE IF NOT EXISTS watch(
  id INTEGER PRIMARY KEY, tmdb_id INTEGER, title TEXT NOT NULL, original_title TEXT, year INTEGER, poster_path TEXT, overview TEXT,
  note TEXT, status TEXT, release_date TEXT, digital_date TEXT, next_air_date TEXT, next_season INTEGER, next_episode INTEGER,
  last_season INTEGER, number_of_seasons INTEGER, networks TEXT, providers TEXT, providers_buy TEXT, providers_link TEXT,
  checked_at TEXT, added_at TEXT, done_at TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""
FIELDS = ['title', 'year', 'poster_path', 'status', 'release_date', 'digital_date', 'next_air_date', 'next_season', 'next_episode',
          'last_season', 'number_of_seasons', 'networks', 'providers', 'providers_buy', 'providers_link']
RUNNING = ('Returning Series', 'In Production', 'Planned', 'Pilot')
DBS = {'movie': F, 'tv': S}

UPD = {'state': 'idle', 'done': 0, 'total': 0, 'current': '', 'error': '', 'last': None, 'changes': []}
_lock = threading.Lock()


def init():
    for m in DBS.values():
        with m.db(plain=True) as c:
            c.executescript(SCHEMA)
            if 'user_id' not in {r[1] for r in c.execute('PRAGMA table_info(watch)')}:  # seit 1.22: Merkliste pro Person
                c.execute('ALTER TABLE watch ADD COLUMN user_id INTEGER')


def now():
    return datetime.now().isoformat(timespec='seconds')


# ---------------------------------------------------------------- Merkliste
def items(include_done=False):
    out = []
    for kind, m in DBS.items():
        with m.db() as c:
            have = {r[0]: r[1] for r in c.execute(f"SELECT tmdb_id, id FROM {'films' if kind == 'movie' else 'series'} WHERE tmdb_id IS NOT NULL")}
            for r in c.execute('SELECT * FROM watch' + ('' if include_done else ' WHERE done_at IS NULL')):
                out.append(dict(r, kind=kind, owned=have.get(r['tmdb_id'])))
    for x in out:
        x['date'], x['date_label'] = next_date(x)
    return sorted(out, key=lambda x: (x['done_at'] is not None, x['date'] is None, x['date'] or '', x['added_at'] or ''))


def next_date(x):
    """Wichtigster kommender Termin eines Eintrags mit Beschriftung."""
    today = datetime.now().date().isoformat()
    if x['kind'] == 'tv':
        if x.get('next_air_date'):
            if x.get('next_episode') == 1:
                return x['next_air_date'], 'Staffel § startet'
            return x['next_air_date'], 'Nächste Folge'
        return None, ''
    for key, label in (('release_date', 'Kinostart'), ('digital_date', 'Digital ab')):
        if x.get(key) and x[key] >= today:
            return x[key], label
    return None, ''


def add(kind, tmdb_id, title, note='', year=None, poster_path=None, overview=None, original_title=None):
    m = DBS[kind]
    with m.db() as c:
        if tmdb_id:
            r = c.execute('SELECT id FROM watch WHERE tmdb_id=?', (tmdb_id,)).fetchone()
            if r:
                c.execute('UPDATE watch SET done_at=NULL, note=coalesce(nullif(?,\'\'), note) WHERE id=?', (note, r['id']))
                return r['id'], False
        wid = c.execute('INSERT INTO main.watch(tmdb_id, title, original_title, year, poster_path, overview, note, added_at, user_id) VALUES(?,?,?,?,?,?,?,?,?)',
                        (tmdb_id, title or 'Ohne Titel', original_title, year, poster_path, overview, note or None, now(), U.current_id())).lastrowid
    if tmdb_id and T.configured():
        refresh_item(kind, wid)
    return wid, True


def refresh_item(kind, wid):
    m = DBS[kind]
    with m.db() as c:
        r = c.execute('SELECT tmdb_id FROM watch WHERE id=?', (wid,)).fetchone()
    if not r or not r['tmdb_id']:
        return None
    d, err = T.watch_status(kind, r['tmdb_id'])
    if not d:
        return err
    with m.db() as c:
        d = {k: d.get(k) for k in FIELDS if k in d and (k not in ('title', 'poster_path', 'year') or d.get(k))}
        c.execute(f'UPDATE watch SET {",".join(k + "=?" for k in d)}, checked_at=? WHERE id=?', (*d.values(), now(), wid))
    return None


def set_note(kind, wid, note):
    with DBS[kind].db() as c:
        c.execute('UPDATE watch SET note=? WHERE id=?', (note or None, wid))


def set_done(kind, wid, done=True):
    with DBS[kind].db() as c:
        c.execute('UPDATE watch SET done_at=? WHERE id=?', (now() if done else None, wid))


def delete(kind, wid):
    with DBS[kind].db() as c:
        c.execute('DELETE FROM watch WHERE id=?', (wid,))


# ---------------------------------------------------------------- Aktualisierung
def _meta(key, value=None):
    with S.db() as c:
        if value is None:
            r = c.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            return r[0] if r else None
        c.execute('INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)', (key, value))


def due_series(force=False):
    """Serien, die aufgefrischt werden sollten: laufende taeglich, beendete alle 30 Tage."""
    day = (datetime.now() - timedelta(hours=20)).isoformat(timespec='seconds')
    month = (datetime.now() - timedelta(days=30)).isoformat(timespec='seconds')
    with S.db() as c:
        rows = c.execute('SELECT id, title, status, guide_at, providers_at FROM series WHERE tmdb_id IS NOT NULL ORDER BY sort_title').fetchall()
    out = []
    for r in rows:
        running = r['status'] in RUNNING or not r['status']
        if force and running:
            out.append(r)
        elif not r['guide_at'] or not r['providers_at'] or r['guide_at'] < (day if running else month):
            out.append(r)
    out.sort(key=lambda r: r['status'] not in RUNNING)  # laufende zuerst
    return out


def refresh_series(sid):
    """Angaben, Streamingdienste und die letzte sowie neue Staffeln einer Serie neu laden. Gibt Fehlertext oder None."""
    with S.db() as c:
        s = S.get(c, sid)
        if not s or not s['tmdb_id']:
            return None
        known = c.execute('SELECT max(season) FROM episodes WHERE series_id=? AND season>0', (sid,)).fetchone()[0]
        before = c.execute("SELECT max(air_date) FROM episodes WHERE series_id=?", (sid,)).fetchone()[0]
    d, err = T.tv_details(s['tmdb_id'])
    if err or not d:
        return err or 'TMDB lieferte keine Daten.'
    seasons = d['_seasons']
    fetch = {x['season'] for x in seasons if x['season'] > 0 and (known is None or x['season'] >= known)}
    eps = []
    for se in sorted(fetch):
        e, _ = T.tv_season(s['tmdb_id'], se)
        eps += e or []
    with S.db() as c:
        S.update(c, sid, {k: v for k, v in d.items() if not k.startswith('_') and k not in ('title', 'poster', 'backdrop')})
        S.set_people(c, sid, d.get('_people'))
        S.upsert_guide(c, sid, seasons, eps, fetch)
        after = c.execute("SELECT max(air_date) FROM episodes WHERE series_id=?", (sid,)).fetchone()[0]
    if after and after != before:
        UPD['changes'].append(s['title'])
    return None


def run(force=False):
    if not _lock.acquire(blocking=False):
        return
    try:
        if not T.configured():
            UPD['state'] = 'idle'
            return
        # nur eingeschaltete Bereiche: Serien-Updates bei Serien, Merkliste je nach Filme ('movie') und Serien ('tv')
        todo = due_series(force) if C.area_on('series') else []
        w = [(k, r['id']) for k in DBS if C.area_on({'movie': 'films', 'tv': 'series'}[k]) for r in _watch_ids(k)]
        UPD.update(state='running', done=0, total=len(todo) + len(w), error='', changes=[])
        for r in todo:
            UPD['current'] = r['title']
            try:
                err = refresh_series(r['id'])
                if err and 'Schlüssel' in err:
                    raise RuntimeError(err)
            except RuntimeError:
                raise
            except Exception:
                logging.exception('Serie nicht aktualisiert: %s', r['title'])
            UPD['done'] += 1
        for kind, wid in w:
            UPD['current'] = ''
            try:
                refresh_item(kind, wid)
            except Exception:
                logging.exception('Merklisten-Eintrag nicht aktualisiert')
            UPD['done'] += 1
        _meta('updated_at', now())
        UPD.update(state='idle', last=now(), current='')
    except Exception as e:
        logging.exception('Aktualisierung fehlgeschlagen')
        UPD.update(state='idle', error=str(e), current='')
    finally:
        _lock.release()


def _watch_ids(kind):
    with DBS[kind].db() as c:
        return c.execute('SELECT id FROM watch WHERE done_at IS NULL AND tmdb_id IS NOT NULL').fetchall()


def start(force=False):
    if UPD['state'] == 'running':
        return False
    UPD.update(state='running', done=0, total=0, current='')  # sofort sichtbar, auch bevor der Hintergrundlauf startet
    threading.Thread(target=run, args=(force,), daemon=True).start()
    return True


def last_run():
    return UPD['last'] or _meta('updated_at')


def scheduler():
    """Einmal am Tag aktualisieren: kurz nach dem Start pruefen, danach stuendlich."""
    def loop():
        time.sleep(90)
        while True:
            try:
                last = last_run()
                if C.area_on('watch') and T.configured() and os.getenv('AUTO_UPDATE', '1').strip().lower() not in ('0', 'false', 'no', 'nein', 'off') and (not last or last < (datetime.now() - timedelta(hours=20)).isoformat(timespec='seconds')):
                    run()
            except Exception:
                logging.exception('Zeitplan der Aktualisierung')
            time.sleep(3600)
    threading.Thread(target=loop, daemon=True).start()
