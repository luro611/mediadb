"""Zugriffsschutz und Unterpfad.

- Unterpfad: Laeuft die App hinter Home Assistant (Ingress) oder einem Reverse Proxy unter einer Unteradresse,
  steht diese im Kopf X-Ingress-Path bzw. X-Forwarded-Prefix oder fest in BASE_PATH. Der Proxy entfernt den
  Unterpfad vor der Weitergabe; die App setzt ihn nur vor ihre Links (Vorlagen: {{ base }}) und Weiterleitungen.
- Heimnetz: Ohne ALLOW_PUBLIC=1 werden Anfragen von oeffentlichen IP-Adressen abgewiesen.
- Passwort: Ist APP_PASSWORD gesetzt, muss man sich anmelden (Cookie, 30 Tage gueltig)."""
import hashlib, hmac, ipaddress, os, re, secrets, time
from pathlib import Path
from urllib.parse import quote

_PREFIX_OK = re.compile(r'^(/[A-Za-z0-9._~\-]+)+$')
COOKIE = 'musikdb_auth'
MAX_AGE = 60 * 60 * 24 * 30
OPEN_PATHS = ('/login', '/static/', '/healthz')


def _flag(name):
    return os.getenv(name, '0').strip().lower() in ('1', 'true', 'yes', 'ja', 'on')


def clean_prefix(p):
    p = (p or '').strip().rstrip('/')
    return p if p and _PREFIX_OK.match(p) else ''


class Settings:
    def __init__(self, data_dir):
        self.base_path = clean_prefix(os.getenv('BASE_PATH', ''))
        self.allow_public = _flag('ALLOW_PUBLIC')
        self.password = os.getenv('APP_PASSWORD', '')
        self.data_dir = Path(data_dir)
        self._secret = None

    @property
    def auth_on(self):
        return bool(self.password)

    def secret(self):
        if self._secret is None:
            env = os.getenv('SECRET_KEY', '').strip()
            if env:
                self._secret = env.encode()
            else:
                f = self.data_dir / 'secret.key'
                try:
                    self._secret = f.read_bytes().strip()
                except Exception:
                    self._secret = b''
                if not self._secret:
                    self._secret = secrets.token_hex(32).encode()
                    try:
                        f.write_bytes(self._secret)
                        os.chmod(f, 0o600)
                    except Exception:
                        pass
        return self._secret

    def _sig(self, exp):
        key = self.secret() + b'|' + hashlib.sha256(self.password.encode()).digest()
        return hmac.new(key, str(exp).encode(), hashlib.sha256).hexdigest()

    def make_token(self):
        exp = int(time.time()) + MAX_AGE
        return f'{exp}.{self._sig(exp)}'

    def token_ok(self, tok):
        try:
            exp, sig = (tok or '').split('.', 1)
            return int(exp) > time.time() and hmac.compare_digest(sig, self._sig(int(exp)))
        except Exception:
            return False

    def password_ok(self, pw):
        return bool(self.password) and hmac.compare_digest((pw or '').encode(), self.password.encode())


def is_local(host):
    """Heimnetz, eigener Rechner, VPN (z. B. Tailscale 100.64.0.0/10) zaehlen als lokal; alles Oeffentliche nicht."""
    if not host:
        return True
    try:
        ip = ipaddress.ip_address(host.split('%')[0])
    except ValueError:
        return True  # z. B. Unix-Socket oder Testclient
    if getattr(ip, 'ipv4_mapped', None):
        ip = ip.ipv4_mapped
    return not ip.is_global


def get_base(request):
    try:
        return request.scope.get('state', {}).get('base', '')
    except Exception:
        return ''


def strip_base(path, base):
    """Pfad aus dem Browser (location.pathname) ohne den Unterpfad."""
    if base and (path == base or path.startswith(base + '/')):
        return path[len(base):] or '/'
    return path


def _cookie(headers, name):
    for k, v in headers:
        if k == b'cookie':
            for part in v.decode('latin-1').split(';'):
                if '=' in part:
                    a, b = part.strip().split('=', 1)
                    if a == name:
                        return b
    return None


_BLOCKED = ('<!doctype html><meta charset="utf-8"><title>MusikDB</title><body style="font-family:sans-serif;max-width:40em;margin:3em auto">'
            '<h1>Kein Zugriff aus dem Internet</h1><p>Diese App ist nur für das eigene Heimnetz gedacht. '
            'Zugriffe von öffentlichen Adressen sind gesperrt.</p>'
            '<h1 lang="en">No access from the internet</h1><p lang="en">This app is meant for your home network only. '
            'Requests from public addresses are blocked.</p>'
            '<p style="color:#666">Betreiber: siehe docs/BETRIEB.md (ALLOW_PUBLIC, APP_PASSWORD).</p></body>').encode()


class Gate:
    """ASGI-Middleware: Unterpfad bestimmen, Heimnetz pruefen, Anmeldung pruefen, Weiterleitungen anpassen."""

    def __init__(self, app, settings):
        self.app = app
        self.s = settings

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = scope.get('headers') or []
        base = ''
        for k, v in headers:
            if k in (b'x-ingress-path', b'x-forwarded-prefix'):
                base = clean_prefix(v.decode('latin-1'))
                if base:
                    break
        base = base or self.s.base_path
        scope.setdefault('state', {})['base'] = base
        path = scope.get('path', '/')
        client = (scope.get('client') or (None,))[0]

        if not self.s.allow_public and not is_local(client):
            return await _respond(send, 403, _BLOCKED, [(b'content-type', b'text/html; charset=utf-8')])

        if self.s.auth_on and not path.startswith(OPEN_PATHS) and not self.s.token_ok(_cookie(headers, COOKIE)):
            qs = scope.get('query_string', b'').decode('latin-1')
            nxt = path + ('?' + qs if qs else '')
            loc = f'{base}/login?next={quote(nxt)}'
            return await _respond(send, 303, b'', [(b'location', loc.encode())])

        async def send_wrapped(msg):
            if base and msg['type'] == 'http.response.start':
                hs = []
                for k, v in msg.get('headers', []):
                    if k.lower() == b'location' and v.startswith(b'/') and not v.startswith(b'//'):
                        v = base.encode() + v
                    hs.append((k, v))
                msg = dict(msg, headers=hs)
            await send(msg)

        return await self.app(scope, receive, send_wrapped)


async def _respond(send, status, body, headers):
    await send({'type': 'http.response.start', 'status': status,
                'headers': headers + [(b'content-length', str(len(body)).encode())]})
    await send({'type': 'http.response.body', 'body': body})
