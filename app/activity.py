"""Was laeuft gerade im Hintergrund? Sammelt den Stand aller Hintergrundaufgaben fuer die Anzeige oben in der Navigation.

Jeder Bereich meldet eine Funktion an (register), die None liefert oder ein dict:
  {'label': deutscher Text, 'net': True/False, 'files': True/False, 'done': n, 'total': n, 'current': '', 'url': '/...'}
'files' heisst: Die App liest gerade Dateien in deinen Ordnern (Umbenennen kann dann scheitern)."""
import logging
from starlette.responses import JSONResponse
from . import i18n

SOURCES = []


def register(fn):
    SOURCES.append(fn)
    return fn


def current():
    out = []
    for fn in SOURCES:
        try:
            r = fn()
        except Exception:
            logging.exception('Status einer Hintergrundaufgabe')
            r = None
        if r:
            out.extend(r if isinstance(r, list) else [r])
    return out


async def endpoint(request):
    lang = request.query_params.get('lang', 'de')
    if lang not in i18n.LANGS:
        lang = 'de'
    items = []
    for x in current():
        items.append({'label': i18n.tr_text(lang, x['label']), 'net': bool(x.get('net')), 'files': bool(x.get('files')),
                      'done': x.get('done') or 0, 'total': x.get('total') or 0, 'url': x.get('url') or '',
                      'current': i18n.tr_text(lang, *x['note']) if x.get('note') else (x.get('current') or '')})
    return JSONResponse({'items': items}, headers={'Cache-Control': 'no-store'})


# ---------------------------------------------------------------- Bereiche Filme, Serien, Merkliste
def register_media():
    from . import films_files as FX, films_art as FA, series_files as SX, watchlist as WL

    @register
    def _films_import():
        j = FX.JOB
        if j['state'] in ('scanning', 'applying'):
            return {'label': 'Filme: Ordner einlesen' if j['state'] == 'scanning' else 'Filme: übernehmen und Poster laden',
                    'files': True, 'net': True, 'done': j['done'], 'total': j['total'], 'url': '/films/files'}

    @register
    def _films_art():
        j = FA.JOB
        if j['state'] == 'running':
            return {'label': 'Filme: fehlende Poster laden', 'files': True, 'net': True, 'done': j['done'], 'total': j['total'], 'url': '/films'}

    @register
    def _films_people():
        j = FX.PEOPLE
        if j['running']:
            return {'label': 'Filme: Besetzung nachladen', 'net': True, 'done': j['done'], 'total': j['total'], 'url': '/films'}

    @register
    def _series_import():
        j = SX.JOB
        if j['state'] in ('scanning', 'applying'):
            return {'label': 'Serien: Ordner einlesen' if j['state'] == 'scanning' else 'Serien: übernehmen, Episodenführer laden',
                    'files': j['state'] == 'applying' or j.get('phase') in ('collect', 'parse'), 'net': j.get('phase') in ('tmdb', 'apply'),
                    'done': j['done'], 'total': j['total'], 'current': j.get('current') if j.get('phase') != 'collect' else '',
                    'note': ('§ Videodateien gefunden', j.get('found', 0)) if j.get('phase') == 'collect' else None, 'url': '/series/files'}

    @register
    def _watch():
        u = WL.UPD
        if u['state'] == 'running':
            return {'label': 'Serien und Merkliste aktualisieren', 'net': True, 'done': u['done'], 'total': u['total'],
                    'current': u.get('current') or '', 'url': '/watchlist'}
