"""Filmdaten von TMDB (themoviedb.org) und Barcode-Abfrage fuer DVD/Blu-ray.

TMDB: kostenloser API-Schluessel fuer nicht kommerzielle Nutzung, Quellenhinweis Pflicht
("This product uses the TMDB API but is not endorsed or certified by TMDB.").
Einstellungen (.env): TMDB_API_KEY (v3-Schluessel oder v4-Lesetoken), TMDB_LANGUAGE (Standard de-DE),
BARCODE_LOOKUP (1 = Barcode bei UPCitemdb nachschlagen, 0 = aus)."""
import json, logging, os, re, threading, time
from pathlib import Path
import requests

API = 'https://api.themoviedb.org/3'
IMG = 'https://image.tmdb.org/t/p/'
def ua():
    return os.getenv('MB_USER_AGENT', 'MediaDB/1.1 (contact@example.invalid)')
_lock = threading.Lock()
_last = [0.0]
MIN_GAP = 0.12  # TMDB erlaubt deutlich mehr; wir bleiben freundlich


def api_key():
    return os.getenv('TMDB_API_KEY', '').strip()


def language():
    return os.getenv('TMDB_LANGUAGE', 'de-DE').strip() or 'de-DE'


def region():
    lang = language()
    return lang.split('-')[1].upper() if '-' in lang else 'DE'


def configured():
    return bool(api_key())


def _http_get(url, params=None, headers=None, timeout=15):
    """Einzige Stelle mit Netzwerkzugriff (Tests ersetzen diese Funktion)."""
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    return r.status_code, (r.json() if 'json' in r.headers.get('Content-Type', '') else None), r.content, r.headers.get('Content-Type', '')


def tmdb_get(path, **params):
    key = api_key()
    if not key:
        return None, 'Kein TMDB-Schlüssel eingetragen (siehe Einstellungen).'
    headers = {'User-Agent': ua(), 'Accept': 'application/json'}
    if key.startswith('eyJ'):  # v4-Lesetoken
        headers['Authorization'] = 'Bearer ' + key
    else:
        params['api_key'] = key
    params.setdefault('language', language())
    params = {k: v for k, v in params.items() if v is not None}
    with _lock:
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    try:
        code, data, _, _ = _http_get(API + path, params=params, headers=headers)
    except Exception as e:
        return None, f'TMDB nicht erreichbar ({e.__class__.__name__}).'
    if code == 401:
        return None, 'TMDB lehnt den Schlüssel ab. Bitte TMDB_API_KEY prüfen.'
    if code == 429:
        time.sleep(2)
        return tmdb_get(path, **params)
    if code != 200 or data is None:
        return None, f'TMDB antwortet mit Fehler {code}.'
    return data, None


# ---------------------------------------------------------------- Suche
def search(query, year=None):
    """Kandidaten fuer eine Titelsuche (beste zuerst)."""
    q = (query or '').strip()
    if not q:
        return [], None
    params = {'query': q, 'include_adult': 'false'}
    if year:
        params['year'] = int(year)
    d, err = tmdb_get('/search/movie', **params)
    if err:
        return [], err
    res = d.get('results') or []
    if year and not res:  # Jahr passt oft nicht genau (Kinostart vs. Veroeffentlichung)
        d, err = tmdb_get('/search/movie', query=q, include_adult='false')
        res = (d or {}).get('results') or []
    return [cand(r) for r in res[:12]], None


def cand(r):
    rd = r.get('release_date') or ''
    return {'tmdb_id': r.get('id'), 'title': r.get('title') or r.get('original_title') or '', 'original_title': r.get('original_title') or '',
            'year': int(rd[:4]) if rd[:4].isdigit() else None, 'overview': (r.get('overview') or '')[:280],
            'poster_url': (IMG + 'w154' + r['poster_path']) if r.get('poster_path') else '', 'popularity': r.get('popularity') or 0}


def find_imdb(imdb_id):
    d, err = tmdb_get(f'/find/{imdb_id}', external_source='imdb_id')
    if err or not d:
        return None
    res = d.get('movie_results') or []
    return res[0].get('id') if res else None


def details(tmdb_id):
    """Alle Angaben zu einem Film als Feldwerte fuer films_db (ohne Bilder)."""
    d, err = tmdb_get(f'/movie/{int(tmdb_id)}', append_to_response='credits,release_dates,videos,keywords',
                      include_video_language=f'{language().split("-")[0]},en,null')
    if err:
        return None, err
    if not (d.get('overview') or '').strip():  # keine Beschreibung in der Wunschsprache: englische nehmen
        en, _ = tmdb_get(f'/movie/{int(tmdb_id)}', language='en-US')
        if en and en.get('overview'):
            d['overview'] = en['overview']
            d['_overview_lang'] = 'en'
    return parse_details(d), None


def parse_details(d):
    rd = d.get('release_date') or ''
    crew = (d.get('credits') or {}).get('crew') or []
    cast = (d.get('credits') or {}).get('cast') or []
    directors = list(dict.fromkeys(p['name'] for p in crew if p.get('job') == 'Director' and p.get('name')))
    writers = list(dict.fromkeys(p['name'] for p in crew if p.get('department') == 'Writing' and p.get('name')))[:5]
    cert = ''
    for country in (region(), 'DE', 'US'):
        for rr in (d.get('release_dates') or {}).get('results') or []:
            if rr.get('iso_3166_1') == country:
                cs = [x.get('certification') for x in rr.get('release_dates') or [] if (x.get('certification') or '').strip()]
                if cs:
                    cert = ('FSK ' + cs[0]) if country == 'DE' and cs[0].isdigit() else cs[0]
                    break
        if cert:
            break
    trailer = ''
    vids = [v for v in (d.get('videos') or {}).get('results') or [] if v.get('site') == 'YouTube' and v.get('key')]
    vids.sort(key=lambda v: (v.get('type') != 'Trailer', v.get('iso_639_1') != language().split('-')[0], not v.get('official')))
    if vids:
        trailer = 'https://www.youtube.com/watch?v=' + vids[0]['key']
    coll = d.get('belongs_to_collection') or {}
    kw = (d.get('keywords') or {}).get('keywords') or []
    return {
        'tmdb_id': d.get('id'), 'imdb_id': d.get('imdb_id') or None, 'title': d.get('title') or d.get('original_title') or '',
        'original_title': d.get('original_title') or None, 'year': int(rd[:4]) if rd[:4].isdigit() else None,
        'release_date': rd or None, 'runtime': d.get('runtime') or None, 'overview': d.get('overview') or None,
        'tagline': d.get('tagline') or None, 'genres': ', '.join(g['name'] for g in d.get('genres') or [] if g.get('name')) or None,
        'directors': ', '.join(directors) or None, 'writers': ', '.join(writers) or None,
        'cast_json': json.dumps([{'name': p.get('name'), 'character': p.get('character') or ''} for p in cast[:20] if p.get('name')], ensure_ascii=False),
        'countries': ', '.join(c.get('iso_3166_1', '') for c in d.get('production_countries') or []) or None,
        'original_language': d.get('original_language') or None,
        'studios': ', '.join(c['name'] for c in (d.get('production_companies') or [])[:4] if c.get('name')) or None,
        'certification': cert or None, 'collection_id': coll.get('id'), 'collection_name': coll.get('name'),
        'trailer_url': trailer or None, 'tmdb_rating': d.get('vote_average'), 'tmdb_votes': d.get('vote_count'),
        'keywords': ', '.join(k['name'] for k in kw[:15] if k.get('name')) or None, 'source': 'tmdb',
        '_poster_path': d.get('poster_path'), '_backdrop_path': d.get('backdrop_path'),
        '_people': people_from_credits(d.get('credits') or {}),
    }


def people_from_credits(credits):
    """Besetzung (die ersten 20), Regie und Drehbuch mit TMDB-Personennummer."""
    out = []
    for i, p in enumerate((credits.get('cast') or [])[:20]):
        if p.get('id') and p.get('name'):
            out.append({'id': p['id'], 'name': p['name'], 'profile_path': p.get('profile_path'), 'role': 'cast',
                        'character': p.get('character') or '', 'ord': p.get('order', i)})
    seen = set()
    for p in credits.get('crew') or []:
        role = 'director' if p.get('job') == 'Director' else 'writer' if p.get('department') == 'Writing' else None
        if role and p.get('id') and (p['id'], role) not in seen and (role == 'director' or len([x for x in out if x['role'] == 'writer']) < 5):
            seen.add((p['id'], role))
            out.append({'id': p['id'], 'name': p.get('name') or '?', 'profile_path': p.get('profile_path'), 'role': role, 'ord': len(out)})
    return out


def credits(tmdb_id):
    """Nur die Personen eines Films (zum Nachladen fuer schon erfasste Filme)."""
    d, err = tmdb_get(f'/movie/{int(tmdb_id)}/credits')
    return (people_from_credits(d), None) if d else (None, err)


_SKIP_TV_GENRES = {10763, 10767}  # Nachrichten, Talkshows


def person(pid):
    """Angaben zu einer Person samt Filmografie (Filme und Serien, als Darsteller oder Regie)."""
    d, err = tmdb_get(f'/person/{int(pid)}', append_to_response='combined_credits,external_ids')
    if err:
        return None, err
    bio = (d.get('biography') or '').strip()
    if not bio:
        en, _ = tmdb_get(f'/person/{int(pid)}', language='en-US')
        bio = ((en or {}).get('biography') or '').strip()
    items = {}
    cc = d.get('combined_credits') or {}
    for role, lst in (('cast', cc.get('cast') or []), ('director', [x for x in cc.get('crew') or [] if x.get('job') == 'Director'])):
        for x in lst:
            mt = x.get('media_type')
            if mt not in ('movie', 'tv') or not x.get('id'):
                continue
            ch = (x.get('character') or '').strip()
            if mt == 'tv' and (set(x.get('genre_ids') or []) & _SKIP_TV_GENRES or re.search(r'\b(self|himself|herself|selbst)\b', ch, re.I)):
                continue
            if mt == 'movie' and re.fullmatch(r'(self|himself|herself|selbst)( .*)?', ch, re.I):
                continue
            date_ = x.get('release_date') or x.get('first_air_date') or ''
            key = (mt, x['id'])
            e = items.setdefault(key, {'media': mt, 'tmdb_id': x['id'], 'title': x.get('title') or x.get('name') or '',
                                      'original_title': x.get('original_title') or x.get('original_name') or '',
                                      'year': int(date_[:4]) if date_[:4].isdigit() else None, 'poster_path': x.get('poster_path'),
                                      'popularity': x.get('popularity') or 0, 'roles': [], 'character': ''})
            if role not in e['roles']:
                e['roles'].append(role)
            if role == 'cast' and ch and not e['character']:
                e['character'] = ch
    return {'name': d.get('name') or '?', 'profile_path': d.get('profile_path'), 'biography': bio or None,
            'birthday': d.get('birthday'), 'deathday': d.get('deathday'), 'place': d.get('place_of_birth'),
            'department': d.get('known_for_department'), 'imdb_id': (d.get('external_ids') or {}).get('imdb_id') or d.get('imdb_id'),
            'credits': sorted(items.values(), key=lambda e: (e['year'] is None, -(e['year'] or 0), -e['popularity']))}, None


def fetch_image(tmdb_path, size):
    """Bild von TMDB als Bytes (oder None)."""
    if not tmdb_path:
        return None
    for attempt in range(2):  # ein zweiter Versuch bei Zeitueberschreitung
        try:
            code, _, content, ctype = _http_get(IMG + size + tmdb_path, headers={'User-Agent': ua()}, timeout=20)
            if code == 200 and ctype.startswith('image/') and len(content) > 500:
                return content
            return None
        except Exception as e:
            logging.warning('TMDB-Bild nicht geladen (%s): %s', attempt + 1, e)
    return None


def download_image(tmdb_path, size, target):
    """Bild von TMDB laden und speichern. Gibt True zurueck, wenn es geklappt hat."""
    content = fetch_image(tmdb_path, size)
    if content:
        Path(target).write_bytes(content)
        return True
    return False


def images(tmdb_id):
    """Alle Poster und Hintergrundbilder eines Films: Wunschsprache zuerst, dann ohne Text, dann Englisch, dann der Rest."""
    lang = language().split('-')[0]
    d, err = tmdb_get(f'/movie/{int(tmdb_id)}/images', language=None, include_image_language=f'{lang},null,en')
    if err or not d:
        d2, err2 = tmdb_get(f'/movie/{int(tmdb_id)}/images', language=None)
        if not d2:
            return {'posters': [], 'backdrops': []}, err or err2
        d = d2
    rank = {lang: 0, None: 1, 'en': 2}
    def order(lst):
        return sorted(lst or [], key=lambda x: (rank.get(x.get('iso_639_1'), 3), -(x.get('vote_average') or 0), -(x.get('vote_count') or 0)))
    return {'posters': [{'path': x['file_path'], 'lang': x.get('iso_639_1') or '', 'w': x.get('width'), 'h': x.get('height')} for x in order(d.get('posters')) if x.get('file_path')],
            'backdrops': [{'path': x['file_path'], 'lang': x.get('iso_639_1') or ''} for x in order(d.get('backdrops')) if x.get('file_path')]}, None


# ---------------------------------------------------------------- Barcode
def barcode_lookup_enabled():
    return os.getenv('BARCODE_LOOKUP', '1').strip().lower() not in ('0', 'false', 'no', 'nein', 'off')


def norm_barcode(b):
    return re.sub(r'\D', '', b or '')


def upc_lookup(barcode):
    """Produktname zu einem Barcode bei UPCitemdb (kostenlose Testschnittstelle, etwa 100 Abfragen pro Tag).
    Gibt (titel, rohdaten, fehler) zurueck."""
    bc = norm_barcode(barcode)
    if not bc or not barcode_lookup_enabled():
        return '', None, None
    try:
        code, data, _, _ = _http_get('https://api.upcitemdb.com/prod/trial/lookup', params={'upc': bc},
                                     headers={'User-Agent': ua(), 'Accept': 'application/json'})
    except Exception as e:
        return '', None, f'Barcode-Dienst nicht erreichbar ({e.__class__.__name__}).'
    if code == 429:
        return '', None, 'Tageskontingent des Barcode-Dienstes erreicht. Bitte nach Titel suchen.'
    if code != 200 or not data:
        return '', None, None
    items = data.get('items') or []
    return (items[0].get('title') or '').strip() if items else '', data, None


_FORMAT_WORDS = (r'blu-?ray|bluray|blu ray|dvd|4k|uhd|ultra hd|hd-?dvd|steelbook|limited|edition|special|collector\'?s?|'
                 r'director\'?s cut|extended|uncut|ungeschnitten|remastered|digital|import|region|widescreen|fullscreen|'
                 r'2[- ]disc|3[- ]disc|\d+[- ]?discs?|box ?set|mediabook|digibook|fsk ?\d+|neuauflage|version|exklusiv|exclusive|'
                 r'pal|ntsc|secam|region ?\d|rc ?\d|code ?\d|import|deutsche? (?:fassung|version)|german|deutsch|o-?ton|ov|omu')
# Haendlerangaben zum Zustand; nur als ganzer Teil weg, sonst wuerde aus 'New York' 'York'
_SHOP_WORDS = r'condition|used|new|brand new|very good|good|acceptable|like new|neu|neuwertig|gebraucht|wie neu|sehr gut|gut|ovp|zustand'


def clean_product_title(t):
    """'Der Pate [Blu-ray] (Steelbook) - Limited Edition' -> 'Der Pate'. Klammern fallen weg, Teile zwischen ' - ',
    die nur aus Formatangaben bestehen (Edition, Pal, 2 DVDs ...), ebenso."""
    s = re.sub(r'[\[(][^\])]*[\])]', ' ', str(t or ''))
    keep = []
    for seg in re.split(r'\s+[-–|/]\s+', s):
        c = re.sub(r'\b(' + _FORMAT_WORDS + r')\b', ' ', seg, flags=re.I)
        c = re.sub(r'\s+', ' ', c).strip(' -–|:,/.+&')
        if re.search(r'\w', c) and not re.fullmatch(r'(?:' + _SHOP_WORDS + r')(?:\s*[,:]?\s*(?:' + _SHOP_WORDS + r'))*', c, flags=re.I):
            keep.append(c)
    return ' - '.join(keep)


def guess_kind(product_title, default='dvd'):
    t = (product_title or '').lower()
    if re.search(r'4k|uhd|ultra hd', t):
        return 'uhd'
    if re.search(r'blu-?ray|blu ray', t):
        return 'bluray'
    if 'dvd' in t:
        return 'dvd'
    return default


def query_variants(product_title):
    """Suchbegriffe aus einem Produktnamen, bester zuerst. Produktnamen aus Barcode-Datenbanken haben oft Zusaetze wie
    'David Tattersall - Star Wars I: Phantom Menace (2 Dvd) - Pal' (Person vorne, Norm hinten)."""
    base = clean_product_title(product_title)
    out = []

    def add(q):
        q = re.sub(r'\s+', ' ', q or '').strip(' -–:,/')
        if len(q) >= 2 and q.lower() not in [x.lower() for x in out]:
            out.append(q)
    add(base)
    parts = [p for p in re.split(r'\s+[-–|/]\s+', base) if p.strip()]
    if len(parts) > 1:
        for p in sorted(parts, key=len, reverse=True):  # einzelne Teile, laengster zuerst
            add(p)
        add(' '.join(parts[1:]))
    for p in parts:  # 'Chocolat By Lasse Hallström' -> 'Chocolat' (Regie hinten); 'Stand by Me' findet TMDB vorher
        m = re.match(r'(.+?)\s+(?:by|von)\s+\S', p, flags=re.I)
        if m:
            add(m.group(1))
    for q in list(out):
        if ':' in q:  # 'Star Wars I: Phantom Menace' -> 'Phantom Menace'
            add(q.split(':', 1)[1])
    return out[:6]


# ================================================================ Serien (TV)
def tv_search(query, year=None):
    q = (query or '').strip()
    if not q:
        return [], None
    params = {'query': q, 'include_adult': 'false'}
    if year:
        params['first_air_date_year'] = int(year)
    d, err = tmdb_get('/search/tv', **params)
    if err:
        return [], err
    res = d.get('results') or []
    if year and not res:
        d, err = tmdb_get('/search/tv', query=q, include_adult='false')
        res = (d or {}).get('results') or []
    out = []
    for r in res[:12]:
        fd = r.get('first_air_date') or ''
        out.append({'tmdb_id': r.get('id'), 'title': r.get('name') or r.get('original_name') or '', 'original_title': r.get('original_name') or '',
                    'year': int(fd[:4]) if fd[:4].isdigit() else None, 'overview': (r.get('overview') or '')[:280],
                    'poster_url': (IMG + 'w154' + r['poster_path']) if r.get('poster_path') else '', 'popularity': r.get('popularity') or 0})
    return out, None


def tv_find(external_id, source):
    """TMDB-Nummer einer Serie ueber IMDb- oder TVDB-Nummer (source: 'imdb_id' oder 'tvdb_id')."""
    d, err = tmdb_get(f'/find/{external_id}', external_source=source)
    res = (d or {}).get('tv_results') or []
    return res[0].get('id') if res else None


def tv_details(tmdb_id):
    d, err = tmdb_get(f'/tv/{int(tmdb_id)}', append_to_response='aggregate_credits,content_ratings,videos,keywords,external_ids,watch/providers',
                      include_video_language=f'{language().split("-")[0]},en,null')
    if err:
        return None, err
    if not (d.get('overview') or '').strip():
        en, _ = tmdb_get(f'/tv/{int(tmdb_id)}', language='en-US')
        if en and en.get('overview'):
            d['overview'] = en['overview']
    fd = d.get('first_air_date') or ''
    cert = ''
    for country in (region(), 'DE', 'US'):
        for rr in (d.get('content_ratings') or {}).get('results') or []:
            if rr.get('iso_3166_1') == country and (rr.get('rating') or '').strip():
                v = rr['rating'].strip()
                cert = ('FSK ' + v) if country == 'DE' and v.isdigit() else v
                break
        if cert:
            break
    vids = [v for v in (d.get('videos') or {}).get('results') or [] if v.get('site') == 'YouTube' and v.get('key')]
    vids.sort(key=lambda v: (v.get('type') != 'Trailer', v.get('iso_639_1') != language().split('-')[0]))
    ext = d.get('external_ids') or {}
    kw = (d.get('keywords') or {}).get('results') or []
    people = []
    for i, p in enumerate(((d.get('aggregate_credits') or {}).get('cast') or [])[:25]):
        roles = p.get('roles') or []
        ch = ', '.join(dict.fromkeys(r.get('character') for r in roles if r.get('character')))[:120]
        people.append({'id': p.get('id'), 'name': p.get('name'), 'profile_path': p.get('profile_path'), 'role': 'cast',
                       'character': ch, 'episodes': p.get('total_episode_count'), 'ord': p.get('order', i)})
    for c in d.get('created_by') or []:
        people.append({'id': c.get('id'), 'name': c.get('name'), 'profile_path': c.get('profile_path'), 'role': 'creator'})
    seasons = [{'season': s.get('season_number'), 'name': s.get('name'), 'overview': s.get('overview'), 'air_date': s.get('air_date'),
                'episode_count': s.get('episode_count'), 'poster_path': s.get('poster_path')}
               for s in d.get('seasons') or [] if s.get('season_number') is not None]
    runtimes = d.get('episode_run_time') or []
    return {
        'tmdb_id': d.get('id'), 'imdb_id': ext.get('imdb_id') or None, 'tvdb_id': ext.get('tvdb_id') or None,
        'title': d.get('name') or d.get('original_name') or '', 'original_title': d.get('original_name') or None,
        'year': int(fd[:4]) if fd[:4].isdigit() else None, 'first_air_date': fd or None, 'last_air_date': d.get('last_air_date') or None,
        'status': d.get('status') or None, 'networks': ', '.join(n['name'] for n in d.get('networks') or [] if n.get('name')) or None,
        'genres': ', '.join(g['name'] for g in d.get('genres') or [] if g.get('name')) or None,
        'creators': ', '.join(c['name'] for c in d.get('created_by') or [] if c.get('name')) or None,
        'overview': d.get('overview') or None, 'tagline': d.get('tagline') or None,
        'countries': ', '.join(d.get('origin_country') or []) or None, 'original_language': d.get('original_language') or None,
        'certification': cert or None, 'episode_runtime': runtimes[0] if runtimes else None,
        'number_of_seasons': d.get('number_of_seasons'), 'number_of_episodes': d.get('number_of_episodes'),
        'trailer_url': ('https://www.youtube.com/watch?v=' + vids[0]['key']) if vids else None,
        'tmdb_rating': d.get('vote_average'), 'tmdb_votes': d.get('vote_count'),
        'keywords': ', '.join(k['name'] for k in kw[:15] if k.get('name')) or None, 'source': 'tmdb',
        '_poster_path': d.get('poster_path'), '_backdrop_path': d.get('backdrop_path'), '_people': people, '_seasons': seasons,
        **providers_of(d), **next_of(d),
    }, None


def tv_season(tmdb_id, season):
    """Folgen einer Staffel: [{'season','episode','name','overview','air_date','runtime'}]."""
    d, err = tmdb_get(f'/tv/{int(tmdb_id)}/season/{int(season)}')
    if err or not d:
        return None, err
    eps = []
    for e in d.get('episodes') or []:
        if e.get('episode_number') is None:
            continue
        eps.append({'season': int(season), 'episode': e['episode_number'], 'name': e.get('name') or None,
                    'overview': e.get('overview') or None, 'air_date': e.get('air_date') or None, 'runtime': e.get('runtime')})
    # fehlende deutsche Folgentitel ("Episode 3", leer): englische nachladen
    if any(not x['name'] or re.fullmatch(r'(Folge|Episode|Épisode|Episodio|Capítulo|Aflevering|Afl\.)\s*\d+', x['name'] or '') for x in eps):
        en, _ = tmdb_get(f'/tv/{int(tmdb_id)}/season/{int(season)}', language='en-US')
        en_names = {e.get('episode_number'): e.get('name') for e in (en or {}).get('episodes') or []}
        for x in eps:
            if (not x['name'] or re.fullmatch(r'(Folge|Episode|Épisode|Episodio|Capítulo|Aflevering|Afl\.)\s*\d+', x['name'])) and en_names.get(x['episode']):
                x['name'] = en_names[x['episode']]
    return eps, None


def tv_guide(tmdb_id, seasons):
    """Alle Folgen aller Staffeln."""
    out = []
    for s in seasons:
        eps, err = tv_season(tmdb_id, s['season'])
        if eps:
            out += eps
    return out


def tv_images(tmdb_id):
    lang = language().split('-')[0]
    d, err = tmdb_get(f'/tv/{int(tmdb_id)}/images', language=None, include_image_language=f'{lang},null,en')
    if err or not d:
        return {'posters': [], 'backdrops': []}, err
    rank = {lang: 0, None: 1, 'en': 2}
    def order(lst):
        return sorted(lst or [], key=lambda x: (rank.get(x.get('iso_639_1'), 3), -(x.get('vote_average') or 0)))
    return {'posters': [{'path': x['file_path'], 'lang': x.get('iso_639_1') or ''} for x in order(d.get('posters')) if x.get('file_path')],
            'backdrops': [{'path': x['file_path'], 'lang': x.get('iso_639_1') or ''} for x in order(d.get('backdrops')) if x.get('file_path')]}, None


_SEASON_WORDS = r'staffel|season|saison|temporada|series'


def seasons_from_product(title):
    """'Breaking Bad - Staffel 1-3 [DVD]' -> '1-3'; 'Die komplette Serie' -> 'komplett'; sonst ''."""
    t = (title or '').lower()
    if re.search(r'komplett\w*\s+(serie|box)|complete\s+(series|collection|box)|gesamtbox|die komplette', t):
        return 'komplett'
    m = re.search(r'(?:' + _SEASON_WORDS + r')\s*(\d+)\s*(?:-|–|bis|to|&|\+|und|and)\s*(\d+)', t)
    if m:
        return f'{int(m.group(1))}-{int(m.group(2))}'
    m = re.findall(r'(?:' + _SEASON_WORDS + r')\s*(\d+)', t) or re.findall(r'(\d+)\.\s*staffel', t)
    if m:
        return ', '.join(str(int(x)) for x in dict.fromkeys(m))
    return ''


def tv_query_variants(product_title):
    """Wie query_variants, zusaetzlich ohne Staffelangaben."""
    base = re.sub(r'(?:die\s+)?(?:komplett\w*|complete)\s+(?:serie|series|box|collection)|gesamtbox', ' ', product_title or '', flags=re.I)
    base = re.sub(r'(?:' + _SEASON_WORDS + r')\s*\d+(?:\s*(?:-|–|bis|to|&|\+|und|and)\s*\d+)?|\d+\.\s*staffel', ' ', base, flags=re.I)
    return query_variants(base)


# ---------------------------------------------------------------- Streaming und Termine
def providers_of(d):
    """Streamingdienste fuer das eigene Land aus 'watch/providers' (Daten von JustWatch).
    Gezaehlt werden Abo, kostenlos und mit Werbung; Kauf/Leihe nicht."""
    r = ((d.get('watch/providers') or {}).get('results') or {}).get(region()) or {}
    names = []
    for k in ('flatrate', 'free', 'ads'):
        for p in sorted(r.get(k) or [], key=lambda x: x.get('display_priority') or 99):
            n = (p.get('provider_name') or '').strip()
            if n and n not in names:
                names.append(n)
    buy = sorted({(p.get('provider_name') or '').strip() for k in ('buy', 'rent') for p in r.get(k) or []} - {''} - set(names))
    return {'providers': ', '.join(names) or None, 'providers_buy': ', '.join(buy[:6]) or None,
            'providers_link': r.get('link') or None, 'providers_at': time.strftime('%Y-%m-%d')}


def next_of(d):
    """Naechste Folge laut TMDB (next_episode_to_air)."""
    n = d.get('next_episode_to_air') or {}
    return {'next_air_date': n.get('air_date') or None, 'next_season': n.get('season_number'), 'next_episode': n.get('episode_number')}


def multi_search(query):
    """Filme und Serien in einem Rutsch suchen (fuer die Merkliste)."""
    q = (query or '').strip()
    if not q:
        return [], None
    d, err = tmdb_get('/search/multi', query=q, include_adult='false')
    if err:
        return [], err
    out = []
    for r in (d.get('results') or [])[:20]:
        kind = r.get('media_type')
        if kind not in ('movie', 'tv'):
            continue
        date = r.get('release_date') if kind == 'movie' else r.get('first_air_date')
        out.append({'kind': kind, 'tmdb_id': r.get('id'), 'title': r.get('title') or r.get('name') or '',
                    'original_title': r.get('original_title') or r.get('original_name') or '',
                    'year': int(date[:4]) if (date or '')[:4].isdigit() else None, 'overview': (r.get('overview') or '')[:280],
                    'poster_path': r.get('poster_path'), 'poster_url': (IMG + 'w154' + r['poster_path']) if r.get('poster_path') else ''})
    return out, None


def watch_status(kind, tmdb_id):
    """Aktueller Stand fuer die Merkliste: Termin, Streamingdienst, Status."""
    if kind == 'tv':
        d, err = tmdb_get(f'/tv/{int(tmdb_id)}', append_to_response='watch/providers')
        if err:
            return None, err
        last = d.get('last_episode_to_air') or {}
        out = {'title': d.get('name') or '', 'status': d.get('status'), 'poster_path': d.get('poster_path'),
               'networks': ', '.join(n['name'] for n in d.get('networks') or [] if n.get('name')) or None,
               'last_air_date': last.get('air_date'), 'last_season': last.get('season_number'),
               'number_of_seasons': d.get('number_of_seasons'), **providers_of(d), **next_of(d)}
        fd = d.get('first_air_date') or ''
        out['year'] = int(fd[:4]) if fd[:4].isdigit() else None
        return out, None
    d, err = tmdb_get(f'/movie/{int(tmdb_id)}', append_to_response='release_dates,watch/providers')
    if err:
        return None, err
    cinema = digital = None
    for rr in (d.get('release_dates') or {}).get('results') or []:
        if rr.get('iso_3166_1') != region():
            continue
        for x in rr.get('release_dates') or []:
            day = (x.get('release_date') or '')[:10] or None
            if x.get('type') in (2, 3) and day and (not cinema or day < cinema):
                cinema = day
            if x.get('type') in (4, 6) and day and (not digital or day < digital):
                digital = day
    rd = d.get('release_date') or ''
    return {'title': d.get('title') or '', 'status': d.get('status'), 'poster_path': d.get('poster_path'),
            'year': int(rd[:4]) if rd[:4].isdigit() else None, 'release_date': cinema or rd or None, 'digital_date': digital,
            **providers_of(d)}, None
