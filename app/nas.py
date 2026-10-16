"""NAS-Freigaben (SMB 2/3) direkt lesen, ohne sie im Betriebssystem einzuhaengen.

Hintergrund: In einem unprivilegierten Proxmox-LXC lassen sich Netzwerkfreigaben weder im LXC noch im Docker-Container
einhaengen. MediaDB spricht deshalb selbst SMB (Bibliothek smbprotocol). Jede Freigabe aus den Einstellungen bekommt
einen Pfad /nas/<name>/..., den die Importe wie einen normalen Ordner benutzen (ueber app/fs.py).

Fuer ffprobe/ffmpeg gibt es einen kleinen HTTP-Vermittler nur auf 127.0.0.1: Er reicht die Datei mit Range-Anfragen
weiter, so liest ffprobe nur die Teile, die es braucht (nicht den ganzen Film). Es wird nie etwas geschrieben.

Gespeichert in data/settings.json unter "nas": [{id, label, host, share, folder, user, password}]."""
import errno, logging, posixpath, re, secrets, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote
from . import config as C

logging.getLogger('smbclient').setLevel(logging.ERROR)  # "Failed to close connection" samt Traceback ist nur Laerm

PREFIX = '/nas'
TIMEOUT = 10        # Sekunden fuer den Verbindungsaufbau
DOWN_PAUSE = 60     # so lange gilt eine NAS nach einem Verbindungsfehler als nicht erreichbar (kein erneutes Warten)
_down = {}          # host -> (zeitpunkt, fehlertext)
_seen = {}          # host -> (zeitpunkt, erreichbar) fuer die schnelle Pruefung (reachable)
SEEN_TTL = 5        # so lange gilt das Ergebnis der schnellen Pruefung
_lock = threading.Lock()


# ---------------------------------------------------------------- Einstellungen
def shares():
    return [s for s in (C.section('nas') or []) if isinstance(s, dict) and s.get('id')]


def get_share(sid):
    return next((s for s in shares() if s['id'] == sid), None)


def slug(label, taken=()):
    t = (label or '').strip().lower()
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        t = t.replace(a, b)
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:30] or 'nas'
    base, i = t, 2
    while t in taken:
        t, i = f'{base}-{i}', i + 1
    return t


def clean_host(h):
    h = (h or '').strip().strip('\\/')
    h = re.sub(r'^(smb|cifs)://', '', h, flags=re.I)
    return h.split('/')[0].split('\\')[0]


def clean_part(p):
    """Freigabe oder Unterordner: Schraegstriche vereinheitlichen, keine '..'."""
    parts = [x for x in re.split(r'[\\/]+', (p or '').strip()) if x and x not in ('.', '..')]
    return '/'.join(parts)


def logins():
    """Gespeicherte Zugaenge zum Uebernehmen in eine neue Freigabe: je NAS und Benutzer einmal (ohne Passwort)."""
    seen, out = set(), []
    for s in shares():
        key = (s['host'].lower(), s.get('user') or '')
        if key not in seen:
            seen.add(key)
            out.append({'id': s['id'], 'host': s['host'], 'user': s.get('user') or '', 'label': s['label']})
    return out


def _entry(data, sid=None):
    """Formular -> Freigabe (ohne zu speichern). Gibt (eintrag, alter_eintrag, fehler) zurueck.
    Passwort leer: beim Aendern das gespeicherte, sonst das der Freigabe aus data['from'] (gleiche NAS, gleicher Benutzer)."""
    label = (data.get('label') or '').strip()[:40]
    raw = (data.get('host') or '').strip()
    host = clean_host(raw)
    share, folder = clean_part(data.get('share')), clean_part(data.get('folder'))
    if not share:  # ganze Adresse ins Feld NAS-Adresse kopiert: smb://nas/Musik/Alben oder \\nas\Musik\Alben
        rest = re.sub(r'^(smb|cifs)://', '', raw.replace('\\', '/').strip('/'), flags=re.I).split('/')[1:]
        share, folder = (rest[0], clean_part('/'.join(rest[1:])) or folder) if rest else ('', folder)
    if '/' in share:  # "Musik/Alben" im Feld Freigabe: der Rest ist ein Unterordner
        share, more = share.split('/', 1)
        folder = clean_part(more + '/' + folder)
    if not label or not host or not share:
        return None, None, 'Bitte Name, NAS-Adresse und Freigabe eintragen.'
    if not re.fullmatch(r'[A-Za-z0-9.\-_]+(:\d{1,5})?|\[[0-9a-fA-F:]+\](:\d{1,5})?', host):
        return None, None, 'Die NAS-Adresse ist nicht lesbar (z. B. 192.168.1.20).'
    lst = shares()
    old = next((s for s in lst if s['id'] == sid), None) if sid else None
    if sid and not old:
        return None, None, 'Freigabe nicht gefunden.'
    user = (data.get('user') or '').strip()[:100]
    password = data.get('password') or ''
    if not password:
        src = old or get_share(data.get('from') or '')
        if src and src['host'].lower() == host.lower() and (src.get('user') or '') == user:
            password = src.get('password', '')
    if not user or not password:
        return None, None, 'Bitte Benutzer und Passwort der NAS eintragen. Ein Zugang als Gast ohne Passwort ist nicht möglich.'
    entry = {'id': old['id'] if old else slug(label, {s['id'] for s in lst}), 'label': label, 'host': host, 'share': share,
             'folder': folder, 'user': user, 'password': password}
    return entry, old, ''


def save_share(data, sid=None):
    """Freigabe anlegen (sid=None) oder aendern. Leeres Passwort beim Aendern = unveraendert. Gibt (id, fehler) zurueck."""
    entry, old, err = _entry(data, sid)
    if err:
        return None, err
    lst = shares()
    lst = [entry if s['id'] == old['id'] else s for s in lst] if old else lst + [entry]
    if not C.save_section('nas', lst):
        return None, 'Die Einstellungen konnten nicht gespeichert werden.'
    reset()
    return entry['id'], ''


def delete_share(sid):
    lst = shares()
    ok = C.save_section('nas', [s for s in lst if s['id'] != sid])
    reset()
    return ok


def reset_cache(s=None):
    """Offene SMB-Verbindungen schliessen: alle oder nur die zur NAS der Freigabe s."""
    try:
        import smbclient
        if s is None:
            smbclient.reset_connection_cache(fail_on_error=False)
            return
        from smbclient import _pool
        con = _pool._SMB_CONNECTIONS.pop(f'{_hostname(s).lower()}:{_port(s)}', None)
        if con:
            con.disconnect()
    except Exception:
        pass


def reset():
    """Nach einer Aenderung der Zugangsdaten: offene Verbindungen schliessen, Sperren vergessen."""
    _down.clear()
    reset_cache()


def roots():
    """(Pfad, Anzeige, Beschreibung) fuer die Ordnerauswahl der Importe."""
    return [(f'{PREFIX}/{s["id"]}', f'NAS: {s["label"]}', 'NAS-Freigabe') for s in shares()]


# ---------------------------------------------------------------- Pfade
def is_nas(path):
    p = str(path or '')
    return p == PREFIX or p.startswith(PREFIX + '/')


def norm(path):
    """/nas/musik/a/../b -> /nas/musik/b; verlaesst nie /nas/<name>."""
    p = posixpath.normpath('/' + str(path).lstrip('/'))
    parts = p.split('/')
    return p if len(parts) >= 3 and parts[1] == PREFIX[1:] else None


def _split(path):
    """/nas/<id>/rest -> (freigabe, UNC-Pfad). OSError, wenn es die Freigabe nicht (mehr) gibt."""
    p = norm(path)
    if not p:
        raise OSError(errno.ENOENT, 'Kein NAS-Pfad', str(path))
    _, _, sid, *rest = p.split('/')
    s = get_share(sid)
    if not s:
        raise OSError(errno.ENOENT, 'NAS-Freigabe nicht (mehr) eingerichtet', str(path))
    return s, _unc(s, rest)


def _hostname(s):
    """NAS-Adresse ohne Port (IPv6 ohne Klammern)."""
    h = s['host']
    if h.startswith('['):
        return h[1:h.index(']')]
    return h.split(':')[0]


def _unc(s, rest=()):
    parts = [s['share']] + ([s['folder']] if s.get('folder') else []) + list(rest)
    return '\\\\' + _hostname(s) + '\\' + '\\'.join(x.replace('/', '\\') for x in parts)


def _port(s):
    m = re.search(r':(\d{1,5})$', s['host'])
    return int(m.group(1)) if m and not s['host'].endswith(']') else 445


def _kw(s):
    return {'username': s.get('user') or None, 'password': s.get('password') or None, 'port': _port(s),
            'connection_timeout': TIMEOUT, 'auth_protocol': 'ntlm'}


def _call(path, fn):
    """fn(smbclient, unc, kwargs) ausfuehren; Verbindungsfehler merken, damit eine ausgeschaltete NAS nicht jedes Mal
    TIMEOUT Sekunden kostet."""
    s, unc = _split(path)
    host = s['host']
    d = _down.get(host)
    if d and time.time() - d[0] < DOWN_PAUSE:
        if not reachable(s):  # wieder eingeschaltet? Dann nicht die volle Minute warten
            raise OSError(errno.EHOSTUNREACH, d[1], str(path))
        _down.pop(host, None)
    import smbclient
    try:
        return fn(smbclient, unc, _kw(s))
    except OSError:
        raise  # Datei/Ordner fehlt, keine Rechte: die NAS ist aber erreichbar
    except Exception as e:
        msg = describe(e)
        if _is_conn_error(e):
            _down[host] = (time.time(), msg)
            reset_cache(s)  # z. B. NAS neu gestartet: beim naechsten Versuch neu verbinden statt die tote Verbindung zu nehmen
        raise OSError(errno.EIO, msg, str(path)) from e


def _is_conn_error(e):
    n = type(e).__name__
    return isinstance(e, (ConnectionError, TimeoutError)) or n in ('SMBConnectionClosed', 'SMBAuthenticationError', 'ValueError') \
        or 'connect' in str(e).lower() or 'timed out' in str(e).lower()


def describe(e):
    """Fehler verstaendlich beschreiben (fuer die Seite Einstellungen und die Importe)."""
    st = getattr(e, 'ntstatus', None)
    if st in (0xC00000CC, 0xC0000225):  # BAD_NETWORK_NAME, NOT_FOUND (falscher Name der Freigabe)
        return 'Die Freigabe gibt es auf der NAS nicht. Bitte den Namen der Freigabe prüfen.'
    if st in (0xC0000034, 0xC000003A):
        return 'Den Unterordner gibt es auf der NAS nicht.'
    if st in (0xC0000022, 0xC0000203):
        return 'Kein Zugriff: Der Benutzer darf diese Freigabe nicht lesen.'
    if st == 0xC000006D:
        return 'Anmeldung abgelehnt. Bitte Benutzer und Passwort prüfen.'
    t = f'{type(e).__name__}: {e}'.lower()
    if 'as a guest' in t:
        return 'Die NAS kennt diesen Benutzer nicht und würde nur einen Gastzugang erlauben. Bitte den Benutzernamen prüfen (genau so, wie er auf der NAS angelegt ist).'
    if 'negotiat' in t or 'dialect' in t:
        return 'Die NAS spricht wohl nur das alte SMB1. Bitte in der NAS-Oberfläche SMB2 oder SMB3 einschalten.'
    if 'logon' in t or 'authentication' in t or 'access_denied' in t or 'password' in t or 'status_logon_failure' in t:
        return 'Anmeldung abgelehnt. Bitte Benutzer und Passwort prüfen.'
    if 'bad_network_name' in t or 'network name' in t:
        return 'Die Freigabe gibt es auf der NAS nicht. Bitte den Namen der Freigabe prüfen.'
    if 'object_name_not_found' in t or 'object_path_not_found' in t or 'no such file' in t:
        return 'Den Unterordner gibt es auf der NAS nicht.'
    if 'timed out' in t or 'timeout' in t or 'refused' in t or 'unreachable' in t or 'name or service' in t \
            or 'nodename' in t or 'getaddrinfo' in t or 'failed to connect' in t:
        return 'Die NAS ist nicht erreichbar. Läuft sie, und stimmt die Adresse? SMB muss eingeschaltet sein.'
    return 'Fehler beim Zugriff auf die NAS: ' + str(e)[:200]


# ---------------------------------------------------------------- Dateizugriff (wie os)
def scandir(path):
    """Liste von (name, ist_ordner, ist_datei) ohne . und .."""
    def fn(sc, unc, kw):
        with sc.scandir(unc, **kw) as it:
            return [(e.name, e.is_dir(), e.is_file()) for e in it if e.name not in ('.', '..')]
    return _call(path, fn)


def listdir(path):
    return [n for n, _, _ in scandir(path)]


def isdir(path):
    try:
        return bool(_call(path, lambda sc, unc, kw: sc.path.isdir(unc, **kw)))
    except OSError:
        return False


def isfile(path):
    try:
        return bool(_call(path, lambda sc, unc, kw: sc.path.isfile(unc, **kw)))
    except OSError:
        return False


def getsize(path):
    return _call(path, lambda sc, unc, kw: sc.stat(unc, **kw).st_size)


def open_file(path, mode='rb', encoding=None, errors=None):
    if any(c in mode for c in 'wax+'):
        raise OSError(errno.EROFS, 'NAS-Freigaben werden nur gelesen', str(path))
    return _call(path, lambda sc, unc, kw: sc.open_file(unc, mode=mode, encoding=encoding, errors=errors,
                                                         buffering=256 * 1024 if 'b' in mode else -1, **kw))


def walk(top, onerror=None):
    """Wie os.walk (von oben nach unten); Aenderungen an dirs[:] werden beachtet, Fehler in Unterordnern uebersprungen
    und wie bei os.walk an onerror(OSError) gemeldet."""
    top = norm(top)
    if not top:
        return
    try:
        entries = scandir(top)
    except OSError as e:
        logging.warning('NAS-Ordner nicht lesbar: %s (%s)', top, e)
        if onerror:
            e.filename = top
            onerror(e)
        return
    dirs = [n for n, d, _ in entries if d]
    files = [n for n, d, f in entries if not d]
    yield top, dirs, files
    for d in dirs:
        yield from walk(top + '/' + d, onerror)


# ---------------------------------------------------------------- Ist die NAS gerade an?
def reachable(s, timeout=2):
    """Schnelle Pruefung ohne Anmeldung: antwortet die NAS auf dem SMB-Port? Ergebnis gilt SEEN_TTL Sekunden."""
    host = s['host']
    c = _seen.get(host)
    if c and time.time() - c[0] < SEEN_TTL:
        return c[1]
    try:
        addr = socket.getaddrinfo(_hostname(s), _port(s), type=socket.SOCK_STREAM)[0][4]
        socket.create_connection(addr[:2], timeout=timeout).close()
        ok = True
    except (OSError, UnicodeError):
        ok = False
    _seen[host] = (time.time(), ok)
    if ok:
        _down.pop(host, None)
    return ok


def online():
    """{'/nas/<id>': True/False} fuer alle Freigaben; jede NAS wird nur einmal gefragt, alle gleichzeitig."""
    from concurrent.futures import ThreadPoolExecutor
    lst = shares()
    hosts = {s['host']: s for s in lst}
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(hosts)))) as ex:
        ok = dict(zip(hosts, ex.map(reachable, hosts.values())))
    return {f'{PREFIX}/{s["id"]}': ok[s['host']] for s in lst}


def offline_message(path):
    """Meldung fuer die Ordnerauswahl, wenn die NAS hinter einem /nas-Pfad gerade nicht antwortet, sonst ''."""
    p = norm(path)
    s = get_share(p.split('/')[2]) if p else None
    if not s or reachable(s):
        return ''
    return ('Die NAS „§“ ist gerade nicht erreichbar. Ist sie eingeschaltet? Nach dem Einschalten dauert es oft ein bis zwei Minuten, bis sie bereit ist.', s['label'])


def probe(s):
    """Verbindung Schritt fuer Schritt pruefen: Name -> Netz -> SMB-Port -> Anmeldung -> Freigabe und Unterordner.
    Gibt (ok, text, technische_angabe) zurueck; text ist ein String oder (Muster mit §, Werte ...)."""
    host, port = _hostname(s), _port(s)
    try:
        addr = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][4]
    except (socket.gaierror, UnicodeError) as e:
        if host.lower().endswith('.local'):
            return False, ('Den Namen „§“ findet MediaDB nicht: Namen mit .local funktionieren im Docker-Container nicht. Bitte die IP-Adresse der NAS eintragen (z. B. 192.168.1.20).', host), str(e)
        return False, ('Den Namen „§“ findet MediaDB im Netz nicht. Bitte die IP-Adresse der NAS eintragen (z. B. 192.168.1.20).', host), str(e)
    try:
        socket.create_connection(addr[:2], timeout=5).close()
    except ConnectionRefusedError as e:
        return False, ('Die NAS unter § antwortet, aber SMB ist dort nicht eingeschaltet (Port § ist zu). Bitte SMB in der NAS-Oberfläche einschalten.', host, port), str(e)
    except OSError as e:
        return False, ('Unter § antwortet nichts. Stimmt die Adresse, und ist die NAS eingeschaltet? Läuft MediaDB in einem LXC oder einer VM: Ist die NAS von dort aus erreichbar (Firewall, anderes Netz)?', host), f'{type(e).__name__}: {e}'
    import smbclient
    cache = {}  # eigene Verbindung, damit eine alte (z. B. mit anderem Passwort) nicht stoert
    try:
        with smbclient.scandir(_unc(s), **_kw(s), connection_cache=cache) as it:
            entries = [(e.name, e.is_dir()) for e in it if e.name not in ('.', '..')]
    except Exception as e:
        msg = describe(e)
        if type(e).__name__ == 'SMBConnectionClosed' and msg.startswith('Fehler beim'):  # Port offen, aber sofort aufgelegt
            msg = 'Die NAS hat die Verbindung sofort beendet. Meist spricht sie nur das alte SMB1: Bitte in der NAS-Oberfläche SMB2 oder SMB3 einschalten.'
        return False, msg, f'{type(e).__name__}: {e}'[:300]
    finally:
        try:
            smbclient.reset_connection_cache(fail_on_error=False, connection_cache=cache)
        except Exception:
            pass
    nd = sum(1 for _, d in entries if d)
    return True, ('Verbindung klappt: § Ordner und § Dateien gefunden.', nd, len(entries) - nd), ''


def check(sid):
    """Gespeicherte Freigabe pruefen. Gibt (ok, text, technische_angabe) zurueck."""
    s = get_share(sid)
    if not s:
        return False, 'Freigabe nicht gefunden.', ''
    _down.pop(s['host'], None)
    reset_cache(s)
    return probe(s)


def test(data, sid=None):
    """Angaben aus dem Formular pruefen, ohne sie zu speichern (Knopf „Verbindung prüfen“)."""
    entry, _, err = _entry(data, sid)
    return (False, err, '') if err else probe(entry)


# ---------------------------------------------------------------- HTTP-Vermittler fuer ffprobe/ffmpeg
_server = None
_token = secrets.token_urlsafe(16)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _path(self):
        pre = f'/{_token}/'
        if not self.path.startswith(pre):
            return None
        p = norm(unquote(self.path[len(pre) - 1:].split('?')[0]))
        return p if p and is_nas(p) else None

    def do_HEAD(self):
        self._serve(body=False)

    def do_GET(self):
        self._serve(body=True)

    def _serve(self, body):
        p = self._path()
        if not p:
            self.send_error(404)
            return
        try:
            size = getsize(p)
        except OSError:
            self.send_error(404)
            return
        start, end = 0, size - 1
        m = re.fullmatch(r'bytes=(\d*)-(\d*)', self.headers.get('Range') or '')
        partial = bool(m and (m.group(1) or m.group(2)))
        if partial:
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            if start >= size or start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
        self.send_response(206 if partial else 200)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(end - start + 1))
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if not body:
            return
        try:
            with open_file(p, 'rb') as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(left, 1024 * 1024))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # ffprobe bricht ab, sobald es genug gelesen hat
        except OSError as e:
            logging.info('NAS-Datei nicht vollständig gelesen: %s (%s)', p, e)


def media_url(path):
    """Adresse, unter der ffprobe/ffmpeg eine NAS-Datei lesen koennen."""
    global _server
    with _lock:
        if _server is None:
            _server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
            _server.daemon_threads = True
            threading.Thread(target=_server.serve_forever, daemon=True, name='nas-http').start()
    return f'http://127.0.0.1:{_server.server_address[1]}/{_token}' + quote(norm(path) or '')
