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
_cache = {'users': None, 'mode': None, 'guest': None}
_current = contextvars.ContextVar('mediadb_user', default=None)  # die Middleware fragt bei jeder Anfrage; Aenderungen leeren den Zwischenspeicher

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, role TEXT NOT NULL DEFAULT 'member',
  secret TEXT, last_login TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""
GUEST_NAME = '__gast__'  # eingebauter Gast (seit 1.22.3): ohne Passwort, nur lesen; angezeigt als "Gast"/"Guest"
ASSIGN_PHYSICAL = None  # main.py: physische Exemplare gesammelt einer Person geben (Einstellungen -> Nutzer)
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
    _cache.update(users=None, mode=None, guest=None)


# ---------------------------------------------------------------- Lesen
def users():
    """{id: {...}} aller Nutzer, nach Name sortiert (zwischengespeichert)."""
    if _cache['users'] is None:
        with db() as c:
            _cache['users'] = {r['id']: dict(r) for r in c.execute('SELECT * FROM users ORDER BY name COLLATE NOCASE')}
    return _cache['users']


def people():
    """Alle Nutzer ohne den eingebauten Gast (fuer Listen und Auswahl)."""
    return [u for u in users().values() if u['name'] != GUEST_NAME]


def guest_on():
    """Gastzugang ohne Passwort anbieten (Einstellungen -> Nutzer); ohne Eintrag eingeschaltet."""
    if _cache['guest'] is None:
        with db() as c:
            r = c.execute("SELECT value FROM meta WHERE key='guest_access'").fetchone()
        _cache['guest'] = not r or r[0] != '0'
    return _cache['guest']


def set_guest(on):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('guest_access', ?)", ('1' if on else '0',))
    _forget()


def builtin_guest():
    """Konto des eingebauten Gasts, bei Bedarf angelegt (persoenliche Angaben brauchen eine Nummer)."""
    g = next((u for u in users().values() if u['name'] == GUEST_NAME), None)
    if not g:
        with db() as c:
            c.execute('INSERT OR IGNORE INTO users(name, role, created_at) VALUES(?, ?, ?)', (GUEST_NAME, 'guest', now()))
        _forget()
        g = next((u for u in users().values() if u['name'] == GUEST_NAME), None)
    return g


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
        role = fields.get('role', u['role'])
        if role == 'admin' or (mode() == 'password' and role != 'guest'):
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
    if get(uid)['name'] == GUEST_NAME and not guest_on():  # Gastzugang abgeschaltet: Gast ist abgemeldet
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


def physical_copy(kind, path, digital_kinds=('file', 'ebook')):
    """Seit 1.22.2: Besitzer gibt es nur bei physischen Exemplaren (CD, DVD, Blu-ray, 4K, Box, gedrucktes Buch, Hoerbuch-CD).
    Dateien, E-Books und rein digitale Alben gehoeren immer dem Haushalt."""
    return kind not in digital_kinds and not path


def once(name):
    """True genau beim ersten Aufruf mit diesem Namen (einmalige Umstellungen, gemerkt in nutzer.db)."""
    with db() as c:
        if c.execute('SELECT 1 FROM meta WHERE key=?', (name,)).fetchone():
            return False
        c.execute('INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)', (name, now()))
    return True


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
# Datenbankverbindung (nur mit Konten) eine voruebergehende Sicht gleichen Namens an, die die echte Tabelle verdeckt und
# die Werte der angemeldeten Person zeigt. Schreibbefehle auf diese Namen verteilt die Verbindungsklasse Conn selbst auf
# die echte und die persoenliche Tabelle (1.22.1: Trigger mit main.<tabelle> erlaubt SQLite erst ab etwa 3.50, das
# Docker-Image hat 3.46). Ohne angemeldete Person (Hintergrundaufgaben, Konten aus) gelten die Werte in der Tabelle selbst.
# Neue Zeilen muessen ausdruecklich in main.<tabelle> geschrieben werden.
_SQL = {}
_WRITE = re.compile(r'\s*(?P<verb>UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM|(?:INSERT|REPLACE)(?:\s+OR\s+\w+)?\s+INTO)\s+(?P<t>\w+)\b', re.I)


def _uid_sql():
    return current_id()


def personal_table(c, table, utable, fk, fields):
    """Tabelle fuer die persoenlichen Werte anlegen (beim Start, im init des Bereichs)."""
    types = {r[1]: r[2] or 'TEXT' for r in c.execute(f'PRAGMA main.table_info({table})')}
    cols = ', '.join(f'{f} {types.get(f, "TEXT")}' for f in fields)
    c.execute(f'CREATE TABLE IF NOT EXISTS {utable}({fk} INTEGER NOT NULL, user_id INTEGER NOT NULL, {cols}, PRIMARY KEY({fk}, user_id))')


def _view_sql(c, s):
    if s[0] == 'personal':
        table, utable, fk, fields = s[1:5]
        cols = [r[1] for r in c.execute(f'PRAGMA main.table_info({table})')]
        sel = [f'CASE WHEN mdb_uid() IS NULL THEN t.{x} ELSE coalesce(u.{x}, {fields[x]}) END AS {x}' if x in fields else f't.{x}' for x in cols]
        return (f'CREATE TEMP VIEW {table} AS SELECT {", ".join(sel)} FROM main.{table} t '
                f'LEFT JOIN main.{utable} u ON u.{fk}=t.id AND u.user_id=mdb_uid()')
    if s[0] == 'set':  # Menge wie 'watched' (eine Zeile = gesehen): pro Person eine eigene Menge
        view, utable, keys, vals = s[1:5]
        allc = ', '.join(keys + vals)
        return (f'CREATE TEMP VIEW {view} AS SELECT {allc} FROM main.{view} WHERE mdb_uid() IS NULL '
                f'UNION ALL SELECT {allc} FROM main.{utable} WHERE user_id=mdb_uid()')
    return f'CREATE TEMP VIEW {s[1]} AS SELECT * FROM main.{s[1]} WHERE mdb_uid() IS NULL OR user_id=mdb_uid()'  # 'rows': Merkliste


def _split(sql, sep=','):
    """Text auf oberster Ebene (ausserhalb von Klammern und Anfuehrungszeichen) an sep (',' oder 'WHERE') teilen."""
    parts, depth, quote, start, i, low = [], 0, None, 0, 0, sql.lower()
    while i < len(sql):
        ch = sql[i]
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and sep == ',' and ch == ',':
            parts.append(sql[start:i]); start = i + 1
        elif depth == 0 and sep == 'where' and low.startswith('where', i) and not low[i - 1:i].isalnum() and not low[i + 5:i + 6].isalnum():
            parts.append(sql[start:i]); start = i + 5
        i += 1
    parts.append(sql[start:])
    return parts


def _qmarks(sql):
    n, quote = 0, None
    for ch in sql:
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == '?':
            n += 1
    return n


class Conn(sqlite3.Connection):
    """sqlite3-Verbindung, die Schreibbefehle auf persoenlich verdeckte Tabellen selbst verteilt (siehe oben)."""
    shadow = None

    def execute(self, sql, params=()):
        m = _WRITE.match(sql) if self.shadow else None
        if m and m.group('t').lower() in self.shadow:
            return self._redirect(m, sql, params)
        return super().execute(sql, params)

    def _x(self, sql, params=()):
        return sqlite3.Connection.execute(self, sql, params)

    def _redirect(self, m, sql, params):
        spec, uid = self.shadow[m.group('t').lower()], current_id()
        verb, rest = re.sub(r'\s+', ' ', m.group('verb').upper()), sql[m.end():]
        if uid is None or spec[0] == 'rows' or verb.startswith(('INSERT', 'REPLACE')) and spec[0] == 'personal':
            return self._x(sql[:m.start('t')] + 'main.' + sql[m.start('t'):], params)  # echte Tabelle, wie ohne Konten
        uid = int(uid)
        if spec[0] == 'set':
            view, utable, keys, vals = spec[1:5]
            if verb.startswith(('INSERT', 'REPLACE')):
                cm = re.match(r'\s*\(([^)]*)\)\s*(.*)$', rest, re.S)
                cols, tail = (cm.group(1), cm.group(2)) if cm else (', '.join(keys + vals), rest.strip())
                tail = re.sub(r'^(VALUES\s*\(|SELECT\s)', lambda x: x.group(0) + f'{uid}, ', tail, count=1, flags=re.I)
                return self._x(f'{verb} main.{utable}(user_id, {cols}) {tail}', params)
            head, *cond = _split(rest, 'where')
            where = f'user_id={uid}' + (f' AND ({cond[0]})' if cond else '')
            return self._x(f'{verb} main.{utable} {head} WHERE {where}' if verb.startswith('UPDATE') else f'DELETE FROM main.{utable} WHERE {where}', params)
        table, utable, fk, fields = spec[1:5]
        cleanup = spec[5] if len(spec) > 5 else ()
        if verb == 'DELETE FROM':
            cond = _split(rest, 'where')
            ids = [r[0] for r in self._x(f'SELECT id FROM {table}' + (f' WHERE {cond[1]}' if len(cond) > 1 else ''), params)]
            cur = None
            for i in ids:
                cur = self._x(f'DELETE FROM main.{table} WHERE id=?', (i,))
                self._x(f'DELETE FROM main.{utable} WHERE {fk}=?', (i,))
                for t, k in cleanup:
                    self._x(f'DELETE FROM main.{t} WHERE {k}=?', (i,))
            return cur or self._x('SELECT 0')
        sm = re.match(r'\s*SET\s(.*)$', rest, re.S | re.I)
        set_part, *cond = _split(sm.group(1), 'where')
        named = isinstance(params, dict)
        assigns, pos = [], 0
        for a in _split(set_part):
            col, expr = a.split('=', 1)
            n = _qmarks(expr)
            assigns.append((col.strip(), expr.strip(), params if named else tuple(params[pos:pos + n])))
            pos += n
        wparams = params if named else tuple(params[pos:])
        ids = [r[0] for r in self._x(f'SELECT id FROM {table}' + (f' WHERE {cond[0]}' if cond else ''), wparams)]
        own = [a for a in assigns if a[0] in fields]
        rest_a = [a for a in assigns if a[0] not in fields]
        cur = None
        for i in ids:
            if own:  # neue persoenliche Werte aus Sicht der Person berechnen, dann in ihre Tabelle
                p = params if named else sum((a[2] for a in own), ()) + (i,)
                q = f'SELECT {", ".join(a[1] for a in own)} FROM {table} WHERE id=' + (':__id' if named else '?')
                newv = self._x(q, dict(params, __id=i) if named else p).fetchone()
                row = dict(self._x(f'SELECT {", ".join(fields)} FROM {table} WHERE id=?', (i,)).fetchone())
                row.update({a[0]: v for a, v in zip(own, newv)})
                cols = list(fields)
                self._x(f'INSERT INTO main.{utable}({fk}, user_id, {", ".join(cols)}) VALUES({", ".join("?" * (len(cols) + 2))}) '
                        f'ON CONFLICT({fk}, user_id) DO UPDATE SET {", ".join(x + "=excluded." + x for x in cols)}',
                        (i, uid, *[row[x] for x in cols]))
            if rest_a:
                p = params if named else sum((a[2] for a in rest_a), ()) + (i,)
                cur = self._x(f'UPDATE main.{table} SET {", ".join(a[0] + "=" + a[1] for a in rest_a)} WHERE id=' + (':__id' if named else '?'),
                              dict(params, __id=i) if named else p)
        return cur or self._x('SELECT 0')


def personalize(c, key, specs):
    """Fuer eine Verbindung (aus sqlite3.connect(..., factory=Conn)) die Sichten anlegen, nur mit Konten.
    specs: ('personal', table, utable, fk, fields[, cleanup]), ('set', view, utable, keys, vals) oder ('rows', table)."""
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
            out.append((s, _view_sql(c, s)))
        if complete:
            _SQL[key] = out
    for _s, stmt in out:
        c.execute(stmt)
    if isinstance(c, Conn):
        c.shadow = {s[1]: s for s, _x in out}
