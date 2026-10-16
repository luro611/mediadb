"""Mehrsprachigkeit: Deutsch ist die Quellsprache, Uebersetzungen stehen in locales/<sprache>.json.
Schluessel sind die deutschen Texte; ein Platzhalter § steht fuer eingesetzte Werte (Zahlen, Namen).
Fehlt eine Uebersetzung, wird der deutsche Text gezeigt."""
import json, re
from pathlib import Path
from markupsafe import Markup, escape

LANGS={'de':'Deutsch','en':'English','fr':'Français','es':'Español','it':'Italiano'}
DEFAULT='de'
_DIR=Path(__file__).parent/'locales'
_TABLES={}; _PATTERNS={}
def _load(lang):
    if lang in _TABLES: return _TABLES[lang]
    t={}
    f=_DIR/f'{lang}.json'
    if f.exists():
        try: t=json.loads(f.read_text(encoding='utf-8'))
        except Exception: t={}
    _TABLES[lang]=t
    pats=[]
    for k,v in t.items():
        if '§' in k:
            rx='^'+'(.+?)'.join(re.escape(p) for p in k.split('§'))+'$'
            pats.append((len(k),re.compile(rx,re.S),v))
    pats.sort(key=lambda x:-x[0]); _PATTERNS[lang]=pats
    return t
_EM=re.compile(r'\*([^*]+)\*')
def _fill(text,args):
    parts=text.split('§'); out=[escape(parts[0])]
    for i,p in enumerate(parts[1:]):
        out.append(escape(args[i]) if i<len(args) else ''); out.append(escape(p))
    res=Markup('').join(out)
    return Markup(_EM.sub(r'<em>\1</em>',res)) if '*' in text else res
def tr(lang,key,*args):
    """Text uebersetzen. Mit Argumenten: Platzhalter § der Reihe nach fuellen. Ohne Argumente darf der Text auch ein bereits
    zusammengesetzter Satz sein (z. B. eine Meldung aus dem Programm); dann wird er ueber die §-Muster erkannt."""
    if key is None: return Markup('')
    key=str(key); norm=' '.join(key.split())
    if lang!=DEFAULT and lang in LANGS:
        t=_load(lang)
        if norm in t: return _fill(t[norm],args)
        if not args:
            for _,rx,v in _PATTERNS.get(lang,[]):
                m=rx.match(norm)
                if m: return _fill(v,m.groups())
    return _fill(norm,args)
def _plain(text,args):
    text=text.replace('*','')
    parts=text.split('§'); out=parts[0]
    for i,p in enumerate(parts[1:]): out+=(str(args[i]) if i<len(args) else '')+p
    return out
def tr_text(lang,key,*args):
    """Wie tr, aber als einfacher Text ohne HTML-Maskierung (fuer JavaScript-Texte und Dialoge)."""
    if key is None: return ''
    norm=' '.join(str(key).split()); text=norm
    if lang!=DEFAULT and lang in LANGS:
        t=_load(lang)
        if norm in t: text=t[norm]
        elif not args:
            for _,rx,v in _PATTERNS.get(lang,[]):
                m=rx.match(norm)
                if m: return _plain(v,m.groups())
    text=text.replace('*','') if '*' in text else text
    parts=text.split('§'); out=parts[0]
    for i,p in enumerate(parts[1:]): out+=(str(args[i]) if i<len(args) else '')+p
    return out
