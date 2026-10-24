"""Nutzer und Anmeldung (seit 1.20): eigene kleine Datenbank data/nutzer.db. Konzept: docs/KONZEPT_NUTZER.md.

Tabellen:
  users  Name, Rolle (admin = Verwalter, member = Mitglied, guest = Gast, nur ansehen), Passwort oder PIN als scrypt-Pruefwert,
         letzte Anmeldung
  meta   mode: 'off' (wie bisher, ggf. APP_PASSWORD), 'profiles' (Profilwahl, PIN freiwillig), 'password' (Name und Passwort)
Die Anmeldung steht in einem signierten Cookie (Nutzer, Ablauf). Der Pruefwert des Passworts geht in die Signatur ein:
Aendert sich das Passwort, sind alte Anmeldungen ungueltig."""
import hashlib, hmac, re, secrets, sqlite3, threading, time
from contextlib import contextmanager
from pathlib import Path
from .films_db import now

DB_PATH = None
SECRET = lambda: b''  # Schluessel fuer die Signatur; main.py setzt security.Settings.secret
COOKIE = 'mediadb_user'
MAX_AGE = 60 * 60 * 24 * 30
ROLES = {'admin': 'Verwalter', 'member': 'Mitglied', 'guest': 'Gast'}
MODES = ('off', 'profiles', 'password')
_init_lock = threading.Lock()
_cache = {'users': None, 'mode': None}  # die Middleware fragt bei jeder Anfrage; Aenderungen leeren den Zwischenspeicher

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, role TEXT NOT NULL DEFAULT 'member',
  secret TEXT, last_login TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def init(path):
    global DB_PATH
    DB_PATH = Path(path)
    with _init_lock, db() as c:
        c.executescript(SCHEMA)
    _forget()


@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _forget():
    _cache.update(users=None, mode=None)


# ---------------------------------------------------------------- Lesen
def users():
    """{id: {...}} aller Nutzer, nach Name sortiert (zwischengespeichert)."""
    if _cache['users'] is None:
        with db() as c:
            _cache['users'] = {r['id']: dict(r) for r in c.execute('SELECT * FROM users ORDER BY name COLLATE NOCASE')}
    return _cache['users']


def get(uid):
    return users().get(uid)


def by_name(name):
    name = clean_name(name).lower()
    return next((u for u in users().values() if u['name'].lower() == name), None) if name else None


def mode():
    if _cache['mode'] is None:
        with db() as c:
            r = c.execute("SELECT value FROM meta WHERE key='mode'").fetchone()
        _cache['mode'] = r[0] if r and r[0] in MODES else 'off'
    return _cache['mode']


def accounts_on():
    return mode() != 'off' and any(u['role'] == 'admin' for u in users().values())


def admins():
    return [u for u in users().values() if u['role'] == 'admin']


# ---------------------------------------------------------------- Passwort
def hash_secret(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f'scrypt${salt.hex()}${h.hex()}'


def secret_ok(user, pw):
    try:
        _, salt, h = (user.get('secret') or '').split('$')
        got = hashlib.scrypt((pw or '').encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got.hex(), h)
    except Exception:
        return False


def clean_name(name):
    return re.sub(r'\s+', ' ', name or '').strip()[:40]


# ---------------------------------------------------------------- Aendern (Rueckgabe: Fehlermeldung oder '')
def create(name, role='member', pw=''):
    name = clean_name(name)
    if not name:
        return 'Bitte einen Namen eingeben.', None
    if role not in ROLES:
        role = 'member'
    if pw and len(pw) < 4:
        return 'Passwort oder PIN braucht mindestens 4 Zeichen.', None
    try:
        with db() as c:
            uid = c.execute('INSERT INTO users(name, role, secret, created_at) VALUES(?,?,?,?)',
                            (name, role, hash_secret(pw) if pw else None, now())).lastrowid
    except sqlite3.IntegrityError:
        return 'Diesen Namen gibt es schon.', None
    _forget()
    return '', uid


def update(uid, name=None, role=None, pw=None, remove_pw=False):
    u = get(uid)
    if not u:
        return 'Nutzer nicht gefunden.'
    fields = {}
    if name is not None:
        name = clean_name(name)
        if not name:
            return 'Bitte einen Namen eingeben.'
        fields['name'] = name
    if role is not None and role in ROLES and role != u['role']:
        if u['role'] == 'admin' and len(admins()) == 1:
            return 'Mindestens ein Verwalter muss bleiben.'
        fields['role'] = role
    if pw:
        if len(pw) < 4:
            return 'Passwort oder PIN braucht mindestens 4 Zeichen.'
        fields['secret'] = hash_secret(pw)
    elif remove_pw:
        if mode() == 'password' or (fields.get('role', u['role']) == 'admin'):
            return 'Verwalter und alle bei „Name und Passwort“ brauchen ein Passwort.'
        fields['secret'] = None
    if not fields:
        return ''
    try:
        with db() as c:
            c.execute('UPDATE users SET ' + ', '.join(f'{k}=?' for k in fields) + ' WHERE id=?', (*fields.values(), uid))
    except sqlite3.IntegrityError:
        return 'Diesen Namen gibt es schon.'
    _forget()
    return ''


def delete(uid):
    u = get(uid)
    if not u:
        return 'Nutzer nicht gefunden.'
    if u['role'] == 'admin' and len(admins()) == 1:
        return 'Mindestens ein Verwalter muss bleiben.'
    with db() as c:
        c.execute('DELETE FROM users WHERE id=?', (uid,))
    _forget()
    return ''


def set_mode(m):
    if m not in MODES:
        return 'Unbekannte Art der Anmeldung.'
    if m != 'off' and not admins():
        return 'Bitte zuerst einen Verwalter anlegen.'
    if m != 'off' and any(not a['secret'] for a in admins()):
        return 'Jeder Verwalter braucht ein Passwort.'
    with db() as c:
        c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('mode', ?)", (m,))
    _forget()
    return ''


def touch(uid):
    with db() as c:
        c.execute('UPDATE users SET last_login=? WHERE id=?', (now(), uid))
    _forget()


# ---------------------------------------------------------------- Anmelde-Cookie
def _sig(secret_key, uid, exp):
    u = get(uid) or {}
    key = secret_key + b'|' + (u.get('secret') or '').encode()
    return hmac.new(key, f'{uid}.{exp}'.encode(), hashlib.sha256).hexdigest()


def make_token(secret_key, uid):
    exp = int(time.time()) + MAX_AGE
    return f'{uid}.{exp}.{_sig(secret_key, uid, exp)}'


def user_from_token(secret_key, tok):
    try:
        uid, exp, sig = (tok or '').split('.', 2)
        uid, exp = int(uid), int(exp)
    except Exception:
        return None
    if exp < time.time() or not get(uid) or not hmac.compare_digest(sig, _sig(secret_key, uid, exp)):
        return None
    return get(uid)
