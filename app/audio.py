"""Audio-Import: Dateien finden und lesen, zu Alben gruppieren, mit vorhandenen CDs abgleichen.

Dieses Modul kennt keine Datenbank. Die App (main.py) liefert die vorhandenen CDs und speichert das Ergebnis.
"""
import os
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

# Endungen, die eingelesen werden (Tags liest die Bibliothek mutagen)
AUDIO_EXT = {'.mp3', '.m4a', '.flac', '.ogg', '.oga', '.opus', '.wav', '.aac', '.aif', '.aiff', '.wma', '.ape', '.wv'}

# Ordner, die docker-compose.yml dem Container nur lesend freigibt:
# (Pfad im Container, Anzeige auf dem Mac, Beschriftung)
# (Pfad im Container, Anzeige, Beschreibung). /host/music ist fuer Homelab/Linux gedacht: dort den Musikordner
# lesend einhaengen (siehe docker-compose.homelab.yml); erscheint nur, wenn es den Ordner gibt.
ROOTS = [('/host/volumes', '/Volumes', 'Externe Laufwerke'), ('/host/home', '~', 'Benutzerordner'), ('/host/music', '/music', 'Musikordner')]


# ---------------------------------------------------------------- Pfade
def host_label(path):
    """Container-Pfad so anzeigen, wie er auf dem Mac heisst."""
    for c, h, _ in ROOTS:
        if path == c or str(path).startswith(c + '/'):
            return h + str(path)[len(c):]
    return path


def to_container_path(p, host_home=''):
    """Mac-Pfad (/Volumes/..., ~/..., /Users/...) in den Pfad im Container umrechnen."""
    p = (p or '').strip()
    if not p:
        return ''
    if p == '~' or p.startswith('~/'):
        return ROOTS[1][0] + p[1:]
    if p == '/Volumes' or p.startswith('/Volumes/'):
        return ROOTS[0][0] + p[len('/Volumes'):]
    if p == '/music' or p.startswith('/music/'):
        return ROOTS[2][0] + p[len('/music'):]
    hh = (host_home or '').rstrip('/')
    if hh and (p == hh or p.startswith(hh + '/')):
        return ROOTS[1][0] + p[len(hh):]
    return p


def safe_dir(p):
    """Gibt den echten Pfad zurueck, wenn er ein Ordner innerhalb der freigegebenen Wurzeln ist, sonst None."""
    try:
        rp = os.path.realpath(p)
    except Exception:
        return None
    for c, _, _ in ROOTS:
        if rp == c or rp.startswith(c + '/'):
            return rp if os.path.isdir(rp) else None
    return None


def list_dirs(path):
    """Unterordner und Anzahl Audiodateien direkt im Ordner. Links und versteckte Eintraege werden uebergangen."""
    dirs, audio = [], 0
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.name.startswith('.'):
                    continue
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir():
                        dirs.append(e.name)
                    elif os.path.splitext(e.name)[1].lower() in AUDIO_EXT:
                        audio += 1
                except OSError:
                    continue
    except OSError as ex:
        return [], 0, f'Kein Zugriff auf diesen Ordner ({ex.__class__.__name__}). Unter macOS ggf. in den Systemeinstellungen den Zugriff für OrbStack erlauben.'
    return sorted(dirs, key=str.casefold), audio, ''


def collect_files(folder):
    """Alle Audiodateien unterhalb von folder (ohne versteckte Ordner/Dateien, ohne Links), sortiert."""
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted((d for d in dirs if not d.startswith('.')), key=str.casefold)
        for n in sorted(names, key=str.casefold):
            if n.startswith('.'):
                continue
            if os.path.splitext(n)[1].lower() in AUDIO_EXT:
                yield os.path.join(root, n)


# ---------------------------------------------------------------- Tags lesen
def parse_int(v):
    m = re.match(r'\s*(\d+)', str(v or ''))
    return int(m.group(1)) if m else 0


def read_tags(path):
    """Tags einer Datei lesen. Fehlende Angaben werden aus Ordner- und Dateinamen ergaenzt (Interpret/Album/01 Titel.ext)."""
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    rec = {'path': path, 'fmt': ext.upper(), 'artist': '', 'albumartist': '', 'album': '', 'title': '',
           'track': 0, 'disc': 0, 'length': 0, 'date': '', 'genre': ''}
    try:
        import mutagen
        f = mutagen.File(path, easy=True)
    except Exception:
        f = None
    if f is not None:
        def tag(k):
            try:
                v = f.get(k)
            except Exception:
                return ''
            if isinstance(v, (list, tuple)):
                v = v[0] if v else ''
            return str(v or '').strip()
        rec.update(artist=tag('artist'), albumartist=tag('albumartist'), album=tag('album'), title=tag('title'),
                   track=parse_int(tag('tracknumber')), disc=parse_int(tag('discnumber')), date=tag('date'), genre=tag('genre'))
        try:
            rec['length'] = int(round(float(f.info.length)))
        except Exception:
            pass
    d = os.path.dirname(path)
    if not rec['album']:
        rec['album'] = os.path.basename(d)
    if not (rec['artist'] or rec['albumartist']):
        rec['artist'] = os.path.basename(os.path.dirname(d))
    stem = os.path.splitext(os.path.basename(path))[0]
    if not rec['title']:
        rec['title'] = re.sub(r'^\d+[\s.\-_]+', '', stem) or stem
    if not rec['track']:
        m = re.match(r'\s*(\d{1,3})\b', os.path.basename(path))
        rec['track'] = int(m.group(1)) if m else 0
    return rec


# ---------------------------------------------------------------- Namen vergleichen
EDITION = r'(remaster|deluxe|expanded|edition|anniversary|bonus|special|legacy|reissue|version|mix)'


def _clean(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.casefold().replace('&', ' and ')


def _article(t):
    return re.sub(r'^(the|der|die|das|a|an)\s+', '', t)


def norm_full(s):
    """Name ohne Gross/Klein, Satzzeichen, Akzente und fuehrenden Artikel. Klammerinhalt bleibt erhalten."""
    t = re.sub(r'[^\w\s]', ' ', _clean(s))
    return _article(re.sub(r'\s+', ' ', t).strip())


def norm_base(s):
    """Wie norm_full, aber ohne Zusaetze wie (Remastered 2009), [Deluxe] oder '- 2011 Remaster'."""
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', ' ', _clean(s))
    t = re.sub(r'\s+[-:]\s+.*' + EDITION + r'.*$', ' ', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    return _article(re.sub(r'\s+', ' ', t).strip())


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def most_common(vals):
    vals = [v for v in vals if v]
    return Counter(vals).most_common(1)[0][0] if vals else ''


VARIOUS = {'various artists', 'various', 'verschiedene', 'verschiedene interpreten', 'verschiedene kunstler', 'diverse', 'diverse interpreten',
           'compilation', 'compilations', 'sampler', 'va', 'v a', 'soundtrack', 'soundtracks', 'ost'}


def norm_artist(s):
    t = norm_full(s)
    return 'various artists' if t in VARIOUS else t


def main_artist(s):
    """Hauptinterpret eines Titels: 'A feat. B', 'A & B', 'A, B' -> 'A'."""
    t = re.split(r'\s+(?:feat\.?|ft\.?|featuring|with|vs\.?|und|and|x)\s+|\s*[&,;/]\s*', str(s or '').strip(), maxsplit=1, flags=re.I)[0]
    return t.strip()


def album_artist(rs):
    """Album-Interpret: Tag 'Album Artist', sonst der Hauptinterpret, wenn er bei >= 70 % der Titel vorkommt
    (Gastinterpreten zaehlen nicht), sonst Various Artists. Ein Ordner 'Various Artists/Sampler/...' gilt als Sammlung."""
    aa = most_common([r['albumartist'] for r in rs])
    if aa:
        return 'Various Artists' if norm_artist(aa) == 'various artists' else aa
    parent = os.path.basename(os.path.dirname(os.path.dirname(rs[0]['path']))) if rs else ''
    if norm_artist(parent) == 'various artists':
        return 'Various Artists'
    c = Counter(main_artist(r['artist']) for r in rs if r['artist'])
    if not c:
        return ''
    top, n = c.most_common(1)[0]
    return top if n / sum(c.values()) >= 0.7 else 'Various Artists'


# ---------------------------------------------------------------- Gruppieren und abgleichen
def title_set(titles):
    return {x for x in (norm_base(t) for t in titles) if x}


def index_media(rows):
    """rows: (id, artist, title, anzahl_tracks, ownership[, [titel der tracks]]) der vorhandenen CDs."""
    out = []
    for r in rows:
        i, a, t, n, o = r[:5]
        titles = list(r[5]) if len(r) > 5 and r[5] else []
        out.append({'id': i, 'artist': a or '', 'title': t or '', 'n': n or len(titles), 'own': o,
                    'a': norm_artist(a), 'tf': norm_full(t), 'tb': norm_base(t), 'ts': title_set(titles)})
    return out


def match_album(alb, idx):
    """Gibt (status, medium_id, kandidaten, hinweis) zurueck. Strenge Regel:
    match = gleicher Interpret und die Titellisten sind IDENTISCH (Dateien in mehreren Formaten zaehlen einmal).
            Hat die CD noch keine Titelliste, zaehlt der gleiche Albumname.
    new   = alles andere (mehr, weniger oder andere Titel). Aehnliche CDs werden nur als Option angeboten."""
    a, tf, tb, F = norm_artist(alb['artist']), norm_full(alb['album']), norm_base(alb['album']), alb.get('ts') or set()
    near = []
    for m in idx:
        C = m['ts']
        various = a == 'various artists'
        if not (m['a'] == a or (a and m['a'] and not various and (a in m['a'] or m['a'] in a))
                or (various and C and F == C and len(F) >= 3)):
            continue
        if C and F:
            inter = len(F & C)
            if F == C:
                return 'match', m['id'], [], ''
            if inter / max(len(C), len(F)) >= 0.5:
                near.append((m, inter, len(C), len(F)))
        elif m['tf'] == tf or m['tb'] == tb:
            return 'match', m['id'], [], ''
    if near:
        m, inter, nc, nf = max(near, key=lambda x: x[1])
        if nf > nc: why = f'{nf - inter} Titel mehr'
        elif nf < nc: why = f'{nc - nf} Titel weniger'
        else: why = 'andere Titel'
        note = f'Nicht identisch mit der CD „{m["title"]}“ ({why}, {inter} von {nc} Titeln gleich) – wird deshalb als eigener Eintrag angelegt.'
        return 'new', None, [{'id': x['id'], 'artist': x['artist'], 'title': x['title'], 'n': x['n'], 'common': c, 'of': o} for x, c, o, _ in near[:5]], note
    return 'new', None, [], ''


def _discless(d):
    """'.../Album/CD 2' -> '.../Album' (mehrere Discs eines Albums zusammenfassen)."""
    return os.path.dirname(d) if re.match(r'(?i)^(cd|disc|disk|vol\.?)\s*\d+\b', os.path.basename(d)) else d


def _tset(files):
    return title_set(f['title'] for f in files)


def group_files(recs, dir_medium):
    """Dateien zu Alben gruppieren. Grundregel: ein Ordner = ein Album (Disc-Unterordner 'CD 1' zaehlen zum Album).
    Dasselbe Album in mehreren Formaten (MP3 + M4A) bleibt EIN Album, auch wenn die Tags leicht abweichen.
    Nur wenn ein Ordner deutlich mehrere Alben enthaelt, wird nach dem Album-Tag getrennt.
    Dateien in einem Ordner, der schon einer CD/einem Eintrag zugeordnet ist, gehoeren dorthin."""
    groups = {}
    bydir = {}
    for r in recs:
        dm = dir_medium.get(os.path.dirname(r['path']))
        if dm:
            groups.setdefault(('known', dm), []).append(r)
        else:
            bydir.setdefault(_discless(os.path.dirname(r['path'])), []).append(r)
    parts = []
    for d, files in bydir.items():
        tags = Counter(norm_base(f['album']) for f in files if f['album'])
        n = len(files)
        big = [k for k, c in tags.items() if c >= max(3, 0.25 * n)]
        split = len(big) >= 2 or (len(tags) >= 3 and tags.most_common(1)[0][1] < 0.5 * n)
        if split:
            sub = {}
            for f in files:
                sub.setdefault(norm_base(f['album']), []).append(f)
            for k, fs in sub.items():
                parts.append([d, k, fs])
        else:
            parts.append([d, tags.most_common(1)[0][0] if tags else '', files])
    merged = []
    for p in parts:
        for q in merged:
            same_dir = p[0] == q[0]
            if same_dir:
                tp, tq = _tset(p[2]), _tset(q[2])
                ok = bool(tp and tq) and len(tp & tq) / min(len(tp), len(tq)) >= 0.8
            else:
                ok = bool(p[1]) and p[1] == q[1] and os.path.dirname(p[0]) == os.path.dirname(q[0])
            if ok:
                q[2] = q[2] + p[2]
                break
        else:
            merged.append(p)
    for i, (d, k, fs) in enumerate(merged):
        groups[('tag', d, k, i)] = fs
    return groups


def make_albums(groups, idx):
    by_id = {m['id']: m for m in idx}
    albums = []
    for key, rs in groups.items():
        years = [m.group(1) for m in (re.match(r'(\d{4})', r['date']) for r in rs) if m]
        ts = title_set(r['title'] for r in rs)
        alb = {'artist': album_artist(rs), 'album': most_common([r['album'] for r in rs]),
               'year': most_common(years), 'genre': most_common([r.get('genre', '') for r in rs]), 'n': len(ts) or len(rs), 'n_files': len(rs), 'ts': ts, 'note': '',
               'formats': ', '.join(sorted({r['fmt'] for r in rs if r['fmt']})), 'files': rs,
               'candidates': [], 'medium_id': None, 'match_label': ''}
        if key[0] == 'known':
            alb['status'], alb['medium_id'] = 'known', key[1]
            alb['note'] = 'Neue Dateien in einem Ordner, der schon erfasst ist.'
        else:
            alb['status'], alb['medium_id'], alb['candidates'], alb['note'] = match_album(alb, idx)
        m = by_id.get(alb['medium_id'])
        if m:
            alb['match_label'] = f"{m['artist']} – {m['title']}".strip(' –')
        alb['default'] = f"attach:{alb['medium_id']}" if alb['status'] in ('match', 'known') else 'new'
        albums.append(alb)
    albums.sort(key=lambda a: (a['artist'].casefold(), a['album'].casefold()))
    for i, a in enumerate(albums):
        a['idx'] = i
    return albums


# ---------------------------------------------------------------- Cover aus den Dateien
COVER_NAMES = {'cover', 'folder', 'front', 'album', 'albumart', 'artwork', 'albumartlarge'}


def embedded_cover(path):
    """Eingebettetes Cover einer Audiodatei (MP3/ID3, M4A, FLAC). Gibt (bytes, 'jpg'|'png') oder None zurueck."""
    try:
        import mutagen
        f = mutagen.File(path)
        if f is None:
            return None
        tags = getattr(f, 'tags', None)
        if tags is not None and hasattr(tags, 'getall'):
            for a in tags.getall('APIC'):
                return bytes(a.data), ('png' if 'png' in (a.mime or '').lower() else 'jpg')
        if tags is not None and 'covr' in tags:
            c = tags['covr'][0]
            return bytes(c), ('png' if getattr(c, 'imageformat', 13) == 14 else 'jpg')
        pics = getattr(f, 'pictures', None)
        if pics:
            return bytes(pics[0].data), ('png' if 'png' in (pics[0].mime or '').lower() else 'jpg')
    except Exception:
        return None
    return None


def find_cover(paths, max_files=4):
    """Cover zu einem Album suchen: erst Bilddatei im Ordner (cover/folder/front.jpg ...), dann eingebettetes Bild."""
    dirs = []
    for p in paths:
        d = os.path.dirname(p)
        if d not in dirs:
            dirs.append(d)
    for d in dirs:
        try:
            names = sorted(os.listdir(d), key=str.casefold)
        except OSError:
            continue
        for n in names:
            stem, ext = os.path.splitext(n)
            if stem.lower() in COVER_NAMES and ext.lower() in ('.jpg', '.jpeg', '.png'):
                fp = os.path.join(d, n)
                try:
                    if 500 < os.path.getsize(fp) < 15_000_000:
                        with open(fp, 'rb') as fh:
                            return fh.read(), ('png' if ext.lower() == '.png' else 'jpg')
                except OSError:
                    continue
    for p in list(paths)[:max_files]:
        r = embedded_cover(p)
        if r and len(r[0]) > 500:
            return r
    return None
