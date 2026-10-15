"""Bereich Filme: Seiten und Aktionen unter /films (eigene Starlette-App, in main.py eingehaengt).

Ablaeufe:
  Barcode  -> lokale Exemplare, sonst Produktname vom Barcode-Dienst -> TMDB-Suche -> Treffer waehlen
  Titel    -> TMDB-Suche -> Treffer waehlen;  von Hand -> Eintrag ohne TMDB
  Ordner   -> Probelauf (films_files) -> Vorschau -> Uebernehmen
Ein Film kann mehrere Exemplare haben (DVD, Blu-ray, 4K UHD, Datei). Gesehen/Bewertung gelten fuer den Haushalt."""
import json, os, threading, time
from datetime import date
from urllib.parse import quote, urlencode
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route
from . import films_db as F
from . import series_db as S
from . import films_files as X
from . import films_tmdb as T
from . import films_art as A
from . import audio as au
from . import fs

templates = None
ctx = None
IMAGES = None
HOST_HOME = os.getenv('HOST_HOME', '')
PAGE = 120
VIEW_NAMES = {'all': 'Alle', 'unseen': 'Noch nicht gesehen', 'mustsee': 'Top 10: Muss ich sehen', 'favorites': 'Lieblingsfilme',
              'recent_watched': 'Zuletzt gesehen', 'recent_added': 'Zuletzt hinzugefügt'}
SORT_NAMES = {'title': 'Titel', 'year': 'Jahr', 'rating': 'Bewertung', 'added': 'Hinzugefügt', 'watched_at': 'Zuletzt gesehen', 'runtime': 'Laufzeit'}


def setup(templates_, ctx_, data_dir):
    global templates, ctx, IMAGES
    templates, ctx = templates_, ctx_
    IMAGES = os.path.join(str(data_dir), 'film_images')
    os.makedirs(IMAGES, exist_ok=True)
    F.init(os.path.join(str(data_dir), 'filme.db'))
    templates.env.globals.update(FILM_KINDS=F.KINDS, RATING_LABELS=F.RATING_LABELS, DEPARTMENTS={'Acting': 'Schauspiel', 'Directing': 'Regie', 'Writing': 'Drehbuch', 'Production': 'Produktion', 'Sound': 'Musik', 'Camera': 'Kamera', 'Editing': 'Schnitt', 'Art': 'Szenenbild', 'Costume & Make-Up': 'Kostüm und Maske', 'Visual Effects': 'Visuelle Effekte', 'Crew': 'Filmstab', 'Lighting': 'Licht'})
    if T.configured():  # Personen fuer frueher erfasste Filme einmal im Hintergrund nachladen
        threading.Thread(target=X.backfill_people, daemon=True).start()
    templates.env.filters['fdate'] = lambda v: (f'{v[8:10]}.{v[5:7]}.{v[:4]}' if len(v) >= 10 else f'{v[5:7]}.{v[:4]}' if len(v) == 7 else v) if v else ''


def render(request, name, **kw):
    return templates.TemplateResponse(request, name, ctx(request, area='films', tmdb_on=T.configured(), **kw))


def go(path, message=''):
    path, _, frag = path.partition('#')  # Meldung vor die Sprungmarke setzen: /films/1?message=…#gesehen
    url = path + (('&' if '?' in path else '?') + 'message=' + quote(message) if message else '')
    return RedirectResponse(url + ('#' + frag if frag else ''), 303)


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


async def _form(request):
    f = await request.form()
    return {k: (str(v).strip() if isinstance(v, str) else v) for k, v in f.multi_items()}, f


# ---------------------------------------------------------------- Uebersicht
async def index(request):
    p = request.query_params
    view = p.get('view') if p.get('view') in F.VIEWS else 'all'
    list_id, coll = _int(p.get('list')), _int(p.get('collection'))
    sort = p.get('sort') if p.get('sort') in F.SORTS else 'title'
    direction = 'desc' if p.get('dir') == 'desc' else 'asc'
    page = max(1, _int(p.get('page'), 1))
    q, genre, decade, kind = p.get('q', '').strip(), p.get('genre', ''), p.get('decade', ''), p.get('kind', '')
    letter = p.get('l', '') if p.get('l', '') == '#' or (len(p.get('l', '')) == 1 and 'A' <= p.get('l', '') <= 'Z') else ''

    def load():
        with F.db() as c:
            rows, total = F.query(c, view, q, genre, decade, kind, sort, direction, list_id, coll, PAGE, (page - 1) * PAGE, letter)
            lst = c.execute('SELECT * FROM lists WHERE id=?', (list_id,)).fetchone() if list_id else None
            cname = c.execute('SELECT collection_name FROM films WHERE collection_id=? LIMIT 1', (coll,)).fetchone() if coll else None
            people = [dict(x) for x in F.find_people(c, q)] if len(q) >= 3 else []
            no_poster = c.execute("SELECT count(*) FROM films WHERE coalesce(poster,'')=''").fetchone()[0]
            return dict(letters=F.letter_counts(c), rows=[dict(r) for r in rows], total=total, people_hits=people, no_poster=no_poster, pjob=A.JOB, counts=F.view_counts(c), lists=[dict(x) for x in F.lists_all(c)],
                        genres=F.genres(c), decades=F.decades(c), stats=F.stats(c), current_list=dict(lst) if lst else None,
                        collection_name=cname[0] if cname else '')
    data = await run_in_threadpool(load)
    keep = {k: v for k, v in dict(q=q, genre=genre, decade=decade, kind=kind, sort=sort if sort != 'title' else '',
                                  dir=direction if direction != 'asc' else '', list=list_id or '', collection=coll or '', l=letter).items() if v}
    def url(**kw):
        d = {**keep, 'view': view if view != 'all' else ''}
        d.update(kw)
        return '/films?' + urlencode({k: v for k, v in d.items() if v not in ('', None)})
    pages = (data['total'] + PAGE - 1) // PAGE if view not in ('mustsee', 'recent_watched', 'recent_added') else 1
    filtered = bool(q or genre or decade or kind)
    return render(request, 'films_list.html', view=view, q=q, genre=genre, decade=decade, kind=kind, sort=sort, dir=direction,
                  page=page, pages=pages, url=url, view_names=VIEW_NAMES, sort_names=SORT_NAMES, list_id=list_id, coll=coll,
                  filtered=filtered, letter=letter, abc=['#'] + [chr(x) for x in range(65, 91)], message=p.get('message', ''), **data)


async def collections(request):
    def load():
        with F.db() as c:
            return [dict(r) for r in F.collections(c)]
    return render(request, 'films_collections.html', colls=await run_in_threadpool(load))


# ---------------------------------------------------------------- Eigene Listen
async def lists_page(request):
    def load():
        with F.db() as c:
            return [dict(r) for r in F.lists_all(c)]
    return render(request, 'films_lists.html', lists=await run_in_threadpool(load), message=request.query_params.get('message', ''))


async def list_create(request):
    f, _ = await _form(request)
    def do():
        with F.db() as c:
            return F.create_list(c, f.get('name'))
    lid = await run_in_threadpool(do)
    back = f.get('back') or ''
    if back.startswith('/films/') and not back.startswith('//'):
        return go(back)
    return go(f'/films?list={lid}') if lid else go('/films/lists', 'Bitte einen Namen eingeben.')


async def list_rename(request):
    lid = request.path_params['lid']
    f, _ = await _form(request)
    def do():
        with F.db() as c:
            return F.rename_list(c, lid, f.get('name'))
    ok = await run_in_threadpool(do)
    return go('/films/lists', 'Liste umbenannt.' if ok else 'Name leer oder schon vergeben.')


async def list_delete(request):
    lid = request.path_params['lid']
    def do():
        with F.db() as c:
            F.delete_list(c, lid)
    await run_in_threadpool(do)
    return go('/films/lists', 'Liste gelöscht. Die Filme bleiben erhalten.')


# ---------------------------------------------------------------- Hinzufuegen
async def add_page(request):
    return render(request, 'films_add.html', message=request.query_params.get('message', ''), kinds=F.KINDS,
                  barcode_lookup=T.barcode_lookup_enabled())


def _candidates(query, year=None):
    cands, err = T.search(query, year) if query else ([], None)
    with F.db() as c:
        have = {r[0]: r[1] for r in c.execute('SELECT tmdb_id, id FROM films WHERE tmdb_id IS NOT NULL')}
    for x in cands:
        x['have'] = have.get(x['tmdb_id'])
    return cands, err


async def scan(request):
    f, _ = await _form(request)
    bc = T.norm_barcode(f.get('barcode'))
    kind = f.get('kind') if f.get('kind') in F.KINDS else 'auto'
    if not bc:
        return go('/films/add', 'Bitte einen Barcode eingeben.')

    def work():
        with F.db() as c:
            local = [dict(r) for r in F.films_by_barcode(c, bc)]
            cached = c.execute('SELECT title FROM barcode_cache WHERE barcode=?', (bc,)).fetchone()
        if local:
            return dict(local=local, product='', query='', cands=[], err=None)
        product, raw, err = (cached[0], None, None) if cached else T.upc_lookup(bc)
        if not cached and err is None and T.barcode_lookup_enabled():
            with F.db() as c:
                c.execute('INSERT OR REPLACE INTO barcode_cache(barcode,title,raw,fetched_at) VALUES(?,?,?,?)',
                          (bc, product, json.dumps(raw)[:20000] if raw else None, F.now()))
        cands, err2, query = [], None, ''
        for q in T.query_variants(product):  # mehrere Schreibweisen probieren, bis TMDB etwas findet
            cands, err2 = _candidates(q)
            query = query or q
            if cands or err2:
                query = q
                break
        return dict(local=[], product=product, query=query, cands=cands, err=err or err2)
    r = await run_in_threadpool(work)
    if kind == 'auto':
        kind = T.guess_kind(r['product'], 'dvd')
    return render(request, 'films_candidates.html', barcode=bc, kind=kind, kinds=F.KINDS, edition='', year='', attach=None, **r)


async def search(request):
    p = request.query_params
    q, year = p.get('q', '').strip(), _int(p.get('year'))
    attach = _int(p.get('attach'))
    kind = p.get('kind') if p.get('kind') in F.KINDS else 'dvd'
    cands, err = await run_in_threadpool(_candidates, q, year)
    film = None
    if attach:
        def load():
            with F.db() as c:
                r = F.get_film(c, attach)
                return dict(r) if r else None
        film = await run_in_threadpool(load)
    return render(request, 'films_candidates.html', barcode=T.norm_barcode(p.get('barcode')), kind=kind, kinds=F.KINDS,
                  edition=p.get('edition', ''), local=[], product='', query=q, year=year or '', cands=cands, err=err, attach=film)


async def save(request):
    f, _ = await _form(request)
    tmdb_id = _int(f.get('tmdb_id'))
    if not tmdb_id:
        return go('/films/add', 'Kein Film ausgewählt.')
    copy = {k: f.get(k) for k in ('kind', 'barcode', 'edition', 'region') if f.get(k)}
    add_copy = f.get('no_copy') != '1'

    def work():
        with F.db() as c:
            existed = F.film_by_tmdb(c, tmdb_id)
            fid, err = X.save_from_tmdb(c, tmdb_id, IMAGES)
            if not fid:
                return None, err
            if add_copy and (copy.get('kind') or copy.get('barcode')):
                F.add_copy(c, fid, copy)
            return fid, ('Neues Exemplar zum vorhandenen Film hinzugefügt.' if existed else 'Gespeichert.')
    fid, msg = await run_in_threadpool(work)
    if not fid:
        return go('/films/add', msg or 'Speichern fehlgeschlagen.')
    return go(f'/films/{fid}', msg)


async def manual(request):
    f, _ = await _form(request)
    if not f.get('title'):
        return go('/films/add', 'Bitte einen Titel eingeben.')

    def work():
        with F.db() as c:
            fid = F.insert_film(c, {'title': f['title'], 'original_title': f.get('original_title'), 'year': _int(f.get('year')),
                                    'directors': f.get('directors'), 'genres': f.get('genres'), 'runtime': _int(f.get('runtime')),
                                    'overview': f.get('overview'), 'source': 'manual'})
            if f.get('kind') in F.KINDS:
                F.add_copy(c, fid, {k: f.get(k) for k in ('kind', 'barcode', 'edition') if f.get(k)})
            return fid
    fid = await run_in_threadpool(work)
    return go(f'/films/{fid}', 'Gespeichert.')


# ---------------------------------------------------------------- Detail und Aktionen
async def detail(request):
    fid = request.path_params['fid']

    def load():
        with F.db() as c:
            r = F.get_film(c, fid)
            if not r:
                return None
            film = dict(r)
            in_coll = [dict(x) for x in c.execute('SELECT id,title,year,watched FROM films WHERE collection_id=? AND id<>? ORDER BY release_date, year',
                                                  (r['collection_id'], fid))] if r['collection_id'] else []
            ppl = F.people_of(c, fid)
            cast = ppl['cast'] or [dict(p, id=None) for p in F.cast_list(r, 20)]  # ohne Nummern (noch nicht nachgeladen): nur Namen
            return dict(film=film, cast=cast, people=ppl, copies=[dict(x) for x in F.copies_of(c, fid)],
                        lists=[dict(x) for x in F.lists_all(c)], in_lists=F.lists_of(c, fid), in_coll=in_coll)
    d = await run_in_threadpool(load)
    if not d:
        return go('/films', 'Film nicht gefunden.')
    return render(request, 'films_detail.html', message=request.query_params.get('message', ''), kinds=F.KINDS, **d)


def _film_action(fn):
    async def handler(request):
        fid = request.path_params['fid']
        f, raw = await _form(request)
        def do():
            with F.db() as c:
                if not F.get_film(c, fid):
                    return 'Film nicht gefunden.'
                return fn(c, fid, f, raw)
        msg = await run_in_threadpool(do)
        back = f.get('back') or ''
        target = back if back.startswith('/films') and not back.startswith('//') else f'/films/{fid}'
        return go(target + ('#' + f['anchor'] if f.get('anchor', '').isalnum() else ''), msg or '')
    return handler


def _watched(c, fid, f, raw):
    action = f.get('action')
    if action == 'unseen':
        F.set_watched(c, fid, False)
        return ''
    when = F.parse_date(f.get('date')) if 'date' in f else None
    if when is None and 'date' in f:
        return 'Datum nicht erkannt. Bitte TT.MM.JJJJ, MM.JJJJ oder JJJJ eingeben.'
    if action == 'date':
        F.set_watched_date(c, fid, when)
        return 'Datum gespeichert.'
    F.set_watched(c, fid, True, when or None)
    return ''


def _rating(c, fid, f, raw):
    F.set_rating(c, fid, f.get('rating'))
    return ''


def _lists(c, fid, f, raw):
    want = {int(x) for x in raw.getlist('list') if str(x).isdigit()}
    for l in F.lists_all(c):
        F.set_in_list(c, l['id'], fid, l['id'] in want)
    if f.get('new_list'):
        lid = F.create_list(c, f['new_list'])
        if lid:
            F.set_in_list(c, lid, fid, True)
    return 'Listen gespeichert.'


def _notes(c, fid, f, raw):
    F.update_film(c, fid, {'notes': f.get('notes', '')})
    return 'Notiz gespeichert.'


def _edit(c, fid, f, raw):
    if not f.get('title'):
        return 'Bitte einen Titel eingeben.'
    F.update_film(c, fid, {'title': f['title'], 'original_title': f.get('original_title', ''), 'year': _int(f.get('year')),
                           'runtime': _int(f.get('runtime')), 'genres': f.get('genres', ''), 'directors': f.get('directors', ''),
                           'certification': f.get('certification', ''), 'overview': f.get('overview', ''), 'notes': f.get('notes', '')})
    return 'Gespeichert.'


def _refresh(c, fid, f, raw):
    film = F.get_film(c, fid)
    if not film['tmdb_id']:
        return 'Dieser Film ist keinem TMDB-Eintrag zugeordnet. Bitte über „Anderen Film zuordnen“ suchen.'
    d, err = T.details(film['tmdb_id'])
    if err:
        return err
    F.update_film(c, fid, d, only_empty=True)
    if not any(F.people_of(c, fid).values()):
        F.set_film_people(c, fid, d.get('_people'))
    X.fetch_images(c, fid, d.get('_poster_path') if not film['poster'] else None, d.get('_backdrop_path') if not film['backdrop'] else None, IMAGES)
    return 'Von TMDB ergänzt (nur leere Felder).'


def _rematch(c, fid, f, raw):
    tmdb_id = _int(f.get('tmdb_id'))
    if not tmdb_id:
        return 'Kein Film ausgewählt.'
    other = F.film_by_tmdb(c, tmdb_id)
    if other and other['id'] != fid:  # Film gibt es schon: Exemplare dorthin verschieben, diesen Eintrag entfernen
        me = F.get_film(c, fid)
        c.execute('''UPDATE films SET watched=max(watched,?), watch_count=watch_count+?, watched_at=max(coalesce(watched_at,''),?),
                     rating=coalesce(rating,?), notes=CASE WHEN coalesce(notes,'')='' THEN ? WHEN ?='' THEN notes ELSE notes||char(10)||? END WHERE id=?''',
                  (me['watched'], me['watch_count'], me['watched_at'] or '', me['rating'], me['notes'] or '', me['notes'] or '', me['notes'] or '', other['id']))
        c.execute("UPDATE films SET watched_at=NULLIF(watched_at,''), notes=NULLIF(notes,'') WHERE id=?", (other['id'],))
        c.execute('UPDATE copies SET film_id=? WHERE film_id=?', (other['id'], fid))
        c.execute('INSERT OR IGNORE INTO list_items(list_id,film_id,added_at) SELECT list_id,?,added_at FROM list_items WHERE film_id=?', (other['id'], fid))
        F.delete_film(c, fid)
        _remove_images(fid)
        return f'MOVED:{other["id"]}'
    d, err = T.details(tmdb_id)
    if err:
        return err
    fields = {k: v for k, v in d.items() if not k.startswith('_')}
    for k in F.FILM_FIELDS:
        if k != 'notes' and k not in fields:
            fields[k] = None
    F.update_film(c, fid, fields)
    F.set_film_people(c, fid, d.get('_people'))
    _remove_images(fid)
    F.update_film(c, fid, {'poster': None, 'backdrop': None})
    X.fetch_images(c, fid, d.get('_poster_path'), d.get('_backdrop_path'), IMAGES)
    return 'REMATCH'


def _remove_images(fid):
    A.remove_images(IMAGES, fid)


async def rematch(request):
    fid = request.path_params['fid']
    f, raw = await _form(request)

    def do():
        with F.db() as c:
            if not F.get_film(c, fid):
                return 'Film nicht gefunden.', fid
            res = _rematch(c, fid, f, raw)
            if res.startswith('MOVED:'):
                return 'Der Film war schon vorhanden; die Exemplare wurden dorthin verschoben.', int(res[6:])
            if res == 'REMATCH':
                return 'Neu zugeordnet und alle Angaben von TMDB übernommen.', fid
            return res, fid
    msg, target = await run_in_threadpool(do)
    return go(f'/films/{target}', msg)


async def edit_page(request):
    fid = request.path_params['fid']
    def load():
        with F.db() as c:
            r = F.get_film(c, fid)
            return dict(r) if r else None
    film = await run_in_threadpool(load)
    if not film:
        return go('/films', 'Film nicht gefunden.')
    return render(request, 'films_edit.html', film=film)


async def delete(request):
    fid = request.path_params['fid']
    def do():
        with F.db() as c:
            F.delete_film(c, fid)
        _remove_images(fid)
    await run_in_threadpool(do)
    return go('/films', 'Film gelöscht.')


def _copy_add(c, fid, f, raw):
    F.add_copy(c, fid, {k: f.get(k) for k in ('kind', 'barcode', 'edition', 'region', 'notes') if f.get(k)})
    return 'Exemplar hinzugefügt.'


async def copy_delete(request):
    cid = request.path_params['cid']
    def do():
        with F.db() as c:
            r = c.execute('SELECT film_id FROM copies WHERE id=?', (cid,)).fetchone()
            if r:
                F.delete_copy(c, cid)
            return r[0] if r else None
    fid = await run_in_threadpool(do)
    return go(f'/films/{fid}' if fid else '/films', 'Exemplar entfernt.')


# ---------------------------------------------------------------- Poster und Hintergrundbilder
async def posters_fetch(request):
    A.start(IMAGES)
    return go('/films')


async def posters_status(request):
    return JSONResponse({'state': A.JOB['state'], 'done': A.JOB['done'], 'total': A.JOB['total']})


async def poster_page(request):
    fid = request.path_params['fid']

    def load():
        with F.db() as c:
            r = F.get_film(c, fid)
            if not r:
                return None
            loc_p, loc_b = A.local_images(c, fid, 'poster'), A.local_images(c, fid, 'backdrop')
            has_files = any(k['path'] for k in F.copies_of(c, fid))
        imgs, err = (T.images(r['tmdb_id']) if r['tmdb_id'] and T.configured() else ({'posters': [], 'backdrops': []}, None))
        return dict(film=dict(r), tmdb=imgs, err=err, local_posters=loc_p, local_backdrops=loc_b, has_files=has_files, img_base=T.IMG)
    d = await run_in_threadpool(load)
    if not d:
        return go('/films', 'Film nicht gefunden.')
    return render(request, 'films_poster.html', message=request.query_params.get('message', ''), **d)


def _kind(f):
    return 'backdrop' if f.get('kind') == 'backdrop' else 'poster'


async def poster_set(request):
    """Aus TMDB, aus lokalen Bildern oder aus der Datei (eingebettet) setzen; Bild entfernen."""
    fid = request.path_params['fid']
    f, _ = await _form(request)
    kind = _kind(f)

    def do():
        with F.db() as c:
            if not F.get_film(c, fid):
                return 'Film nicht gefunden.'
            src = f.get('source')
            if src == 'remove':
                A.remove_images(IMAGES, fid, kind)
                F.update_film(c, fid, {kind: None})
                return 'Bild entfernt.'
            if src == 'tmdb' and (f.get('path') or '').startswith('/') and '..' not in f['path']:
                data = T.fetch_image(f['path'], 'w342' if kind == 'poster' else 'w780')
            elif src == 'local' and str(f.get('i', '')).isdigit():
                lst = A.local_images(c, fid, kind)
                i = int(f['i'])
                data = None
                if i < len(lst):
                    with fs.open(lst[i], 'rb') as fh:
                        data = fh.read(A.MAX_UPLOAD + 1)
            elif src == 'embedded':
                data = next((d for d in (A.embedded_cover(k['path']) for k in F.copies_of(c, fid) if k['path']) if d), None)
            else:
                data = None
            if not data:
                return 'Kein Bild gefunden.'
            return 'Bild gespeichert.' if A.save_image(c, IMAGES, fid, kind, data) else 'Das ist keine Bilddatei (JPG, PNG oder WebP).'
    msg = await run_in_threadpool(do)
    return go(f'/films/{fid}/poster', msg)


async def poster_upload(request):
    fid = request.path_params['fid']
    form = await request.form(max_files=1, max_part_size=A.MAX_UPLOAD + 1024)
    kind = 'backdrop' if form.get('kind') == 'backdrop' else 'poster'
    up = form.get('file')
    data = await up.read(A.MAX_UPLOAD + 1) if up and hasattr(up, 'read') else b''
    if len(data) > A.MAX_UPLOAD:
        return go(f'/films/{fid}/poster', 'Die Datei ist zu groß (höchstens 15 MB).')

    def do():
        with F.db() as c:
            if not F.get_film(c, fid):
                return 'Film nicht gefunden.'
            return 'Bild gespeichert.' if A.save_image(c, IMAGES, fid, kind, data) else 'Das ist keine Bilddatei (JPG, PNG oder WebP).'
    return go(f'/films/{fid}/poster', await run_in_threadpool(do))


# ---------------------------------------------------------------- Personen
PERSON_MAX_AGE = 14 * 86400  # Angaben von TMDB zwei Wochen zwischenspeichern


async def person_page(request):
    pid = request.path_params['pid']

    def load():
        with F.db() as c:
            p = F.get_person(c, pid)
        fresh = p and p['fetched_at'] and (time.time() - _ts(p['fetched_at'])) < PERSON_MAX_AGE
        err = None
        if not fresh and T.configured():
            d, err = T.person(pid)
            if d:
                with F.db() as c:
                    F.save_person(c, pid, d)
                    if d.get('profile_path') and T.download_image(d['profile_path'], 'w185', os.path.join(IMAGES, f'person-{pid}.jpg')):
                        c.execute('UPDATE people SET profile=? WHERE id=?', (f'person-{pid}.jpg', pid))
        with F.db() as c:
            p = F.get_person(c, pid)
            if p:
                p = dict(p)
                mine = [dict(r) for r in F.films_with_person(c, pid)]
                have = {r[0]: r[1] for r in c.execute('SELECT tmdb_id, id FROM films WHERE tmdb_id IS NOT NULL')}
        with S.db() as c:
            series = [dict(r) for r in S.series_with_person(c, pid)]
            have_tv = {r[0]: r[1] for r in c.execute('SELECT tmdb_id, id FROM series WHERE tmdb_id IS NOT NULL')}
            if not p:  # nur aus einer Serie bekannt und TMDB nicht erreichbar
                r = c.execute('SELECT id, name FROM people WHERE id=?', (pid,)).fetchone()
                if not r:
                    return None
                p, mine, have = {'id': r['id'], 'name': r['name'], 'credits_json': '[]'}, [], {}
        try:
            credits = json.loads(p.get('credits_json') or '[]')
        except Exception:
            credits = []
        mine_ids = {f['tmdb_id'] for f in mine if f['tmdb_id']}
        series_ids = {s['tmdb_id'] for s in series if s['tmdb_id']}
        others = []
        for e in credits:
            if e['media'] == 'tv' and e['tmdb_id'] in have_tv:
                if e['tmdb_id'] not in series_ids:  # Serie in der Sammlung, Person aber nicht in der gespeicherten Besetzung
                    with S.db() as c:
                        r = S.get(c, have_tv[e['tmdb_id']])
                    if r:
                        series.append(dict(r, roles=','.join(e['roles']), character=e['character']))
                        series_ids.add(e['tmdb_id'])
                continue
            if e['media'] == 'movie' and e['tmdb_id'] in have:
                if e['tmdb_id'] not in mine_ids:  # Film in der Sammlung, Person aber nicht unter den ersten 20 der Besetzung
                    with F.db() as c:
                        r = F.get_film(c, have[e['tmdb_id']])
                    if r:
                        mine.append(dict(r, roles=','.join(e['roles']), character=e['character'], kinds=None))
                        mine_ids.add(e['tmdb_id'])
                continue
            e = dict(e, poster_url=(T.IMG + 'w154' + e['poster_path']) if e.get('poster_path') else '')
            others.append(e)
        return dict(person=p, mine=mine, series=series, others=others, err=err)
    d = await run_in_threadpool(load)
    if not d:
        return go('/films', 'Person nicht gefunden.')
    return render(request, 'films_person.html', **d)


def _ts(iso):
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0


# ---------------------------------------------------------------- Ordner-Import
async def files_page(request):
    items = X.JOB['items'] if X.JOB['state'] == 'ready' else []
    groups = {k: [i for i in items if i['status'] == k] for k in ('unsure', 'match', 'known', 'nf')}
    roots = [{'path': c, 'label': h} for c, h, _ in au.available_roots()]
    return render(request, 'films_files.html', job=X.JOB, groups=groups, roots=roots, host_label=au.host_label,
                  message=request.query_params.get('message', ''))


async def files_browse(request):
    path = request.query_params.get('path', '')
    if not path:
        return JSONResponse({'path': '', 'label': '', 'parent': '', 'dirs': [{'name': h, 'path': c} for c, h, _ in au.available_roots()], 'error': ''})
    p = au.safe_dir(au.to_container_path(path, HOST_HOME))
    if not p:
        return JSONResponse({'path': path, 'label': path, 'parent': '', 'dirs': [], 'error': 'Ordner nicht gefunden oder nicht freigegeben.'})
    err = ''
    try:
        dirs = sorted((n for n, is_dir, _ in await run_in_threadpool(fs.scandir, p) if is_dir and not n.startswith('.')), key=str.casefold)
    except OSError as e:
        dirs, err = [], (fs.nas.describe(e) if getattr(e, 'ntstatus', None) is not None else (e.strerror or fs.nas.describe(e))) if fs.is_nas(p) else ''
    roots = [c for c, _, _ in au.all_roots()]
    return JSONResponse({'path': p, 'label': au.host_label(p), 'parent': '' if p in roots else os.path.dirname(p), 'error': ctx(request)['_t'](err) if err else '',
                         'dirs': [{'name': d, 'path': os.path.join(p, d)} for d in dirs]})


async def files_scan(request):
    f, raw = await _form(request)
    if not T.configured():
        return go('/films/files', 'Kein TMDB-Schlüssel eingetragen (siehe Einstellungen).')
    fl = []
    for x in list(raw.getlist('folders')) + [y for y in (f.get('manual') or '').split('\n') if y.strip()]:
        p = au.safe_dir(au.to_container_path(str(x), HOST_HOME))
        if p and p not in fl:
            fl.append(p)
    if not fl:
        return go('/films/files', 'Kein gültiger Ordner ausgewählt.')
    X.JOB.update(folders=fl, done=0, total=0, items=[], error='', result=None)
    X.start(X.scan_worker, fl)
    return go('/films/files')


async def files_apply(request):
    if X.JOB['state'] != 'ready':
        return go('/films/files')
    f, raw = await _form(request)
    choices = {int(k[2:]): str(v) for k, v in raw.multi_items() if k.startswith('d_') and k[2:].isdigit()}
    X.start(X.apply_worker, choices, IMAGES)
    return go('/films/files')


async def files_status(request):
    return JSONResponse({'state': X.JOB['state'], 'done': X.JOB['done'], 'total': X.JOB['total']})


async def files_reset(request):
    if X.JOB['state'] not in ('scanning', 'applying'):
        X.JOB.update(state='idle', items=[], error='', result=None, done=0, total=0)
    return go('/films/files')


routes = [
    Route('/', index), Route('/collections', collections), Route('/lists', lists_page),
    Route('/lists/create', list_create, methods=['POST']), Route('/lists/{lid:int}/rename', list_rename, methods=['POST']),
    Route('/lists/{lid:int}/delete', list_delete, methods=['POST']),
    Route('/add', add_page), Route('/scan', scan, methods=['POST']), Route('/search', search),
    Route('/save', save, methods=['POST']), Route('/manual', manual, methods=['POST']),
    Route('/files', files_page), Route('/files/browse', files_browse), Route('/files/scan', files_scan, methods=['POST']),
    Route('/files/apply', files_apply, methods=['POST']), Route('/files/status', files_status), Route('/files/reset', files_reset, methods=['POST']),
    Route('/copies/{cid:int}/delete', copy_delete, methods=['POST']),
    Route('/person/{pid:int}', person_page),
    Route('/posters/fetch-missing', posters_fetch, methods=['POST']), Route('/posters/status', posters_status),
    Route('/{fid:int}/poster', poster_page), Route('/{fid:int}/poster/set', poster_set, methods=['POST']),
    Route('/{fid:int}/poster/upload', poster_upload, methods=['POST']),
    Route('/{fid:int}', detail), Route('/{fid:int}/edit', edit_page),
    Route('/{fid:int}/edit', _film_action(_edit), methods=['POST']),
    Route('/{fid:int}/watched', _film_action(_watched), methods=['POST']),
    Route('/{fid:int}/rating', _film_action(_rating), methods=['POST']),
    Route('/{fid:int}/lists', _film_action(_lists), methods=['POST']),
    Route('/{fid:int}/notes', _film_action(_notes), methods=['POST']),
    Route('/{fid:int}/refresh', _film_action(_refresh), methods=['POST']),
    Route('/{fid:int}/rematch', rematch, methods=['POST']),
    Route('/{fid:int}/copies', _film_action(_copy_add), methods=['POST']),
    Route('/{fid:int}/delete', delete, methods=['POST']),
]
app = Starlette(routes=routes)
