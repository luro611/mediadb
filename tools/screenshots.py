"""Macht die Bildschirmfotos für die Anleitung neu (docs/bilder/*.png), immer mit der erfundenen Beispiel-Sammlung.

Ablauf: legt mit tools/demo_data.py eine frische Beispiel-Sammlung in einem Zwischenordner an, startet MediaDB damit,
fotografiert die Seiten mit Google Chrome (unsichtbar im Hintergrund) und beendet MediaDB wieder.

Voraussetzungen (einmalig): Google Chrome, die Pakete aus requirements.txt und Playwright:
    python3 -m pip install -r requirements.txt playwright
Aufruf im Projektordner:
    python3 tools/screenshots.py            alle Bilder
    python3 tools/screenshots.py start film  nur Bilder, deren Name so beginnt"""
import os, sys, time, shutil, sqlite3, socket, subprocess, tempfile, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'bilder'
W, H = 1200, 820


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def one(db, sql, *args):
    with sqlite3.connect(db) as c:
        return c.execute(sql, args).fetchone()[0]


def shots(data):
    """Name, Adresse, Ansicht je Bereich, was fotografiert wird: None = sichtbarer Bereich, 'page' = ganze Seite,
    eine Zahl = ganze Seite bis zu dieser Höhe, sonst eine CSS-Auswahl (nur dieser Kasten)."""
    f = lambda t: one(data / 'filme.db', 'SELECT id FROM films WHERE title=?', t)
    s = lambda t: one(data / 'serien.db', 'SELECT id FROM series WHERE title=?', t)
    return [
        ('start', '/', {}, 'page'),
        ('musik-interpreten', '/media', {}, 1250),
        ('musik-kacheln', '/media?mode=list', {'music': 'tiles'}, 1300),
        ('filme-kacheln', '/films', {'films': 'tiles'}, 1300),
        ('filme-liste', '/films', {'films': 'list'}, 1300),
        ('film-detail', f'/films/{f("Der Kartograf")}', {}, 1100),
        ('serie-detail', f'/series/{s("Die Akte Falkenberg")}', {}, 1500),
        ('serien-was-fehlt', '/series/missing', {}, 'page'),
        ('buecher-text', '/books', {'books': 'text'}, 'page'),
        ('buchreihe', '/books/series?name=Kommissarin%20Brandt', {'books': 'tiles'}, 'page'),
        ('merkliste', '/watchlist', {}, 'page'),
        ('verliehen', '/lend', {}, 'page'),
        ('hinzufuegen', '/add', {}, 'page'),
        ('willkommen', '/willkommen', {}, 'page'),
        ('einstellungen-bereiche', '/settings', {}, '#bereiche'),
        ('einstellungen-sprache', '/settings', {}, '#oberflaeche'),
        ('einstellungen-farben', '/settings', {}, '#farben'),
    ]


def main(only):
    tmp = Path(tempfile.mkdtemp(prefix='mediadb-demo-'))
    data = tmp / 'data'
    try:
        subprocess.run([sys.executable, str(ROOT / 'tools' / 'demo_data.py'), str(data)], check=True, cwd=ROOT)
        port = free_port()
        env = dict(os.environ, DATA_DIR=str(data), PORT=str(port), APP_PASSWORD='', ALLOW_PUBLIC='0')
        srv = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', str(port), '--log-level', 'warning'],
                               cwd=ROOT, env=env)
        base = f'http://127.0.0.1:{port}'
        for _ in range(60):
            try:
                urllib.request.urlopen(base + '/healthz', timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit('MediaDB ist nicht gestartet.')
        OUT.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            for name, url, layouts, what in shots(data):
                if only and not any(name.startswith(o) for o in only):
                    continue
                ctx = browser.new_context(viewport={'width': W, 'height': H}, locale='de-DE', color_scheme='light')
                ctx.add_cookies([{'name': f'mediadb_layout_{k}', 'value': v, 'url': base} for k, v in layouts.items()] +
                                [{'name': 'mediadb_lang', 'value': 'de', 'url': base}])
                page = ctx.new_page()
                page.goto(base + url, wait_until='networkidle')
                # ohne Animationen; den Hinweis auf den fehlenden TMDB-Schlüssel ausblenden (die Beispiel-Sammlung braucht keinen)
                page.add_style_tag(content='*{transition:none!important;animation:none!important}.warn:has(a[href$="#tmdb"]){display:none}')
                target = OUT / f'{name}.png'
                if what is None:
                    page.screenshot(path=target)
                elif what == 'page':
                    page.screenshot(path=target, full_page=True)
                elif isinstance(what, int):
                    h = min(what, page.evaluate('document.documentElement.scrollHeight'))
                    page.screenshot(path=target, full_page=True, clip={'x': 0, 'y': 0, 'width': W, 'height': h})
                else:
                    page.locator(what).screenshot(path=target)
                print(f'{target.relative_to(ROOT)}  ({target.stat().st_size // 1024} KB)')
                ctx.close()
            browser.close()
        srv.terminate()
        srv.wait(10)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main(sys.argv[1:])
