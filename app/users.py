"""Nutzer und Anmeldung (seit 1.20): eigene kleine Datenbank data/nutzer.db. Konzept: docs/KONZEPT_NUTZER.md.

Tabellen:
  users  Name, Rolle (admin = Verwalter, member = Mitglied, guest = Gast, nur ansehen), Passwort oder PIN als scrypt-Pruefwert,
         letzte Anmeldung
  meta   mode: 'off' (wie bisher, ggf. APP_PASSWORD), 'profiles' (Profilwahl, PIN freiwillig), 'password' (Name und Passwort)
Die Anmeldung steht in einem signierten Cookie (Nutzer, Ablauf). Der Pruefwert des Passworts geht in die Signatur ein:
Aendert sich das Passwort, sind alte Anmeldungen ungueltig.

Besitzer (seit 1.21): Exemplare (Filme, Serienboxen, Buecher) und Musik-Alben haben die Spalte owner_id; leer = Haushalt
(gemeinsam). Wer etwas anlegt, wird Besitzer: Die Middleware merkt sich den angemeldeten Nutzer fuer die Anfrage
(set_current), current_id() liefert ihn auch in Hintergrundaufgaben, die mit start_thread() gestartet werden."""
import contextvars, hashlib, hmac, re, secrets, sqlite3, threading, time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def now():
    return datetime.now().isoformat(timespec='seconds')

DB_PATH = None
SECRET = lambda: b''  # Schluessel fuer die Signatur; main.py setzt security.Settings.secret
COOKIE = 'mediadb_user'
MAX_AGE = 60 * 60 * 24 * 30
ROLES = {'admin': 'Verwalter', 'member': 'Mitglied', 'guest': 'Gast'}
MODES = ('off', 'profiles', 'password')
_init_lock = threading.Lock()
_cache = {'users': None, 'mode': None}
_current = contextvars.ContextVar('mediadb_user', default=None)  # die Middleware fragt bei jeder Anfrage; Aenderungen leeren den Zwischenspeicher

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, role TEXT NOT NULL DEFAULT 'member',
  secret TEXT, last_login TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""
ON_FIRST_ADMIN = []  # main.py: (Name, Funktion), die beim ersten Verwalter Vorhandenes einmalig uebernehmen (z. B. owner_id leer -> er)


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


# ---------------------------------------------------------------- Besitzer (seit 1.21)
def set_current(user):
    _current.set(user)


def current():
    u = _current.get()
    return u if u and accounts_on() else None


def current_id():
    u = current()
    return u['id'] if u else None


def start_thread(target, *args):
    """Hintergrundaufgabe mit dem angemeldeten Nutzer (fuer den Besitzer neuer Eintraege)."""
    ctx = contextvars.copy_context()
    threading.Thread(target=ctx.run, args=(target, *args), daemon=True).start()


def add_owner_column(c, table):
    """Spalte owner_id in einer bestehenden Tabelle ergaenzen (sqlite3-Verbindung)."""
    if 'owner_id' not in {r[1] for r in c.execute(f'PRAGMA table_info({table})')}:
        c.execute(f'ALTER TABLE {table} ADD COLUMN owner_id INTEGER')


def owner_filter(value):
    """Filter aus der Adresse: '' alle, 'me' meine, 'h' Haushalt, sonst Nummer. Liefert (aktiv, owner_id oder None)."""
    if not accounts_on() or not value:
        return False, None
    if value == 'me':
        uid = current_id()
        return (True, uid) if uid else (False, None)
    if value == 'h':
        return True, None
    return (True, int(value)) if str(value).isdigit() and get(int(value)) else (False, None)


def parse_owner(value):
    """Auswahl im Formular: '' = Haushalt. Liefert (gueltig, owner_id oder None)."""
    if not value:
        return True, None
    return (True, int(value)) if str(value).isdigit() and get(int(value)) else (False, None)


def owner_name(uid):
    u = get(uid) if uid else None
    return u['name'] if u else ''


def claim_unowned():
    """Einmalig je Schritt: Vorhandenes gehoert dem ersten Verwalter (Besitzer seit 1.21, persoenliche Werte seit 1.22)."""
    a = admins()
    if not a:
        return
    first = min(a, key=lambda u: u['id'])['id']
    for name, fn in ON_FIRST_ADMIN:
        with db() as c:
            if c.execute('SELECT 1 FROM meta WHERE key=?', (name,)).fetchone():
                continue
            c.execute('INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)', (name, now()))
        try:
            fn(first)
        except Exception:
            import logging
            logging.exception('Uebernahme fuer den ersten Verwalter fehlgeschlagen: %s', name)


# ---------------------------------------------------------------- persoenliche Angaben (seit 1.22)
# Gesehen, Bewertung, gelesen, "Als Naechstes" und die Merkliste gehoeren jeder Person selbst. Gespeichert werden sie in
# eigenen Tabellen (z. B. film_user). Damit der uebrige Code unveraendert "films" lesen und schreiben kann, legt jede
# Datenbankverbindung (nur mit Konten) eine voruebergehende Sicht gleichen Namens an, die die echte Tabelle verdeckt:
# Sie zeigt die Werte der angemeldeten Person, Aenderungen leiten Trigger in die richtige Tabelle um. Ohne angemeldete
# Person (Hintergrundaufgaben, Konten aus) gelten die Werte in der Tabelle selbst wie bisher.
# Neue Zeilen muessen ausdruecklich in main.<tabelle> geschrieben werden (eine Sicht liefert keine neue Nummer).
_SQL = {}


def _uid_sql():
    return current_id()


def personal_table(c, table, utable, fk, fields):
    """Tabelle fuer die persoenlichen Werte anlegen (beim Start, im init des Bereichs)."""
    types = {r[1]: r[2] or 'TEXT' for r in c.execute(f'PRAGMA main.table_info({table})')}
    cols = ', '.join(f'{f} {types.get(f, "TEXT")}' for f in fields)
    c.execute(f'CREATE TABLE IF NOT EXISTS {utable}({fk} INTEGER NOT NULL, user_id INTEGER NOT NULL, {cols}, PRIMARY KEY({fk}, user_id))')


def _personal_sql(c, table, utable, fk, fields, cleanup=()):
    cols = [r[1] for r in c.execute(f'PRAGMA main.table_info({table})')]
    sel = [f'CASE WHEN mdb_uid() IS NULL THEN t.{x} ELSE coalesce(u.{x}, {fields[x]}) END AS {x}' if x in fields else f't.{x}' for x in cols]
    sets = [f'{x}=CASE WHEN mdb_uid() IS NULL THEN NEW.{x} ELSE {x} END' if x in fields else f'{x}=NEW.{x}' for x in cols if x != 'id']
    f = list(fields)
    return [
        f'CREATE TEMP VIEW {table} AS SELECT {", ".join(sel)} FROM main.{table} t '
        f'LEFT JOIN main.{utable} u ON u.{fk}=t.id AND u.user_id=mdb_uid()',
        f'CREATE TEMP TRIGGER {table}_upd INSTEAD OF UPDATE ON {table} BEGIN '
        f'UPDATE main.{table} SET {", ".join(sets)} WHERE id=OLD.id; '
        f'INSERT INTO main.{utable}({fk}, user_id, {", ".join(f)}) SELECT OLD.id, mdb_uid(), {", ".join("NEW." + x for x in f)} '
        f'WHERE mdb_uid() IS NOT NULL ON CONFLICT({fk}, user_id) DO UPDATE SET {", ".join(x + "=excluded." + x for x in f)}; END',
        f'CREATE TEMP TRIGGER {table}_del INSTEAD OF DELETE ON {table} BEGIN DELETE FROM main.{table} WHERE id=OLD.id; '
        f'DELETE FROM main.{utable} WHERE {fk}=OLD.id; ' + ''.join(f'DELETE FROM main.{t} WHERE {k}=OLD.id; ' for t, k in cleanup) + 'END']


def _set_sql(view, utable, keys, vals):
    """Menge wie 'watched' (eine Zeile = gesehen): pro Person eine eigene Menge."""
    allc = keys + vals
    where = ' AND '.join(f'{k}=OLD.{k}' for k in keys)
    return [
        f'CREATE TEMP VIEW {view} AS SELECT {", ".join(allc)} FROM main.{view} WHERE mdb_uid() IS NULL '
        f'UNION ALL SELECT {", ".join(allc)} FROM main.{utable} WHERE user_id=mdb_uid()',
        f'CREATE TEMP TRIGGER {view}_ins INSTEAD OF INSERT ON {view} BEGIN '
        f'INSERT INTO main.{view}({", ".join(allc)}) SELECT {", ".join("NEW." + x for x in allc)} WHERE mdb_uid() IS NULL; '
        f'INSERT INTO main.{utable}(user_id, {", ".join(allc)}) SELECT mdb_uid(), {", ".join("NEW." + x for x in allc)} WHERE mdb_uid() IS NOT NULL; END',
        f'CREATE TEMP TRIGGER {view}_upd INSTEAD OF UPDATE ON {view} BEGIN '
        f'UPDATE main.{view} SET {", ".join(v + "=NEW." + v for v in vals)} WHERE mdb_uid() IS NULL AND {where}; '
        f'UPDATE main.{utable} SET {", ".join(v + "=NEW." + v for v in vals)} WHERE user_id=mdb_uid() AND {where}; END',
        f'CREATE TEMP TRIGGER {view}_del INSTEAD OF DELETE ON {view} BEGIN '
        f'DELETE FROM main.{view} WHERE mdb_uid() IS NULL AND {where}; DELETE FROM main.{utable} WHERE user_id=mdb_uid() AND {where}; END']


def _rows_sql(c, table):
    """Tabelle mit Spalte user_id (Merkliste): jede Person sieht ihre Zeilen, ohne Person alle."""
    cols = [r[1] for r in c.execute(f'PRAGMA main.table_info({table})') if r[1] != 'id']
    return [
        f'CREATE TEMP VIEW {table} AS SELECT * FROM main.{table} WHERE mdb_uid() IS NULL OR user_id=mdb_uid()',
        f'CREATE TEMP TRIGGER {table}_upd INSTEAD OF UPDATE ON {table} BEGIN UPDATE main.{table} SET '
        f'{", ".join(x + "=NEW." + x for x in cols)} WHERE id=OLD.id; END',
        f'CREATE TEMP TRIGGER {table}_del INSTEAD OF DELETE ON {table} BEGIN DELETE FROM main.{table} WHERE id=OLD.id; END']


def personalize(c, key, specs):
    """Fuer eine Verbindung die Sichten anlegen (nur mit Konten). specs: Liste von ('personal', table, utable, fk, fields[, cleanup]),
    ('set', view, utable, keys, vals) oder ('rows', table). key: Name der Datenbank fuer den Zwischenspeicher."""
    if not accounts_on():
        return
    c.create_function('mdb_uid', 0, _uid_sql)
    out = _SQL.get(key)
    if out is None:
        out, complete = [], True
        have = {r[0] for r in c.execute("SELECT name FROM main.sqlite_master WHERE type='table'")}
        for s in specs:
            if s[1] not in have or s[2 if s[0] != 'rows' else 1] not in have:
                complete = False  # Tabelle fehlt noch (Start laeuft); spaeter neu aufbauen
                continue
            out += _personal_sql(c, *s[1:]) if s[0] == 'personal' else _set_sql(*s[1:]) if s[0] == 'set' else _rows_sql(c, s[1])
        if complete:
            _SQL[key] = out
    for stmt in out:
        c.execute(stmt)
