"""Buchdaten aus dem Netz: Deutsche Nationalbibliothek (SRU, MARC21) und Open Library (Daten und Titelbilder).

DNB: kostenlos, ohne Anmeldung, Metadaten frei nutzbar (CC0); sehr vollstaendig fuer Buecher aus Deutschland, Oesterreich, Schweiz;
     keine Titelbilder. https://www.dnb.de/sru
Open Library (Internet Archive): kostenlos, ohne Schluessel, international, mit Titelbildern. Bilder werden ueber die
     Cover-Nummer geladen (nicht per ISBN, das ist auf 100 Abrufe je 5 Minuten begrenzt) und lokal gespeichert.
Wikipedia: Zusammenfassung (Einleitung des Artikels) ueber die REST-Schnittstelle, Text unter CC BY-SA 4.0, mit Link.
Einzige Netzwerkfunktion: _http_get (in Tests ersetzbar)."""
import html, json, re, threading, time
import xml.etree.ElementTree as ET
from urllib.parse import quote
import requests
from . import films_tmdb as T
from . import books_db as B

DNB = 'https://services.dnb.de/sru/dnb'
OL = 'https://openlibrary.org'
COVERS = 'https://covers.openlibrary.org'
_lock = threading.Lock()
_last = {'dnb': 0.0, 'ol': 0.0, 'cover_isbn': 0.0, 'wiki': 0.0}
GAP = {'dnb': 0.25, 'ol': 0.6, 'cover_isbn': 3.1, 'wiki': 0.2}  # Cover per ISBN: hoechstens 100 je 5 Minuten


def _http_get(url, params=None, timeout=20):
    """Einzige Stelle mit Netzwerkzugriff. Gibt (status, bytes, content_type)."""
    r = requests.get(url, params=params, headers={'User-Agent': T.ua()}, timeout=timeout)
    return r.status_code, r.content, r.headers.get('Content-Type', '')


def _get(kind, url, params=None, timeout=20):
    with _lock:
        wait = GAP[kind] - (time.time() - _last[kind])
        if wait > 0:
            time.sleep(wait)
        _last[kind] = time.time()
    try:
        return _http_get(url, params, timeout)
    except Exception as e:
        return 0, str(e).encode(), ''


# ---------------------------------------------------------------- DNB (MARC21)
def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _clean(s):
    s = (s or '').replace('\x98', '').replace('\x9c', '').replace('&#152;', '').replace('&#156;', '')
    return re.sub(r'\s+', ' ', s).strip(' /:;,=')


def flip_name(n):
    """'Tolkien, J. R. R.' -> 'J. R. R. Tolkien'."""
    n = _clean(n)
    if n.count(',') == 1:
        last, first = [x.strip() for x in n.split(',')]
        return f'{first} {last}'.strip()
    return n


ROLE_MAP = {'aut': 'aut', 'trl': 'trl', 'ill': 'ill', 'nrr': 'nrr', 'spk': 'nrr', 'edt': 'edt', 'hrsg': 'edt'}


def parse_marc(rec):
    f = {}
    for el in rec:
        if _local(el.tag) == 'controlfield':
            f.setdefault(el.get('tag'), []).append({'_': [el.text or '']})
        elif _local(el.tag) == 'datafield':
            sub = {'_ind1': el.get('ind1') or ' ', '_ind2': el.get('ind2') or ' '}
            for s in el:
                code = s.get('code')
                sub.setdefault(code, []).append(s.text or '')
            f.setdefault(el.get('tag'), []).append(sub)

    def first(tag, code):
        for d in f.get(tag, []):
            if d.get(code):
                return d[code][0]
        return ''
    isbns = []
    for d in f.get('020', []):
        for v in d.get('a', []):
            i = B.norm_isbn(v)
            if i and i not in isbns:
                isbns.append(i)
    people = []
    for tag in ('100', '700', '110'):
        for d in f.get(tag, []):
            if d.get('t') or not d.get('a'):  # 700 mit $t ist ein Werktitel (Original), keine Person
                continue
            role = ROLE_MAP.get((d.get('4') or ['aut'])[0], None)
            if role is None:
                e = ' '.join(d.get('e', [])).lower()
                role = 'trl' if 'übers' in e else 'ill' if 'illustr' in e else 'nrr' if 'sprech' in e or 'erzähl' in e else 'edt' if 'herausg' in e else 'aut'
            gnd = next((x[8:] for x in d.get('0', []) if x.startswith('(DE-588)')), None)
            people.append({'name': flip_name(d['a'][0]), 'role': role, 'gnd': gnd})
    orig = next((_clean(d['a'][0]) for d in f.get('240', []) if d.get('a')), '') or \
        next((_clean(d['t'][0]) for d in f.get('700', []) if d.get('t')), '')
    pub = f.get('264', []) or f.get('260', [])
    publisher = _clean(pub[0]['b'][0]) if pub and pub[0].get('b') else ''
    place = _clean(pub[0]['a'][0]) if pub and pub[0].get('a') else ''
    year = None
    for d in pub:
        m = re.search(r'(1[5-9]\d\d|20\d\d)', ' '.join(d.get('c', [])))
        if m:
            year = int(m.group(1))
            break
    if not year:
        m = re.match(r'.{7}(\d{4})', (f.get('008') or [{'_': ['']}])[0]['_'][0])
        year = int(m.group(1)) if m and m.group(1).isdigit() and m.group(1) != '0000' else None
    pages = None
    m = re.search(r'(\d+)\s*(?:S\.|Seiten|p\.|pages)', first('300', 'a'))
    if m:
        pages = int(m.group(1))
    dur = None
    m = re.search(r'(?:(\d+)\s*Std\.?)?\s*(?:(\d+)\s*Min)', first('300', 'a') + ' ' + first('306', 'a'))
    if m and (m.group(1) or m.group(2)):
        dur = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60
    series, series_no = '', ''
    for tag in ('800', '830', '490'):
        for d in f.get(tag, []):
            if d.get('a') or d.get('t'):
                s, no = _clean((d.get('t') or d.get('a'))[0]), _clean((d.get('v') or [''])[0])
                if publisher_series(s, no):  # Verlagsreihe wie 'dtv 21412' ist keine Buchreihe
                    continue
                series, series_no = s, re.sub(r'^(?:Bd|Band|Vol|Volume|Tome|Tomo|T)\.?\s*', '', no, flags=re.I)
                break
        if series:
            break
    genres, form = [], ''
    for d in f.get('655', []):
        for v in d.get('a', []):
            v = _clean(v)
            if v and v not in genres:
                genres.append(v)
    for d in f.get('653', []):
        for v in d.get('a', []):
            m = re.match(r'\(VLB-WN\)\d+:\s*(.+)', v)
            if m:
                parts = [p.strip() for p in m.group(1).split('/') if p.strip()]
                if parts:
                    form = form or parts[0]
                    if len(parts) > 1 and parts[-1] not in genres:
                        genres.append(parts[-1])
            m = re.match(r'\(Produktform\)(.+)', v) or re.match(r'\(VLB-PF\)\w*:\s*(.+)', v)
            if m:
                form = form or m.group(1)
    subjects = []
    for tag in ('689', '650'):
        for d in f.get(tag, []):
            for v in d.get('a', []):
                v = _clean(v)
                if v and v not in subjects and v not in genres:
                    subjects.append(v)
    carrier = ' '.join(d.get('a', [''])[0] for d in f.get('338', []) + f.get('337', []) + f.get('336', []))
    title = _clean(first('245', 'a'))
    part = ' '.join(_clean(x) for d in f.get('245', []) for x in d.get('n', []) + d.get('p', []))
    if part:
        title = f'{title}. {part}' if title else part
    lang = first('041', 'a') or (f.get('008') or [{'_': ['']}])[0]['_'][0][35:38]
    links = {}
    for d in f.get('856', []):  # Verweise: Inhaltstext des Verlags (ueber MVB/DNB), Inhaltsverzeichnis (PDF)
        what, url = (d.get('3') or [''])[0].lower(), (d.get('u') or [''])[0]
        if url.startswith('https://') and ('dnb.de/' in url or 'd-nb.info/' in url):
            if 'inhaltstext' in what:
                links.setdefault('blurb_url', url)
            elif 'inhaltsverzeichnis' in what:
                links.setdefault('toc_url', url)
    return {
        'blurb_url': links.get('blurb_url'), 'toc_url': links.get('toc_url'),
        'title': title, 'subtitle': _clean(first('245', 'b')) or None, 'original_title': orig or None,
        'authors': '; '.join(p['name'] for p in people if p['role'] == 'aut') or None, '_people': people,
        'publisher': publisher or None, 'place': place or None, 'year': year, 'edition': _clean(first('250', 'a')) or None,
        'pages': pages, 'duration_s': dur, 'language': (lang or '').strip() or None, 'series': series or None, 'series_no': series_no or None,
        'genres': ', '.join(genres[:4]) or None, 'subjects': ', '.join(subjects[:8]) or None,
        'isbn': isbns[0] if isbns else None, '_isbns': isbns, 'dnb_id': first('001', '_') or None, 'source': 'dnb',
        '_kind': kind_hint(form + ' ' + carrier),
    }


PUBLISHER_SERIES = re.compile(r'^(dtv|fischer|rororo|goldmann|heyne|bastei|bastei[- ]l(ü|ue)bbe|l(ü|ue)bbe|btb|blanvalet|knaur|ullstein|piper|'
                              r'suhrkamp|insel|reclam|diogenes|kiwi|kiepenheuer|droemer|aufbau|penguin|vintage|folio|livre de poche|'
                              r'pocket|j\'ai lu|debolsillo|anagrama|ravensburger|carlsen|oetinger|arena|cbt|cbj|thienemann)\b', re.I)


def publisher_series(name, no):
    n = re.sub(r'\D', '', no or '')
    return bool(PUBLISHER_SERIES.match(name or '')) or (n.isdigit() and int(n) > 500)


def kind_hint(text):
    t = (text or '').lower()
    if re.search(r'gesprochenes wort|hörbuch|hoerbuch|audio|tonträger|cd\b|mp3', t):
        return 'audiobook'
    if re.search(r'online-ressource|e-book|ebook|computermedien|epub|digital', t):
        return 'ebook'
    if re.search(r'hardback|hardcover|gebunden|fester einband', t):
        return 'hardcover'
    if re.search(r'paperback|softback|taschenbuch|kartoniert|broschiert|kart\.', t):
        return 'paperback'
    return ''


def dnb_query(cql, limit=20):
    code, body, _ = _get('dnb', DNB, {'version': '1.1', 'operation': 'searchRetrieve', 'query': cql,
                                      'recordSchema': 'MARC21-xml', 'maximumRecords': str(limit)})
    if code != 200:
        return None, f'DNB nicht erreichbar ({code}).' if code else 'DNB nicht erreichbar.'
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None, 'DNB lieferte keine lesbare Antwort.'
    out = []
    for rec in root.iter():
        if _local(rec.tag) == 'record' and rec.get('type') == 'Bibliographic':
            try:
                out.append(parse_marc(rec))
            except Exception:
                continue
    return out, None


def _cql(s):
    return '"' + re.sub(r'["\\]', ' ', s).strip() + '"'


def dnb_isbn(isbn):
    return dnb_query(f'isbn={isbn}', 5)


def dnb_search(title='', author='', limit=20):
    parts = []
    if title:
        parts.append(f'tit={_cql(title)}')
    if author:
        parts.append(f'per={_cql(author)}')
    if not parts:
        return [], None
    return dnb_query(' and '.join(parts), limit)


# ---------------------------------------------------------------- Open Library
def _json(kind, url, params=None):
    code, body, _ = _get(kind, url, params)
    if code != 200:
        return None, f'Open Library nicht erreichbar ({code}).' if code else 'Open Library nicht erreichbar.'
    try:
        return json.loads(body), None
    except ValueError:
        return None, 'Open Library lieferte keine lesbare Antwort.'


def ol_isbn(isbn):
    d, err = _json('ol', f'{OL}/api/books', {'bibkeys': f'ISBN:{isbn}', 'format': 'json', 'jscmd': 'data'})
    if err or not d:
        return None, err
    r = d.get(f'ISBN:{isbn}')
    if not r:
        return None, None
    m = re.search(r'(1[5-9]\d\d|20\d\d)', r.get('publish_date') or '')
    cover = (r.get('cover') or {}).get('large') or (r.get('cover') or {}).get('medium') or ''
    cid = re.search(r'/b/id/(\d+)', cover)
    people = [{'name': a.get('name'), 'role': 'aut', 'ol_key': (a.get('url') or '').rsplit('/authors/', 1)[-1].split('/')[0] or None}
              for a in r.get('authors') or [] if a.get('name')]
    return {
        'title': r.get('title') or '', 'subtitle': r.get('subtitle') or None,
        'authors': '; '.join(p['name'] for p in people) or None, '_people': people,
        'publisher': ', '.join(p.get('name', '') for p in r.get('publishers') or []) or None, 'year': int(m.group(1)) if m else None,
        'pages': r.get('number_of_pages'), 'subjects': ', '.join(s.get('name', '') for s in (r.get('subjects') or [])[:8]) or None,
        'isbn': isbn, 'ol_key': (r.get('key') or '').replace('/books/', '') or None, 'source': 'openlibrary',
        '_cover_id': int(cid.group(1)) if cid else None,
    }, None


def ol_description(ol_key):
    """Beschreibung des Werks (oft englisch). ol_key: Ausgabe 'OL...M'."""
    if not ol_key:
        return None
    ed, _ = _json('ol', f'{OL}/books/{ol_key}.json')
    works = [w.get('key') for w in (ed or {}).get('works') or [] if w.get('key')]
    desc = (ed or {}).get('description')
    if not desc and works:
        w, _ = _json('ol', f'{OL}{works[0]}.json')
        desc = (w or {}).get('description')
    if isinstance(desc, dict):
        desc = desc.get('value')
    return re.sub(r'\s+', ' ', desc).strip()[:3000] if desc else None


def ol_search(title='', author='', q='', limit=20):
    params = {'fields': 'key,title,subtitle,author_name,first_publish_year,isbn,cover_i,number_of_pages_median,language,publisher',
              'limit': str(limit)}
    if title:
        params['title'] = title
    if author:
        params['author'] = author
    if q and not (title or author):
        params['q'] = q
    lang = {'de': 'ger', 'en': 'eng', 'fr': 'fre', 'es': 'spa', 'it': 'ita'}.get(T.language()[:2])
    d, err = _json('ol', f'{OL}/search.json', params)
    if err:
        return [], err
    out = []
    for r in (d or {}).get('docs') or []:
        isbns = [B.norm_isbn(x) for x in r.get('isbn') or []]
        isbns = [x for x in isbns if x]
        isbn = next((x for x in isbns if lang == 'ger' and x[3] == '3'), None) or (isbns[0] if isbns else None)
        out.append({'title': r.get('title') or '', 'subtitle': r.get('subtitle'), 'authors': '; '.join(r.get('author_name') or []) or None,
                    '_people': [{'name': n, 'role': 'aut'} for n in r.get('author_name') or []],
                    'year': r.get('first_publish_year'), 'pages': r.get('number_of_pages_median'), 'isbn': isbn,
                    'publisher': ', '.join((r.get('publisher') or [])[:2]) or None, 'source': 'openlibrary',
                    'language': 'ger' if lang == 'ger' and 'ger' in (r.get('language') or []) else ((r.get('language') or [None])[0]),
                    '_cover_id': r.get('cover_i'), 'ol_work': r.get('key')})
    return out, None


def cover_url(cover_id, size='M'):
    return f'{COVERS}/b/id/{cover_id}-{size}.jpg' if cover_id else ''


def fetch_cover(cover_id=None, isbn=None):
    """Titelbild als Bytes (oder None). Bevorzugt ueber die Cover-Nummer; per ISBN nur gedrosselt."""
    if cover_id:
        code, body, ctype = _get('ol', f'{COVERS}/b/id/{cover_id}-L.jpg', {'default': 'false'})
    elif isbn:
        code, body, ctype = _get('cover_isbn', f'{COVERS}/b/isbn/{isbn}-L.jpg', {'default': 'false'})
    else:
        return None
    if code == 200 and body[:3] in (b'\xff\xd8\xff', b'\x89PN') and len(body) > 1000:
        return body
    return None


# ---------------------------------------------------------------- Zusammenfuehren
def merge(primary, extra):
    """Leere Felder von primary aus extra fuellen."""
    out = dict(primary)
    for k, v in (extra or {}).items():
        if k == '_people':
            if not out.get('_people'):
                out['_people'] = v
            continue
        if out.get(k) in (None, '', []) and v not in (None, '', []):
            out[k] = v
    return out


def lookup_isbn(isbn, with_description=True):
    """Alle Angaben zu einer ISBN: DNB zuerst (vollstaendiger bei deutschen Buechern), dann Open Library ergaenzt
    (Titelbild, Beschreibung). Gibt (daten oder None, Fehler oder None)."""
    i = B.norm_isbn(isbn)
    if not i:
        return None, 'Das ist keine gültige ISBN.'
    dnb, err1 = dnb_isbn(i)
    d = None
    if dnb:
        d = next((x for x in dnb if i in x.get('_isbns', [])), dnb[0])
        d['isbn'] = i
    ol, err2 = ol_isbn(i)
    if d and ol:
        d = merge(d, ol)
    elif ol:
        d = ol
    if not d:
        return None, (err1 if err1 and err2 else None)
    if with_description and not d.get('description'):
        d['description'], d['description_src'] = describe(d)
    return d, None


def dnb_blurb(url):
    """Inhaltstext (Klappentext des Verlags), den die DNB zu vielen neueren Buechern bereitstellt."""
    if not url or not url.startswith('https://') or not ('dnb.de/' in url or 'd-nb.info/' in url):
        return None
    code, body, ctype = _get('dnb', url)
    if code != 200 or not body or 'pdf' in (ctype or ''):
        return None
    t = body.decode('utf-8', 'replace')
    t = re.sub(r'(?is)<(script|style|head)\b.*?</\1>', ' ', t)
    t = re.sub(r'(?i)<br\s*/?>|</p>', '\n', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    t = '\n'.join(re.sub(r'[ \t\xa0]+', ' ', x).strip() for x in t.splitlines())
    t = re.sub(r'\n{2,}', '\n', t).strip()
    return t[:4000] if len(t) > 40 else None


def describe(d):
    """Beschreibung zu einem Buch: Verlagstext ueber die DNB (deutsch) und/oder Open Library (oft englisch).
    Bei deutscher Datensprache zuerst die DNB. Gibt (text, quelle) mit quelle 'dnb' oder 'openlibrary'."""
    order = [('dnb', lambda: dnb_blurb(d.get('blurb_url'))), ('openlibrary', lambda: ol_description(d.get('ol_key')))]
    if not T.language().startswith('de'):
        order.reverse()
    for src, fn in order:
        text = fn()
        if text:
            return text, src
    return None, None


def ol_work_of(ol_key):
    """Werk ('/works/OL…W') zu einer Ausgabe ('OL…M')."""
    if not ol_key:
        return None
    ed, _ = _json('ol', f'{OL}/books/{ol_key}.json')
    return next((w.get('key') for w in (ed or {}).get('works') or [] if w.get('key')), None)


def ol_rating(work):
    """Durchschnitt der Bewertungen bei Open Library (1–5 Sterne) und Zahl der Stimmen, oder (None, 0)."""
    if not work or not re.fullmatch(r'/works/OL\d+W', work):
        return None, 0
    d, _ = _json('ol', f'{OL}{work}/ratings.json')
    s = (d or {}).get('summary') or {}
    if not s.get('count') or not s.get('average'):
        return None, 0
    return round(float(s['average']), 2), int(s['count'])


# ---------------------------------------------------------------- Wikipedia
BOOK_WORDS = re.compile(r'\b(roman|romans|romane|buch|kinderbuch|jugendbuch|sachbuch|erzählung|novelle|krimi|thriller|biografie|'
                        r'autobiografie|gedichtband|kurzgeschichte|novel|novella|book|memoir|short story|livre|récit|nouvelle|'
                        r'novela|libro|relato|cuento)\b', re.I)
ARTICLES = {'der', 'die', 'das', 'ein', 'eine', 'the', 'a', 'an', 'le', 'la', 'les', 'l', 'un', 'une', 'el', 'los', 'las', 'una'}


def _words(s):
    return [w for w in re.findall(r'\w+', (s or '').lower()) if w not in ARTICLES]


def _wiki_json(lang, path, params=None):
    code, body, _ = _get('wiki', f'https://{lang}.wikipedia.org{path}', params)
    if code != 200:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def _title_fits(page_title, titles):
    """Passt der Artikelname (ohne Klammerzusatz) zum Buchtitel? Alle Woerter des Artikels muessen im Titel vorkommen."""
    paren = (re.search(r'\(([^)]*)\)\s*$', page_title) or [None, ''])[1].lower()
    if re.search(r'film|serie|series|tv|oper|opera|album|lied|song|spiel|game|begriffskl|disambig|homonymie|desambig', paren):
        return 0
    base = _words(re.sub(r'\s*\(.*?\)\s*$', '', page_title))
    if not base:
        return 0
    bonus = 1 if BOOK_WORDS.search(paren) else 0
    best = 0
    for t in titles:
        tw = _words(t)
        if tw and all(w in tw for w in base):
            best = max(best, (2 if len(base) == len(tw) else 1) + bonus)
    return best


def wiki_find(title, authors='', original_title='', lang='de'):
    """Wikipedia-Artikel zum Buch. Gibt dict(extract, url, title, lang) oder None.
    Treffer nur, wenn der Artikelname zum Titel passt, der Autor im Text vorkommt und es nach einem Buch klingt."""
    first_author = (authors or '').split(';')[0].strip()
    last = first_author.split(' ')[-1] if first_author else ''
    if not title or len(last) < 2:
        return None
    tries = [(lang, title)]
    if original_title and original_title.lower() != title.lower():
        tries.append((lang, original_title))
    if lang != 'en':
        tries.append(('en', original_title or title))
    seen = set()
    for lg, t in tries:
        d = _wiki_json(lg, '/w/api.php', {'action': 'query', 'list': 'search', 'srsearch': f'{t} {last}', 'srlimit': '6',
                                           'srnamespace': '0', 'format': 'json'})
        hits = [h.get('title') for h in ((d or {}).get('query') or {}).get('search') or [] if h.get('title')]
        hits = sorted(((_title_fits(h, [title, original_title]), i, h) for i, h in enumerate(hits)), key=lambda x: (-x[0], x[1]))
        for fit, _, h in hits[:3]:
            if not fit or (lg, h) in seen:
                continue
            seen.add((lg, h))
            s = _wiki_json(lg, '/api/rest_v1/page/summary/' + quote(h.replace(' ', '_'), safe=''))
            if not s or s.get('type') != 'standard':
                continue
            text = (s.get('extract') or '').strip()
            if last.lower() not in text.lower() or not BOOK_WORDS.search(text + ' ' + (s.get('description') or '')):
                continue
            url = ((s.get('content_urls') or {}).get('desktop') or {}).get('page') or f'https://{lg}.wikipedia.org/wiki/{quote(h)}'
            return {'extract': text[:3000], 'url': url, 'title': s.get('title') or h, 'lang': lg}
    return None


def search(title='', author='', q='', limit=20):
    """Kandidaten fuer eine Suche; bei deutscher Datensprache DNB zuerst, sonst Open Library zuerst."""
    if q and not (title or author):
        title = q
    order = [('dnb', dnb_search), ('ol', ol_search)] if T.language().startswith('de') else [('ol', ol_search), ('dnb', dnb_search)]
    out, errs, seen = [], [], set()
    for name, fn in order:
        res, err = fn(title=title, author=author, limit=limit)
        if err:
            errs.append(err)
        for r in res or []:
            key = r.get('isbn') or (B.sort_key(r.get('title')) + '|' + B.sort_key(r.get('authors') or ''))
            if key in seen:
                continue
            seen.add(key)
            r['cover_url'] = cover_url(r.get('_cover_id'), 'S')
            out.append(r)
    return out[:40], (errs[0] if errs and not out else None)
