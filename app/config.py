"""Einstellungen, die man in der App aendern kann (Seite /settings), gespeichert in data/settings.json unter "config".

Reihenfolge: Wert aus der Einstellungsseite, sonst aus .env, sonst Voreinstellung. Beim Start und beim Speichern werden die
Werte in os.environ geschrieben, damit der uebrige Code sie wie bisher mit os.getenv liest; Aenderungen gelten sofort.
Zugriffsschutz (APP_PASSWORD, ALLOW_PUBLIC, BASE_PATH) bleibt bewusst in .env: Wer die Seite erreicht, soll ihn nicht abschalten koennen."""
import json, logging, os, threading
from pathlib import Path

FILE = None
_lock = threading.Lock()
_ENV0 = {}  # Werte aus .env beim Start, um "auf .env zuruecksetzen" zu koennen

# Datensprache fuer Filme, Serien, Buecher: Sprache-Land (Land steuert Altersfreigabe, Kinostart, Streamingdienste)
DATA_LANGUAGES = [
    ('de-DE', 'Deutsch (Deutschland)'), ('de-AT', 'Deutsch (Österreich)'), ('de-CH', 'Deutsch (Schweiz)'),
    ('en-US', 'Englisch (USA)'), ('en-GB', 'Englisch (Großbritannien)'), ('en-CA', 'Englisch (Kanada)'), ('en-AU', 'Englisch (Australien)'),
    ('fr-FR', 'Französisch (Frankreich)'), ('fr-BE', 'Französisch (Belgien)'), ('fr-CA', 'Französisch (Kanada)'), ('fr-CH', 'Französisch (Schweiz)'),
    ('es-ES', 'Spanisch (Spanien)'), ('es-MX', 'Spanisch (Mexiko)'), ('es-AR', 'Spanisch (Argentinien)'),
    ('it-IT', 'Italienisch (Italien)'), ('it-CH', 'Italienisch (Schweiz)'),
]
UI_FOR_DATA = {'de': 'de-DE', 'en': 'en-US', 'fr': 'fr-FR', 'es': 'es-ES', 'it': 'it-IT'}
KEYS = ['TMDB_API_KEY', 'TMDB_LANGUAGE', 'MB_CONTACT', 'DISCOGS_TOKEN', 'BARCODE_LOOKUP', 'COVER_WEB', 'AUTO_UPDATE', 'MEDIATHEK', 'UPDATE_CHECK']
SECRET = {'TMDB_API_KEY', 'DISCOGS_TOKEN'}


def init(data_dir):
    global FILE
    FILE = Path(data_dir) / 'settings.json'
    for k in KEYS + ['MB_USER_AGENT']:
        _ENV0[k] = os.environ.get(k)
    apply()


def _read():
    try:
        return json.loads(FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def stored():
    return _read().get('config') or {}


def apply():
    """Gespeicherte Werte in os.environ uebernehmen (ueberschreiben .env)."""
    for k in KEYS:
        if k in _ENV0:
            if _ENV0[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = _ENV0[k]
    for k, v in stored().items():
        if k in KEYS and v is not None and v != '':
            os.environ[k] = str(v)
    contact = os.environ.get('MB_CONTACT', '').strip()
    if contact:  # MusicBrainz verlangt eine Kontaktangabe im User-Agent
        os.environ['MB_USER_AGENT'] = f'MediaDB/{version()} ({contact})'
    elif _ENV0.get('MB_USER_AGENT'):
        os.environ['MB_USER_AGENT'] = _ENV0['MB_USER_AGENT']


def save(values):
    """values: {KEY: wert}; leerer Text loescht den Eintrag (dann gilt wieder .env)."""
    with _lock:
        d = _read()
        cfg = d.get('config') or {}
        for k, v in values.items():
            if k not in KEYS:
                continue
            if v is None or v == '':
                cfg.pop(k, None)
            else:
                cfg[k] = v
        d['config'] = cfg
        try:
            FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        except Exception:
            logging.exception('Einstellungen konnten nicht gespeichert werden')
            return False
    apply()
    return True


def section(name):
    """Weitere Abschnitte in settings.json (z. B. "nas": Liste der NAS-Freigaben)."""
    return _read().get(name)


def save_section(name, value):
    with _lock:
        d = _read()
        d[name] = value
        try:
            FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
            try:
                os.chmod(FILE, 0o600)  # enthaelt Zugangsdaten
            except OSError:
                pass
        except Exception:
            logging.exception('Einstellungen konnten nicht gespeichert werden')
            return False
    return True


def get(key, default=''):
    return os.environ.get(key, default)


def flag(key, default=True):
    v = os.environ.get(key)
    if v is None or v.strip() == '':
        return default
    return v.strip().lower() not in ('0', 'false', 'no', 'nein', 'off')


def source(key):
    """Woher kommt der Wert: 'app' (Einstellungsseite), 'env' (.env) oder ''."""
    if stored().get(key) not in (None, ''):
        return 'app'
    if _ENV0.get(key):
        return 'env'
    return ''


def mask(v):
    v = v or ''
    return ('•' * 6 + v[-4:]) if len(v) > 8 else ('•' * len(v))


def contact_from_agent():
    ua = _ENV0.get('MB_USER_AGENT') or ''
    if '(' in ua and ua.endswith(')'):
        c = ua[ua.rindex('(') + 1:-1]
        return '' if 'example' in c else c
    return ''


def version():
    try:
        return (Path(__file__).resolve().parent.parent / 'VERSION').read_text().strip()
    except Exception:
        return '1'
