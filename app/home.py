"""Startseite und gemeinsame Suche ueber alle Bereiche (Musik, Filme, Serien).

Liest die Musikdatenbank direkt per sqlite3 (nur lesend), damit diese Seiten ohne SQLAlchemy testbar bleiben.
Ist die Musikdatenbank keine SQLite-Datei (z. B. PostgreSQL), zeigt die Startseite fuer Musik nur den Link."""
import os, sqlite3
from pathlib import Path
from contextlib import closing
from starlette.concurrency import run_in_threadpool
from jinja2 import pass_context
from . import films_db as F
from . import series_db as S
from . import books_db as BK
from . import search as music_search

templates = None
ctx = None
MUSIC_DB = None


def setup(templates_, ctx_, music_db_path):
    global templates, ctx, MUSIC_DB
    templates, ctx, MUSIC_DB = templates_, ctx_, (str(music_db_path) if music_db_path else None)
    # Tausendertrennung je Sprache: 1.222 (de, es), 1,222 (en), 1 222 (fr, festes Leerzeichen)
    sep = {'en': ',', 'fr': '\u00a0'}

    @pass_context
    def num(context, v):
        if not isinstance(v, (int, float)):
            return v
        return f'{int(v):,}'.replace(',', sep.get(context.get('lang'), '.'))
    templates.env.filters['num'] = num


def _music():
    if not MUSIC_DB or not os.path.exists(MUSIC_DB):
        return None
    try:
        with closing(sqlite3.connect(Path(MUSIC_DB).as_uri() + '?mode=ro', uri=True, timeout=10)) as c:
            c.row_factory = sqlite3.Row
            own = dict(c.execute("SELECT coalesce(ownership,'cd'), count(*) FROM media GROUP BY 1").fetchall())
            n = sum(own.values())
            artists = c.execute("SELECT count(DISTINCT lower(trim(coalesce(artist,'')))) FROM media").fetchone()[0]
            # Lieder: je Album die Titelliste, bei reinen Dateialben ohne Titelliste die Audiodateien
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            songs = 0
            if 'tracks' in tables:
                songs = c.execute('SELECT count(*) FROM tracks').fetchone()[0]
                if 'audio_files' in tables:
                    songs += c.execute('''SELECT count(*) FROM audio_files a WHERE a.medium_id IS NOT NULL
                                          AND NOT EXISTS (SELECT 1 FROM tracks t WHERE t.medium_id=a.medium_id)''').fetchone()[0]
            latest = [dict(r) for r in c.execute("""SELECT id, title, artist, cover_path FROM media
                                                    ORDER BY created_at DESC, id DESC LIMIT 8""")]
            return {'n': n, 'cd': own.get('cd', 0) + own.get('cd_digital', 0), 'digital': own.get('digital', 0) + own.get('cd_digital', 0),
                    'artists': artists, 'songs': songs, 'latest': latest}
    except Exception:
        return None


def _films():
    try:
        with F.db() as c:
            st = F.stats(c)
            latest = [dict(r) for r in c.execute('SELECT id, title, year, poster FROM films ORDER BY created_at DESC, id DESC LIMIT 8')]
            must, _ = F.query(c, 'mustsee')
            recent, _ = F.query(c, 'recent_watched')
            return {**st, 'latest': latest, 'mustsee': [dict(r) for r in must], 'recent': [dict(r) for r in recent[:8]]}
    except Exception:
        return None


def _series():
    try:
        with S.db() as c:
            st = S.stats(c)
            rows, _ = S.query(c, 'all', limit=10**6)
            latest = sorted(rows, key=lambda r: (r['created_at'] or '', r['id']), reverse=True)[:8]
            watching = [r for r in rows if 0 < r['n_seen'] < r['n_aired']][:8]
            return {**st, 'latest': latest, 'watching': watching}
    except Exception:
        return None


def _books():
    try:
        with BK.db() as c:
            st = BK.stats(c)
            latest = [dict(r) for r in c.execute('SELECT id, title, authors, cover FROM books ORDER BY created_at DESC, id DESC LIMIT 8')]
            reading, _ = BK.query(c, 'reading', limit=8)
            return {**st, 'latest': latest, 'reading': [dict(r) for r in reading]}
    except Exception:
        return None


async def home(request):
    music, films, series, books = (await run_in_threadpool(_music), await run_in_threadpool(_films), await run_in_threadpool(_series),
                                   await run_in_threadpool(_books))
    return templates.TemplateResponse(request, 'home.html', ctx(request, area='home', music=music, films=films, series=series, books=books))


def _music_hits(q, limit=12):
    if not MUSIC_DB or not os.path.exists(MUSIC_DB):
        return [], 0
    toks = q.split()
    long_, short = [t for t in toks if len(t) >= music_search.MIN_LEN], [t for t in toks if len(t) < music_search.MIN_LEN]
    where, args = [], []
    try:
        with closing(sqlite3.connect(Path(MUSIC_DB).as_uri() + '?mode=ro', uri=True, timeout=10)) as c:
            c.row_factory = sqlite3.Row
            has_fts = c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (music_search.TABLE,)).fetchone()
            if long_ and has_fts:
                where.append(f'm.id IN (SELECT rowid FROM {music_search.TABLE} WHERE {music_search.TABLE} MATCH ?)')
                args.append(music_search.match_expr(long_))
            else:
                short = toks
            for t in short:
                where.append('(m.title LIKE ? OR m.artist LIKE ?)')
                args += [f'%{t}%', f'%{t}%']
            if not where:
                return [], 0
            w = ' AND '.join(where)
            total = c.execute(f'SELECT count(*) FROM media m WHERE {w}', args).fetchone()[0]
            rows = [dict(r) for r in c.execute(f"""SELECT m.id, m.title, m.artist, m.year, m.cover_path, m.ownership FROM media m WHERE {w}
                                                   ORDER BY lower(coalesce(m.artist,'')), lower(m.title) LIMIT ?""", (*args, limit))]
            return rows, total
    except Exception:
        return [], 0


async def search(request):
    q = request.query_params.get('q', '').strip()

    def work():
        if not q:
            return [], 0, [], 0, [], 0, [], 0, [], []
        music, n_music = _music_hits(q)
        with F.db() as c:
            films, n_films = F.query(c, 'all', q=q, limit=12)
            people = {x['id']: dict(x) for x in F.find_people(c, q, 12)} if len(q) >= 3 else {}
        with S.db() as c:
            series, n_series = S.query(c, 'all', q=q, limit=12)
            for x in (S.find_people(c, q, 12) if len(q) >= 3 else []):  # Personen aus beiden Datenbanken zusammenfuehren
                if x['id'] in people:
                    people[x['id']]['n'] += x['n']
                else:
                    people[x['id']] = dict(x)
        people = sorted(people.values(), key=lambda p: (-p['n'], p['name']))[:12]
        try:
            with BK.db() as c:
                books, n_books = BK.query(c, 'all', q=q, sort='title', limit=12)
                authors = [dict(x) for x in BK.find_authors(c, q, 12)] if len(q) >= 3 else []
        except Exception:
            books, n_books, authors = [], 0, []
        return music, n_music, [dict(r) for r in films], n_films, series, n_series, [dict(r) for r in books], n_books, people, authors
    music, n_music, films, n_films, series, n_series, books, n_books, people, authors = await run_in_threadpool(work)
    return templates.TemplateResponse(request, 'search.html', ctx(request, area='home', q=q, music=music, n_music=n_music,
                                                                  films=films, n_films=n_films, series=series, n_series=n_series,
                                                                  books=books, n_books=n_books, people=people, authors=authors))
