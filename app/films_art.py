"""Poster und Hintergrundbilder fuer Filme: lokale Bilddateien, in die Datei eingebettete Cover, TMDB, eigener Upload.

Reihenfolge beim Nachladen fehlender Poster:
  1. Bild neben der Datei (poster.jpg, folder.jpg, cover.jpg, <Dateiname>-poster.jpg ...), wie es Jellyfin, Kodi oder Plex ablegen
  2. In MKV/MP4 eingebettetes Cover
  3. TMDB (bevorzugt Wunschsprache, dann ohne Text, dann Englisch)
Gespeichert wird als data/film_images/<id>-poster-<zeit>.<ext>; der Zeitstempel sorgt dafuer, dass der Browser das neue Bild zeigt."""
import glob, json, logging, os, shutil, subprocess, tempfile, threading, time
from . import films_db as F
from . import films_tmdb as T
from . import fs

POSTER_NAMES = ('poster', 'folder', 'cover', 'movie', 'default', 'front')
BACKDROP_NAMES = ('fanart', 'backdrop', 'background', 'art')
IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp')
MAX_UPLOAD = 15 * 1024 * 1024
JOB = {'state': 'idle', 'done': 0, 'total': 0, 'result': None, 'unmatched': [], 'missing': [], 'finished': 0}


def image_ext(data):
    """Dateiendung nach Inhalt (nicht nach Name); None, wenn es kein Bild ist."""
    if not data or len(data) < 12:
        return None
    if data[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    return None


def remove_images(images_dir, fid, kind=None):
    for k in ([kind] if kind else ['poster', 'backdrop']):
        for f in glob.glob(os.path.join(images_dir, f'{fid}-{k}*')):
            try:
                os.remove(f)
            except OSError:
                pass


def save_image(c, images_dir, fid, kind, data):
    """Bild speichern und im Film eintragen. kind: 'poster' oder 'backdrop'. Gibt den Dateinamen zurueck oder None."""
    ext = image_ext(data)
    if not ext:
        return None
    remove_images(images_dir, fid, kind)
    name = f'{fid}-{kind}-{int(time.time() * 1000) % 10**10}.{ext}'
    with open(os.path.join(images_dir, name), 'wb') as fh:
        fh.write(data)
    F.update_film(c, fid, {kind: name})
    return name


# ---------------------------------------------------------------- lokale Quellen
def _folders_and_stems(c, fid):
    out = []
    for k in F.copies_of(c, fid):
        p = k['path']
        if not p:
            continue
        if fs.isdir(p):  # DVD-/Blu-ray-Ordner
            out.append((p, None))
            out.append((os.path.dirname(p), os.path.basename(p)))
        else:
            out.append((os.path.dirname(p), os.path.splitext(os.path.basename(p))[0]))
    return out


def local_images(c, fid, kind='poster'):
    """Bilddateien neben den Filmdateien (Pfade), beste zuerst."""
    names = POSTER_NAMES if kind == 'poster' else BACKDROP_NAMES
    found = []
    for folder, stem in _folders_and_stems(c, fid):
        try:
            files = fs.listdir(folder)
        except OSError:
            continue
        low = {f.lower(): f for f in files}
        cands = []
        if stem:
            cands += [f'{stem}-{n}' for n in names] + ([stem] if kind == 'poster' else [])
        cands += list(names)
        for base in cands:
            for ext in IMG_EXT:
                f = low.get((base + ext).lower())
                if f:
                    p = os.path.join(folder, f)
                    if p not in found:
                        found.append(p)
    return found


def embedded_cover(path):
    """In MKV (Anhang) oder MP4 (Coverbild) eingebettetes Bild als Bytes, sonst None."""
    if not path or not shutil.which('ffprobe') or not shutil.which('ffmpeg') or not fs.isfile(path):
        return None
    src = fs.media_url(path)
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', src], capture_output=True, timeout=30)
        streams = json.loads(r.stdout or b'{}').get('streams') or []
    except Exception:
        return None
    pick = None
    for s in streams:  # MKV-Anhang "cover.jpg" bevorzugen, sonst irgendein Bild-Anhang, sonst MP4-Coverbild
        tags = {k.lower(): v for k, v in (s.get('tags') or {}).items()}
        is_img = s.get('codec_type') == 'attachment' and str(tags.get('mimetype', '')).startswith('image/')
        is_pic = s.get('codec_type') == 'video' and (s.get('disposition') or {}).get('attached_pic')
        if is_img or is_pic:
            score = 0 if 'cover' in str(tags.get('filename', '')).lower() and 'small' not in str(tags.get('filename', '')).lower() else 1 if is_img else 2
            if pick is None or score < pick[0]:
                pick = (score, s['index'], is_img)
    if not pick:
        return None
    _, idx, is_attachment = pick
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'cover')
        try:
            if is_attachment:
                subprocess.run(['ffmpeg', '-v', 'error', '-y', f'-dump_attachment:{idx}', out, '-i', src], capture_output=True, timeout=60, cwd=tmp)
            else:
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-map', f'0:{idx}', '-c', 'copy', '-frames:v', '1', '-f', 'image2', out + '.jpg'],
                               capture_output=True, timeout=60)
                out += '.jpg'
            data = open(out, 'rb').read() if os.path.exists(out) else None
        except Exception as e:
            logging.warning('Eingebettetes Cover nicht lesbar (%s): %s', path, e)
            data = None
    return data if image_ext(data) else None


# ---------------------------------------------------------------- Nachladen
def fill_missing(c, images_dir, fid):
    """Fehlendes Poster/Hintergrundbild fuer einen Film suchen. Gibt die Quelle zurueck ('local', 'embedded', 'tmdb') oder None."""
    film = F.get_film(c, fid)
    src = None
    if not film['poster']:
        for p in local_images(c, fid, 'poster'):
            try:
                with fs.open(p, 'rb') as fh:
                    data = fh.read(MAX_UPLOAD + 1)
            except OSError:
                continue
            if len(data) <= MAX_UPLOAD and save_image(c, images_dir, fid, 'poster', data):
                src = 'local'
                break
    if not src and not film['poster']:
        for k in F.copies_of(c, fid):
            data = embedded_cover(k['path']) if k['path'] else None
            if data and save_image(c, images_dir, fid, 'poster', data):
                src = 'embedded'
                break
    if film['tmdb_id'] and (not F.get_film(c, fid)['poster'] or not film['backdrop']):
        imgs, err = T.images(film['tmdb_id'])
        if not F.get_film(c, fid)['poster']:
            for x in imgs['posters'][:3]:
                data = T.fetch_image(x['path'], 'w342')
                if data and save_image(c, images_dir, fid, 'poster', data):
                    src = 'tmdb'
                    break
        if not film['backdrop']:
            for x in imgs['backdrops'][:2]:
                data = T.fetch_image(x['path'], 'w780')
                if data and save_image(c, images_dir, fid, 'backdrop', data):
                    break
    if not F.get_film(c, fid)['backdrop']:
        for p in local_images(c, fid, 'backdrop'):
            try:
                with fs.open(p, 'rb') as fh:
                    data = fh.read(MAX_UPLOAD + 1)
            except OSError:
                continue
            if len(data) <= MAX_UPLOAD and save_image(c, images_dir, fid, 'backdrop', data):
                break
    return src


def missing_worker(images_dir):
    res = {'local': 0, 'embedded': 0, 'tmdb': 0, 'none': 0}
    unmatched, missing = [], []
    try:
        with F.db() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM films WHERE coalesce(poster,'')='' OR coalesce(backdrop,'')='' ORDER BY sort_title")]
        JOB.update(total=len(ids), done=0)
        for fid in ids:
            try:
                with F.db() as c:
                    had = bool(F.get_film(c, fid)['poster'])
                    src = fill_missing(c, images_dir, fid)
                    film = F.get_film(c, fid)
                if src:
                    res[src] += 1
                elif not had:
                    res['none'] += 1
                    entry = {'id': fid, 'title': film['title'], 'year': film['year']}
                    (missing if film['tmdb_id'] else unmatched).append(entry)
            except Exception:
                logging.exception('Poster für Film %s fehlgeschlagen', fid)
            JOB['done'] += 1
        JOB.update(state='done', result=res, unmatched=unmatched[:200], missing=missing[:200], finished=time.time())
    except Exception:
        logging.exception('Poster nachladen fehlgeschlagen')
        JOB.update(state='done', result=res, finished=time.time())


def start(images_dir):
    if JOB['state'] == 'running':
        return False
    JOB.update(state='running', done=0, total=0, result=None, unmatched=[], missing=[])
    threading.Thread(target=missing_worker, args=(images_dir,), daemon=True).start()
    return True
