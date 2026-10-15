"""Dateizugriff fuer die Importe: normale Pfade ueber os, NAS-Pfade (/nas/<name>/...) ueber SMB (app/nas.py).
Die Funktionen verhalten sich wie ihre Vorbilder aus os/os.path/open; Fehler sind OSError."""
import builtins, os
from . import nas

is_nas = nas.is_nas


def walk(top):
    return nas.walk(top) if is_nas(top) else os.walk(top)


def listdir(path):
    return nas.listdir(path) if is_nas(path) else os.listdir(path)


def scandir(path):
    """Liste von (name, ist_ordner, ist_datei); Links werden wie bisher uebergangen."""
    if is_nas(path):
        return nas.scandir(path)
    out = []
    with os.scandir(path) as it:
        for e in it:
            try:
                if e.is_symlink():
                    continue
                out.append((e.name, e.is_dir(), e.is_file()))
            except OSError:
                continue
    return out


def isdir(path):
    return nas.isdir(path) if is_nas(path) else os.path.isdir(path)


def isfile(path):
    return nas.isfile(path) if is_nas(path) else os.path.isfile(path)


def exists(path):
    return (nas.isdir(path) or nas.isfile(path)) if is_nas(path) else os.path.exists(path)


def getsize(path):
    return nas.getsize(path) if is_nas(path) else os.path.getsize(path)


def open(path, mode='rb', encoding=None, errors=None):
    if is_nas(path):
        return nas.open_file(path, mode, encoding=encoding, errors=errors)
    return builtins.open(path, mode, encoding=encoding, errors=errors)


def read_text(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        return fh.read()


def media_url(path):
    """Pfad fuer ffprobe/ffmpeg: lokale Dateien unveraendert, NAS-Dateien ueber den HTTP-Vermittler."""
    return nas.media_url(path) if is_nas(path) else path


def mutagen_file(path, **kw):
    """mutagen.File fuer lokale und NAS-Dateien (die Tags werden dabei komplett gelesen)."""
    import mutagen
    if not is_nas(path):
        return mutagen.File(path, **kw)
    with open(path, 'rb') as fh:
        return mutagen.File(fh, **kw)
