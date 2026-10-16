"""Seite Einstellungen (/settings): TMDB-Schluessel, Datensprache, MusicBrainz-Kontakt, Discogs, Schalter.
Dazu der Hintergrundlauf "Alle Filme und Serien in der neuen Sprache laden" (RELANG)."""
import logging, os, threading
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.routing import Route
from . import config as C
from . import films_db as F
from . import films_tmdb as T
from . import series_db as S
from . import series_files as SX
from . import watchlist as WL
from . import films_web as FW
from . import i18n
from . import nas

templates = None
ctx = None
go = FW.go
_form = FW._form
RELANG = {'state': 'idle', 'done': 0, 'total': 0, 'current': '', 'lang': '', 'errors': 0}

# Felder, die von der Datensprache abhaengen (Filme); die Serien laden ihre Angaben und den Episodenfuehrer komplett neu
FILM_LANG_FIELDS = ['overview', 'tagline', 'genres', 'certification', 'collection_name', 'keywords', 'trailer_url']


def setup(templates_, ctx_):
    global templates, ctx
    templates, ctx = templates_, ctx_


def render(request, name, **kw):
    return templates.TemplateResponse(request, name, ctx(request, area='settings', tmdb_on=T.configured(), **kw))


def _view():
    cfg = {k: C.get(k) for k in C.KEYS}
    return dict(cfg=cfg, src={k: C.source(k) for k in C.KEYS}, masked={k: C.mask(cfg[k]) for k in C.SECRET},
                languages=C.DATA_LANGUAGES, data_lang=T.language(), contact=C.get('MB_CONTACT') or C.contact_from_agent(),
                flags={k: C.flag(k) for k in ('BARCODE_LOOKUP', 'COVER_WEB', 'AUTO_UPDATE', 'MEDIATHEK', 'UPDATE_CHECK')}, relang=RELANG,
                stored_lang=C.stored().get('TMDB_LANGUAGE'),
                password_on=bool(os.getenv('APP_PASSWORD')), public=os.getenv('ALLOW_PUBLIC', '0') in ('1', 'true', 'yes', 'ja', 'on'),
                ui_langs=i18n.LANGS,
                nas_shares=[{k: v for k, v in x.items() if k != 'password'} | {'has_password': bool(x.get('password'))} for x in nas.shares()],
                nas_logins=nas.logins())


async def page(request):
    p = request.query_params
    return render(request, 'settings.html', message=p.get('message', ''), err=p.get('err', ''), changed=p.get('changed', ''), part=p.get('part', ''), **_view())


async def save(request):
    f, _ = await _form(request)
    old_lang = T.language()
    values = {}
    for k in ('TMDB_API_KEY', 'DISCOGS_TOKEN'):
        if f.get(k + '_remove') == '1':
            values[k] = ''
        elif (f.get(k) or '').strip():
            values[k] = f.get(k).strip()
    lang = f.get('TMDB_LANGUAGE', '')
    if lang in dict(C.DATA_LANGUAGES):
        values['TMDB_LANGUAGE'] = lang
    contact = (f.get('MB_CONTACT') or '').strip()
    if contact and ('@' not in contact or ' ' in contact or len(contact) > 120):
        return go('/settings', 'Bitte eine gültige E-Mail-Adresse eintragen.')
    values['MB_CONTACT'] = contact
    for k in ('BARCODE_LOOKUP', 'COVER_WEB', 'AUTO_UPDATE', 'MEDIATHEK', 'UPDATE_CHECK'):
        values[k] = '1' if f.get(k) == '1' else '0'
    ok = await run_in_threadpool(C.save, values)
    if not ok:
        return go('/settings', 'Die Einstellungen konnten nicht gespeichert werden.')
    if T.language() != old_lang:
        return go(f'/settings?changed=1#sprache', 'Gespeichert. Die Datensprache wurde geändert.')
    return go('/settings', 'Gespeichert.')


async def test_tmdb(request):
    def work():
        if not T.configured():
            return 'Kein TMDB-Schlüssel eingetragen.'
        d, err = T.tmdb_get('/configuration')
        return err or 'Der TMDB-Schlüssel funktioniert.'
    return go('/settings#tmdb', await run_in_threadpool(work))


# ---------------------------------------------------------------- NAS-Freigaben
NAS_FIELDS = ('label', 'host', 'share', 'folder', 'user', 'password', 'from')


async def nas_save(request):
    f, _ = await _form(request)
    sid = (f.get('id') or '').strip() or None
    new_id, err = await run_in_threadpool(nas.save_share, {k: f.get(k) for k in NAS_FIELDS}, sid)
    if err:
        return go('/settings?part=nas#nas', err)
    ok, text, _ = await run_in_threadpool(nas.check, new_id)
    return go('/settings?part=nas#nas', _filled(text))  # gespeichert ist schon; die Meldung sagt, ob die Verbindung klappt


async def nas_check(request):
    f, _ = await _form(request)
    ok, text, _ = await run_in_threadpool(nas.check, f.get('id') or '')
    return go('/settings?part=nas#nas', _filled(text))


async def nas_test(request):
    """Knopf „Verbindung prüfen“ im Formular: prueft die eingetragenen Angaben, ohne zu speichern (Antwort als JSON)."""
    f, _ = await _form(request)
    ok, text, detail = await run_in_threadpool(nas.test, {k: f.get(k) for k in NAS_FIELDS}, (f.get('id') or '').strip() or None)
    lang = ctx(request)['lang']
    t = i18n.tr_text(lang, text[0], *text[1:]) if isinstance(text, tuple) else i18n.tr_text(lang, text)
    return JSONResponse({'ok': ok, 'message': t, 'detail': detail})


async def nas_delete(request):
    f, _ = await _form(request)
    await run_in_threadpool(nas.delete_share, f.get('id') or '')
    return go('/settings?part=nas#nas', 'Freigabe entfernt. Schon eingelesene Einträge bleiben erhalten.')


def _filled(text):
    """('Text mit § und §', 1, 2) -> 'Text mit 1 und 2' (wird beim Anzeigen ueber die §-Muster uebersetzt)."""
    if isinstance(text, tuple):
        t, *args = text
        for a in args:
            t = t.replace('§', str(a), 1)
        return t
    return text


# ---------------------------------------------------------------- Neu laden in der Datensprache
def relang_worker(with_titles):
    try:
        with F.db() as c:
            films = [dict(r) for r in c.execute('SELECT id, tmdb_id, title FROM films WHERE tmdb_id IS NOT NULL ORDER BY id')]
        with S.db() as c:
            series = [dict(r) for r in c.execute('SELECT id, tmdb_id, title FROM series WHERE tmdb_id IS NOT NULL ORDER BY id')]
        RELANG.update(total=len(films) + len(series), done=0, errors=0, lang=T.language())
        for fl in films:
            RELANG['current'] = fl['title']
            d, err = T.details(fl['tmdb_id'])
            if err and 'Schlüssel' in err:
                raise RuntimeError(err)
            if d:
                keys = FILM_LANG_FIELDS + (['title'] if with_titles else [])
                with F.db() as c:
                    F.update_film(c, fl['id'], {k: d.get(k) for k in keys if k in d})
            else:
                RELANG['errors'] += 1
            RELANG['done'] += 1
        for s in series:
            RELANG['current'] = s['title']
            with S.db() as c:
                err = SX.refresh_guide(c, s['id'])
                if not err and with_titles:
                    d, _ = T.tv_details(s['tmdb_id'])
                    if d and d.get('title'):
                        S.update(c, s['id'], {'title': d['title']})
            if err:
                if 'Schlüssel' in err:
                    raise RuntimeError(err)
                RELANG['errors'] += 1
            RELANG['done'] += 1
        for kind in WL.DBS:  # Merkliste: Titel und Termine
            for r in WL._watch_ids(kind):
                WL.refresh_item(kind, r['id'])
        RELANG.update(state='done', current='')
    except Exception as e:
        logging.exception('Neu laden in der Datensprache fehlgeschlagen')
        RELANG.update(state='error', current=str(e))


async def relang(request):
    f, _ = await _form(request)
    if RELANG['state'] == 'running':
        return go('/settings#sprache')
    if not T.configured():
        return go('/settings', 'Kein TMDB-Schlüssel eingetragen.')
    RELANG.update(state='running', done=0, total=0, current='', errors=0)
    threading.Thread(target=relang_worker, args=(f.get('titles') == '1',), daemon=True).start()
    return go('/settings#sprache')


async def relang_status(request):
    return JSONResponse({k: RELANG[k] for k in ('state', 'done', 'total', 'current')})


def activity():
    if RELANG['state'] == 'running':
        return {'label': 'Filme und Serien in der Datensprache neu laden', 'net': True, 'done': RELANG['done'],
                'total': RELANG['total'], 'current': RELANG['current'], 'url': '/settings#sprache'}


routes = [Route('/', page), Route('/save', save, methods=['POST']), Route('/test-tmdb', test_tmdb, methods=['POST']),
          Route('/relang', relang, methods=['POST']), Route('/relang/status', relang_status),
          Route('/nas/save', nas_save, methods=['POST']), Route('/nas/check', nas_check, methods=['POST']),
          Route('/nas/test', nas_test, methods=['POST']),
          Route('/nas/delete', nas_delete, methods=['POST'])]
app = Starlette(routes=routes)
