"""Hinweis auf eine neue Version: einmal am Tag das neueste Release auf Codeberg abfragen.

Es wird nur die oeffentliche Release-Liste gelesen (keine Daten aus der Sammlung, keine Kennung), abschaltbar unter
Einstellungen -> Dienste und Automatik (UPDATE_CHECK=0). Ein Release wird erst angelegt, wenn das Docker-Image fertig
hochgeladen ist; der Hinweis erscheint also erst, wenn "Pull" in Dockhand auch wirklich die neue Version bringt."""
import logging, re, threading, time
import requests
from . import config as C

REPO = 'luro61/mediadb'
API = f'https://codeberg.org/api/v1/repos/{REPO}/releases/latest'
RELEASES = f'https://codeberg.org/{REPO}/releases'
EVERY = 24 * 3600
STATE = {'latest': None, 'url': None, 'checked': 0.0, 'error': ''}


def parse(v):
    """'v1.9.1' -> (1, 9, 1); Unlesbares -> None."""
    m = re.fullmatch(r'v?(\d+)\.(\d+)(?:\.(\d+))?', str(v or '').strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


def enabled():
    return C.flag('UPDATE_CHECK')


def check():
    """Neuestes Release holen. Gibt (version, url) zurueck oder (None, None)."""
    try:
        r = requests.get(API, timeout=10, headers={'User-Agent': f'MediaDB/{C.version()} (+https://codeberg.org/{REPO})',
                                                   'Accept': 'application/json'})
        if r.status_code == 404:  # noch kein Release
            STATE.update(latest=None, url=None, checked=time.time(), error='')
            return None, None
        r.raise_for_status()
        d = r.json()
        tag = d.get('tag_name') or ''
        if d.get('draft') or d.get('prerelease') or not parse(tag):
            return None, None
        STATE.update(latest=tag.lstrip('v'), url=d.get('html_url') or RELEASES, checked=time.time(), error='')
    except Exception as e:
        STATE.update(checked=time.time(), error=str(e)[:200])
        logging.info('Update-Pruefung nicht moeglich: %s', e)
    return STATE['latest'], STATE['url']


def info():
    """Fuer die Fusszeile: {'version', 'url'}, wenn ein neueres Release vorliegt, sonst None."""
    if not enabled() or not STATE['latest']:
        return None
    now, new = parse(C.version()), parse(STATE['latest'])
    if now and new and new > now:
        return {'version': STATE['latest'], 'url': STATE['url'] or RELEASES}
    return None


def scheduler():
    """Kurz nach dem Start und danach einmal am Tag pruefen."""
    def loop():
        time.sleep(30)
        while True:
            try:
                if enabled():
                    check()
            except Exception:
                logging.exception('Update-Pruefung')
            time.sleep(EVERY)
    threading.Thread(target=loop, daemon=True, name='update-check').start()
