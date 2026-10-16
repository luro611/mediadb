"""Hilfe in der App (/hilfe): zeigt die Anleitung und die anderen Texte aus docs/ als Seiten in MediaDB.

Quelle bleibt die Markdown-Datei im Projekt (docs/ANLEITUNG.md usw.); sie wird mit jeder Version ins Docker-Image kopiert,
deshalb passt die Hilfe immer zur laufenden Version und funktioniert auch ohne Internet. Bisher nur auf Deutsch."""
import re
from pathlib import Path
import markdown
from markupsafe import Markup
from starlette.responses import RedirectResponse

ROOT = Path(__file__).resolve().parent.parent
# Seite -> (Datei, Titel); die Schluessel sind die Adressen unter /hilfe
PAGES = {'': (ROOT / 'docs' / 'ANLEITUNG.md', 'Anleitung'), 'betrieb': (ROOT / 'docs' / 'BETRIEB.md', 'Betrieb im Homelab'),
         'datenquellen': (ROOT / 'docs' / 'DATENQUELLEN_UND_RECHT.md', 'Datenquellen und Rechtliches'),
         'aenderungen': (ROOT / 'CHANGELOG.md', 'Änderungen')}
FILE_TO_PAGE = {p.name: k for k, (p, _) in PAGES.items()}
REPO = 'https://codeberg.org/luro61/mediadb/src/branch/main/'

templates = None
ctx = None
_cache = {}


def setup(templates_, ctx_):
    global templates, ctx
    templates, ctx = templates_, ctx_


def slug(text, sep='-'):
    """Sprungmarken wie auf Codeberg: '3. Einstellungen' -> '3-einstellungen', '(ab 1.9)' -> 'ab-1-9'."""
    t = re.sub(r'[^\w\s-]', ' ', text.lower())
    return re.sub(r'[\s-]+', sep, t.strip()).strip(sep)


def _link(m, base):
    """Links zwischen den Dateien auf die Hilfeseiten umbiegen; andere Projektdateien zeigen auf Codeberg."""
    label, target = m.group(1), m.group(2)
    if re.match(r'^[a-z]+:|^#', target):
        return m.group(0)
    path, _, frag = target.partition('#')
    name = Path(path).name
    if name in FILE_TO_PAGE:
        page = FILE_TO_PAGE[name]
        url = f'{base}/hilfe' + (f'/{page}' if page else '')
    else:
        url = REPO + ('docs/' + path if not path.startswith('../') else path[3:])
    return f'[{label}]({url}' + (f'#{frag}' if frag else '') + ')'


_ITEM = re.compile(r'^(\s*)([-*+]|\d+\.)\s')


def _commonmark_lists(text):
    """Listen so schreiben, wie Python-Markdown sie braucht (Codeberg ist grosszuegiger): Leerzeile vor einer Liste,
    die direkt unter einem Absatz beginnt, und Unterpunkte mit 4 statt 2 Leerzeichen eingerueckt."""
    out, prev = [], ''
    for line in text.split('\n'):
        m = _ITEM.match(line)
        if m:
            ind = len(m.group(1))
            if 0 < ind < 4:
                line = '    ' + line.lstrip()
            elif ind == 0 and prev.strip() and not _ITEM.match(prev) and not prev.lstrip().startswith(('|', '>')):
                out.append('')
        out.append(line)
        prev = line
    return '\n'.join(out)


def render(page, base):
    path, title = PAGES[page]
    mtime = path.stat().st_mtime
    key = (page, base)
    if key in _cache and _cache[key][0] == mtime:
        return _cache[key][1], title
    text = _commonmark_lists(path.read_text(encoding='utf-8'))
    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', lambda m: _link(m, base), text)
    md = markdown.Markdown(extensions=['tables', 'fenced_code', 'sane_lists', 'toc'],
                           extension_configs={'toc': {'slugify': slug, 'permalink': False}})
    html = md.convert(text)
    # externe Links in einem neuen Tab oeffnen
    html = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener noreferrer"', html)
    _cache[key] = (mtime, Markup(html))
    return Markup(html), title


async def page(request):
    name = request.path_params.get('page', '')
    if name not in PAGES or not PAGES[name][0].exists():
        return RedirectResponse('/hilfe', 303)
    c = ctx(request, area='help')
    html, title = render(name, c['base'])
    return templates.TemplateResponse(request, 'help.html', {**c, 'doc': html, 'title': title, 'page': name, 'pages': PAGES})
