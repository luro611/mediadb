"""Seite Einstellungen (/settings): TMDB-Schluessel, Datensprache, MusicBrainz-Kontakt, Discogs, Schalter.
Dazu der Hintergrundlauf "Alle Filme und Serien in der neuen Sprache laden" (RELANG)."""
import logging, os, threading, time
from urllib.parse import quote
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
from . import updates
from . import users as U

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
    return templates.TemplateResponse(request, name, ctx(request, area='settings', tmdb_on=T.configured(), tmdb_state=T.key_state(), **kw))


def _view():
    cfg = {k: C.get(k) for k in C.KEYS}
    return dict(cfg=cfg, src={k: C.source(k) for k in C.KEYS}, masked={k: C.mask(cfg[k]) for k in C.SECRET},
                languages=C.DATA_LANGUAGES, data_lang=T.language(), contact=C.get('MB_CONTACT') or C.contact_from_agent(),
                flags={k: C.flag(k) for k in ('BARCODE_LOOKUP', 'COVER_WEB', 'AUTO_UPDATE', 'MEDIATHEK', 'UPDATE_CHECK')}, relang=RELANG,
                stored_lang=C.stored().get('TMDB_LANGUAGE'),
                password_on=bool(os.getenv('APP_PASSWORD')), public=os.getenv('ALLOW_PUBLIC', '0') in ('1', 'true', 'yes', 'ja', 'on'),
                ui_langs=i18n.LANGS, people=list(U.users().values()),
                nas_shares=[{k: v for k, v in x.items() if k != 'password'} | {'has_password': bool(x.get('password'))} for x in nas.shares()],
                nas_logins=nas.logins(), upd=updates.STATE, upd_info=updates.info(), app_ver=C.version(),
                upd_checked=time.strftime('%d.%m.%Y %H:%M', time.localtime(updates.STATE['checked'])) if updates.STATE['checked'] else '')


async def page(request):
    p = request.query_params
    return render(request, 'settings.html', message=p.get('message', ''), err=p.get('err', ''), changed=p.get('changed', ''), part=p.get('part', ''),
                  nas_label=p.get('nas', '')[:40], **_view())


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


async def update_check(request):
    """Knopf „Jetzt nach neuer Version suchen“."""
    await run_in_threadpool(updates.check)
    if updates.STATE['error']:
        return go('/settings?part=update#update', 'GitHub ist gerade nicht erreichbar. Bitte später noch einmal versuchen.')
    i = updates.info()
    return go('/settings?part=update#update', f'Neue Version {i["version"]} verfügbar.' if i else f'MediaDB {C.version()} ist die neueste Version.')


async def test_tmdb(request):
    def work():
        if not T.configured():
            return 'Kein TMDB-Schlüssel eingetragen.'
        d, err = T.tmdb_get('/configuration')
        return err or 'Der TMDB-Schlüssel funktioniert.'
    return go('/settings#tmdb', await run_in_threadpool(work))


# ---------------------------------------------------------------- Nutzer und Anmeldung (seit 1.20)
def _users_back(msg):
    return go('/settings?part=users#nutzer', msg)


def _login_as(resp, uid):
    resp.set_cookie(U.COOKIE, U.make_token(U.SECRET(), uid), max_age=U.MAX_AGE, httponly=True, samesite='lax')
    return resp


async def users_setup(request):
    """Erster Verwalter und Art der Anmeldung in einem Schritt; danach ist man gleich als dieser Verwalter angemeldet."""
    f, _ = await _form(request)
    if U.users():
        return _users_back('Es gibt schon Nutzer.')
    if len(f.get('password') or '') < 4:
        return _users_back('Der Verwalter braucht ein Passwort mit mindestens 4 Zeichen.')
    err, uid = U.create(f.get('name'), 'admin', f.get('password'))
    if err:
        return _users_back(err)
    err = U.set_mode(f.get('mode') if f.get('mode') in ('profiles', 'password') else 'profiles')
    if err:
        return _users_back(err)
    return _login_as(_users_back('Konten eingeschaltet. Du bist als Verwalter angemeldet.'), uid)


async def users_add(request):
    f, _ = await _form(request)
    if U.mode() == 'password' and not f.get('password'):
        return _users_back('Bei „Name und Passwort“ braucht jeder ein Passwort.')
    if f.get('role') == 'admin' and not f.get('password'):
        return _users_back('Verwalter und alle bei „Name und Passwort“ brauchen ein Passwort.')
    err, _uid = U.create(f.get('name'), f.get('role'), f.get('password') or '')
    return _users_back(err or 'Nutzer hinzugefügt.')


async def users_save(request):
    f, _ = await _form(request)
    uid = int(request.path_params['uid'])
    role = f.get('role')
    u = U.get(uid)
    if u and role == 'admin' and not u['secret'] and not f.get('password'):
        return _users_back('Verwalter und alle bei „Name und Passwort“ brauchen ein Passwort.')
    err = U.update(uid, name=f.get('name'), role=role, pw=f.get('password') or None, remove_pw=f.get('remove_pw') == '1')
    return _users_back(err or 'Gespeichert.')


async def users_delete(request):
    err = U.delete(int(request.path_params['uid']))
    return _users_back(err or 'Nutzer entfernt.')


async def users_mode(request):
    f, _ = await _form(request)
    err = U.set_mode(f.get('mode', ''))
    return _users_back(err or 'Gespeichert.')


# ---------------------------------------------------------------- NAS-Freigaben
NAS_FIELDS = ('label', 'host', 'share', 'folder', 'user', 'password', 'from')


async def nas_save(request):
    f, _ = await _form(request)
    sid = (f.get('id') or '').strip() or None
    new_id, err = await run_in_threadpool(nas.save_share, {k: f.get(k) for k in NAS_FIELDS}, sid)
    if err:
        return go('/settings?part=nas#nas', err)
    ok, text, _ = await run_in_threadpool(nas.check, new_id)
    return go(_nas_url(new_id), _filled(text))  # gespeichert ist schon; die Meldung sagt, ob die Verbindung klappt


async def nas_check(request):
    f, _ = await _form(request)
    ok, text, _ = await run_in_threadpool(nas.check, f.get('id') or '')
    return go(_nas_url(f.get('id') or ''), _filled(text))


def _nas_url(sid):
    """Zurueck zu den NAS-Freigaben; der Name steht dann vor der Meldung („NAS: Musik · Verbindung klappt …“)."""
    s = nas.get_share(sid)
    return '/settings?part=nas' + ('&nas=' + quote(s['label']) if s else '') + '#nas'


async def nas_test(request):
    """Knopf „Verbindung prüfen“ im Formular: prueft die eingetragenen Angaben, ohne zu speichern (Antwort als JSON)."""
    f, _ = await _form(request)
    ok, text, detail = await run_in_threadpool(nas.test, {k: f.get(k) for k in NAS_FIELDS}, (f.get('id') or '').strip() or None)
    lang = ctx(request)['lang']
    t = i18n.tr_text(lang, text[0], *text[1:]) if isinstance(text, tuple) else i18n.tr_text(lang, text)
    return JSONResponse({'ok': ok, 'message': t, 'detail': detail})


async def nas_status(request):
    """Fuer den Punkt neben „NAS: …“ in der Ordnerauswahl: {'/nas/<id>': true/false}."""
    return JSONResponse(await run_in_threadpool(nas.online))


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


routes = [Route('/', page), Route('/save', save, methods=['POST']), Route('/test-tmdb', test_tmdb, methods=['POST']), Route('/update-check', update_check, methods=['POST']),
          Route('/relang', relang, methods=['POST']), Route('/relang/status', relang_status),
          Route('/nas/save', nas_save, methods=['POST']), Route('/nas/check', nas_check, methods=['POST']),
          Route('/nas/test', nas_test, methods=['POST']), Route('/nas/status', nas_status),
          Route('/nas/delete', nas_delete, methods=['POST']),
          Route('/users/setup', users_setup, methods=['POST']), Route('/users/add', users_add, methods=['POST']),
          Route('/users/mode', users_mode, methods=['POST']), Route('/users/{uid:int}/save', users_save, methods=['POST']),
          Route('/users/{uid:int}/delete', users_delete, methods=['POST'])]
app = Starlette(routes=routes)
