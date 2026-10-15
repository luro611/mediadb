"""Seite "Verliehen" (/lend) und der Kasten "Verleihen" auf den Detailseiten aller Bereiche.

Verleihen laesst sich nur, was es physisch gibt: CDs (Besitz "CD" oder "CD + digital"), DVD/Blu-ray/4K-Exemplare von
Filmen, Serien-Boxen und Buch-Exemplare ohne Datei (gedruckt oder Hoerbuch-CD, keine E-Books).
Starlette-App wie die anderen Bereiche, in main.py unter /lend eingehaengt."""
import os, sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route
from . import loans as L
from . import films_db as F
from . import series_db as S
from . import books_db as BK
from . import films_web as FW
from . import home as H

templates = None
ctx = None
go = FW.go
_form = FW._form
_int = FW._int


def setup(templates_, ctx_, data_dir):
    global templates, ctx
    templates, ctx = templates_, ctx_
    L.init(os.path.join(str(data_dir), 'verleih.db'))
    g = templates.env.globals
    g.update(lend_info=lend_info, lent_ids=lent_ids, LEND_AREAS=L.AREAS, lend_since=L.since,
             lend_today=lambda: date.today().strftime('%d.%m.%Y'), lend_stats=lend_stats, lend_find=lend_find)


def lend_find(q):
    try:
        with L.db() as c:
            return L.find_people(c, q, 12)
    except Exception:
        return []


def lend_stats():
    try:
        with L.db() as c:
            return L.stats(c)
    except Exception:
        return None


def render(request, tpl, **kw):
    return templates.TemplateResponse(request, tpl, ctx(request, area='lend', **kw))


# ---------------------------------------------------------------- Was gibt es physisch?
def _music_row(mid):
    if not H.MUSIC_DB or not os.path.exists(H.MUSIC_DB):
        return None
    with closing(sqlite3.connect(Path(H.MUSIC_DB).as_uri() + '?mode=ro', uri=True, timeout=10)) as c:
        c.row_factory = sqlite3.Row
        r = c.execute('SELECT id, title, artist, ownership, format FROM media WHERE id=?', (mid,)).fetchone()
        return dict(r) if r else None


def physical(area, item_id):
    """Verleihbare Exemplare eines Eintrags: Liste von {'copy_id', 'kind', 'extra'}; leer, wenn nur digital vorhanden."""
    if area == 'music':
        r = _music_row(item_id)
        if not r or (r['ownership'] or 'cd') not in ('cd', 'cd_digital'):
            return []
        return [{'copy_id': None, 'kind': 'CD', 'extra': r['format'] if r['format'] and r['format'] != 'CD' else ''}]
    if area == 'film':
        with F.db() as c:
            rows = c.execute("SELECT id, kind, edition FROM copies WHERE film_id=? AND kind<>'file' AND path IS NULL ORDER BY id",
                             (item_id,)).fetchall()
        return [{'copy_id': k['id'], 'kind': F.KINDS.get(k['kind'], k['kind']), 'extra': k['edition'] or ''} for k in rows]
    if area == 'series':
        with S.db() as c:
            rows = c.execute('SELECT id, kind, seasons, edition FROM copies WHERE series_id=? ORDER BY id', (item_id,)).fetchall()
        return [{'copy_id': k['id'], 'kind': S.KINDS.get(k['kind'], k['kind']), 'extra': k['edition'] or '', 'seasons': k['seasons'] or ''}
                for k in rows]
    if area == 'book':
        with BK.db() as c:
            rows = c.execute("SELECT id, kind, edition FROM copies WHERE book_id=? AND path IS NULL AND kind<>'ebook' ORDER BY id",
                             (item_id,)).fetchall()
        return [{'copy_id': k['id'], 'kind': BK.KINDS.get(k['kind'], k['kind']), 'extra': k['edition'] or ''} for k in rows]
    return []


def lend_info(area, item_id):
    """Fuer den Kasten auf der Detailseite: offene Vorgaenge, noch verleihbare Exemplare, bekannte Namen."""
    try:
        with L.db() as c:
            open_ = L.open_for(c, area, item_id)
            names = [p['name'] for p in L.people(c)]
        phys = physical(area, item_id)
    except Exception:
        return {'open': [], 'free': [], 'phys': [], 'names': []}
    lent = {x['copy_id'] for x in open_}
    if area == 'music':
        free = [] if open_ else phys
    else:
        free = [p for p in phys if p['copy_id'] not in lent]
    return {'open': open_, 'free': free, 'phys': phys, 'names': names}


def lent_ids(area):
    try:
        with L.db() as c:
            return L.open_ids(c, area)
    except Exception:
        return set()


def _detail_text(area, item_id, copy_id):
    for p in physical(area, item_id):
        if p['copy_id'] == copy_id:
            return ' · '.join(x for x in (p['kind'], ('Staffel ' + p['seasons']) if p.get('seasons') else '', p['extra']) if x)
    return None


def _safe_back(v, default='/lend'):
    v = v or ''
    return v if v.startswith('/') and not v.startswith('//') else default


# ---------------------------------------------------------------- Seiten
async def index(request):
    p = request.query_params
    q, area, person = p.get('q', '').strip(), p.get('area', ''), p.get('person', '').strip()
    area = area if area in L.AREAS else ''

    def load():
        with L.db() as c:
            rows, ppl, hist, st = L.open_all(c, area or None), L.people(c), L.history(c, limit=60), L.stats(c)
        groups = {}
        for r in rows:
            groups.setdefault((r['person_id'], r['person']), []).append(r)
        return dict(groups=list(groups.items()), people=ppl, history=hist, stats=st, results=_search(q) if q else [])
    d = await run_in_threadpool(load)
    return render(request, 'lend.html', q=q, sel_area=area, person=person, message=p.get('message', ''), **d)


def _search(q):
    """Treffer aus allen Bereichen mit ihren verleihbaren Exemplaren."""
    out = []
    music, _ = H._music_hits(q, 20)
    for m in music:
        out.append({'area': 'music', 'id': m['id'], 'title': m['title'], 'sub': m['artist'] or '', 'year': m['year']})
    with F.db() as c:
        films, _ = F.query(c, 'all', q=q, limit=20)
        out += [{'area': 'film', 'id': f['id'], 'title': f['title'], 'sub': '', 'year': f['year']} for f in films]
    with S.db() as c:
        series, _ = S.query(c, 'all', q=q, limit=20)
        out += [{'area': 'series', 'id': s['id'], 'title': s['title'], 'sub': '', 'year': s.get('year') if isinstance(s, dict) else s['year']}
                for s in series]
    try:
        with BK.db() as c:
            books, _ = BK.query(c, 'all', q=q, sort='title', limit=20)
            out += [{'area': 'book', 'id': b['id'], 'title': b['title'], 'sub': b['authors'] or '', 'year': b['year']} for b in books]
    except Exception:
        pass
    for x in out:
        info = lend_info(x['area'], x['id'])
        x.update(free=info['free'], open=info['open'], digital=not info['phys'])
    return out


async def add(request):
    f, _ = await _form(request)
    area, item_id = f.get('area'), _int(f.get('item_id'))
    back = _safe_back(f.get('back'))
    if area not in L.AREAS or not item_id:
        return go(back, 'Nichts ausgewählt.')
    if not L.clean_name(f.get('person')):
        return go(back, 'Bitte eintragen, an wen.')
    lent_at, due_at = L.parse(f.get('date')), L.parse(f.get('due'))
    if lent_at is False or due_at is False:
        return go(back, 'Das Datum ist nicht lesbar (z. B. 24.12.2019 oder nur 2019).')
    copy_id = _int(f.get('copy_id'))

    def do():
        info = lend_info(area, item_id)
        free = info['free']
        if not free:
            return 'Nur digital vorhanden oder schon verliehen.' if info['phys'] else 'Nur digital vorhanden – das lässt sich nicht verleihen.'
        pick = next((x for x in free if x['copy_id'] == copy_id), None) if copy_id else free[0]
        if not pick:
            return 'Dieses Exemplar ist schon verliehen.'
        with L.db() as c:
            L.lend(c, area, item_id, f.get('title') or '?', f.get('person'), lent_at, due_at, f.get('note'), pick['copy_id'],
                   _detail_text(area, item_id, pick['copy_id']), f.get('subtitle'))
        return 'Als verliehen eingetragen.'
    return go(back, await run_in_threadpool(do))


def _loan_action(fn):
    async def handler(request):
        lid = request.path_params['lid']
        f, _ = await _form(request)
        back = _safe_back(f.get('back'))

        def do():
            with L.db() as c:
                if not L.get(c, lid):
                    return 'Nicht gefunden.'
                return fn(c, lid, f)
        return go(back, await run_in_threadpool(do))
    return handler


def _return(c, lid, f):
    when = L.parse(f.get('date'))
    if when is False:
        return 'Das Datum ist nicht lesbar (z. B. 24.12.2019 oder nur 2019).'
    L.give_back(c, lid, when or None)
    return 'Als zurückbekommen eingetragen.'


def _delete(c, lid, f):
    L.delete(c, lid)
    return 'Eintrag gelöscht.'


def _reopen(c, lid, f):
    c.execute('UPDATE loans SET returned_at=NULL WHERE id=?', (lid,))
    return 'Wieder als verliehen eingetragen.'


async def person_page(request):
    pid = request.path_params['pid']

    def load():
        with L.db() as c:
            p = L.person(c, pid)
            return p and dict(person=p, rows=L.by_person(c, pid), history=L.history(c, person=pid, limit=200))
    d = await run_in_threadpool(load)
    if not d:
        return go('/lend', 'Nicht gefunden.')
    return render(request, 'lend_person.html', message=request.query_params.get('message', ''), **d)


async def person_edit(request):
    pid = request.path_params['pid']
    f, _ = await _form(request)

    def do():
        with L.db() as c:
            if not L.person(c, pid):
                return pid, 'Nicht gefunden.'
            return L.rename_person(c, pid, f.get('name'), f.get('note')), 'Gespeichert.'
    new, msg = await run_in_threadpool(do)
    return go(f'/lend/person/{new}', msg)


async def person_return_all(request):
    pid = request.path_params['pid']
    f, _ = await _form(request)
    when = L.parse(f.get('date'))

    def do():
        with L.db() as c:
            for r in L.by_person(c, pid):
                L.give_back(c, r['id'], when or None)
    await run_in_threadpool(do)
    return go(f'/lend/person/{pid}', 'Alles als zurückbekommen eingetragen.')


async def text_list(request):
    """Alles Verliehene als einfacher Text, z. B. zum Kopieren in eine Nachricht."""
    from starlette.responses import PlainTextResponse
    lang = ctx(request)['_']

    def load():
        with L.db() as c:
            return L.open_all(c)
    rows = await run_in_threadpool(load)
    out, cur = [], None
    for r in rows:
        if r['person'] != cur:
            cur = r['person']
            out.append(('' if not out else '\n') + cur)
        dt = r['lent_at'] or ''
        dt = f'{dt[8:10]}.{dt[5:7]}.{dt[:4]}' if len(dt) >= 10 else dt
        out.append(f"  - {r['title']}" + (f" ({r['subtitle']})" if r['subtitle'] else '') + (f", {r['detail']}" if r['detail'] else '')
                   + (f", {lang('seit §', dt)}" if dt else ''))
    return PlainTextResponse('\n'.join(out) + '\n' if out else '')


routes = [
    Route('/', index), Route('/add', add, methods=['POST']), Route('/text', text_list),
    Route('/{lid:int}/return', _loan_action(_return), methods=['POST']),
    Route('/{lid:int}/reopen', _loan_action(_reopen), methods=['POST']),
    Route('/{lid:int}/delete', _loan_action(_delete), methods=['POST']),
    Route('/person/{pid:int}', person_page), Route('/person/{pid:int}/edit', person_edit, methods=['POST']),
    Route('/person/{pid:int}/return-all', person_return_all, methods=['POST']),
]
app = Starlette(routes=routes)
