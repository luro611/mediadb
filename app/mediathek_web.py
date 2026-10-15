"""Treffer aus den Mediatheken als nachgeladene Abschnitte (/mediathek/...), damit die Detailseiten nicht warten muessen.
  /mediathek/series/<id>   Folgen einer Serie (mit Abgleich gegen den Episodenfuehrer: vorhanden / fehlt dir)
  /mediathek/film/<id>     ein Film
  /mediathek/watchlist     vorgemerkte Filme und Serien, die gerade in einer Mediathek stehen"""
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse
from starlette.routing import Route
from . import mediathek as M
from . import films_db as F
from . import series_db as S
from . import watchlist as WL

templates = None
ctx = None


def setup(templates_, ctx_):
    global templates, ctx
    templates, ctx = templates_, ctx_
    templates.env.globals['mediathek_on'] = M.enabled


def _render(request, **kw):
    return templates.TemplateResponse(request, '_mediathek_hits.html', ctx(request, **kw), headers={'Cache-Control': 'no-store'})


async def series(request):
    sid = request.path_params['sid']
    if not M.enabled():
        return HTMLResponse('')

    def load():
        with S.db() as c:
            s = S.get(c, sid)
            if not s:
                return None
            eps = [(r['season'], r['episode'], r['name']) for r in c.execute('SELECT season, episode, name FROM episodes WHERE series_id=?', (sid,))]
            have = set(S.have_map(c, sid))
        return M.series_hits(s['title'], s['original_title'], eps, have)
    r = await run_in_threadpool(load)
    if r is None:
        return HTMLResponse('')
    hits, err = r
    return _render(request, kind='series', hits=hits, err=err, n_missing=sum(1 for x in hits if x['state'] == 'missing'))


async def film(request):
    fid = request.path_params['fid']
    if not M.enabled():
        return HTMLResponse('')

    def load():
        with F.db() as c:
            f = F.get_film(c, fid)
        return f and M.film_hits(f['title'], f['original_title'], f['year'])
    r = await run_in_threadpool(load)
    if not r:
        return HTMLResponse('')
    hits, err = r
    return _render(request, kind='film', hits=hits, err=err)


async def watchlist(request):
    if not M.enabled():
        return HTMLResponse('')

    def load():
        out = []
        for x in WL.items(include_done=False):
            if x['kind'] == 'tv':
                hits, _ = M.series_hits(x['title'], x.get('original_title'))
            else:
                hits, _ = M.film_hits(x['title'], x.get('original_title'), x.get('year'))
            if hits:
                out.append({'item': x, 'hits': hits[:3], 'n': len(hits)})
        return out
    found = await run_in_threadpool(load)
    return _render(request, kind='watchlist', found=found, hits=[], err=None)


routes = [Route('/series/{sid:int}', series), Route('/film/{fid:int}', film), Route('/watchlist', watchlist)]
app = Starlette(routes=routes)
