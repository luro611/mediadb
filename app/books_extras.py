"""Zusammenfassung und Bewertungen zu Buechern aus anderen Quellen (seit 1.6.1):
  - Inhaltstext des Verlags ueber die DNB (wenn noch keine Beschreibung da ist), sonst Beschreibung von Open Library
  - Einleitung des Wikipedia-Artikels zum Buch (CC BY-SA 4.0, mit Link)
  - Durchschnitt der Bewertungen bei Open Library
Laeuft im Hintergrund fuer alle Buecher ohne extras_at (nach dem Speichern, nach einem Import, kurz nach dem Start)."""
import logging, threading, time
from . import books_api as A
from . import books_db as B
from . import films_tmdb as T

JOB = {'state': 'idle', 'done': 0, 'total': 0, 'current': ''}
_lock = threading.Lock()


def fetch(b, force=False):
    """Alle Zusatzangaben zu einem Buch (dict-Zeile aus books). Nur Netz, keine Datenbank. Gibt dict fuer B.set_extras."""
    out = {}
    blurb, ol_key, work = b.get('blurb_url'), b.get('ol_key'), b.get('ol_work')
    if not blurb and b.get('dnb_id') and not b.get('description'):
        recs, _ = A.dnb_query(f'idn={b["dnb_id"]}', 1)  # aeltere Eintraege: Verweis auf den Inhaltstext nachholen
        if recs:
            blurb = recs[0].get('blurb_url')
            out['blurb_url'] = blurb
            if recs[0].get('toc_url') and not b.get('toc_url'):
                out['toc_url'] = recs[0]['toc_url']
    if not ol_key and b.get('isbn'):
        ol, _ = A.ol_isbn(b['isbn'])
        if ol and ol.get('ol_key'):
            ol_key = out['ol_key'] = ol['ol_key']
    if not b.get('description') or (force and b.get('description_src') in ('dnb', 'openlibrary')):
        text, src = A.describe({'blurb_url': blurb, 'ol_key': ol_key})
        if text:
            out['description'], out['description_src'] = text, src
    if not work and ol_key:
        work = A.ol_work_of(ol_key)
        if work:
            out['ol_work'] = work
    if work:
        out['ol_rating'], out['ol_rating_count'] = A.ol_rating(work)
    if b.get('wiki_url') != '-' or force:  # '-' heisst: Wikipedia-Text bewusst entfernt
        w = A.wiki_find(b.get('title'), b.get('authors'), b.get('original_title'), T.language()[:2] or 'de')
        if w:
            out.update(wiki_extract=w['extract'], wiki_url=w['url'], wiki_title=w['title'], wiki_lang=w['lang'])
        elif b.get('wiki_url') != '-':
            out.update(wiki_extract=None, wiki_url=None, wiki_title=None, wiki_lang=None)
    return out


def refresh_one(bid, force=True):
    with B.db() as c:
        b = B.get(c, bid)
    if not b:
        return 'Buch nicht gefunden.'
    data = fetch(dict(b), force=force)
    with B.db() as c:
        B.set_extras(c, bid, data)
    found = [x for x, k in (('Inhalt', 'description'), ('Wikipedia', 'wiki_extract'), ('Bewertung', 'ol_rating')) if data.get(k)]
    return 'Zusammenfassung und Bewertungen geladen.' if found else 'Keine weiteren Angaben gefunden.'


def run():
    with B.db() as c:
        ids = B.missing_extras(c)
    JOB.update(total=len(ids), done=0, current='')
    for bid in ids:
        with B.db() as c:
            b = B.get(c, bid)
        if not b:
            JOB['done'] += 1
            continue
        JOB['current'] = b['title']
        try:
            data = fetch(dict(b))
        except Exception:
            logging.exception('Zusatzangaben zu Buch %s', bid)
            data = {}
        with B.db() as c:
            if B.get(c, bid):
                B.set_extras(c, bid, data)
        JOB['done'] += 1


def start():
    """Startet den Lauf fuer alle Buecher ohne Zusatzangaben, falls nicht schon einer laeuft."""
    with _lock:
        if JOB['state'] == 'running':
            JOB['again'] = True
            return False
        JOB.update(state='running', again=False)

    def work():
        try:
            while True:
                run()
                with _lock:
                    if not JOB.get('again'):
                        JOB.update(state='idle', current='')
                        return
                    JOB['again'] = False
        except Exception:
            logging.exception('Zusatzangaben zu Buechern')
            JOB.update(state='idle', current='')
    threading.Thread(target=work, daemon=True).start()
    return True


def scheduler(delay=120):
    def loop():
        time.sleep(delay)
        try:
            with B.db() as c:
                if B.missing_extras(c, 1):
                    start()
        except Exception:
            logging.exception('Zusatzangaben zu Buechern (Start)')
    threading.Thread(target=loop, daemon=True).start()


def activity():
    if JOB['state'] == 'running' and JOB['total']:
        return {'label': 'Bücher: Zusammenfassungen und Bewertungen laden', 'net': True, 'files': False,
                'done': JOB['done'], 'total': JOB['total'], 'current': JOB['current'], 'url': '/books'}
