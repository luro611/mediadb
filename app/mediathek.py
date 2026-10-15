"""Suche in den Mediatheken von ARD, ZDF, Arte, 3sat und den anderen oeffentlich-rechtlichen Sendern (seit 1.8).

Quelle: MediathekViewWeb (https://mediathekviewweb.de), der Web-Ableger von MediathekView (freie Software, GPL-3.0).
Genutzt wird der oeffentliche RSS-Feed, den die Seite zu jeder Suche anbietet (dokumentiert: "Jede Suche kann als Feed
abonniert werden"). MediaDB zeigt nur Treffer an und verlinkt auf die Seite der Sendung in der jeweiligen Mediathek;
es wird nichts heruntergeladen. Abschaltbar mit MEDIATHEK=0 (Einstellungen).
Einzige Netzwerkfunktion: _http_get (in Tests ersetzbar)."""
import email.utils, re, threading, time
import xml.etree.ElementTree as ET
import requests
from . import config as C
from . import films_tmdb as T

FEED = 'https://mediathekviewweb.de/feed'
CACHE_S = 6 * 3600
_cache = {}
_lock = threading.Lock()
_last = [0.0]
GAP = 0.5
# Fassungen, die als eigene Eintraege kommen; sie werden zusammengefasst, nicht einzeln gezeigt
VARIANTS = re.compile(r'\s*[(\[-]?\s*(mit\s+)?(audiodeskription|h[öo]rfassung|geb[äa]rdensprache|klare sprache|'
                      r'untertitel|originalversion|originalfassung|OV|OmU|englische fassung|english version)\s*[)\]]?\s*$', re.I)
SKIP = re.compile(r'\b(trailer|teaser|vorschau|making[- ]of|clip|ausschnitt)\b', re.I)
NS = {'dc': 'http://purl.org/dc/elements/1.1/'}


def enabled():
    return C.flag('MEDIATHEK')


def _http_get(url, params=None, timeout=20):
    r = requests.get(url, params=params, headers={'User-Agent': T.ua()}, timeout=timeout)
    return r.status_code, r.content


def norm(s):
    s = (s or '').lower().replace('ß', 'ss')
    s = re.sub(r'[„“"\'’`´]', '', s)
    s = re.sub(r'[^\w]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _feed(query, everywhere=False):
    """Alle Eintraege eines Suchfeeds als Liste von dicts (aus dem Zwischenspeicher, wenn juenger als 6 Stunden)."""
    key = (query, everywhere)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1], None
    with _lock:
        wait = GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    try:
        code, body = _http_get(FEED, {'query': query, 'everywhere': 'true' if everywhere else 'false'})
    except Exception:
        return [], 'Die Mediatheken-Suche ist gerade nicht erreichbar.'
    if code != 200:
        return [], 'Die Mediatheken-Suche ist gerade nicht erreichbar.'
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], 'Die Mediatheken-Suche lieferte keine lesbare Antwort.'
    out = []
    for it in root.iter('item'):
        def t(tag):
            e = it.find(tag, NS)
            return (e.text or '').strip() if e is not None and e.text else ''
        when = None
        try:
            when = email.utils.parsedate_to_datetime(t('pubDate')).date().isoformat() if t('pubDate') else None
        except (TypeError, ValueError):
            pass
        dur = t('duration')
        out.append({'title': t('title'), 'topic': t('category'), 'channel': t('dc:creator'), 'description': t('description'),
                    'date': when, 'duration_s': int(dur) if dur.isdigit() else None, 'website': t('websiteUrl'),
                    'id': t('guid')})
    _cache[key] = (time.time(), out)
    return out, None


def _clean(items, today):
    """Fassungen zusammenfassen, Trailer und Zukuenftiges weglassen, Doppelte entfernen."""
    seen, out = {}, []
    for x in items:
        if SKIP.search(x['title']) or not x['website'] or not x['website'].startswith('https://'):
            continue
        if x['date'] and x['date'] > today:
            continue
        base = VARIANTS.sub('', x['title']).strip()
        k = (norm(base), x['channel'], x['date'])
        if k in seen:
            seen[k]['variants'] += 1
            continue
        x = dict(x, title=base, variants=0)
        seen[k] = x
        out.append(x)
    return out


def _topic_fits(topic, names):
    t = norm(topic)
    for n in names:
        n = norm(n)
        if n and t == n:
            return True
        if n and t.startswith(n + ' ') and re.match(r'(staffel|season|saison|temporada|teil|folge|\d)', t[len(n):].strip()):
            return True  # 'Babylon Berlin Staffel 2'
    return False


EP_PATTERNS = [re.compile(r'\(S(\d{1,2})\s*/\s*E(\d{1,3})\)', re.I), re.compile(r'\bS(\d{1,2})\s*E(\d{1,3})\b', re.I),
               re.compile(r'Staffel\s*(\d{1,2})\s*,?\s*(?:Folge|Episode|Teil)\s*(\d{1,3})', re.I)]
EP_OF = re.compile(r'\((\d{1,3})\s*/\s*(\d{1,3})\)')  # 'Babylon Berlin (3/8)'
TOPIC_SEASON = re.compile(r'\b(?:Staffel|Season|Saison|Temporada)\s*(\d{1,2})\b', re.I)
EP_ONLY = re.compile(r'(?:^|\b)(?:Folge|Episode|Teil)\s*(\d{1,3})\b', re.I)


def selector(sign, text):
    """Suchbegriff fuer MediathekViewWeb: mehrere Woerter in einem Selektor mit Komma ('#babylon,berlin')."""
    return sign + ','.join(norm(text).split())


def episode_of(title, topic=''):
    """(staffel oder None, folge oder None, titel ohne Nummer) aus einem Mediathek-Titel (und dem Thema)."""
    m = EP_OF.search(title)
    if m and int(m.group(1)) <= int(m.group(2)):
        ts = TOPIC_SEASON.search(topic or '')
        rest = (title[:m.start()] + title[m.end():]).strip(' :-–()')
        return (int(ts.group(1)) if ts else None), int(m.group(1)), rest
    for p in EP_PATTERNS:
        m = p.search(title)
        if m:
            rest = (title[:m.start()] + title[m.end():]).strip(' :-–()')
            return int(m.group(1)), int(m.group(2)), rest
    m = EP_ONLY.search(title)
    if m:
        rest = (title[:m.start()] + title[m.end():]).strip(' :-–()')
        return None, int(m.group(1)), rest
    return None, None, title


def series_hits(title, original_title=None, episodes=None, have=None, today=None):
    """Folgen einer Serie in den Mediatheken. episodes: Liste (staffel, folge, name) aus dem Episodenfuehrer,
    have: Menge (staffel, folge), die schon da sind. Gibt (liste, fehler) zurueck; jede Folge mit season/episode
    (wenn zuordenbar) und state 'have', 'missing' oder ''."""
    today = today or time.strftime('%Y-%m-%d')
    names = [n for n in (title, original_title) if n]
    items, err = _feed(selector('#', title))
    if original_title and norm(original_title) != norm(title):
        more, err2 = _feed(selector('#', original_title))
        items, err = items + more, err if items else err2
    items = [x for x in _clean(items, today) if _topic_fits(x['topic'], names) and (x['duration_s'] or 0) >= 10 * 60]
    known = {(s, e) for s, e, n in episodes or []}
    by_name = {}
    for s, e, n in episodes or []:
        if n and len(norm(n)) >= 4:
            by_name.setdefault(norm(n), (s, e))
    seasons = {s for s, e, n in episodes or [] if s}
    names_by_key = {(s, e): n for s, e, n in episodes or [] if n}
    for x in items:
        s, e, rest = episode_of(x['title'], x['topic'])
        if e and s is None and len(seasons) == 1:
            s = next(iter(seasons))
        if not e and by_name:
            hit = by_name.get(norm(rest))
            if hit:
                s, e = hit
        if e and s is None:  # Folgennummer ohne Staffel: ueber den Titel absichern
            hit = by_name.get(norm(rest))
            s = hit[0] if hit and hit[1] == e else None
            e = e if s else None
        if e and known and (s, e) not in known:  # z. B. Doku oder Special mit eigener Nummer
            s = e = None
        x['season'], x['episode'] = (s, e) if e else (None, None)
        x['state'] = '' if not e or not known else ('have' if (s, e) in (have or set()) else 'missing')
        x['ep_name'] = names_by_key.get((s, e)) if e else None
    items.sort(key=lambda x: (x['season'] is None, x['season'] or 0, x['episode'] or 0, x['date'] or ''))
    return items, (err if not items else None)


def film_hits(title, original_title=None, year=None, today=None):
    """Ein Film in den Mediatheken: Eintraege, deren Titel genau passt und die mindestens 45 Minuten lang sind."""
    today = today or time.strftime('%Y-%m-%d')
    names = {norm(n) for n in (title, original_title) if n}
    items, err = _feed(selector('+', title))
    if original_title and norm(original_title) != norm(title):
        more, _ = _feed(selector('+', original_title))
        items += more
    out = []
    for x in _clean(items, today):
        if norm(x['title']) not in names or (x['duration_s'] or 0) < 45 * 60:
            continue
        years = [int(y) for y in re.findall(r'\b(19[2-9]\d|20[0-4]\d)\b', x['description'][:200])]
        if year and years and all(abs(y - year) > 1 for y in years):
            continue  # anderer Film mit gleichem Titel (z. B. Neuverfilmung)
        out.append(x)
    out.sort(key=lambda x: x['date'] or '', reverse=True)
    return out, (err if not out else None)
