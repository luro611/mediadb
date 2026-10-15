"""Seite "Merkliste" (/watchlist): neue Folgen und Staffeln der eigenen Serien, vorgemerkte Filme und Serien.
Starlette-App wie films_web und series_web, in main.py eingehaengt."""
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.routing import Route
from . import watchlist as WL
from . import series_db as S
from . import films_tmdb as T
from . import films_web as FW

templates = None
ctx = None
go = FW.go
_int = FW._int
_form = FW._form


def setup(templates_, ctx_, start_scheduler=True):
    global templates, ctx
    templates, ctx = templates_, ctx_
    WL.init()
    if start_scheduler:
        WL.scheduler()


def render(request, name, **kw):
    return templates.TemplateResponse(request, name, ctx(request, area='watch', tmdb_on=T.configured(), **kw))


async def index(request):
    p = request.query_params
    q = p.get('q', '').strip()

    def load():
        with S.db() as c:
            soon, new, announced = S.upcoming(c)
        res, err = T.multi_search(q) if q and T.configured() else ([], None)
        if res:
            mine = {(x['kind'], x['tmdb_id']) for x in WL.items(include_done=False)}
            owned = {}
            for kind, m in WL.DBS.items():
                with m.db() as c:
                    tbl = 'films' if kind == 'movie' else 'series'
                    owned.update({(kind, r[0]): r[1] for r in c.execute(f'SELECT tmdb_id, id FROM {tbl} WHERE tmdb_id IS NOT NULL')})
            for x in res:
                x['listed'] = (x['kind'], x['tmdb_id']) in mine
                x['owned'] = owned.get((x['kind'], x['tmdb_id']))
        return dict(soon=soon, new=new, announced=announced, items=WL.items(), results=res, err=err)
    d = await run_in_threadpool(load)
    return render(request, 'watchlist.html', q=q, upd=WL.UPD, last=WL.last_run(), img_base=T.IMG,
                  message=p.get('message', ''), **d)


async def add(request):
    f, _ = await _form(request)
    kind = f.get('kind') if f.get('kind') in WL.DBS else 'movie'
    if not (f.get('title') or '').strip():
        return go('/watchlist', 'Bitte einen Titel eingeben.')
    _, new = await run_in_threadpool(WL.add, kind, _int(f.get('tmdb_id')), f.get('title').strip(), (f.get('note') or '').strip(),
                                     _int(f.get('year')), f.get('poster_path') or None, f.get('overview') or None, f.get('original_title') or None)
    return go('/watchlist#merkliste', 'Vorgemerkt.' if new else 'Stand schon auf der Merkliste.')


def _item_action(fn, msg=''):
    async def handler(request):
        kind, wid = request.path_params['kind'], request.path_params['wid']
        if kind not in WL.DBS:
            return go('/watchlist')
        f, _ = await _form(request)
        r = await run_in_threadpool(fn, kind, wid, f)
        return go('/watchlist#w-%s-%d' % (kind, wid) if fn is not _delete else '/watchlist#merkliste', r or msg)
    return handler


def _note(kind, wid, f):
    WL.set_note(kind, wid, (f.get('note') or '').strip())
    return 'Notiz gespeichert.'


def _done(kind, wid, f):
    WL.set_done(kind, wid, f.get('on') != '0')
    return ''


def _delete(kind, wid, f):
    WL.delete(kind, wid)
    return 'Von der Merkliste entfernt.'


def _refresh(kind, wid, f):
    return WL.refresh_item(kind, wid) or 'Aktualisiert.'


async def update(request):
    f, _ = await _form(request)
    if not T.configured():
        return go('/watchlist', 'Kein TMDB-Schlüssel eingetragen (siehe Einstellungen).')
    WL.start(force=f.get('force') == '1')
    return go('/watchlist')


async def status(request):
    u = WL.UPD
    return JSONResponse({'state': u['state'], 'done': u['done'], 'total': u['total'], 'current': u['current']})


async def done_list(request):
    items = await run_in_threadpool(WL.items, True)
    return render(request, 'watchlist_done.html', items=[x for x in items if x['done_at']], img_base=T.IMG)


routes = [
    Route('/', index), Route('/add', add, methods=['POST']), Route('/update', update, methods=['POST']), Route('/status', status),
    Route('/done', done_list),
    Route('/{kind}/{wid:int}/note', _item_action(_note), methods=['POST']),
    Route('/{kind}/{wid:int}/done', _item_action(_done), methods=['POST']),
    Route('/{kind}/{wid:int}/delete', _item_action(_delete), methods=['POST']),
    Route('/{kind}/{wid:int}/refresh', _item_action(_refresh), methods=['POST']),
]
app = Starlette(routes=routes)
