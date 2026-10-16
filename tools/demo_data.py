"""Legt eine erfundene Beispiel-Sammlung an (für Bildschirmfotos der Anleitung und zum Ausprobieren).

Alle Titel, Namen und Personen sind erfunden; statt echter Cover gibt es schlichte farbige Platzhalter (SVG).
So enthalten die Bildschirmfotos nichts Privates und keine fremden Bilder.

Aufruf:  python3 tools/demo_data.py <leerer-ordner>
Danach startet MediaDB mit DATA_DIR=<leerer-ordner> mit dieser Sammlung (siehe tools/screenshots.py)."""
import os, sys, json, hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit(__doc__)
DATA = Path(sys.argv[1]).resolve()
if DATA.exists() and any(DATA.iterdir()):
    sys.exit(f'Der Ordner {DATA} ist nicht leer. Bitte einen leeren oder neuen Ordner angeben.')
DATA.mkdir(parents=True, exist_ok=True)
# Einstellungen vor dem Start: Deutsch, nichts aus dem Internet nachladen
(DATA / 'settings.json').write_text(json.dumps({'lang': 'de', 'nav_langs': [], 'config': {
    'BARCODE_LOOKUP': '0', 'COVER_WEB': '0', 'AUTO_UPDATE': '0', 'MEDIATHEK': '0', 'UPDATE_CHECK': '0',
    'MB_CONTACT': 'demo@example.invalid'}}), encoding='utf-8')
os.environ['DATA_DIR'] = str(DATA)
for k in ('BARCODE_LOOKUP', 'COVER_WEB', 'AUTO_UPDATE', 'MEDIATHEK', 'UPDATE_CHECK'):
    os.environ[k] = '0'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import main as M  # legt alle Datenbanken an
from app import films_db as F, series_db as S, books_db as B, loans as L, watchlist as WL

TODAY = date.today()
PALETTE = ['#c75d3b', '#2a6f97', '#6a994e', '#8d5a97', '#d08c2f', '#3d5a80', '#b5838d', '#457b9d', '#9c6644', '#588157',
           '#e07a5f', '#5e548e', '#bc4749', '#0f7173', '#a98467']


def days(n):
    return (TODAY - timedelta(days=n)).isoformat()


def color(text):
    return PALETTE[int(hashlib.md5(text.encode()).hexdigest(), 16) % len(PALETTE)]


def svg(title, sub, w, h):
    """Schlichter Platzhalter: Farbfläche mit Titel (keine fremden Bilder)."""
    c = color(title + sub)
    words, lines, cur = title.split(), [], ''
    for wd in words:
        if len(cur) + len(wd) > 14 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + ' ' + wd).strip()
    lines.append(cur)
    y0 = h * 0.42 - (len(lines) - 1) * 13
    esc = lambda s: s.replace('&', '&amp;').replace('<', '&lt;')
    text = ''.join(f'<text x="{w/2}" y="{y0 + i*26:.0f}" font-size="22" text-anchor="middle" fill="#fff" '
                   f'font-family="Georgia,serif">{esc(l)}</text>' for i, l in enumerate(lines))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="{c}"/><rect x="12" y="12" width="{w-24}" height="{h-24}" fill="none" '
            f'stroke="#ffffff" stroke-opacity=".35"/>{text}<text x="{w/2}" y="{h-30}" font-size="14" text-anchor="middle" '
            f'fill="#fff" fill-opacity=".85" font-family="Helvetica,Arial,sans-serif">{esc(sub)}</text></svg>')


def image(folder, name, title, sub, w, h):
    (DATA / folder / name).write_text(svg(title, sub, w, h), encoding='utf-8')
    return name


# ---------------------------------------------------------------- Musik
MUSIC = [  # Interpret, Album, Jahr, Genre, Besitz, Formate, Titel
    ('Die Abendband', 'Sommerlicht', 2019, 'Pop', 'cd', '', ['Sommerlicht', 'Am Fluss', 'Leuchtturm', 'Kurz vor acht', 'Heimweg']),
    ('Die Abendband', 'Nachtfahrt', 2022, 'Pop', 'cd_digital', 'FLAC', ['Nachtfahrt', 'Tankstelle', 'Neonblau', 'Ausfahrt Nord']),
    ('Anna Feldmann', 'Klavierstücke', 2016, 'Klassik', 'cd', '', ['Präludium', 'Etüde in Grau', 'Regentag', 'Nocturne']),
    ('Anna Feldmann', 'Winterreise neu', 2021, 'Klassik', 'digital', 'M4A', ['Aufbruch', 'Schnee', 'Rast', 'Ankunft']),
    ('Blaue Stunde', 'Hafenlichter', 2018, 'Jazz', 'cd', '', ['Hafenlichter', 'Möwen', 'Spätschicht', 'Kai 7']),
    ('Carla Mond', 'Zwischen den Zeilen', 2020, 'Singer-Songwriter', 'cd', '', ['Zwischen den Zeilen', 'Papierboot', 'Altbau']),
    ('Elektro Kollektiv', 'Puls', 2023, 'Electronic', 'digital', 'MP3', ['Puls', 'Strom', 'Frequenz', 'Echo']),
    ('Gustav Brenner Trio', 'Live im Kesselhaus', 2015, 'Jazz', 'cd', '', ['Intro', 'Kesselblues', 'Ballade', 'Zugabe']),
    ('Die Kranichs', 'Zugvögel', 2017, 'Folk', 'cd', '', ['Zugvögel', 'Heideweg', 'Abschied']),
    ('Die Kranichs', 'Heimkehr', 2024, 'Folk', 'cd_digital', 'MP3', ['Heimkehr', 'Lindenbaum', 'Morgentau']),
    ('Lena Sturm', 'Gewitter', 2021, 'Rock', 'cd', '', ['Gewitter', 'Blitzlicht', 'Donnerstag', 'Regenbogen']),
    ('Orchester am See', 'Sinfonische Skizzen', 2014, 'Klassik', 'cd', '', ['Allegro', 'Adagio', 'Finale']),
    ('Paul Wiesner', 'Landstraße', 2019, 'Country', 'digital', 'FLAC', ['Landstraße', 'Diesel', 'Weites Feld']),
    ('Verschiedene', 'Sommerhits 2020', 2020, 'Pop', 'cd', '', ['Sonnendeck', 'Freibad', 'Eis am Stiel']),
]
s = M.Session()
for i, (artist, title, year, genre, own, fmts, tracks) in enumerate(MUSIC):
    m = M.Medium(title=title, artist=artist, year=str(year), release_date=f'{year}-0{1 + i % 9}-15', genre=genre, ownership=own,
                 file_formats=fmts or None, label='Beispiel-Label', format='CD' if own != 'digital' else 'Digital Media',
                 country='DE', barcode=f'4000000{i:06d}' if own != 'digital' else None, source='demo',
                 release_group_type='Album; Compilation' if artist == 'Verschiedene' else 'Album',
                 created_at=datetime.now() - timedelta(days=60 - i * 4))
    for n, t in enumerate(tracks, 1):
        m.tracks.append(M.Track(position=n, number=str(n), title=t, disc_number=1, duration=f'{3 + n % 3}:{(17 * n) % 60:02d}'))
    s.add(m)
    s.flush()
    m.cover_path = image('covers', f'demo-{m.id}.svg', title, artist, 500, 500)
s.commit()
music_ids = {x.title: x.id for x in s.query(M.Medium).all()}
for t in ('Hafenlichter', 'Zugvögel'):
    s.query(M.Medium).filter(M.Medium.id == music_ids[t]).update({'next_at': datetime.now().isoformat(timespec='seconds')})
s.commit()
s.close()

# ---------------------------------------------------------------- Filme
FILMS = [  # Titel, Jahr, Genres, Regie, Minuten, gesehen vor Tagen (None = nicht), Bewertung, Formate, Handlung
    ('Der letzte Sommer am See', 2019, 'Drama', 'Marie Lindqvist', 112, 40, 8, ['bluray'], 'Drei Geschwister verbringen einen letzten Sommer im Ferienhaus ihrer Eltern.'),
    ('Nebel über Hamburg', 2021, 'Krimi, Thriller', 'Jonas Peters', 98, 12, 7, ['dvd'], 'Eine Kommissarin jagt im Herbstnebel einen Kunstdieb.'),
    ('Die Uhrmacherin', 2018, 'Drama, Historie', 'Clara Brandt', 124, 200, 9, ['bluray'], 'Wien 1912: Eine junge Frau übernimmt die Werkstatt ihres Vaters.'),
    ('Kometenjagd', 2022, 'Science Fiction, Abenteuer', 'Tom Akers', 131, None, 9, ['uhd', 'file'], 'Eine kleine Crew fliegt einem Kometen hinterher.'),
    ('Omas Rezeptbuch', 2020, 'Komödie, Familie', 'Sabine Ott', 95, 5, 7, ['dvd'], 'Ein Kochwettbewerb bringt eine zerstrittene Familie zusammen.'),
    ('Funkstille', 2017, 'Thriller', 'Jonas Peters', 101, None, 6, ['dvd'], 'Auf einer Bohrinsel bricht der Kontakt zum Festland ab.'),
    ('Der Kartograf', 2023, 'Abenteuer', 'Tom Akers', 140, None, 10, ['bluray'], 'Ein Kartenzeichner sucht eine Insel, die es nicht geben dürfte.'),
    ('Zwei Tickets nach Lissabon', 2019, 'Romantik, Komödie', 'Marie Lindqvist', 104, 90, 8, ['file'], 'Zwei Fremde, ein verpasster Zug und ein langer Tag.'),
    ('Schattenspiel', 2016, 'Krimi', 'Clara Brandt', 109, 400, 6, ['dvd'], 'Ein Puppenspieler gerät unter Verdacht.'),
    ('Polarlicht', 2021, 'Dokumentation', 'Erik Sand', 88, None, None, ['bluray'], 'Ein Winter in einer Forschungsstation am Polarkreis.'),
    ('Kometenjagd 2', 2025, 'Science Fiction, Abenteuer', 'Tom Akers', 137, None, None, ['uhd'], 'Die Crew ist zurück, der Komet auch.'),
    ('Der Bäcker von Brügge', 2015, 'Komödie', 'Sabine Ott', 92, 700, 7, ['dvd'], 'Ein Bäcker erbt eine Schokoladenfabrik.'),
]
with F.db() as c:
    fids = {}
    for i, (t, y, g, d, rt, seen, r, kinds, ov) in enumerate(FILMS):
        fid = F.insert_film(c, {'title': t, 'year': y, 'genres': g, 'directors': d, 'runtime': rt, 'overview': ov,
                                'countries': 'Deutschland', 'certification': '12', 'source': 'demo',
                                'collection_id': 900 if t.startswith('Kometenjagd') else None,
                                'collection_name': 'Kometenjagd – Filmreihe' if t.startswith('Kometenjagd') else None})
        poster = image('film_images', f'demo-f{fid}.svg', t, str(y), 400, 600)
        c.execute('UPDATE films SET poster=?, created_at=? WHERE id=?', (poster, (datetime.now() - timedelta(days=50 - i * 4)).isoformat(timespec='seconds'), fid))
        for k in kinds:
            F.add_copy(c, fid, {'kind': k, 'resolution': '2160p' if k == 'uhd' else ('1080p' if k in ('bluray', 'file') else None),
                                'path': f'/demo/Filme/{t} ({y}).mkv' if k == 'file' else None})
        if seen is not None:
            F.set_watched(c, fid, True, days(seen))
        if r:
            F.set_rating(c, fid, r)
        fids[t] = fid
    F.set_next(c, fids['Der Kartograf'], True)
    F.set_next(c, fids['Polarlicht'], True)
    lid = F.create_list(c, 'Filmabend mit Freunden')
    for t in ('Omas Rezeptbuch', 'Kometenjagd', 'Zwei Tickets nach Lissabon'):
        F.set_in_list(c, lid, fids[t], True)

# ---------------------------------------------------------------- Serien
SERIES = [  # Titel, Jahr, Status, Sender, Genres, Staffeln (Folgen je Staffel), gesehen bis (Staffel, Folge), Dateien bis Staffel
    ('Leuchtturmwärter', 2019, 'Ended', 'Nordkanal', 'Drama', [8, 8, 6], (3, 6), 3, 'Auf einer Nordseeinsel hütet eine Familie den letzten bemannten Leuchtturm.'),
    ('Die Akte Falkenberg', 2021, 'Returning Series', 'Krimi Plus', 'Krimi', [10, 10, 8], (2, 4), 2, 'Ein Ermittlerduo rollt alte Fälle in einer Kleinstadt neu auf.'),
    ('Raumstation Aurora', 2022, 'Returning Series', 'Sternenfunk', 'Science Fiction', [6, 6], (0, 0), 2, 'Leben und Arbeiten auf einer Station im Erdorbit.'),
    ('Café Zeitlos', 2018, 'Ended', 'Heimatkanal', 'Komödie', [12, 12], (1, 12), 1, 'In einem kleinen Café trifft sich jeden Tag die halbe Nachbarschaft.'),
    ('Grenzland', 2023, 'Returning Series', 'Krimi Plus', 'Thriller', [8], (0, 0), 1, 'Schmuggler, Zöllner und ein verschwundener Lastwagen.'),
]
with S.db() as c:
    sids = {}
    for i, (t, y, st, net, g, seasons, seen, files_to, ov) in enumerate(SERIES):
        sid = S.insert(c, {'title': t, 'year': y, 'first_air_date': f'{y}-03-01', 'status': st, 'networks': net, 'genres': g,
                           'overview': ov, 'number_of_seasons': len(seasons), 'number_of_episodes': sum(seasons), 'source': 'demo',
                           'episode_runtime': 45, 'providers': 'Beispiel-Stream'})
        poster = image('film_images', f'demo-s{sid}.svg', t, f'seit {y}', 400, 600)
        c.execute('UPDATE series SET poster=?, created_at=? WHERE id=?', (poster, (datetime.now() - timedelta(days=45 - i * 6)).isoformat(timespec='seconds'), sid))
        eps, ss = [], []
        for sn, n in enumerate(seasons, 1):
            start = date(y + sn - 1, 3, 1)
            ss.append({'season': sn, 'name': f'Staffel {sn}', 'episode_count': n, 'air_date': start.isoformat()})
            for e in range(1, n + 1):
                eps.append({'season': sn, 'episode': e, 'name': f'Folge {e}', 'air_date': (start + timedelta(days=7 * (e - 1))).isoformat(), 'runtime': 45})
        S.set_guide(c, sid, ss, eps)
        for e in eps:
            if e['season'] <= files_to and not (t == 'Die Akte Falkenberg' and e['season'] == 2 and e['episode'] > 7):
                S.add_file(c, sid, {'season': e['season'], 'episode': e['episode'], 'path': f'/demo/Serien/{t}/S{e["season"]:02d}E{e["episode"]:02d}.mkv',
                                    'resolution': '1080p', 'container': 'mkv'})
            if (e['season'], e['episode']) <= seen:
                S.set_watched(c, sid, e['season'], e['episode'], True, days(30))
        sids[t] = sid
    S.add_copy(c, sids['Café Zeitlos'], {'kind': 'dvd', 'seasons': '1-2'})
    S.set_rating(c, sids['Leuchtturmwärter'], 9)
    S.set_next(c, sids['Raumstation Aurora'], True)

# ---------------------------------------------------------------- Bücher
BOOKS = [  # Titel, Autor, Jahr, Genres, Reihe, Band, Status, Bewertung, Format, Seiten
    ('Das Haus am Deich', 'Henrike Paulsen', 2018, 'Roman', '', '', 'read', 8, 'paperback', 320),
    ('Salz und Sturm', 'Henrike Paulsen', 2020, 'Roman', '', '', 'reading', None, 'hardcover', 410),
    ('Der stille Gast', 'Martin Kober', 2019, 'Krimi', 'Kommissarin Brandt', '1', 'read', 7, 'paperback', 288),
    ('Die dritte Tür', 'Martin Kober', 2020, 'Krimi', 'Kommissarin Brandt', '2', 'read', 8, 'paperback', 302),
    ('Tod im Kurpark', 'Martin Kober', 2023, 'Krimi', 'Kommissarin Brandt', '4', '', None, 'ebook', 276),
    ('Gärtnern im Halbschatten', 'Ida Wendt', 2017, 'Ratgeber', '', '', 'read', 6, 'hardcover', 180),
    ('Die Sternenkarte', 'Leo Albrecht', 2021, 'Fantasy', 'Die Sternenkarte', '1', '', 9, 'hardcover', 520),
    ('Kleine Geschichte des Kaffees', 'Paula Reis', 2016, 'Sachbuch', '', '', 'read', 7, 'paperback', 210),
    ('Abends am Fjord', 'Henrike Paulsen', 2024, 'Roman', '', '', '', None, 'audiobook', None),
    ('Die Kunst des Wartens', 'Tobias Hain', 2022, 'Essay', '', '', '', None, 'paperback', 150),
]
with B.db() as c:
    bids = {}
    for i, (t, a, y, g, ser, no, stt, r, kind, pages) in enumerate(BOOKS):
        bid = B.insert(c, {'title': t, 'authors': a, 'year': y, 'genres': g, 'series': ser or None, 'series_no': no or None,
                           'publisher': 'Beispiel-Verlag', 'language': 'ger', 'pages': pages, 'source': 'demo',
                           'description': f'Ein erfundenes Beispielbuch von {a}.', '_people': [{'name': a, 'role': 'aut'}]})
        cover = image('film_images', f'demo-b{bid}.svg', t, a, 400, 600)
        c.execute('UPDATE books SET cover=?, created_at=? WHERE id=?', (cover, (datetime.now() - timedelta(days=40 - i * 3)).isoformat(timespec='seconds'), bid))
        B.add_copy(c, bid, {'kind': kind, 'path': f'/demo/Bücher/{t}.epub' if kind == 'ebook' else None})
        if stt == 'read':
            B.set_status(c, bid, 'read', days(20 + i * 30))
        elif stt:
            B.set_status(c, bid, stt)
        if r:
            B.set_rating(c, bid, r)
        bids[t] = bid
    B.set_next(c, bids['Die Sternenkarte'], True)
    B.set_next(c, bids['Tod im Kurpark'], True)

# ---------------------------------------------------------------- Verliehen und Merkliste
with L.db() as c:
    L.lend(c, 'film', fids['Die Uhrmacherin'], 'Die Uhrmacherin', 'Jana', lent_at=days(18))
    L.lend(c, 'book', bids['Das Haus am Deich'], 'Das Haus am Deich', 'Jana', lent_at=days(45), due_at=days(3))
    L.lend(c, 'music', music_ids['Sommerlicht'], 'Sommerlicht', 'Onkel Bernd', lent_at=days(120), subtitle='Die Abendband')
WL.add('movie', None, 'Die Glasbläserin', note='Tipp von Jana')
WL.add('tv', None, 'Inselarzt', note='läuft ab Herbst')

print(f'Beispiel-Sammlung angelegt in {DATA}: {len(MUSIC)} Alben, {len(FILMS)} Filme, {len(SERIES)} Serien, {len(BOOKS)} Bücher.')
