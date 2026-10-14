"""Volltextsuche fuer die Sammlung (SQLite FTS5 mit Trigramm-Zerlegung).
Pro Eintrag (media.id) steht ein Suchtext im Index: Albumfelder plus alle Titel und Titel-Interpreten.
Trigramme finden beliebige Teilwoerter ab 3 Zeichen ("lied" findet "Liebeslied"), wie die fruehere LIKE-Suche,
nur mit Index. Kuerzere Suchwoerter laufen weiter ueber LIKE (siehe main.py).
Funktioniert nur mit SQLite; bei anderen Datenbanken bleibt ENABLED False und die LIKE-Suche wird benutzt."""
import logging

TABLE = 'search_media_v1'  # bei geaendertem Aufbau neuen Namen waehlen, dann wird neu aufgebaut
FIELDS = ('title', 'artist', 'barcode', 'genre', 'tags', 'styles', 'label', 'catalog_number', 'notes', 'year',
          'release_date', 'file_formats')
MIN_LEN = 3
ENABLED = False
SEP = " || ' | ' || "


def _body_sql(where=''):
    m = SEP.join(f"coalesce(m.{f},'')" for f in FIELDS)
    t = ("coalesce((SELECT group_concat(coalesce(t.title,'') || ' | ' || coalesce(t.artist,''), ' | ') "
         "FROM tracks t WHERE t.medium_id=m.id),'')")
    return f"INSERT INTO {TABLE}(rowid, body) SELECT m.id, {m}{SEP}{t} FROM media m {where}"


def _exec(conn, sql, params=None):
    """Funktioniert mit sqlite3-Verbindungen und mit SQLAlchemy-Verbindungen."""
    if hasattr(conn, 'exec_driver_sql'):
        return conn.exec_driver_sql(sql, params) if params else conn.exec_driver_sql(sql)
    return conn.execute(sql, params or ())


def setup(conn):
    """Index anlegen und bei Bedarf (neu) aufbauen. Gibt True zurueck, wenn die Volltextsuche verfuegbar ist."""
    global ENABLED
    try:
        _exec(conn, f"CREATE VIRTUAL TABLE IF NOT EXISTS {TABLE} USING fts5(body, tokenize='trigram')")
        n_media = _exec(conn, 'SELECT count(*) FROM media').fetchone()[0]
        n_idx = _exec(conn, f'SELECT count(*) FROM {TABLE}').fetchone()[0]
        if n_media != n_idx:
            rebuild(conn)
            logging.warning('Suchindex aufgebaut: %s Einträge', n_media)
        ENABLED = True
    except Exception:
        logging.exception('Volltextsuche nicht verfügbar, Suche läuft ohne Index')
        ENABLED = False
    return ENABLED


def rebuild(conn):
    _exec(conn, f'DELETE FROM {TABLE}')
    _exec(conn, _body_sql())


def refresh(conn, ids):
    """Suchtext fuer diese Eintraege neu schreiben (geloeschte verschwinden aus dem Index)."""
    ids = sorted({int(i) for i in ids if i is not None})
    for k in range(0, len(ids), 500):
        part = ids[k:k + 500]
        marks = ','.join('?' * len(part))
        _exec(conn, f'DELETE FROM {TABLE} WHERE rowid IN ({marks})', tuple(part))
        _exec(conn, _body_sql(f'WHERE m.id IN ({marks})'), tuple(part))


def match_expr(tokens):
    """Suchwoerter (je mindestens 3 Zeichen) als FTS5-Ausdruck: alle muessen vorkommen."""
    return ' AND '.join('"' + t.replace('"', '""') + '"' for t in tokens)

