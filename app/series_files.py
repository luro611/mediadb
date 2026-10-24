"""Seriendateien einlesen: Folgen erkennen, nach Serie gruppieren, Serie EINMAL bei TMDB zuordnen, Dateien den Folgen zuordnen.

Erkannte Schreibweisen (Punkte, Unterstriche und Leerzeichen sind egal):
  Sacrifice.S01E01.GERMAN.DL.1080P.WEB.H264.mkv                       -> Sacrifice, Staffel 1, Folge 1
  Serie.S02E05E06... / S02E05-E06 / S02E05-06                         -> Doppelfolge 5-6
  Serie.1x05...                                                       -> Staffel 1, Folge 5
  Stephen.Hawkings.Grosser.Entwurf.E01.Wie.das.Universum.entstand...   -> Staffel aus dem Ordner (sonst 1), Folge 1, Titel als Hinweis
  Serie/Staffel 2/Folge 3.mkv, Season 02/03 - Titel.mkv                -> Serie und Staffel aus den Ordnern
Jellyfin/Kodi: tvshow.nfo im Serienordner (TMDB-/TVDB-/IMDb-Nummer) und Folgen-.nfo (season/episode) werden bevorzugt."""
import logging, os, re, threading, xml.etree.ElementTree as ET
from collections import Counter
from difflib import SequenceMatcher
from . import films_tmdb as T
from . import films_files as FF
from . import fs
from . import series_db as S

VIDEO_EXT = FF.VIDEO_EXT - {'.iso'}
SKIP_DIRS = FF.SKIP_DIRS | {'extras', 'specials-extra', 'bonus'}
SEASON_DIR = re.compile(r'^(?:staffel|season|saison|temporada|series|s)[ ._-]*(\d{1,3})\b|^(\d{1,2})\.?\s*staffel\b|^specials?$', re.I)
SXE = re.compile(r'(?<![a-z0-9])s(\d{1,3})[ ._-]?e(\d{1,4})(?:[ ._-]?(?:-|e|-e)(\d{1,4}))?(?![0-9])', re.I)
NXN = re.compile(r'(?<![a-z0-9])(\d{1,2})x(\d{2,3})(?:-(\d{2,3}))?(?![0-9])', re.I)
EONLY = re.compile(r'(?<![a-z0-9])(?:e|ep|episode|folge|teil|part)[ ._-]?(\d{1,4})(?:[ ._-]?(?:-|e)(\d{1,4}))?(?![0-9])', re.I)
LEAD_NUM = re.compile(r'^(\d{1,3})(?:[ ._-]+|$)')
JOB = {'state': 'idle', 'folders': [], 'done': 0, 'total': 0, 'items': [], 'error': '', 'result': None, 'phase': '', 'found': 0, 'current': ''}
_lock = threading.Lock()


def _spaces(s):
    s = s.replace('_', ' ')
    if s.count('.') >= 2 and s.count(' ') < 2:
        s = s.replace('.', ' ')
    return re.sub(r'\s+', ' ', s).strip()


_SERIES_JUNK = re.compile(r'doku|dokumentation|documentaire|documental|ws|komplett|integrale|intégrale|completa|staffel|season|saison|temporada|s\d{1,2}|t\d{1,2}', re.I)


def strip_junk(s):
    """Szene-Zusaetze nur am Ende entfernen, damit Woerter im Titel bleiben ('A Very English Scandal', 'The Germans')."""
    return FF.strip_junk(s, _SERIES_JUNK)


def clean_name(s):
    """Seriennamen saeubern: Jahr in Klammern merken, Szene-Zusaetze entfernen."""
    s = _spaces(s or '')
    year = None
    m = re.search(r'[\s(\[]((?:19|20)\d{2})[)\]]?\s*$', s) or re.search(r'\(((?:19|20)\d{2})\)', s)
    if m:
        year = int(m.group(1))
        s = s[:m.start()] + s[m.end():]
    tm = re.search(r'[\[{(]\s*tmdb(?:id)?\s*[-=:]\s*(\d+)\s*[\]})]', s, re.I)
    tv = re.search(r'[\[{(]\s*tvdb(?:id)?\s*[-=:]\s*(\d+)\s*[\]})]', s, re.I)
    s = re.sub(r'[\[{(][^\]})]*[\]})]', ' ', s)
    s = strip_junk(re.sub(r'\s+', ' ', s).strip())
    s = re.sub(r'\s+', ' ', s).strip(' -._')
    return s, year, (int(tm.group(1)) if tm else None), (int(tv.group(1)) if tv else None)


def _title_hint(rest):
    t = FF.JUNK.sub('', _spaces(rest))
    t = re.sub(r'\b(doku|ws)\b.*$', '', t, flags=re.I)
    return re.sub(r'\s+', ' ', t).strip(' -._') or None


def season_of_dir(name):
    m = SEASON_DIR.search((name or '').strip())
    if not m:
        return None
    if re.match(r'^specials?$', name.strip(), re.I):
        return 0
    return int(m.group(1) or m.group(2))


def parse_episode(path):
    """Erkennt Serie, Staffel, Folge(n) und Folgentitel aus Datei- und Ordnernamen."""
    stem = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path))
    grand = os.path.basename(os.path.dirname(os.path.dirname(path)))
    dir_season = season_of_dir(parent)
    series_dir = grand if dir_season is not None else parent
    s = _spaces(stem)
    out = {'season': None, 'episode': None, 'episode_end': None, 'title_hint': None, 'name': None, 'season_from': None}
    for rx, kind in ((SXE, 'sxe'), (NXN, 'nxn')):
        m = rx.search(s)
        if m:
            out.update(season=int(m.group(1)), episode=int(m.group(2)), episode_end=int(m.group(3)) if m.group(3) else None, season_from='name')
            out['name'] = s[:m.start()]
            out['title_hint'] = _title_hint(s[m.end():])
            break
    else:
        m = EONLY.search(s)
        if m:
            out.update(episode=int(m.group(1)), episode_end=int(m.group(2)) if m.group(2) else None)
            out['name'] = s[:m.start()]
            out['title_hint'] = _title_hint(s[m.end():])
        else:
            m = LEAD_NUM.match(s)  # '03 - Titel.mkv' im Staffelordner
            if m and dir_season is not None:
                out['episode'] = int(m.group(1))
                out['title_hint'] = _title_hint(s[m.end():])
        if out['episode'] is not None:
            out['season'] = dir_season if dir_season is not None else 1
            out['season_from'] = 'folder' if dir_season is not None else 'guess'
    if out['episode_end'] is not None and out['episode_end'] <= (out['episode'] or 0):
        out['episode_end'] = None
    name, year, tmdb, tvdb = clean_name(out['name'] or '')
    if not name or len(name) < 2:  # Serienname aus dem Ordner
        name, year2, tmdb2, tvdb2 = clean_name(series_dir)
        year, tmdb, tvdb = year or year2, tmdb or tmdb2, tvdb or tvdb2
    else:
        dname, year2, tmdb2, tvdb2 = clean_name(os.path.basename(os.path.dirname(os.path.dirname(path)) if dir_season is not None else os.path.dirname(path)))
        if dname and len(norm(dname)) > len(norm(name)) and norm(dname).startswith(norm(name) + ' '):
            name = dname
        year, tmdb, tvdb = year or year2, tmdb or tmdb2, tvdb or tvdb2
    out.update(name=name, year=year, tmdb=tmdb, tvdb=tvdb,
               series_dir=os.path.dirname(os.path.dirname(path)) if dir_season is not None else os.path.dirname(path))
    nfo = os.path.splitext(path)[0] + '.nfo'  # Folgen-.nfo (Jellyfin/Kodi)
    if fs.isfile(nfo):
        try:
            with fs.open(nfo, 'rb') as fh:
                r = ET.parse(fh).getroot()
            if r.tag == 'episodedetails':
                se, ep = r.findtext('season'), r.findtext('episode')
                if (se or '').strip().isdigit() and (ep or '').strip().isdigit():
                    out.update(season=int(se), episode=int(ep), season_from='nfo')
                if r.findtext('title'):
                    out['title_hint'] = r.findtext('title').strip()
        except Exception:
            pass
    return out


def tvshow_nfo(series_dir):
    """IDs aus tvshow.nfo im Serienordner."""
    p = os.path.join(series_dir or '', 'tvshow.nfo')
    if not fs.isfile(p):
        return {}
    try:
        with fs.open(p, 'rb') as fh:
            root = ET.parse(fh).getroot()
    except Exception:
        txt = fs.read_text(p)
        m = re.search(r'themoviedb\.org/tv/(\d+)', txt)
        return {'tmdb': int(m.group(1))} if m else {}
    out = {}
    for u in root.iter('uniqueid'):
        t, v = (u.get('type') or '').lower(), (u.text or '').strip()
        if t == 'tmdb' and v.isdigit():
            out['tmdb'] = int(v)
        elif t == 'tvdb' and v.isdigit():
            out['tvdb'] = int(v)
        elif t == 'imdb' and v.startswith('tt'):
            out['imdb'] = v
    for tag, key in (('tmdbid', 'tmdb'), ('tvdbid', 'tvdb'), ('imdb_id', 'imdb')):
        v = (root.findtext(tag) or '').strip()
        if v and key not in out:
            out[key] = int(v) if v.isdigit() else v
    if root.findtext('title'):
        out['title'] = root.findtext('title').strip()
    return out


def collect(folder, progress=None):
    out = []
    for root, dirs, files in fs.walk(folder):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith('.'))
        if progress:
            progress(root, len(out))
        for f in sorted(files):
            stem, ext = os.path.splitext(f)
            if ext.lower() in VIDEO_EXT and not f.startswith('.') and not FF.SKIP_FILE.search(stem):
                out.append(os.path.join(root, f))
    return out


def norm(t):
    t = (t or '').lower()
    t = t.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def similarity(a, b):
    if (a or '').strip().lower() == (b or '').strip().lower() and (a or '').strip():
        return 1.0  # genau gleich, auch bei reinen Zahlen wie '24' oder '1883'
    a, b = norm(a), norm(b)
    # Titel in anderer Schrift (kyrillisch, japanisch ...) schrumpfen beim Vereinfachen auf fast nichts zusammen
    # ('10 историй о любви и смерти' -> '10'); solche Vergleiche zaehlen nicht
    if len(re.sub(r'[^a-z]', '', a)) < 2 or len(re.sub(r'[^a-z]', '', b)) < 2:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def name_variants(name):
    """'Stephen Hawkings Grosser Entwurf' -> auch 'Stephen Hawkings Großer Entwurf' (Umlaute aus der Umschrift)."""
    out = [name]
    v = re.sub(r'ae', 'ä', re.sub(r'oe', 'ö', re.sub(r'ue', 'ü', name)))
    v = re.sub(r'(?<=[aeiouäöü])ss(?=[aeiou]|er\b|e\b)', 'ß', v)
    if v != name:
        out.append(v)
    words = name.split()
    if len(words) > 3:
        out.append(' '.join(words[:3]))
    return out


def identify(group):
    """Eine Serie (Gruppe von Dateien) bei TMDB finden."""
    nfo = tvshow_nfo(group['series_dir'])
    tmdb = nfo.get('tmdb') or group.get('tmdb')
    if not tmdb and (nfo.get('tvdb') or group.get('tvdb')):
        tmdb = T.tv_find(nfo.get('tvdb') or group.get('tvdb'), 'tvdb_id')
    if not tmdb and nfo.get('imdb'):
        tmdb = T.tv_find(nfo['imdb'], 'imdb_id')
    res = {'tmdb_id': None, 'cands': [], 'status': 'nf', 'note': '', 'source': 'nfo' if nfo else 'name'}
    if tmdb:
        res.update(tmdb_id=int(tmdb), status='match', note='TMDB-Nummer aus tvshow.nfo' if nfo.get('tmdb') or nfo.get('tvdb') else 'TMDB-Nummer aus dem Namen')
        return res
    name = nfo.get('title') or group['name']
    cands, err = [], None
    for q in name_variants(name):
        cands, err = T.tv_search(q, group.get('year'))
        if cands or err:
            break
    if err:
        res['note'] = err
        return res
    res['cands'] = cands[:6]
    if not cands:
        res['note'] = 'Bei TMDB nicht gefunden'
        return res
    best = max(cands[:5], key=lambda c: max(similarity(name, c['title']), similarity(name, c['original_title'])))
    sim = max(similarity(name, best['title']), similarity(name, best['original_title']))
    year_ok = not group.get('year') or (best['year'] and abs(best['year'] - group['year']) <= 1)
    if sim >= 0.86 and year_ok:
        res.update(tmdb_id=best['tmdb_id'], status='match')
    else:
        res.update(tmdb_id=best['tmdb_id'], status='unsure', sim=sim, note='Titel nur ähnlich' if sim < 0.86 else 'Bitte Jahr prüfen')
    return res


def scan_worker(folders):
    """Probelauf: Dateien finden, nach Serie gruppieren, jede Serie einmal bei TMDB suchen. Speichert nichts."""
    try:
        with S.db() as c:
            known = S.known_paths(c)
            have = {r['tmdb_id']: (r['id'], r['title']) for r in c.execute('SELECT id, tmdb_id, title FROM series WHERE tmdb_id IS NOT NULL')}
        groups = {}
        JOB.update(phase='collect', found=0, current='', total=0, done=0)

        def prog(root, n):
            JOB.update(current=root, found=base + n)
        paths, base = [], 0
        with fs.unreadable() as bad:
            for f in folders:
                paths += collect(f, prog)
                base = len(paths)
        JOB['unreadable'] = bad
        JOB['found'] = len(paths)
        paths = [p for p in paths if p not in known]
        JOB.update(phase='parse', total=len(paths), done=0, current='')
        for p in paths:
            e = parse_episode(p)
            key = (norm(e['name']), e['series_dir'] if not e['name'] else '')
            g = groups.setdefault(key, {'name': e['name'] or os.path.basename(e['series_dir']), 'year': e['year'], 'tmdb': e['tmdb'],
                                        'tvdb': e['tvdb'], 'series_dir': e['series_dir'], 'files': []})
            g['year'] = g['year'] or e['year']
            g['files'].append(dict(e, path=p))
            JOB['done'] += 1
        items = []
        JOB.update(phase='tmdb', total=len(groups), done=0)
        for i, g in enumerate(groups.values()):
            JOB['current'] = g['name']
            try:
                r = identify(g)
            except Exception as ex:
                logging.exception('Serie nicht erkannt: %s', g['name'])
                r = {'tmdb_id': None, 'cands': [], 'status': 'nf', 'note': str(ex), 'source': 'name'}
            seasons = {}
            for f in g['files']:
                seasons.setdefault(f['season'], []).append(f)
            r.update(idx=i, name=g['name'], year=g['year'], series_dir=g['series_dir'], files=sorted(g['files'], key=lambda f: (f['season'] or 0, f['episode'] or 0, f['path'])),
                     n_files=len(g['files']), seasons_found=sorted((s, len(v)) for s, v in seasons.items() if s is not None),
                     unnumbered=len(seasons.get(None, [])))
            if r['status'] == 'match' and r['tmdb_id'] in have:
                r['status'] = 'known'
                r['series_id'], r['series_title'] = have[r['tmdb_id']]
                eps = {(f['season'], f['episode']) for f in g['files'] if f['episode'] is not None}
                with S.db() as c:
                    old = [dict(x) for x in c.execute('SELECT id, season, episode, path, resolution FROM ep_files WHERE series_id=?', (r['series_id'],))
                           if (x['season'], x['episode']) in eps]
                new_res = Counter(FF.resolution_from_name(os.path.basename(f['path'])) for f in g['files'] if (f['season'], f['episode']) in {(o['season'], o['episode']) for o in old})
                r.update(FF.compare_files(old, new_res.most_common(1)[0][0] if new_res else None))
                if old:
                    r['n_overlap'] = len({(o['season'], o['episode']) for o in old})
                    r['old_res'] = sorted({o['resolution'] or '' for o in old}, key=FF.res_px, reverse=True)
            if r['status'] == 'known' and r.get('suggest') in ('replace', 'skip'):
                r['default'] = 'skip' if r['suggest'] == 'skip' else f"replace:{r['tmdb_id']}"
            elif r['status'] in ('match', 'known') or (r['status'] == 'unsure' and r.get('sim', 0) >= 0.7):
                r['default'] = f"tmdb:{r['tmdb_id']}"  # bei 'Bitte pruefen' den besten Vorschlag vorwaehlen, wenn er halbwegs passt
            else:
                r['default'] = 'plain' if r['status'] == 'nf' else 'skip'
            items.append(r)
            JOB['done'] += 1
        JOB.update(items=items, state='ready')
    except Exception as e:
        logging.exception('Serien-Scan fehlgeschlagen')
        JOB.update(state='error', error=str(e))


def save_from_tmdb(c, tmdb_id, images_dir):
    """Serie mit Episodenfuehrer, Personen und Bildern anlegen (oder vorhandene zurueckgeben)."""
    row = S.by_tmdb(c, tmdb_id)
    if row:
        return row['id'], None
    d, err = T.tv_details(tmdb_id)
    if err or not d:
        return None, err or 'TMDB lieferte keine Daten.'
    sid = S.insert(c, d)
    S.set_people(c, sid, d.get('_people'))
    S.set_guide(c, sid, d['_seasons'], T.tv_guide(tmdb_id, d['_seasons']))
    fetch_images(c, sid, d, images_dir)
    return sid, None


def refresh_guide(c, sid):
    """Episodenfuehrer neu von TMDB laden (neue Folgen, Titel)."""
    s = S.get(c, sid)
    if not s or not s['tmdb_id']:
        return 'Diese Serie ist keinem TMDB-Eintrag zugeordnet.'
    d, err = T.tv_details(s['tmdb_id'])
    if err:
        return err
    S.update(c, sid, {k: v for k, v in d.items() if not k.startswith('_') and k not in ('title',)}, only_empty=False)
    S.set_people(c, sid, d.get('_people'))
    S.set_guide(c, sid, d['_seasons'], T.tv_guide(s['tmdb_id'], d['_seasons']))
    return None


def image_name(sid, kind, ext):
    import time
    return f's{sid}-{kind}-{int(time.time() * 1000) % 10**10}.{ext}'


def save_image(c, images_dir, sid, kind, data):
    from .films_art import image_ext
    import glob
    ext = image_ext(data)
    if not ext:
        return None
    for f in glob.glob(os.path.join(images_dir, f's{sid}-{kind}*')):
        try:
            os.remove(f)
        except OSError:
            pass
    name = image_name(sid, kind, ext)
    with open(os.path.join(images_dir, name), 'wb') as fh:
        fh.write(data)
    S.update(c, sid, {kind: name})
    return name


def remove_images(images_dir, sid):
    import glob
    for f in glob.glob(os.path.join(images_dir, f's{sid}-*')):
        try:
            os.remove(f)
        except OSError:
            pass


def fetch_images(c, sid, d, images_dir):
    ok = d.get('_poster_path') and save_image(c, images_dir, sid, 'poster', T.fetch_image(d['_poster_path'], 'w342') or b'')
    if d.get('_backdrop_path'):
        save_image(c, images_dir, sid, 'backdrop', T.fetch_image(d['_backdrop_path'], 'w780') or b'')
    if not ok and d.get('tmdb_id'):
        imgs, _ = T.tv_images(d['tmdb_id'])
        for x in imgs['posters'][:3]:
            if save_image(c, images_dir, sid, 'poster', T.fetch_image(x['path'], 'w342') or b''):
                break


def place_file(c, sid, f):
    """Staffel/Folge einer Datei festlegen. Ohne Staffel im Namen (nur 'E01') hilft der Folgentitel, wenn TMDB ihn kennt."""
    season, ep = f.get('season'), f.get('episode')
    hint = f.get('title_hint')
    if hint and f.get('season_from') in ('guess', 'folder', None):
        best, score = None, 0
        for e in c.execute('SELECT season, episode, name FROM episodes WHERE series_id=? AND name IS NOT NULL', (sid,)):
            sc = similarity(hint, e['name'])
            if sc > score:
                best, score = e, sc
        if best and score >= 0.8 and (best['season'], best['episode']) != (season, ep):
            if f.get('season_from') == 'guess' or score >= 0.92:
                season, ep = best['season'], best['episode']
    return season, ep


def file_data(f, season, ep):
    data = {'season': season, 'episode': ep, 'episode_end': f.get('episode_end'), 'title_hint': f.get('title_hint'), 'path': f['path']}
    data.update({k: v for k, v in FF.probe(f['path']).items() if v not in (None, '')})
    if not data.get('resolution'):
        data['resolution'] = FF.resolution_from_name(os.path.basename(f['path']))
    return data


def apply_worker(choices, images_dir):
    res = {'new': 0, 'attached': 0, 'plain': 0, 'skipped': 0, 'files': 0, 'replaced': 0}
    try:
        total = sum(it['n_files'] for it in JOB['items'])
        JOB.update(state='applying', total=total, done=0, phase='apply')
        for it in JOB['items']:
            JOB['current'] = it['name']
            ch = choices.get(it['idx'], it['default'])
            try:
                if ch == 'skip':
                    res['skipped'] += 1
                    JOB['done'] += it['n_files']
                    continue
                with S.db() as c:
                    if ch.partition(':')[0] in ('tmdb', 'replace') and ch.partition(':')[2].isdigit():
                        existed = S.by_tmdb(c, int(ch.partition(':')[2]))
                        sid, err = save_from_tmdb(c, int(ch.partition(':')[2]), images_dir)
                        if not sid:
                            raise RuntimeError(err)
                        res['attached' if existed else 'new'] += 1
                    else:
                        sid = S.insert(c, {'title': it['name'], 'year': it.get('year'), 'source': 'file'})
                        res['plain'] += 1
                for f in it['files']:
                    with S.db() as c:
                        if c.execute('SELECT 1 FROM ep_files WHERE path=?', (f['path'],)).fetchone():
                            JOB['done'] += 1
                            continue
                        season, ep = place_file(c, sid, f)
                    data = file_data(f, season, ep)  # ffprobe ausserhalb der Transaktion
                    with S.db() as c:
                        if ch.startswith('replace:'):  # Eintraege der alten Dateien dieser Folge; die Dateien selbst bleiben
                            for o in it.get('old_files') or []:
                                if (o['season'], o['episode']) == (season, ep):
                                    c.execute('DELETE FROM ep_files WHERE id=? AND series_id=?', (o['id'], sid))
                                    res['replaced'] += 1
                        S.add_file(c, sid, data)
                    res['files'] += 1
                    JOB['done'] += 1
            except Exception:
                logging.exception('Serie nicht übernommen: %s', it.get('name'))
                res['skipped'] += 1
        JOB.update(state='done', result=res, items=[])
    except Exception as e:
        logging.exception('Serien-Import fehlgeschlagen')
        JOB.update(state='error', error=str(e))


def start(target, *args):
    with _lock:
        if JOB['state'] in ('scanning', 'applying'):
            return False
        JOB['state'] = 'scanning' if target is scan_worker else 'applying'
    threading.Thread(target=target, args=args, daemon=True).start()
    return True
