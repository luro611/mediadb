"""Filmdateien einlesen: Videodateien finden, Film erkennen (Jellyfin/Kodi-.nfo, Dateiname), Technikdaten per ffprobe.

Erkennung in dieser Reihenfolge:
  1. .nfo neben der Datei (Dateiname.nfo oder movie.nfo) mit TMDB- oder IMDb-Nummer  -> sicher
  2. Nummer im Namen: "Film (2001) [tmdbid-123]" oder "{tmdb-123}" bzw. "[imdbid-tt0123456]"  -> sicher
  3. Titel und Jahr aus Ordner- oder Dateiname ("Titel (Jahr)", "Titel.Jahr.1080p.BluRay")  -> TMDB-Suche
Ordner mit VIDEO_TS (DVD) oder BDMV (Blu-ray) zaehlen als ein Film. Trailer, Samples und Extras werden uebersprungen."""
import json, logging, os, re, shutil, subprocess, threading, xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from . import films_db as F
from . import fs
from . import films_tmdb as T

VIDEO_EXT = {'.mkv', '.mp4', '.m4v', '.avi', '.mov', '.wmv', '.ts', '.m2ts', '.mts', '.webm', '.mpg', '.mpeg', '.iso', '.divx', '.ogm', '.flv'}
SKIP_DIRS = {'extras', 'extra', 'featurettes', 'behind the scenes', 'deleted scenes', 'interviews', 'scenes', 'shorts', 'trailers',
             'trailer', 'samples', 'sample', 'other', 'specials', '@eadir', '.ds_store', '#recycle', '$recycle.bin'}
SKIP_FILE = re.compile(r'(^|[ ._-])(sample|trailer|teaser|featurette|behindthescenes|deleted|interview|extra)s?([ ._-]|$)', re.I)
JUNK = re.compile(r'\b(2160p|1080p|1080i|720p|576p|480p|4k|uhd|hdr10?\+?|hdr|dv|dovi|sdr|blu-?ray|bdrip|brrip|bdremux|remux|web-?dl|webrip|web|'
                  r'hdtv|dvdrip|dvd|dvd9|dvd5|x264|x265|h\.?264|h\.?265|hevc|avc|xvid|divx|aac|ac3|eac3|dts(-?hd)?|truehd|atmos|ddp?5\.1|'
                  r'5\.1|7\.1|2\.0|german|deutsch|english|multi|dl|dual|ml|subbed|untouched|proper|repack|internal|complete|retail)\b.*$', re.I)
# Dieselben Woerter einzeln, dazu Sprach- und Streamingkennungen; entfernt werden sie nur am Ende eines Namens (strip_junk),
# damit Titel wie 'The English Patient', 'The French Dispatch' oder 'A Very English Scandal' heil bleiben.
JUNK_TOKEN = re.compile(JUNK.pattern.replace(r'\b.*$', '').replace(r'\b(', '(', 1)
                        + r'|french|truefrench|vff|vfq|vfi|vf|vf2|vost|vostfr|subfrench|fr|'
                        r'spanish|castellano|espanol|español|latino|esp|spa|cast|vose|'
                        r'italian|ita|eng|ger|dubbed|dub|subs?|hdrip|webhd|dl|bd|'
                        r'amzn|amazon|amazonhd|amazonuhd|amazonprime|primevideo|netflix|nflx|nf|dsnp|disneyplus|atvp|appletv|hmax|hbo|'
                        r'paramountplus|pmtp|joyn|rtlplus|magentatv|wowtv|skyhd|ardmediathek|zdfmediathek|mediathek|hd|fhd|uhdtv', re.I)


def strip_junk(s, extra=None):
    """Szene-Zusaetze nur am Ende entfernen ('Matrix German DL 1080p WEB x264-GRP' -> 'Matrix'). Das erste Wort bleibt immer."""
    def junk(t):
        return bool(JUNK_TOKEN.fullmatch(t) or (extra and extra.fullmatch(t)))
    toks = s.split()
    while len(toks) > 1:
        t = toks[-1].strip('-._[]()')
        base = re.sub(r'-[A-Za-z0-9]+$', '', t)  # Gruppenname hinter Bindestrich
        if not t or t.startswith('-') or junk(t) or (base != t and junk(base)) or (re.fullmatch(r'\d{1,2}', t) and junk(toks[-2].strip('-._'))):
            toks.pop()
        else:
            break
    return ' '.join(toks)


CHECK_MIN = 0.86  # ab dieser Aehnlichkeit gilt ein Treffer als sicher

JOB = {'state': 'idle', 'folders': [], 'done': 0, 'total': 0, 'items': [], 'error': '', 'result': None}
_job_lock = threading.Lock()


# ---------------------------------------------------------------- Dateien finden
def collect(folder):
    """Liefert Eintraege {'path','name','folder'}; DVD/Blu-ray-Ordnerstrukturen als ein Eintrag."""
    out = []
    for root, dirs, files in fs.walk(folder):
        up = {d.upper() for d in dirs}
        if 'VIDEO_TS' in up or 'BDMV' in up:
            out.append({'path': root, 'name': os.path.basename(root), 'folder': os.path.dirname(root),
                        'disc': 'bluray' if 'BDMV' in up else 'dvd'})
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith('.'))
        for f in sorted(files):
            stem, ext = os.path.splitext(f)
            if ext.lower() not in VIDEO_EXT or f.startswith('.') or SKIP_FILE.search(stem):
                continue
            out.append({'path': os.path.join(root, f), 'name': stem, 'folder': root, 'disc': ''})
    return out


# ---------------------------------------------------------------- Erkennen
def parse_nfo(path):
    """TMDB-/IMDb-Nummer, Titel und Jahr aus einer Jellyfin-/Kodi-.nfo."""
    try:
        with fs.open(path, 'rb') as fh:
            root = ET.parse(fh).getroot()
    except Exception:
        try:  # manche .nfo enthalten nur eine URL
            txt = fs.read_text(path)
        except Exception:
            return {}
        m = re.search(r'themoviedb\.org/movie/(\d+)', txt)
        i = re.search(r'(tt\d{7,})', txt)
        return {'tmdb': int(m.group(1)) if m else None, 'imdb': i.group(1) if i else None}
    out = {'tmdb': None, 'imdb': None, 'title': None, 'year': None}
    for u in root.iter('uniqueid'):
        t = (u.get('type') or '').lower()
        v = (u.text or '').strip()
        if t == 'tmdb' and v.isdigit():
            out['tmdb'] = int(v)
        elif t == 'imdb' and v.startswith('tt'):
            out['imdb'] = v
    for tag, key in (('tmdbid', 'tmdb'), ('imdbid', 'imdb'), ('id', 'imdb')):
        el = root.find(tag)
        v = (el.text or '').strip() if el is not None and el.text else ''
        if key == 'tmdb' and v.isdigit() and not out['tmdb']:
            out['tmdb'] = int(v)
        if key == 'imdb' and v.startswith('tt') and not out['imdb']:
            out['imdb'] = v
    t = root.find('title')
    y = root.find('year')
    out['title'] = (t.text or '').strip() if t is not None and t.text else None
    out['year'] = int(y.text) if y is not None and (y.text or '').strip().isdigit() else None
    return out


def find_nfo(item):
    if item['disc']:
        cands = [os.path.join(item['path'], 'movie.nfo'), item['path'] + '.nfo']
    else:
        stem = os.path.splitext(item['path'])[0]
        cands = [stem + '.nfo', os.path.join(item['folder'], 'movie.nfo')]
    for c in cands:
        if fs.isfile(c):
            return c
    return None


def parse_name(name):
    """Titel, Jahr und Nummern aus einem Datei- oder Ordnernamen."""
    s = name
    tm = re.search(r'[\[{(]\s*tmdb(?:id)?\s*[-=:]\s*(\d+)\s*[\]})]', s, re.I)
    im = re.search(r'[\[{(]\s*imdb(?:id)?\s*[-=:]\s*(tt\d+)\s*[\]})]', s, re.I) or re.search(r'\b(tt\d{7,})\b', s)
    s = re.sub(r'[\[{]\s*(tmdb|imdb|tvdb)(id)?\s*[-=:][^\]}]*[\]}]', ' ', s, flags=re.I)
    s = re.sub(r'\b(tt\d{7,})\b', ' ', s)
    s = re.sub(r'\s*-\s*(cd|disc|disk|part|pt)\s*\d+$', '', s, flags=re.I)
    if s.count('.') >= 2 and ' ' not in s.strip():
        s = s.replace('.', ' ')
    s = s.replace('_', ' ')
    year = None
    edition = edition_of(s)
    m = re.search(r'^(.*?)\s*[(\[]\s*((?:19|20)\d{2})\s*[)\]]', s)  # Jahr in Klammern hat Vorrang
    if not (m and m.group(1).strip()):
        m = None
        for mm in re.finditer(r'(?:^|[\s.])((?:19|20)\d{2})(?=[\s.)\]]|$)', s):  # sonst das letzte Jahr mit Titel davor
            if s[:mm.start()].strip():
                m = mm
    if m:
        title, year = s[:m.start(1) if m.re.groups == 1 else m.start(2)], int(m.group(m.re.groups))
        title = title.rstrip(' ([.')
    else:
        title = s
    title = re.sub(r'[\[(].*?[\])]', ' ', title)
    title = strip_junk(re.sub(r'\s+', ' ', title).strip())
    title = re.sub(r'\s+', ' ', title).strip(' -._')
    title = re.sub(r'\s*-\s*$', '', EDITION.sub('', title)).strip(' -._')
    return {'title': title, 'year': year, 'tmdb': int(tm.group(1)) if tm else None, 'imdb': im.group(1) if im else None, 'edition': edition}


EDITION = re.compile(r"[\s.\-(\[]*\b(director'?s[ .]?cut|extended(?:[ .]edition|[ .]cut)?|uncut|unrated|final[ .]cut|"
                     r"kinofassung|theatrical(?:[ .]cut)?|special[ .]edition|collector'?s?[ .]edition|limited[ .]edition|remastered|imax(?:[ .]edition)?|ultimate[ .]cut)\b[)\]]?", re.I)


def edition_of(s):
    m = EDITION.search(s or '')
    if not m:
        return ''
    t = m.group(1).replace('.', ' ')
    return {"director's cut": "Director's Cut", 'directors cut': "Director's Cut"}.get(t.lower(), t.title())


def _norm(t):
    t = (t or '').lower()
    t = re.sub(r'[^\w\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def similarity(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def identify(item):
    """Erkennt einen Film. Ergebnis: dict mit status match/unsure/nf und Kandidaten."""
    hint = {}
    nfo = find_nfo(item)
    if nfo:
        hint = parse_nfo(nfo)
    by_file = parse_name(item['name'])
    by_dir = parse_name(os.path.basename(item['folder'])) if not item['disc'] else {}
    tmdb = hint.get('tmdb') or by_file['tmdb'] or (by_dir or {}).get('tmdb')
    imdb = hint.get('imdb') or by_file['imdb'] or (by_dir or {}).get('imdb')
    # Titel: bevorzugt der Name mit Jahr (Ordner "Film (2001)" ist oft sauberer als "film.2001.1080p")
    named = by_file if by_file['year'] or not by_dir else (by_dir if by_dir.get('year') else by_file)
    title = hint.get('title') or named['title'] or by_file['title']
    year = hint.get('year') or named['year'] or by_file['year']
    res = {'title': title, 'year': year, 'source': 'nfo' if nfo and (hint.get('tmdb') or hint.get('imdb')) else 'name',
           'edition': by_file.get('edition') or (by_dir or {}).get('edition') or '',
           'tmdb_id': None, 'cands': [], 'status': 'nf', 'note': ''}
    if not tmdb and imdb:
        tmdb = T.find_imdb(imdb)
    if tmdb:
        res.update(tmdb_id=int(tmdb), status='match', note='TMDB-Nummer aus ' + ('.nfo' if nfo else 'Dateiname'))
        return res
    if not title:
        res['note'] = 'Kein Titel erkennbar'
        return res
    cands, err = T.search(title, year)
    if err:
        res['note'] = err
        return res
    res['cands'] = cands[:6]
    if cands:
        best = max(cands[:5], key=lambda c: (max(similarity(title, c['title']), similarity(title, c['original_title'])),
                                             bool(year and c['year'] and abs(c['year'] - year) <= 1)))
        sim = max(similarity(title, best['title']), similarity(title, best['original_title']))
        year_ok = (not year) or (best['year'] and abs(best['year'] - year) <= 1)
        if sim >= CHECK_MIN and year_ok and (year or len(cands) == 1 or sim >= 0.97):
            res.update(tmdb_id=best['tmdb_id'], status='match')
        else:
            res.update(status='unsure', tmdb_id=best['tmdb_id'], note='Titel nur ähnlich' if sim < CHECK_MIN else 'Bitte Jahr prüfen')
    else:
        res['note'] = 'Bei TMDB nicht gefunden'
    return res


# ---------------------------------------------------------------- Technikdaten
def probe(path):
    """Aufloesung, Codec, HDR, Laufzeit, Tonspuren, Untertitel per ffprobe (wenn vorhanden)."""
    out = {}
    try:
        if fs.isfile(path):
            out['size_bytes'] = fs.getsize(path)
            out['container'] = os.path.splitext(path)[1].lstrip('.').upper()
    except Exception:
        pass
    if not shutil.which('ffprobe') or 'size_bytes' not in out or path.lower().endswith('.iso'):
        return out
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', fs.media_url(path)],
                           capture_output=True, timeout=40)
        d = json.loads(r.stdout or b'{}')
    except Exception as e:
        logging.warning('ffprobe fehlgeschlagen für %s: %s', path, e)
        return out
    streams = d.get('streams') or []
    v = next((s for s in streams if s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')), None)
    if v:
        w, h = v.get('width') or 0, v.get('height') or 0
        out['resolution'] = '2160p' if w >= 3200 or h >= 2000 else '1080p' if w >= 1800 or h >= 1000 else '720p' if w >= 1200 or h >= 700 else (f'{h}p' if h else None)
        out['video_codec'] = {'hevc': 'HEVC', 'h264': 'H.264', 'av1': 'AV1', 'mpeg2video': 'MPEG-2', 'mpeg4': 'MPEG-4', 'vp9': 'VP9'}.get(v.get('codec_name'), (v.get('codec_name') or '').upper() or None)
        tr = (v.get('color_transfer') or '')
        if any((sd.get('side_data_type') or '').startswith('DOVI') for sd in v.get('side_data_list') or []):
            out['hdr'] = 'Dolby Vision'
        elif tr == 'smpte2084':
            out['hdr'] = 'HDR10'
        elif tr == 'arib-std-b67':
            out['hdr'] = 'HLG'
    try:
        out['duration_s'] = int(float((d.get('format') or {}).get('duration') or 0)) or None
    except Exception:
        pass
    auds = []
    for s in streams:
        if s.get('codec_type') == 'audio':
            lang = (s.get('tags') or {}).get('language') or '?'
            ch = s.get('channels') or 0
            layout = {1: '1.0', 2: '2.0', 6: '5.1', 8: '7.1'}.get(ch, str(ch) if ch else '')
            auds.append(' '.join(x for x in (lang, (s.get('codec_name') or '').upper(), layout) if x))
    subs = [((s.get('tags') or {}).get('language') or '?') for s in streams if s.get('codec_type') == 'subtitle']
    out['audio'] = ', '.join(auds) or None
    out['subtitles'] = ', '.join(dict.fromkeys(subs)) or None
    return out


# ---------------------------------------------------------------- Probelauf und Uebernahme
def scan_worker(folders):
    """Liest Ordner ein und erkennt Filme. Speichert nichts (Probelauf)."""
    try:
        with F.db() as c:
            known = F.known_paths(c)
            have = {r['tmdb_id']: (r['id'], r['title']) for r in c.execute('SELECT id, tmdb_id, title FROM films WHERE tmdb_id IS NOT NULL')}
        items = []
        with fs.unreadable() as bad:
            for f in folders:
                for it in collect(f):
                    if it['path'] not in known and all(i['path'] != it['path'] for i in items):
                        items.append(it)
        JOB['unreadable'] = bad
        JOB.update(total=len(items), done=0)
        out = []
        for i, it in enumerate(items):
            try:
                r = identify(it)
            except Exception as e:
                logging.exception('Erkennung fehlgeschlagen: %s', it['path'])
                r = {'title': it['name'], 'year': None, 'edition': '', 'tmdb_id': None, 'cands': [], 'status': 'nf', 'note': str(e), 'source': 'name'}
            r.update(idx=i, path=it['path'], name=it['name'], disc=it['disc'])
            if r['status'] == 'match' and r['tmdb_id'] in have:
                r['status'] = 'known'
                r['film_id'], r['film_title'] = have[r['tmdb_id']]
            # nicht gefunden: mit Jahr im Namen vermutlich ein Film (anlegen), ohne Jahr eher ein eigenes Video (ueberspringen)
            r['default'] = {'match': f"tmdb:{r['tmdb_id']}", 'known': f"tmdb:{r['tmdb_id']}", 'unsure': 'skip',
                            'nf': 'plain' if r.get('year') else 'skip'}[r['status']]
            out.append(r)
            JOB['done'] += 1
        # dieselbe TMDB-Nummer mehrfach (z. B. 1080p und 4K): bleibt ein Film mit mehreren Exemplaren
        JOB.update(items=out, state='ready')
    except Exception as e:
        logging.exception('Film-Scan fehlgeschlagen')
        JOB.update(state='error', error=str(e))


def save_from_tmdb(c, tmdb_id, images_dir):
    """Film anlegen (oder vorhandenen zurueckgeben). Gibt (film_id, fehler) zurueck."""
    row = F.film_by_tmdb(c, tmdb_id)
    if row:
        return row['id'], None
    d, err = T.details(tmdb_id)
    if err or not d:
        return None, err or 'TMDB lieferte keine Daten.'
    fid = F.insert_film(c, d)
    F.set_film_people(c, fid, d.get('_people'))
    fetch_images(c, fid, d.get('_poster_path'), d.get('_backdrop_path'), images_dir)
    return fid, None


PEOPLE = {'running': False, 'done': 0, 'total': 0}


def backfill_people(stop_after=None):
    """Fuer schon erfasste Filme die Personen (mit TMDB-Nummern) nachladen. Laeuft einmal im Hintergrund."""
    try:
        return _backfill_people(stop_after)
    finally:
        PEOPLE['running'] = False


def _backfill_people(stop_after=None):
    done = 0
    with F.db() as c:
        PEOPLE.update(total=len(F.films_without_people(c, 100000)) if T.configured() else 0, done=0)
    PEOPLE['running'] = PEOPLE['total'] > 0
    while T.configured():
        with F.db() as c:
            todo = F.films_without_people(c, 50)
        if not todo:
            break
        for r in todo:
            people, err = T.credits(r['tmdb_id'])
            if err:
                logging.warning('Personen für Film %s nicht geladen: %s', r['id'], err)
                return done
            with F.db() as c:
                if people:
                    F.set_film_people(c, r['id'], people)
                else:  # TMDB kennt keine Personen: Platzhalter, damit der Film nicht immer wieder abgefragt wird
                    c.execute("INSERT OR IGNORE INTO people(id, name) VALUES(0, '-')")
                    c.execute("INSERT OR IGNORE INTO film_people(film_id, person_id, role) VALUES(?, 0, 'none')", (r['id'],))
            done += 1
            PEOPLE['done'] = done
            if stop_after and done >= stop_after:
                return done
    return done


def fetch_images(c, fid, poster_path, backdrop_path, images_dir):
    from . import films_art as A
    ok = bool(poster_path) and bool(A.save_image(c, images_dir, fid, 'poster', T.fetch_image(poster_path, 'w342') or b''))
    if backdrop_path:
        A.save_image(c, images_dir, fid, 'backdrop', T.fetch_image(backdrop_path, 'w780') or b'')
    if not ok:  # kein oder kein ladbares Standardposter: lokale Bilder, eingebettetes Cover, andere TMDB-Poster
        A.fill_missing(c, images_dir, fid)


def resolution_from_name(name):
    """'11.Rebels.2024.German.1080p.BluRay' -> '1080p'; 4K/UHD -> '2160p'. Sonst None."""
    n = (name or '').lower()
    m = re.search(r'(?<![0-9])(2160|1440|1080|720|576|480)[pi](?![a-z0-9])', n)
    if m:
        return m.group(1) + 'p'
    if re.search(r'(?<![a-z0-9])(4k|uhd)(?![a-z0-9])', n):
        return '2160p'
    return None


def copy_from_file(path, disc='', edition=''):
    data = {'kind': 'file', 'path': path, 'edition': edition or None}
    if disc:
        data['container'] = 'Blu-ray-Ordner' if disc == 'bluray' else 'DVD-Ordner'
    else:
        data.update({k: v for k, v in probe(path).items() if v not in (None, '')})
    if not data.get('resolution'):  # ffprobe konnte nichts lesen: Angabe im Namen nehmen, sonst leer lassen
        data['resolution'] = resolution_from_name(os.path.basename(path)) or (resolution_from_name(os.path.basename(os.path.dirname(path))) if not disc else None)
    return data


def apply_worker(choices, images_dir):
    res = {'new': 0, 'attached': 0, 'plain': 0, 'skipped': 0}
    try:
        JOB.update(state='applying', total=len(JOB['items']), done=0)
        for it in JOB['items']:
            ch = choices.get(it['idx'], it['default'])
            try:
                with F.db() as c:
                    if ch == 'skip' or c.execute('SELECT 1 FROM copies WHERE path=?', (it['path'],)).fetchone():
                        res['skipped'] += 1
                    elif ch.startswith('tmdb:') and ch[5:].isdigit():
                        existed = F.film_by_tmdb(c, int(ch[5:]))
                        fid, err = save_from_tmdb(c, int(ch[5:]), images_dir)
                        if not fid:
                            raise RuntimeError(err)
                        F.add_copy(c, fid, copy_from_file(it['path'], it['disc'], it.get('edition')))
                        if not F.get_film(c, fid)['poster']:
                            from . import films_art as A
                            A.fill_missing(c, images_dir, fid)
                        res['attached' if existed else 'new'] += 1
                    else:
                        fid = F.insert_film(c, {'title': it['title'] or it['name'], 'year': it.get('year'), 'source': 'file'})
                        F.add_copy(c, fid, copy_from_file(it['path'], it['disc'], it.get('edition')))
                        from . import films_art as A
                        A.fill_missing(c, images_dir, fid)  # ohne TMDB: wenigstens ein lokales oder eingebettetes Poster
                        res['plain'] += 1
            except Exception:
                logging.exception('Film nicht übernommen: %s', it.get('path'))
                res['skipped'] += 1
            JOB['done'] += 1
        JOB.update(state='done', result=res, items=[])
    except Exception as e:
        logging.exception('Film-Import fehlgeschlagen')
        JOB.update(state='error', error=str(e))


def start(target, *args):
    with _job_lock:
        if JOB['state'] in ('scanning', 'applying'):
            return False
        JOB['state'] = 'scanning' if target is scan_worker else 'applying'
    threading.Thread(target=target, args=args, daemon=True).start()
    return True
