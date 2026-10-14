"""Datenbankdateien: Musik, Filme und Serien bekommen je eine eigene SQLite-Datei im Datenordner.
Ab 1.2 heisst die Musikdatenbank musik.db; eine alte musikdb.db wird beim ersten Start einmalig umbenannt,
vorher wird eine Sicherungskopie in data/backup/ angelegt."""
import logging, os, shutil
from datetime import datetime
from pathlib import Path

DB_FILES = {'musik': 'musik.db', 'filme': 'filme.db', 'serien': 'serien.db'}
LEGACY_MUSIC = 'musikdb.db'
_SIDECARS = ('-wal', '-shm', '-journal')


def sqlite_path(url):
    """Pfad aus einer sqlite-URL (sqlite:///relativ oder sqlite:////absolut), sonst None."""
    if not url or not url.startswith('sqlite:///'):
        return None
    return Path(url[len('sqlite:///'):])


def migrate_legacy(data_dir):
    """Alte musikdb.db -> musik.db. Gibt eine Meldung zurueck oder ''."""
    data_dir = Path(data_dir)
    old, new = data_dir / LEGACY_MUSIC, data_dir / DB_FILES['musik']
    if not old.exists() or new.exists():
        return ''
    bdir = data_dir / 'backup'
    bdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy2(old, bdir / f'musikdb-vor-1.2-{stamp}.db')
    for suf in _SIDECARS:
        side = Path(str(old) + suf)
        if side.exists():
            shutil.copy2(side, bdir / f'musikdb-vor-1.2-{stamp}.db{suf}')
    os.replace(old, new)
    for suf in _SIDECARS:
        side = Path(str(old) + suf)
        if side.exists():
            os.replace(side, Path(str(new) + suf))
    msg = f'Datenbank umbenannt: {LEGACY_MUSIC} -> {new.name} (Sicherung in {bdir})'
    logging.warning(msg)
    return msg


def music_db_url(data_dir, env_url=''):
    """URL der Musikdatenbank. Eine eingetragene DATABASE_URL gilt weiter; zeigt sie noch auf die alte musikdb.db
    im Datenordner (alte .env), wird automatisch musik.db verwendet."""
    data_dir = Path(data_dir)
    p = sqlite_path(env_url)
    if env_url and p is None:
        return env_url  # z. B. PostgreSQL
    if p is not None and p.name != LEGACY_MUSIC:
        return env_url
    if p is not None and p.parent.resolve() != data_dir.resolve():
        return env_url  # musikdb.db an anderem Ort: nicht anfassen
    migrate_legacy(data_dir)
    return f'sqlite:///{data_dir / DB_FILES["musik"]}'
