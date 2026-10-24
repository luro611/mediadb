"""Bereich Buecher: Seiten und Aktionen unter /books (Starlette-App, in main.py eingehaengt)."""
import json, os, re
from urllib.parse import quote, urlencode
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.routing import Route
from . import books_db as B
from . import books_api as A
from . import books_files as X
from . import books_extras as BE
from . import films_web as FW
from . import fs
from . import users as U
from .films_art import MAX_UPLOAD

templates = None
ctx = None
IMAGES = None
PAGE = 120
go = FW.go
_int = FW._int
_form = FW._form
VIEW_NAMES = {'all': 'Alle', 'next': 'Als Nächstes', 'unread': 'Ungelesen', 'reading': 'Lese ich gerade', 'read': 'Gelesen', 'favorites': 'Lieblingsbücher',
              'recent_read': 'Zuletzt gelesen', 'recent_added': 'Zuletzt hinzugefügt', 'ebooks': 'E-Books', 'audiobooks': 'Hörbücher'}
SORT_NAMES = {'author': 'Autor', 'title': 'Titel', 'year': 'Jahr', 'rating': 'Bewertung', 'added': 'Hinzugefügt'}
# Felder, die ein Kandidat als JSON im Formular mitbringt (keine grossen Texte)
CAND_KEYS = ['isbn', 'title', 'subtitle', 'original_title', 'authors', '_people', 'publisher', 'place', 'year', 'edition', 'pages',
             'language', 'series', 'series_no', 'genres', 'subjects', 'dnb_id', 'ol_key', 'source', '_cover_id', '_kind']


def setup(templates_, ctx_, data_dir, start_scheduler=True):
    global templates, ctx, IMAGES
    templates, ctx = templates_, ctx_
    IMAGES = os.path.join(str(data_dir), 'film_images')  # gleiche Bildablage, Dateinamen beginnen mit 'b'
    os.makedirs(IMAGES, exist_ok=True)
    B.init(os.path.join(str(data_dir), 'buecher.db'))
    templates.env.globals.update(BOOK_KINDS=B.KINDS, BOOK_ROLES=B.ROLES, BOOK_STATUS=B.STATUS, BOOK_LANGS=B.LANG_NAMES,
                                 BOOK_RATING_LABELS=B.RATING_LABELS)
    templates.env.filters['isbn'] = B.isbn_pretty
    if start_scheduler:
        BE.scheduler()
    templates.env.filters['hours'] = lambda s: (f'{int(s) // 3600}:{int(s) % 3600 // 60:02d} h' if s else '')


def render(request, tpl, **kw):
    return templates.TemplateResponse(request, tpl, ctx(request, area="books", **kw))


def cand_json(c):
    return json.dumps({k: c.get(k) for k in CAND_KEYS if c.get(k) not in (None, '', [])}, ensure_ascii=False)


# ---------------------------------------------------------------- Uebersicht
async def index(request):
    p = request.query_params
    view = p.get('view') if p.get('view') in VIEW_NAMES else 'all'
    sort = p.get('sort') if p.get('sort') in SORT_NAMES else 'author'
    direction = 'desc' if p.get('dir') == 'desc' else 'asc'
    q, genre, kind, lang = p.get('q', '').strip(), p.get('genre', ''), p.get('kind', ''), p.get('lang', '')
    letter = p.get('l', '') if p.get('l', '') == '#' or (len(p.get('l', '')) == 1 and 'A' <= p.get('l', '') <= 'Z') else ''
    page = max(1, _int(p.get('page'), 1))
    owner = U.owner_filter(p.get('owner', ''))
    own = p.get('owner', '') if owner[0] else ''

    def load():
        with B.db() as c:
            rows, total = B.query(c, view, q, genre, kind, lang, sort, direction, PAGE, (page - 1) * PAGE, letter, owner)
            return dict(rows=[dict(r) for r in rows], total=total, counts=B.view_counts(c), genres=B.genres(c), book_langs=B.languages(c),
                        letters=B.letter_counts(c, sort), authors_hits=[dict(x) for x in B.find_authors(c, q)] if len(q) >= 3 else [])
    d = await run_in_threadpool(load)
    keep = {k: v for k, v in dict(q=q, genre=genre, kind=kind, lang=lang, sort=sort if sort != 'author' else '',
                                  dir=direction if direction != 'asc' else '', l=letter, owner=own).items() if v}

    def url(**kw):
        x = {**keep, 'view': view if view != 'all' else ''}
        x.update(kw)
        return '/books?' + urlencode({k: v for k, v in x.items() if v not in ('', None)})
    return render(request, 'books_list.html', view=view, q=q, genre=genre, kind=kind, lang=lang, sort=sort, dir=direction,
                  letter=letter, url=url, page=page, pages=(d['total'] + PAGE - 1) // PAGE, view_names=VIEW_NAMES,
                  sort_names=SORT_NAMES, abc=['#'] + [chr(x) for x in range(65, 91)], filtered=bool(q or genre or kind or lang or own),
                  owner=own, message=p.get('message', ''), **d)


async def series_page(request):
    name = request.query_params.get('name', '')

    def load():
        with B.db() as c:
            if name:
                books = [dict(r) for r in B.series_books(c, name)]
                return dict(name=name, books=books, gaps=B.series_gaps([b['series_sort'] for b in books]))
            rows = []
            for r in B.series_list(c):
                nos = [float(x) for x in (r['nos'] or '').split(',') if x]
                rows.append(dict(r, gaps=B.series_gaps(nos)))
            return dict(name='', series=rows)
    return render(request, 'books_series.html', **await run_in_threadpool(load))


# ---------------------------------------------------------------- Hinzufuegen
async def add_page(request):
    return render(request, 'books_add.html', message=request.query_params.get('message', ''), kinds=B.KINDS)


async def scan(request):
    f, _ = await _form(request)
    isbn = B.norm_isbn(f.get('isbn'))
    kind = f.get('kind') if f.get('kind') in B.KINDS else ''
    if not isbn:
        return go('/books/add', 'Das ist keine gültige ISBN.')

    def work():
        with B.db() as c:
            local = [dict(r) for r in B.by_isbn(c, isbn)]
        if local:
            return dict(local=local, cands=[], err=None)
        d, err = A.lookup_isbn(isbn, with_description=False)
        if d:
            d['cover_url'] = A.cover_url(d.get('_cover_id'), 'M')
        return dict(local=[], cands=[d] if d else [], err=err)
    r = await run_in_threadpool(work)
    if not kind and r['cands']:
        kind = r['cands'][0].get('_kind') or ''
    return render(request, 'books_candidates.html', isbn=isbn, kind=kind or 'paperback', kinds=B.KINDS, query='', author='',
                  attach=None, cand_json=cand_json, **r)


async def search(request):
    p = request.query_params
    q, author, attach = p.get('q', '').strip(), p.get('author', '').strip(), _int(p.get('attach'))
    kind = p.get('kind') if p.get('kind') in B.KINDS else 'paperback'

    def work():
        cands, err = A.search(title=q, author=author) if (q or author) else ([], None)
        with B.db() as c:
            have = {r[0]: r[1] for r in c.execute('SELECT isbn, id FROM books WHERE isbn IS NOT NULL')}
            b = dict(B.get(c, attach)) if attach and B.get(c, attach) else None
        for x in cands:
            x['have'] = have.get(x.get('isbn'))
        return cands, err, b
    cands, err, b = await run_in_threadpool(work)
    return render(request, 'books_candidates.html', isbn=B.norm_isbn(p.get('isbn')), kind=kind, kinds=B.KINDS, local=[], cands=cands,
                  err=err, query=q, author=author, attach=b, cand_json=cand_json)


def _cand_from_form(f):
    try:
        d = json.loads(f.get('data') or '{}')
    except ValueError:
        d = {}
    return {k: v for k, v in d.items() if k in CAND_KEYS}


async def save(request):
    f, _ = await _form(request)
    d = _cand_from_form(f)
    if not d.get('title'):
        return go('/books/add', 'Kein Buch ausgewählt.')

    def work():
        full = d
        if d.get('isbn'):
            x, _ = A.lookup_isbn(d['isbn'], with_description=True)
            full = A.merge(x, d) if x else d
        elif d.get('ol_key'):
            full = dict(d, description=A.ol_description(d['ol_key']), description_src='openlibrary')
        with B.db() as c:
            existed = bool(full.get('isbn') and B.by_isbn(c, full['isbn']))
            bid, new = X.save_book(c, full, IMAGES)
            kind = f.get('kind') if f.get('kind') in B.KINDS else (full.get('_kind') or 'paperback')
            B.add_copy(c, bid, {'kind': kind, 'isbn': B.norm_isbn(f.get('isbn')) or full.get('isbn'), 'edition': f.get('edition')})
            return bid, ('Exemplar zum vorhandenen Buch hinzugefügt.' if existed else 'Gespeichert.')
    bid, msg = await run_in_threadpool(work)
    BE.start()
    return go(f'/books/{bid}', msg)


async def manual(request):
    f, _ = await _form(request)
    if not f.get('title'):
        return go('/books/add', 'Bitte einen Titel eingeben.')

    def work():
        people = [{'name': x.strip(), 'role': 'aut'} for x in re.split(r';|\s+und\s+|&', f.get('authors') or '') if x.strip()]
        data = {'title': f['title'], 'authors': '; '.join(p['name'] for p in people) or None, '_people': people,
                'year': _int(f.get('year')), 'publisher': f.get('publisher'), 'isbn': B.norm_isbn(f.get('isbn')) or None,
                'series': f.get('series'), 'series_no': f.get('series_no'), 'description': f.get('description'), 'source': 'manual',
                'description_src': 'manual' if f.get('description') else None}
        with B.db() as c:
            bid = B.insert(c, data)
            B.add_copy(c, bid, {'kind': f.get('kind'), 'isbn': data['isbn']})
            return bid
    bid = await run_in_threadpool(work)
    BE.start()
    return go(f'/books/{bid}', 'Gespeichert.')


# ---------------------------------------------------------------- Detail
async def detail(request):
    bid = request.path_params['bid']

    def load():
        with B.db() as c:
            b = B.get(c, bid)
            if not b:
                return None
            b = dict(b)
            series = [dict(r) for r in B.series_books(c, b['series'])] if b['series'] else []
            return dict(b=b, people=B.people_of(c, bid), copies=[dict(k) for k in B.copies_of(c, bid)], series_books=series)
    d = await run_in_threadpool(load)
    if not d:
        return go('/books', 'Buch nicht gefunden.')
    return render(request, 'books_detail.html', message=request.query_params.get('message', ''), kinds=B.KINDS,
                  host_label=FW.au.host_label, **d)


def _action(fn):
    async def handler(request):
        bid = request.path_params['bid']
        f, raw = await _form(request)

        def do():
            with B.db() as c:
                if not B.get(c, bid):
                    return 'Buch nicht gefunden.'
                return fn(c, bid, f)
        msg = await run_in_threadpool(do)
        anchor = f.get('anchor', '')
        return go(f'/books/{bid}' + ('#' + anchor if re.fullmatch(r'[A-Za-z0-9_-]+', anchor or '') else ''), msg or '')
    return handler


def _status(c, bid, f):
    s = f.get('status', '')
    if s == 'read' and f.get('date') is not None and f.get('date') != '':
        when = B.parse_date(f.get('date'))
        if when is None:
            return 'Datum nicht erkannt. Bitte TT.MM.JJJJ, MM.JJJJ oder JJJJ eingeben.'
        B.set_status(c, bid, 'read', when)
    else:
        B.set_status(c, bid, s)
    return 'Gespeichert.'


def _read_date(c, bid, f):
    when = B.parse_date(f.get('date'))
    if when is None:
        return 'Datum nicht erkannt. Bitte TT.MM.JJJJ, MM.JJJJ oder JJJJ eingeben.'
    B.set_read_date(c, bid, when)
    return 'Datum gespeichert.'


def _rating(c, bid, f):
    B.set_rating(c, bid, f.get('rating'))
    return 'Bewertung gespeichert.' if f.get('rating') else 'Bewertung entfernt.'


def _notes(c, bid, f):
    B.update(c, bid, {'notes': f.get('notes', '')})
    return 'Notiz gespeichert.'


def _copy_add(c, bid, f):
    B.add_copy(c, bid, f)
    return 'Exemplar hinzugefügt.'


def _edit(c, bid, f):
    if not f.get('title'):
        return 'Bitte einen Titel eingeben.'
    people = [{'name': x.strip(), 'role': 'aut'} for x in re.split(r';', f.get('authors') or '') if x.strip()]
    old = B.people_of(c, bid)
    # nur Felder aendern, die das Formular wirklich mitschickt; fehlende bleiben, wie sie sind
    data = {k: (f.get(k) or '').strip() for k in ('title', 'subtitle', 'original_title', 'publisher', 'place', 'edition', 'series',
                                                  'series_no', 'genres', 'description', 'notes', 'language') if k in f}
    for k in ('year', 'pages'):
        if k in f:
            data[k] = _int(f.get(k))
    if 'isbn' in f:
        data['isbn'] = B.norm_isbn(f.get('isbn')) or None
    if 'authors' in f:
        data['authors'] = '; '.join(p['name'] for p in people) or None
    if 'description' in data:
        cur = B.get(c, bid)
        if (cur['description'] or '') != data['description']:
            data['description_src'] = 'manual' if data['description'] else None
    B.update(c, bid, data)
    if 'authors' in f:
        others = [dict(p, role=r) for r, lst in old.items() if r != 'aut' for p in lst]
        B.set_people(c, bid, people + others)
    return 'Gespeichert.'


def _refresh(c, bid, f):
    b = B.get(c, bid)
    if not b['isbn']:
        return 'Ohne ISBN lässt sich nichts nachladen. Bitte über „Anderes Buch zuordnen“ suchen.'
    d, err = A.lookup_isbn(b['isbn'])
    if not d:
        return err or 'Nichts gefunden.'
    B.update(c, bid, d, only_empty=True)
    if not b['cover']:
        img = A.fetch_cover(d.get('_cover_id'), b['isbn'] if not d.get('_cover_id') else None)
        if img:
            X.save_cover(c, IMAGES, bid, img)
    return 'Leere Felder ergänzt.'


async def rematch(request):
    bid = request.path_params['bid']
    f, _ = await _form(request)
    d = _cand_from_form(f)

    def do():
        full = d
        if d.get('isbn'):
            x, _ = A.lookup_isbn(d['isbn'])
            full = A.merge(x, d) if x else d
        with B.db() as c:
            if not B.get(c, bid) or not full.get('title'):
                return 'Kein Buch ausgewählt.'
            other = B.by_isbn(c, full['isbn']) if full.get('isbn') else []
            other = [o for o in other if o['id'] != bid]
            if other:  # gibt es schon: Exemplare dorthin, Lesestand mitnehmen
                oid = other[0]['id']
                cur = B.get(c, bid)
                c.execute('UPDATE copies SET book_id=? WHERE book_id=?', (oid, bid))
                c.execute('''UPDATE books SET status=CASE WHEN status='' THEN ? ELSE status END, read_at=coalesce(read_at, ?),
                             read_count=max(read_count, ?), rating=coalesce(rating, ?), notes=coalesce(notes, ?) WHERE id=?''',
                          (cur['status'], cur['read_at'], cur['read_count'], cur['rating'], cur['notes'], oid))
                B.delete(c, bid)
                X.remove_covers(IMAGES, bid)
                return f'merged:{oid}'
            keep = {k: full.get(k) for k in B.BOOK_FIELDS if k not in ('notes', 'cover')}
            B.update(c, bid, keep)
            c.execute('''UPDATE books SET extras_at=NULL, wiki_extract=NULL, wiki_url=NULL, wiki_title=NULL, wiki_lang=NULL,
                         ol_rating=NULL, ol_rating_count=NULL WHERE id=?''', (bid,))
            if full.get('_people'):
                B.set_people(c, bid, full['_people'])
            img = A.fetch_cover(full.get('_cover_id'), full.get('isbn') if not full.get('_cover_id') else None)
            if img:
                X.save_cover(c, IMAGES, bid, img)
            return 'Neu zugeordnet und alle Angaben übernommen.'
    msg = await run_in_threadpool(do)
    BE.start()
    if msg.startswith('merged:'):
        return go('/books/' + msg[7:], 'Das Buch war schon vorhanden; die Exemplare wurden dorthin verschoben.')
    return go(f'/books/{bid}', msg)


async def copy_delete(request):
    cid = request.path_params['cid']

    def do():
        with B.db() as c:
            r = c.execute('SELECT book_id FROM copies WHERE id=?', (cid,)).fetchone()
            if r:
                c.execute('DELETE FROM copies WHERE id=?', (cid,))
            return r[0] if r else None
    bid = await run_in_threadpool(do)
    return go(f'/books/{bid}#exemplare' if bid else '/books', 'Exemplar entfernt.')


async def copy_owner(request):
    """Besitzer eines Exemplars aendern (seit 1.21); leer = Haushalt."""
    cid = request.path_params['cid']
    f, _ = await _form(request)
    ok, uid = U.parse_owner(f.get('owner', ''))

    def do():
        with B.db() as c:
            r = c.execute('SELECT book_id FROM copies WHERE id=?', (cid,)).fetchone()
            if r and ok:
                c.execute('UPDATE copies SET owner_id=? WHERE id=?', (uid, cid))
            return r[0] if r else None
    pid = await run_in_threadpool(do)
    return go(f'/books/{pid}#exemplare' if pid else '/books', 'Besitzer gespeichert.' if ok else 'Unbekannter Besitzer.')


async def delete(request):
    bid = request.path_params['bid']

    def do():
        with B.db() as c:
            B.delete(c, bid)
        X.remove_covers(IMAGES, bid)
    await run_in_threadpool(do)
    return go('/books', 'Buch gelöscht.')


async def edit_page(request):
    bid = request.path_params['bid']

    def load():
        with B.db() as c:
            b = B.get(c, bid)
            return dict(b) if b else None
    b = await run_in_threadpool(load)
    return render(request, 'books_edit.html', b=b) if b else go('/books', 'Buch nicht gefunden.')


# ---------------------------------------------------------------- Titelbild
async def cover_page(request):
    bid = request.path_params['bid']

    def load():
        with B.db() as c:
            b = B.get(c, bid)
            files = [dict(k) for k in B.copies_of(c, bid) if k['path']]
        return dict(b=dict(b), has_files=bool(files)) if b else None
    d = await run_in_threadpool(load)
    return render(request, 'books_cover.html', message=request.query_params.get('message', ''), **d) if d else go('/books')


async def cover_set(request):
    bid = request.path_params['bid']
    f, _ = await _form(request)

    def do():
        with B.db() as c:
            b = B.get(c, bid)
            if f.get('source') == 'remove':
                X.remove_covers(IMAGES, bid)
                B.update(c, bid, {'cover': None})
                return 'Bild entfernt.'
            if f.get('source') == 'file':
                for k in B.copies_of(c, bid):
                    if k['path']:
                        it = {'kind': k['kind'], 'path': k['path'], 'files': None}
                        if k['kind'] == 'audiobook' and fs.isdir(k['path']):
                            it['files'] = sorted(os.path.join(k['path'], x) for x in fs.listdir(k['path'])
                                                 if os.path.splitext(x)[1].lower() in X.AUDIO_EXT)
                        elif k['kind'] == 'audiobook':
                            it['files'] = [k['path']]
                        img = X.local_cover(it)
                        if img and X.save_cover(c, IMAGES, bid, img):
                            return 'Bild gespeichert.'
                return 'Kein Bild gefunden.'
            img = None
            if b['isbn']:
                d, _ = A.ol_isbn(b['isbn'])
                img = A.fetch_cover((d or {}).get('_cover_id'), b['isbn'])
            return 'Bild gespeichert.' if img and X.save_cover(c, IMAGES, bid, img) else 'Kein Bild gefunden.'
    return go(f'/books/{bid}/cover', await run_in_threadpool(do))


async def cover_upload(request):
    bid = request.path_params['bid']
    form = await request.form(max_files=1, max_part_size=MAX_UPLOAD + 1024)
    up = form.get('file')
    data = await up.read(MAX_UPLOAD + 1) if up and hasattr(up, 'read') else b''
    if len(data) > MAX_UPLOAD:
        return go(f'/books/{bid}/cover', 'Die Datei ist zu groß (höchstens 15 MB).')

    def do():
        with B.db() as c:
            return 'Bild gespeichert.' if X.save_cover(c, IMAGES, bid, data) else 'Das ist keine Bilddatei (JPG, PNG oder WebP).'
    return go(f'/books/{bid}/cover', await run_in_threadpool(do))


# ---------------------------------------------------------------- Autoren
async def author_page(request):
    aid = request.path_params['aid']

    def load():
        with B.db() as c:
            a = B.get_author(c, aid)
            if not a:
                return None
            return dict(a=dict(a), books=[dict(r) for r in B.books_by_author(c, aid)])
    d = await run_in_threadpool(load)
    return render(request, 'books_author.html', **d) if d else go('/books', 'Person nicht gefunden.')


# ---------------------------------------------------------------- Import aus Ordnern und Listen
async def files_page(request):
    items = X.JOB['items'] if X.JOB['state'] == 'ready' else []
    groups = {k: [i for i in items if i['status'] == k] for k in ('unsure', 'nf', 'match', 'known')}
    roots = [{'path': c, 'label': h} for c, h, _ in FW.au.available_roots()]
    return render(request, 'books_files.html', job=X.JOB, groups=groups, roots=roots, host_label=FW.au.host_label, kinds=B.KINDS,
                  message=request.query_params.get('message', ''), cand_cover=A.cover_url)


async def files_scan(request):
    f, raw = await _form(request)
    fl = []
    for x in list(raw.getlist('folders')) + [y for y in (f.get('manual') or '').split('\n') if y.strip()]:
        p = FW.au.safe_dir(FW.au.to_container_path(str(x), FW.HOST_HOME))
        if p and p not in fl:
            fl.append(p)
    if not fl:
        return go('/books/files', 'Kein gültiger Ordner ausgewählt.')
    audio = f.get('audio') == '1'
    X.JOB.update(folders=fl, done=0, total=0, items=[], error='', result=None, audio=audio, unreadable=[])
    X.start(X.scan_worker, fl, audio)
    return go('/books/files')


async def list_scan(request):
    form = await request.form(max_files=1, max_part_size=MAX_UPLOAD + 1024)
    up = form.get('file')
    data = await up.read(MAX_UPLOAD + 1) if up and hasattr(up, 'read') else b''
    name = getattr(up, 'filename', '') or ''
    text = (form.get('isbns') or '').strip()
    kind = form.get('kind') if form.get('kind') in B.KINDS else 'paperback'
    if len(data) > MAX_UPLOAD:
        return go('/books/files', 'Die Datei ist zu groß (höchstens 15 MB).')
    try:
        rows = await run_in_threadpool(X.read_table, name, data) if data else await run_in_threadpool(X.read_table, 'liste.txt', text)
    except Exception:
        return go('/books/files', 'Die Datei konnte nicht gelesen werden (CSV, Excel oder eine ISBN je Zeile).')
    if not rows:
        return go('/books/files', 'Keine Bücher in der Liste gefunden.')
    X.JOB.update(folders=[], done=0, total=0, items=[], error='', result=None)
    X.start_table(X.table_scan_worker, rows, kind)
    return go('/books/files')


async def files_apply(request):
    if X.JOB['state'] != 'ready':
        return go('/books/files')
    f, raw = await _form(request)
    choices = {int(k[2:]): str(v) for k, v in raw.multi_items() if k.startswith('d_') and k[2:].isdigit()}
    if X.JOB.get('source') == 'table':
        kinds = {int(k[2:]): str(v) for k, v in raw.multi_items() if k.startswith('k_') and k[2:].isdigit()}
        X.start_table(X.table_apply_worker, choices, kinds, IMAGES)
    else:
        X.start(X.apply_worker, choices, IMAGES)
    return go('/books/files')


async def files_status(request):
    return JSONResponse({'state': X.JOB['state'], 'done': X.JOB['done'], 'total': X.JOB['total'], 'phase': X.JOB.get('phase', ''),
                         'found': X.JOB.get('found', 0), 'current': X.JOB.get('current') or ''})


async def files_reset(request):
    if X.JOB['state'] not in ('scanning', 'applying'):
        X.JOB.update(state='idle', items=[], error='', result=None, done=0, total=0)
    return go('/books/files')


def activity():
    return [x for x in (_import_activity(), BE.activity()) if x] or None


def _import_activity():
    j = X.JOB
    if j['state'] in ('scanning', 'applying'):
        files = j.get('source') == 'files' and (j['state'] == 'applying' or j.get('phase') in ('collect', 'read'))
        label = {'collect': 'Bücher: Ordner durchsuchen', 'read': 'Bücher: Dateien lesen', 'match': 'Bücher: bei DNB und Open Library suchen',
                 'apply': 'Bücher: übernehmen und Titelbilder laden'}.get(j.get('phase'), 'Bücher: Import')
        return {'label': label, 'files': files, 'net': j.get('phase') in ('match', 'apply'), 'done': j['done'], 'total': j['total'],
                'current': j.get('current') if j.get('phase') != 'collect' else '',
                'note': ('§ Bücher gefunden', j.get('found', 0)) if j.get('phase') == 'collect' else None, 'url': '/books/files'}


async def extras(request):
    bid = request.path_params['bid']
    msg = await run_in_threadpool(BE.refresh_one, bid)
    return go(f'/books/{bid}#quellen', msg)


def _wiki_remove(c, bid, f):
    c.execute("UPDATE books SET wiki_extract=NULL, wiki_url='-', wiki_title=NULL, wiki_lang=NULL WHERE id=?", (bid,))
    return 'Wikipedia-Text entfernt.'


routes = [
    Route('/', index), Route('/series', series_page), Route('/add', add_page), Route('/scan', scan, methods=['POST']),
    Route('/search', search), Route('/save', save, methods=['POST']), Route('/manual', manual, methods=['POST']),
    Route('/files', files_page), Route('/files/browse', FW.files_browse), Route('/files/scan', files_scan, methods=['POST']),
    Route('/files/list', list_scan, methods=['POST']), Route('/files/apply', files_apply, methods=['POST']),
    Route('/files/status', files_status), Route('/files/reset', files_reset, methods=['POST']),
    Route('/copies/{cid:int}/delete', copy_delete, methods=['POST']), Route('/copies/{cid:int}/owner', copy_owner, methods=['POST']), Route('/author/{aid:int}', author_page),
    Route('/{bid:int}', detail), Route('/{bid:int}/edit', edit_page), Route('/{bid:int}/edit', _action(_edit), methods=['POST']),
    Route('/{bid:int}/status', _action(_status), methods=['POST']), Route('/{bid:int}/read-date', _action(_read_date), methods=['POST']),
    Route('/{bid:int}/rating', _action(_rating), methods=['POST']), Route('/{bid:int}/notes', _action(_notes), methods=['POST']),
    Route('/{bid:int}/copies', _action(_copy_add), methods=['POST']), Route('/{bid:int}/refresh', _action(_refresh), methods=['POST']),
    Route('/{bid:int}/rematch', rematch, methods=['POST']), Route('/{bid:int}/extras', extras, methods=['POST']),
    Route('/{bid:int}/wiki-remove', _action(_wiki_remove), methods=['POST']), Route('/{bid:int}/delete', delete, methods=['POST']),
    Route('/{bid:int}/cover', cover_page), Route('/{bid:int}/cover/set', cover_set, methods=['POST']),
    Route('/{bid:int}/cover/upload', cover_upload, methods=['POST']),
]
app = Starlette(routes=routes)
