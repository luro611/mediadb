"""Bereich Serien: Seiten und Aktionen unter /series (Starlette-App, in main.py eingehaengt).
Aufbau wie bei den Filmen; Personen-Seiten sind gemeinsam (/films/person/<id>)."""
import json, os, re
from urllib.parse import quote, urlencode
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Route
from . import series_db as S
from . import series_files as X
from . import films_tmdb as T
from . import films_web as FW
from .films_art import MAX_UPLOAD

templates = None
ctx = None
IMAGES = None
PAGE = 120
VIEW_NAMES = {'all': 'Alle', 'next': 'Als Nächstes', 'incomplete': 'Unvollständig', 'watching': 'Angefangen', 'unstarted': 'Noch nicht angefangen',
              'finished': 'Ganz gesehen', 'running': 'Läuft noch', 'recent_added': 'Zuletzt hinzugefügt'}
SORT_NAMES = {'title': 'Titel', 'year': 'Jahr', 'rating': 'Bewertung', 'added': 'Hinzugefügt'}


def setup(templates_, ctx_, data_dir):
    global templates, ctx, IMAGES
    templates, ctx = templates_, ctx_
    IMAGES = os.path.join(str(data_dir), 'film_images')  # gleiche Bildablage, Dateinamen beginnen mit 's'
    os.makedirs(IMAGES, exist_ok=True)
    S.init(os.path.join(str(data_dir), 'serien.db'))
    templates.env.globals.update(SERIES_KINDS=S.KINDS, SERIES_STATUS=S.STATUS)
    templates.env.filters['hostpath'] = FW.au.host_label


def render(request, name, **kw):
    return templates.TemplateResponse(request, name, ctx(request, area='series', tmdb_on=T.configured(), **kw))


go = FW.go
_int = FW._int
_form = FW._form


# ---------------------------------------------------------------- Uebersicht
async def index(request):
    p = request.query_params
    view = p.get('view') if p.get('view') in S.VIEWS else 'all'
    sort = p.get('sort') if p.get('sort') in SORT_NAMES else 'title'
    direction = 'desc' if p.get('dir') == 'desc' else 'asc'
    q, genre, prov = p.get('q', '').strip(), p.get('genre', ''), p.get('dienst', '')
    letter = p.get('l', '') if p.get('l', '') == '#' or (len(p.get('l', '')) == 1 and 'A' <= p.get('l', '') <= 'Z') else ''
    page = max(1, _int(p.get('page'), 1))

    def load():
        with S.db() as c:
            rows, total = S.query(c, view, q, genre, letter, sort, direction, PAGE, (page - 1) * PAGE, provider=prov)
            return dict(rows=rows, total=total, counts=S.view_counts(c), genres=S.genres(c), letters=S.letter_counts(c), providers=S.providers_all(c),
                        people_hits=[dict(x) for x in S.find_people(c, q)] if len(q) >= 3 else [])
    d = await run_in_threadpool(load)
    keep = {k: v for k, v in dict(q=q, genre=genre, dienst=prov, sort=sort if sort != 'title' else '', dir=direction if direction != 'asc' else '', l=letter).items() if v}

    def url(**kw):
        x = {**keep, 'view': view if view != 'all' else ''}
        x.update(kw)
        return '/series?' + urlencode({k: v for k, v in x.items() if v not in ('', None)})
    return render(request, 'series_list.html', view=view, q=q, genre=genre, prov=prov, sort=sort, dir=direction, letter=letter, url=url,
                  page=page, pages=(d['total'] + PAGE - 1) // PAGE, view_names=VIEW_NAMES, sort_names=SORT_NAMES,
                  abc=['#'] + [chr(x) for x in range(65, 91)], filtered=bool(q or genre or prov), message=p.get('message', ''), **d)


async def missing(request):
    def load():
        with S.db() as c:
            return S.missing_all(c)
    data = await run_in_threadpool(load)
    if request.query_params.get('format') == 'txt':  # zum Kopieren, z. B. als Einkaufszettel
        lines = []
        for s in data:
            lines.append(f"{s['title']}{' (' + str(s['year']) + ')' if s['year'] else ''}: {s['missing']} {'fehlt' if s['missing'] == 1 else 'fehlen'}")
            for g in s['gaps']:
                if g['absent']:
                    lines.append(f"  Staffel {g['season']} komplett ({g['n_aired']} Folgen)")
                else:
                    for e in g['episodes']:
                        lines.append(f"  S{e['season']:02d}E{e['episode']:02d}  {e['name'] or ''}")
            lines.append('')
        return PlainTextResponse('\n'.join(lines) or 'Nichts fehlt.\n')
    return render(request, 'series_missing.html', items=data)


# ---------------------------------------------------------------- Hinzufuegen
async def add_page(request):
    return render(request, 'series_add.html', message=request.query_params.get('message', ''), kinds=S.KINDS,
                  barcode_lookup=T.barcode_lookup_enabled())


def _cands(q, year=None):
    cands, err = T.tv_search(q, year) if q else ([], None)
    with S.db() as c:
        have = {r[0]: r[1] for r in c.execute('SELECT tmdb_id, id FROM series WHERE tmdb_id IS NOT NULL')}
    for x in cands:
        x['have'] = have.get(x['tmdb_id'])
    return cands, err


async def scan(request):
    f, _ = await _form(request)
    bc = T.norm_barcode(f.get('barcode'))
    if not bc:
        return go('/series/add', 'Bitte einen Barcode eingeben.')

    def work():
        with S.db() as c:
            local = [dict(r) for r in S.series_by_barcode(c, bc)]
            cached = c.execute('SELECT title FROM barcode_cache WHERE barcode=?', (bc,)).fetchone()
        if local:
            return dict(local=local, product='', query='', cands=[], err=None, seasons='')
        product, _, err = (cached[0], None, None) if cached else T.upc_lookup(bc)
        if not cached and err is None and T.barcode_lookup_enabled():
            with S.db() as c:
                c.execute('INSERT OR REPLACE INTO barcode_cache(barcode,title,fetched_at) VALUES(?,?,?)', (bc, product, S.now()))
        cands, err2, query = [], None, ''
        for q in T.tv_query_variants(product):
            cands, err2 = _cands(q)
            query = query or q
            if cands or err2:
                query = q
                break
        return dict(local=[], product=product, query=query, cands=cands, err=err or err2, seasons=T.seasons_from_product(product))
    r = await run_in_threadpool(work)
    kind = f.get('kind') if f.get('kind') in S.KINDS else T.guess_kind(r['product'], 'dvd')
    if kind == 'file':
        kind = 'dvd'
    return render(request, 'series_candidates.html', barcode=bc, kind=kind, kinds=S.KINDS, year='', attach=None, **r)


async def search(request):
    p = request.query_params
    q, year, attach = p.get('q', '').strip(), _int(p.get('year')), _int(p.get('attach'))
    cands, err = await run_in_threadpool(_cands, q, year)
    s = None
    if attach:
        def load():
            with S.db() as c:
                r = S.get(c, attach)
                return dict(r) if r else None
        s = await run_in_threadpool(load)
    kind = p.get('kind') if p.get('kind') in S.KINDS else ''
    return render(request, 'series_candidates.html', barcode=T.norm_barcode(p.get('barcode')), kind=kind, kinds=S.KINDS, local=[],
                  product='', query=q, year=year or '', cands=cands, err=err, attach=s, seasons=p.get('seasons', ''))


async def save(request):
    f, _ = await _form(request)
    tmdb_id = _int(f.get('tmdb_id'))
    if not tmdb_id:
        return go('/series/add', 'Keine Serie ausgewählt.')

    def work():
        with S.db() as c:
            existed = S.by_tmdb(c, tmdb_id)
            sid, err = X.save_from_tmdb(c, tmdb_id, IMAGES)
            if not sid:
                return None, err
            if f.get('kind') in S.KINDS:
                S.add_copy(c, sid, f)
            return sid, ('Box zur vorhandenen Serie hinzugefügt.' if existed and f.get('kind') else 'Gespeichert.')
    sid, msg = await run_in_threadpool(work)
    return go(f'/series/{sid}', msg) if sid else go('/series/add', msg or 'Speichern fehlgeschlagen.')


async def manual(request):
    f, _ = await _form(request)
    if not f.get('title'):
        return go('/series/add', 'Bitte einen Titel eingeben.')

    def work():
        with S.db() as c:
            sid = S.insert(c, {'title': f['title'], 'year': _int(f.get('year')), 'overview': f.get('overview'), 'source': 'manual'})
            if f.get('kind') in S.KINDS:
                S.add_copy(c, sid, f)
            return sid
    return go(f'/series/{await run_in_threadpool(work)}', 'Gespeichert.')


# ---------------------------------------------------------------- Detail
async def detail(request):
    sid = request.path_params['sid']

    def load():
        with S.db() as c:
            s = S.get(c, sid)
            if not s:
                return None
            seasons, tot = S.overview(c, sid, specials=False)
            nxt = S.next_up(c, sid)
            extra_files = [dict(r) for r in c.execute("""SELECT * FROM ep_files f WHERE series_id=? AND (season IS NULL OR episode IS NULL) ORDER BY path""", (sid,))]
            dirs = sorted({os.path.dirname(r[0]) for r in c.execute('SELECT path FROM ep_files WHERE series_id=?', (sid,))})
            # Staffelordner zusammenfassen: nur den Serienordner zeigen, wenn alle darunter liegen
            tops = sorted({X.parse_episode(d + '/x.mkv')['series_dir'] for d in dirs})
            return dict(s=dict(s), seasons=seasons, tot=tot, folders=[FW.au.host_label(d) for d in tops], next=dict(nxt) if nxt else None, people=S.people_of(c, sid),
                        copies=[dict(k) for k in S.copies_of(c, sid)], extra_files=extra_files)
    d = await run_in_threadpool(load)
    if not d:
        return go('/series', 'Serie nicht gefunden.')
    return render(request, 'series_detail.html', message=request.query_params.get('message', ''), kinds=S.KINDS, **d)


def _action(fn):
    async def handler(request):
        sid = request.path_params['sid']
        f, raw = await _form(request)

        def do():
            with S.db() as c:
                if not S.get(c, sid):
                    return 'Serie nicht gefunden.'
                return fn(c, sid, f, raw)
        msg = await run_in_threadpool(do)
        anchor = f.get('anchor', '')
        return go(f'/series/{sid}' + ('#' + anchor if re.fullmatch(r'[A-Za-z0-9_-]+', anchor or '') else ''), msg or '')
    return handler



def _watched(c, sid, f, raw):
    se, ep = _int(f.get('season')), _int(f.get('episode'))
    if se is None:
        return ''
    if ep is None:
        S.set_season_watched(c, sid, se, f.get('on') == '1')
    else:
        S.set_watched(c, sid, se, ep, f.get('on') == '1')
    if f.get('on') == '1':
        S.drop_next_if_caught_up(c, sid)
    return ''


def _next_seen(c, sid, f, raw):
    n = S.next_up(c, sid)
    if n:
        S.set_watched(c, sid, n['season'], n['episode'], True)
        S.drop_next_if_caught_up(c, sid)
    return ''


def _rating(c, sid, f, raw):
    S.set_rating(c, sid, f.get('rating'))
    return ''


def _notes(c, sid, f, raw):
    S.update(c, sid, {'notes': f.get('notes', '')})
    return 'Notiz gespeichert.'


def _edit(c, sid, f, raw):
    if not f.get('title'):
        return 'Bitte einen Titel eingeben.'
    S.update(c, sid, {'title': f['title'], 'year': _int(f.get('year')), 'overview': f.get('overview', ''), 'notes': f.get('notes', ''),
                      'providers_own': (f.get('providers_own') or '').strip()})
    return 'Gespeichert.'


def _refresh(c, sid, f, raw):
    err = X.refresh_guide(c, sid)
    if err:
        return err
    s = S.get(c, sid)
    if not s['poster']:
        d, _ = T.tv_details(s['tmdb_id'])
        if d:
            X.fetch_images(c, sid, d, IMAGES)
    return 'Episodenführer aktualisiert.'


def _copy_add(c, sid, f, raw):
    S.add_copy(c, sid, f)
    return 'Box hinzugefügt.'


async def copy_delete(request):
    cid = request.path_params['cid']

    def do():
        with S.db() as c:
            r = c.execute('SELECT series_id FROM copies WHERE id=?', (cid,)).fetchone()
            if r:
                c.execute('DELETE FROM copies WHERE id=?', (cid,))
            return r[0] if r else None
    sid = await run_in_threadpool(do)
    return go(f'/series/{sid}#boxen' if sid else '/series', 'Box entfernt.')


async def file_delete(request):
    fid = request.path_params['fid']

    def do():
        with S.db() as c:
            r = c.execute('SELECT series_id FROM ep_files WHERE id=?', (fid,)).fetchone()
            if r:
                c.execute('DELETE FROM ep_files WHERE id=?', (fid,))
            return r[0] if r else None
    sid = await run_in_threadpool(do)
    return go(f'/series/{sid}' if sid else '/series', 'Datei-Eintrag entfernt. Die Datei selbst bleibt unberührt.')


async def file_move(request):
    """Datei einer anderen Staffel/Folge zuordnen (falls der Name falsch erkannt wurde)."""
    fid = request.path_params['fid']
    f, _ = await _form(request)
    se, ep = _int(f.get('season')), _int(f.get('episode'))

    def do():
        with S.db() as c:
            r = c.execute('SELECT series_id FROM ep_files WHERE id=?', (fid,)).fetchone()
            if r and se is not None and ep is not None:
                c.execute('UPDATE ep_files SET season=?, episode=?, episode_end=NULL WHERE id=?', (se, ep, fid))
            return r[0] if r else None
    sid = await run_in_threadpool(do)
    return go(f'/series/{sid}' if sid else '/series', 'Datei neu zugeordnet.')


async def rematch(request):
    sid = request.path_params['sid']
    f, _ = await _form(request)
    tmdb_id = _int(f.get('tmdb_id'))

    def do():
        with S.db() as c:
            if not S.get(c, sid) or not tmdb_id:
                return 'Keine Serie ausgewählt.', sid
            other = S.by_tmdb(c, tmdb_id)
            if other and other['id'] != sid:  # zusammenfuehren
                for t in ('ep_files', 'copies'):
                    c.execute(f'UPDATE {t} SET series_id=? WHERE series_id=?', (other['id'], sid))
                c.execute('INSERT OR IGNORE INTO watched SELECT ?, season, episode, watched_at FROM watched WHERE series_id=?', (other['id'], sid))
                S.delete(c, sid)
                X.remove_images(IMAGES, sid)
                return 'Die Serie war schon vorhanden; Dateien und Boxen wurden dorthin verschoben.', other['id']
            c.execute('UPDATE series SET tmdb_id=? WHERE id=?', (tmdb_id, sid))
            err = X.refresh_guide(c, sid)
            if err:
                return err, sid
            d, _ = T.tv_details(tmdb_id)
            S.update(c, sid, {'title': d['title']} if d else {})
            X.remove_images(IMAGES, sid)
            S.update(c, sid, {'poster': None, 'backdrop': None})
            if d:
                X.fetch_images(c, sid, d, IMAGES)
            return 'Neu zugeordnet und alle Angaben von TMDB übernommen.', sid
    msg, target = await run_in_threadpool(do)
    return go(f'/series/{target}', msg)


async def delete(request):
    sid = request.path_params['sid']

    def do():
        with S.db() as c:
            S.delete(c, sid)
        X.remove_images(IMAGES, sid)
    await run_in_threadpool(do)
    return go('/series', 'Serie gelöscht.')


async def edit_page(request):
    sid = request.path_params['sid']

    def load():
        with S.db() as c:
            r = S.get(c, sid)
            return dict(r) if r else None
    s = await run_in_threadpool(load)
    return render(request, 'series_edit.html', s=s) if s else go('/series', 'Serie nicht gefunden.')


# ---------------------------------------------------------------- Poster
async def poster_page(request):
    sid = request.path_params['sid']

    def load():
        with S.db() as c:
            r = S.get(c, sid)
        if not r:
            return None
        imgs, err = T.tv_images(r['tmdb_id']) if r['tmdb_id'] and T.configured() else ({'posters': [], 'backdrops': []}, None)
        return dict(s=dict(r), tmdb=imgs, err=err, img_base=T.IMG)
    d = await run_in_threadpool(load)
    return render(request, 'series_poster.html', message=request.query_params.get('message', ''), **d) if d else go('/series')


async def poster_set(request):
    sid = request.path_params['sid']
    f, _ = await _form(request)
    kind = 'backdrop' if f.get('kind') == 'backdrop' else 'poster'

    def do():
        with S.db() as c:
            if f.get('source') == 'remove':
                S.update(c, sid, {kind: None})
                return 'Bild entfernt.'
            p = f.get('path') or ''
            data = T.fetch_image(p, 'w342' if kind == 'poster' else 'w780') if p.startswith('/') and '..' not in p else None
            return 'Bild gespeichert.' if data and X.save_image(c, IMAGES, sid, kind, data) else 'Kein Bild gefunden.'
    return go(f'/series/{sid}/poster', await run_in_threadpool(do))


async def poster_upload(request):
    sid = request.path_params['sid']
    form = await request.form(max_files=1, max_part_size=MAX_UPLOAD + 1024)
    kind = 'backdrop' if form.get('kind') == 'backdrop' else 'poster'
    up = form.get('file')
    data = await up.read(MAX_UPLOAD + 1) if up and hasattr(up, 'read') else b''
    if len(data) > MAX_UPLOAD:
        return go(f'/series/{sid}/poster', 'Die Datei ist zu groß (höchstens 15 MB).')

    def do():
        with S.db() as c:
            return 'Bild gespeichert.' if X.save_image(c, IMAGES, sid, kind, data) else 'Das ist keine Bilddatei (JPG, PNG oder WebP).'
    return go(f'/series/{sid}/poster', await run_in_threadpool(do))


# ---------------------------------------------------------------- Ordner-Import
async def files_page(request):
    items = X.JOB['items'] if X.JOB['state'] == 'ready' else []
    groups = {k: [i for i in items if i['status'] == k] for k in ('unsure', 'match', 'known', 'nf')}
    roots = [{'path': c, 'label': h} for c, h, _ in FW.au.available_roots()]
    return render(request, 'series_files.html', job=X.JOB, groups=groups, roots=roots, host_label=FW.au.host_label,
                  message=request.query_params.get('message', ''))


async def files_scan(request):
    f, raw = await _form(request)
    if not T.configured():
        return go('/series/files', 'Kein TMDB-Schlüssel eingetragen (siehe Einstellungen).')
    fl = []
    for x in list(raw.getlist('folders')) + [y for y in (f.get('manual') or '').split('\n') if y.strip()]:
        p = FW.au.safe_dir(FW.au.to_container_path(str(x), FW.HOST_HOME))
        if p and p not in fl:
            fl.append(p)
    if not fl:
        return go('/series/files', 'Kein gültiger Ordner ausgewählt.')
    X.JOB.update(folders=fl, done=0, total=0, items=[], error='', result=None, unreadable=[])
    X.start(X.scan_worker, fl)
    return go('/series/files')


async def files_apply(request):
    if X.JOB['state'] != 'ready':
        return go('/series/files')
    f, raw = await _form(request)
    choices = {int(k[2:]): str(v) for k, v in raw.multi_items() if k.startswith('d_') and k[2:].isdigit()}
    X.start(X.apply_worker, choices, IMAGES)
    return go('/series/files')


async def files_status(request):
    return JSONResponse({'state': X.JOB['state'], 'done': X.JOB['done'], 'total': X.JOB['total'], 'phase': X.JOB.get('phase', ''),
                         'found': X.JOB.get('found', 0), 'current': FW.au.host_label(X.JOB.get('current') or '') if X.JOB.get('phase') == 'collect' else (X.JOB.get('current') or '')})


async def files_reset(request):
    if X.JOB['state'] not in ('scanning', 'applying'):
        X.JOB.update(state='idle', items=[], error='', result=None, done=0, total=0)
    return go('/series/files')


routes = [
    Route('/', index), Route('/missing', missing), Route('/add', add_page), Route('/scan', scan, methods=['POST']),
    Route('/search', search), Route('/save', save, methods=['POST']), Route('/manual', manual, methods=['POST']),
    Route('/files', files_page), Route('/files/browse', FW.files_browse), Route('/files/scan', files_scan, methods=['POST']),
    Route('/files/apply', files_apply, methods=['POST']), Route('/files/status', files_status), Route('/files/reset', files_reset, methods=['POST']),
    Route('/copies/{cid:int}/delete', copy_delete, methods=['POST']),
    Route('/file/{fid:int}/delete', file_delete, methods=['POST']), Route('/file/{fid:int}/move', file_move, methods=['POST']),
    Route('/{sid:int}', detail), Route('/{sid:int}/edit', edit_page), Route('/{sid:int}/edit', _action(_edit), methods=['POST']),
    Route('/{sid:int}/watched', _action(_watched), methods=['POST']), Route('/{sid:int}/next-seen', _action(_next_seen), methods=['POST']),
    Route('/{sid:int}/rating', _action(_rating), methods=['POST']), Route('/{sid:int}/notes', _action(_notes), methods=['POST']),
    Route('/{sid:int}/refresh', _action(_refresh), methods=['POST']), Route('/{sid:int}/copies', _action(_copy_add), methods=['POST']),
    Route('/{sid:int}/rematch', rematch, methods=['POST']), Route('/{sid:int}/delete', delete, methods=['POST']),
    Route('/{sid:int}/poster', poster_page), Route('/{sid:int}/poster/set', poster_set, methods=['POST']),
    Route('/{sid:int}/poster/upload', poster_upload, methods=['POST']),
]
app = Starlette(routes=routes)
