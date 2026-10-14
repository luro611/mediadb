import os, json, re, time, threading, logging, unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from types import SimpleNamespace
import requests
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, select, or_, func, case, inspect, text, event, literal_column
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from openpyxl import Workbook, load_workbook
from io import BytesIO
from . import audio as au
from . import i18n
from . import storage, search
from . import security as sec
from functools import partial

BASE=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('DATA_DIR',BASE/'data')); DATA.mkdir(exist_ok=True); (DATA/'covers').mkdir(exist_ok=True)
DB_URL=storage.music_db_url(DATA,os.getenv('DATABASE_URL','').strip())  # seit MediaDB 1.0: data/musik.db (alte musikdb.db wird uebernommen)
IS_SQLITE=DB_URL.startswith('sqlite')
engine=create_engine(DB_URL, connect_args={'check_same_thread':False,'timeout':15} if IS_SQLITE else {})
Session=sessionmaker(bind=engine); Base=declarative_base()
class Medium(Base):
 __tablename__='media'
 id=Column(Integer,primary_key=True); barcode=Column(String,index=True,unique=True); title=Column(String,nullable=False); artist=Column(String); artist_sort=Column(String); artist_mbid=Column(String); year=Column(String); date=Column(String); release_date=Column(String); ownership=Column(String); file_formats=Column(String); country=Column(String); label=Column(String); catalog_number=Column(String); format=Column(String); media_count=Column(Integer); disc_count=Column(Integer); track_count=Column(Integer); status=Column(String); packaging=Column(String); language=Column(String); script=Column(String); release_mbid=Column(String); release_group_mbid=Column(String); release_group_type=Column(String); asin=Column(String); annotation=Column(Text); disambiguation=Column(String); quality=Column(String); genre=Column(Text); genres=Column(Text); tags=Column(Text); styles=Column(Text); notes=Column(Text); cover_path=Column(String); cover_url=Column(String); source=Column(String); source_id=Column(String); created_at=Column(DateTime,default=datetime.utcnow); raw_json=Column(Text)
 tracks=relationship('Track',back_populates='medium',cascade='all, delete-orphan',order_by='Track.disc_number,Track.position')
class Track(Base):
 __tablename__='tracks'; id=Column(Integer,primary_key=True); medium_id=Column(Integer,ForeignKey('media.id')); position=Column(Integer); disc_number=Column(Integer); number=Column(String); title=Column(String); length_ms=Column(Integer); duration=Column(String); recording_mbid=Column(String); artist=Column(String); medium=relationship('Medium',back_populates='tracks')
class AudioFile(Base):
 __tablename__='audio_files'; id=Column(Integer,primary_key=True); path=Column(String,unique=True,index=True); fmt=Column(String); artist=Column(String); album=Column(String); title=Column(String); track_no=Column(Integer); disc_no=Column(Integer); length_s=Column(Integer); medium_id=Column(Integer,ForeignKey('media.id'),index=True)
Base.metadata.create_all(engine)
@event.listens_for(Session,'after_flush')
def _search_index_update(session,flush_ctx):
 """Suchindex fuer geaenderte Eintraege nachziehen (gleiche Transaktion wie die Aenderung)."""
 if not search.ENABLED: return
 ids=set()
 for o in list(session.new)+list(session.dirty)+list(session.deleted):
  st=inspect(o)  # nur bereits geladene Werte lesen, nichts nachladen (geloeschte Zeilen!)
  if isinstance(o,Medium): ids.add(st.dict.get('id') or (st.identity or (None,))[0])
  elif isinstance(o,Track): ids.add(st.dict.get('medium_id'))
 ids.discard(None)
 if ids: search.refresh(session.connection(),ids)
SEC=sec.Settings(DATA)
app=FastAPI(title='MediaDB'); app.add_middleware(sec.Gate,settings=SEC); app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static'); app.mount('/covers',StaticFiles(directory=str(DATA/'covers')),name='covers'); templates=Jinja2Templates(directory=str(BASE/'app/templates'))
lock=threading.Lock(); last_mb=0.0
templates.env.globals['asset_v']=int((BASE/'static'/'style.css').stat().st_mtime)

def clean_barcode(x): return re.sub(r"^'+",'',str(x or '').strip())
def duration(ms):
 if not ms:return ''
 return f'{int(ms)//60000}:{int(ms)//1000%60:02d}'
def artist_credit(a): return ''.join(x.get('name') or x.get('artist',{}).get('name','') for x in a or []) or ''
def parse_release(r, barcode=''):
 ac=r.get('artist-credit',[]); rg=r.get('release-group') or {}; media=r.get('media',[]); tracks=[]
 for m in media:
  for t in m.get('tracks',[]):
   rec=t.get('recording') or {}; ms=t.get('length') or rec.get('length')
   tracks.append({'position':t.get('position'),'disc_number':m.get('position',1),'number':t.get('number',''),'title':t.get('title') or rec.get('title',''),'length_ms':ms,'duration':duration(ms),'recording_mbid':rec.get('id',''),'artist':artist_credit(t.get('artist-credit') or [])})
 labels=r.get('label-info',[]); label=next((x.get('label',{}).get('name','') for x in labels if x.get('label')), '')
 cats=', '.join(x.get('catalog-number','') for x in labels if x.get('catalog-number'))
 genres=', '.join(x.get('name','') for x in r.get('genres',[])); tags=', '.join(x.get('name','') for x in r.get('tags',[])); types=', '.join(rg.get('secondary-types',[]))
 return {'barcode':barcode or r.get('barcode',''),'title':r.get('title',''),'artist':artist_credit(ac),'artist_sort':next((x.get('artist',{}).get('sort-name','') for x in ac),''),'artist_mbid':next((x.get('artist',{}).get('id','') for x in ac),''),'year':(r.get('date') or '')[:4],'date':r.get('date',''),'release_date':rg.get('first-release-date',''),'country':r.get('country',''),'label':label,'catalog_number':cats,'format':', '.join(m.get('format','') for m in media),'media_count':len(media),'disc_count':len(media),'track_count':sum(len(m.get('tracks',[])) for m in media),'status':r.get('status',''),'packaging':r.get('packaging',''),'language':r.get('language',''),'script':r.get('script',''),'release_mbid':r.get('id',''),'release_group_mbid':rg.get('id',''),'release_group_type':', '.join([rg.get('primary-type','')]+[types] if types else [rg.get('primary-type','')]),'asin':r.get('asin',''),'annotation':r.get('annotation',''),'disambiguation':r.get('disambiguation',''),'quality':r.get('quality',''),'genre':genres,'genres':genres,'tags':tags,'styles':'','notes':'','cover_url':f"https://coverartarchive.org/release/{r.get('id')}/front" if r.get('id') else '','source':'musicbrainz','source_id':r.get('id',''),'tracks':tracks,'raw_json':json.dumps(r,ensure_ascii=False)}
def mb_get(url):
 global last_mb
 with lock:
  wait=1-(time.time()-last_mb)
  if wait>0: time.sleep(wait)
  try:
   h={'User-Agent':os.getenv('MB_USER_AGENT','MediaDB/1.0 (contact@example.invalid)')}; x=requests.get(url,headers=h,timeout=12); last_mb=time.time(); x.raise_for_status(); return x.json(),None
  except Exception as e: last_mb=time.time(); return None,str(e)
def norm_bc(x): return re.sub(r'\D','',str(x or '')).lstrip('0')
STATUS_RANK={'official':0,'promotion':1,'bootleg':3,'pseudo-release':4}
def status_rank(r): return STATUS_RANK.get((r.get('status') or '').strip().lower(),2)
def upc_check(d11):
 """Pruefziffer fuer UPC-A (11 Ziffern -> 1 Ziffer)."""
 odd=sum(int(c) for c in d11[0::2]); even=sum(int(c) for c in d11[1::2]); return str((10-(odd*3+even)%10)%10)
def barcode_equivalents(barcode):
 """Alle plausiblen Schreibweisen: Striche/Leerzeichen/fuehrende Nullen egal; fehlt bei 10 oder 11 Ziffern die Systemziffer bzw. Pruefziffer, wird sie ergaenzt."""
 t=norm_bc(barcode); out=[]
 def add(v):
  v=v.lstrip('0')
  if v and v not in out: out.append(v)
 add(t)
 raw=re.sub(r'\D','',str(barcode or ''))
 if len(raw) in (10,11):
  base=raw if len(raw)==11 else '0'+raw
  add(base+upc_check(base))
 return out
def mb_releases_by_barcode(barcode, limit=15, official_only=False):
 """Suche bei MusicBrainz, aber nur Releases, deren Barcode wirklich zum gesuchten passt (UPC 12-stellig und EAN 13-stellig gelten als gleich; unvollstaendige 10/11-stellige Barcodes werden ergaenzt). Gibt (treffer, ignoriert, fehler) zurueck."""
 targets=barcode_equivalents(barcode)
 if not targets: return [],0,None
 variants=[]
 for t in targets:
  for v in (t,t.zfill(12),t.zfill(13)):
   if v not in variants: variants.append(v)
 q='barcode:('+' OR '.join(variants)+')'
 d,err=mb_get(f'https://musicbrainz.org/ws/2/release?query={quote(q)}&fmt=json&limit={limit}')
 if err or not d: return [],0,(err or 'keine Antwort')
 ok=[]; skipped=0
 for r in d.get('releases',[]):
  if 'barcode' in r and norm_bc(r.get('barcode')) not in targets: skipped+=1; continue
  ok.append(r)
 if official_only: ok=[r for r in ok if status_rank(r)<3]
 ok.sort(key=lambda r:(status_rank(r),r.get('date') or '9999'))
 return ok,skipped,None
def search_mb(barcode):
 hits,skipped,err=mb_releases_by_barcode(barcode,25)
 if err: return [],'MusicBrainz ist momentan nicht erreichbar. Bitte später erneut versuchen.'
 out=[]
 good=[r for r in hits if status_rank(r)<3]; boot=[r for r in hits if status_rank(r)>=3]
 for r in good[:8]+boot[:3]:
  d,e=mb_get(f"https://musicbrainz.org/ws/2/release/{r.get('id')}?inc=artist-credits+labels+recordings+release-groups+genres+tags+media+discids+isrcs&fmt=json")
  if e or not d: continue
  if 'barcode' in d and norm_bc(d.get('barcode')) not in barcode_equivalents(barcode): skipped+=1; continue
  out.append(parse_release(d,d.get('barcode') or barcode))
 note=None
 if skipped and not out: note=f'MusicBrainz lieferte {skipped} Treffer, aber keiner hat genau diesen Barcode. Sie wurden ausgeblendet.'
 elif skipped: note=f'{skipped} Treffer mit abweichendem Barcode wurden ausgeblendet.'
 return out,note
OWN={'cd':'Physische CD','digital':'Nur digital (Audiodateien)','cd_digital':'CD + digital'}; OWN_SHORT={'cd':'CD','digital':'Digital','cd_digital':'CD + Digital'}
DIGITAL_WORDS=('digital','datei','file','mp3','m4a','flac','aac','alac','ogg','opus','wav','aiff','wma')
def norm_ownership(v):
 """Besitz vereinheitlichen: cd / digital / cd_digital. Leer oder unbekannt = physische CD. Alte Werte mp3 / cd_mp3 werden uebernommen."""
 t=str(v or '').strip().lower().replace('+',' ').replace('_',' '); dig=any(w in t for w in DIGITAL_WORDS); cd=bool(re.search(r'\bcd\b',t))
 if dig and cd: return 'cd_digital'
 if dig: return 'digital'
 return 'cd'
def norm_formats(v):
 """Dateiformate vereinheitlichen: 'mp3 ; flac/M4A' -> 'MP3, FLAC, M4A'."""
 out=[]
 for t in re.split(r'[,;/]+',str(v or '')):
  t=t.strip().upper()
  if t and t not in out: out.append(t)
 return ', '.join(out)
templates.env.globals['OWN']=OWN; templates.env.globals['OWN_SHORT']=OWN_SHORT
def save_item(data,s):
 item=Medium(**{k:v for k,v in data.items() if k in Medium.__table__.columns.keys() and k not in ('id','created_at')}); item.barcode=clean_barcode(item.barcode) or None; item.ownership=norm_ownership(item.ownership); item.file_formats=norm_formats(item.file_formats) or None; s.add(item); s.flush()
 for t in data.get('tracks',[]): s.add(Track(medium_id=item.id,**{k:v for k,v in t.items() if k in Track.__table__.columns.keys() and k not in ('id','medium_id')}))
 s.commit(); return item

CAA_HEADERS={'User-Agent':os.getenv('MB_USER_AGENT','MediaDB/1.0 (contact@example.invalid)')}
def download_cover(item_id, release_mbid='', release_group_mbid='', extra=()):
 """Holt das Frontcover vom Cover Art Archive: erst Release, dann Release-Group, dann weitere Kandidaten. Gibt Dateiname oder None zurueck."""
 pairs=[]
 if release_mbid: pairs.append(('release',release_mbid))
 if release_group_mbid: pairs.append(('release-group',release_group_mbid))
 pairs+=list(extra); seen=set()
 for kind,mbid in pairs:
  if not mbid or (kind,mbid) in seen: continue
  seen.add((kind,mbid))
  try:
   r=requests.get(f'https://coverartarchive.org/{kind}/{mbid}/front-500',headers=CAA_HEADERS,timeout=12,allow_redirects=True)
   ctype=r.headers.get('Content-Type','')
   if r.status_code==200 and ctype.startswith('image/') and len(r.content)>500:
    ext='png' if 'png' in ctype else 'jpg'; name=f'{item_id}.{ext}'
    for old in (DATA/'covers').glob(f'{item_id}.*'): old.unlink()
    (DATA/'covers'/name).write_bytes(r.content); return name
  except Exception: continue
 return None
def cover_fallback_ids(item):
 """Weitere Kandidaten fuer ein Cover: andere Ausgaben mit gleichem Barcode, zuletzt Album-Suche nach Kuenstler und Titel."""
 out=[]
 if item.barcode:
  hits,_,err=mb_releases_by_barcode(item.barcode,15,official_only=True)
  for r in hits: out.append(('release',r.get('id',''))); out.append(('release-group',(r.get('release-group') or {}).get('id','')))
 if item.artist and item.title:
  t=item.title.replace('"',' ').strip(); a=item.artist.replace('"',' ').strip()
  d,err=mb_get(f'https://musicbrainz.org/ws/2/release-group?query={quote(chr(34)+t+chr(34)+" AND artist:"+chr(34)+a+chr(34))}&fmt=json&limit=5')
  if not err and d:
   for g in d.get('release-groups',[]):
    if (g.get('title') or '').strip().lower()==item.title.strip().lower(): out.append(('release-group',g.get('id','')))
 return out
def resolve_mbids(item):
 """Release-MBID bestimmen: gespeichert, aus source_id oder per Barcode-Suche bei MusicBrainz."""
 rel=item.release_mbid or (item.source_id if item.source=='musicbrainz' else '') or ''
 rg=item.release_group_mbid or ''
 if rel and not rg:
  d,err=mb_get(f'https://musicbrainz.org/ws/2/release/{rel}?inc=release-groups&fmt=json')
  if not err and d: rg=(d.get('release-group') or {}).get('id','') or ''
 if not rel and item.barcode:
  hits,_,err=mb_releases_by_barcode(item.barcode,10,official_only=True)
  if hits: rel=hits[0].get('id',''); rg=(hits[0].get('release-group') or {}).get('id','')
 return rel,rg
def save_cover_bytes(item_id, content, ext):
 name=f'{item_id}.{ext}'
 for old in (DATA/'covers').glob(f'{item_id}.*'): old.unlink()
 (DATA/'covers'/name).write_bytes(content); return name
def _clean_title(t):
 return re.sub(r'\s*[\(\[]?\s*(?:feat\.?|featuring|ft\.?)\s+.*$','',str(t or ''),flags=re.I).strip()
def _cover_match(item, t, a):
 """Passt das gefundene Album (Titel t, Interpret a) zu unserem Eintrag?"""
 mt=au.norm_base(_clean_title(item.title)); tt=au.norm_base(_clean_title(t)); sim=au.similar(mt,tt)
 if sim<0.85: return False
 mine=au.norm_artist(item.artist); theirs=au.norm_artist(a)
 if mine=='various artists' or not mine: return True
 if mine==theirs or mine in theirs or theirs in mine: return True
 # Kuenstler heisst woanders anders (z. B. 2Pac / Tupac Shakur): nur bei praktisch gleichem, aussagekraeftigem Titel
 return sim>=0.95 and len(mt.split())>=3
_last_itunes=[0.0]
def _itunes_wait():
 """Apple nennt ca. 20 Anfragen pro Minute als Grenze: mindestens 3,2 s Abstand."""
 w=3.2-(time.time()-_last_itunes[0])
 if w>0: time.sleep(w)
 _last_itunes[0]=time.time()
def cover_from_web(item):
 """Ausweichquellen, wenn MusicBrainz kein Cover hat: iTunes/Apple Music, dann Deezer. Gibt (bytes, ext, quelle) oder None zurueck."""
 if os.getenv('COVER_WEB','1').strip().lower() in ('0','false','no','nein','off'): return None
 title=_clean_title(item.title); queries=[f'{item.artist or ""} {title}'.strip(),title]; urls=[]; seen=[]
 for q in dict.fromkeys(queries):
  try:
   _itunes_wait()
   r=requests.get('https://itunes.apple.com/search',params={'term':q,'entity':'album','limit':10},timeout=12)
   for x in (r.json().get('results') or []) if r.status_code==200 else []:
    seen.append(f"iTunes: {x.get('artistName')} – {x.get('collectionName')}")
    if _cover_match(item,x.get('collectionName',''),x.get('artistName','')) and x.get('artworkUrl100'): urls.append(('iTunes',x['artworkUrl100'].replace('100x100bb','600x600bb')))
  except Exception as e: logging.warning('iTunes-Suche fehlgeschlagen: %s',e)
  try:
   r=requests.get('https://api.deezer.com/search/album',params={'q':q,'limit':10},timeout=12)
   for x in (r.json().get('data') or []) if r.status_code==200 else []:
    seen.append(f"Deezer: {(x.get('artist') or {}).get('name')} – {x.get('title')}")
    if _cover_match(item,x.get('title',''),(x.get('artist') or {}).get('name','')) and (x.get('cover_xl') or x.get('cover_big')): urls.append(('Deezer',x.get('cover_xl') or x.get('cover_big')))
  except Exception as e: logging.warning('Deezer-Suche fehlgeschlagen: %s',e)
  if urls: break
 for src,u in urls:
  try:
   r=requests.get(u,timeout=15); ct=r.headers.get('Content-Type','')
   if r.status_code==200 and ct.startswith('image/') and len(r.content)>2000: return r.content,('png' if 'png' in ct else 'jpg'),src
  except Exception as e: logging.warning('Cover-Download fehlgeschlagen: %s',e)
 logging.warning('Kein Web-Cover fuer "%s – %s". Gesehene Treffer: %s',item.artist,item.title,'; '.join(seen[:12]) or 'keine')
 return None
def fetch_cover_for(item, s):
 """Cover suchen: bei Audio-Eintraegen zuerst in den Dateien, sonst MusicBrainz/Cover Art Archive, dann iTunes/Deezer, zuletzt die Dateien."""
 def local():
  paths=[r[0] for r in s.query(AudioFile.path).filter(AudioFile.medium_id==item.id).all()]
  if not paths: return False
  c=au.find_cover(paths)
  if not c: return False
  item.cover_path=save_cover_bytes(item.id,c[0],c[1]); item.cover_url='Datei-Cover'; s.commit(); return True
 def mb():
  rel,rg=resolve_mbids(item)
  name=download_cover(item.id,rel,rg) if (rel or rg) else None
  if not name: name=download_cover(item.id,'','',cover_fallback_ids(item))
  if not name: return False
  item.cover_path=name
  if rel: item.cover_url=f'https://coverartarchive.org/release/{rel}/front'
  if rel and not item.release_mbid: item.release_mbid=rel
  if rg and not item.release_group_mbid: item.release_group_mbid=rg
  s.commit(); return True
 def web():
  c=cover_from_web(item)
  if not c: return False
  item.cover_path=save_cover_bytes(item.id,c[0],c[1]); item.cover_url=c[2]; s.commit(); return True
 steps=[local,mb,web] if item.source=='files' else [mb,web,local]
 for step in steps:
  try:
   if step(): return True
  except Exception: logging.exception('Cover-Schritt fehlgeschlagen')
 return False

def fetch_release_date_for(item, s):
 """Erscheinungsdatum (erstes Erscheinen des Albums) von MusicBrainz holen."""
 rel,rg=resolve_mbids(item)
 if not rel: return False
 d,err=mb_get(f'https://musicbrainz.org/ws/2/release/{rel}?inc=release-groups&fmt=json')
 if err or not d: return False
 rgo=d.get('release-group') or {}; date=rgo.get('first-release-date') or ''
 if not date: return False
 item.release_date=date
 if not item.release_group_mbid and rgo.get('id'): item.release_group_mbid=rgo['id']
 if not item.date and d.get('date'): item.date=d['date']
 s.commit(); return True

def fetch_genre_for(item, s):
 """Genre aus MusicBrainz: Release-Group, dann Kuenstler (erst echte Genres, dann Tags). Gibt True zurueck, wenn etwas gefunden wurde."""
 if item.genre: return False
 rel,rg=resolve_mbids(item); urls=[]
 if rg: urls.append(f'https://musicbrainz.org/ws/2/release-group/{rg}?inc=genres+tags&fmt=json')
 if item.artist_mbid: urls.append(f'https://musicbrainz.org/ws/2/artist/{item.artist_mbid}?inc=genres+tags&fmt=json')
 got=[]
 for d in [mb_get(u)[0] for u in urls]:
  if d: got.append(d)
 def names(d,key): return [x['name'] for x in sorted(d.get(key) or [],key=lambda x:-x.get('count',0)) if x.get('name')]
 for key,n in (('genres',4),('tags',3)):
  for d in got:
   g=names(d,key)[:n]
   if g:
    item.genre=', '.join(x.title() for x in g); item.genres=item.genres or item.genre; s.commit(); return True
 return False

REFRESH={'running':False,'done':0,'total':0,'ok':0,'fail':0,'finished':0,'kind':'Aktualisierung','failed':[]}
def refresh_item(item, s):
 """Ergaenzt fehlende Felder, Tracks und das Cover aus MusicBrainz. Ueberschreibt nichts, was schon ausgefuellt ist."""
 rel=item.release_mbid or (item.source_id if item.source=='musicbrainz' else '') or ''
 if not rel: rel,_=resolve_mbids(item)
 if not rel: return False
 d,err=mb_get(f'https://musicbrainz.org/ws/2/release/{rel}?inc=artist-credits+labels+recordings+release-groups+genres+tags+media+discids+isrcs&fmt=json')
 if err or not d: return False
 p=parse_release(d,item.barcode or ''); cols=Medium.__table__.columns.keys()
 for k,v in p.items():
  if k in ('tracks','barcode','title','notes','source','source_id') or k not in cols or v in ('',None,0): continue
  if getattr(item,k) in (None,''): setattr(item,k,v)
 mbt=p['tracks']; cur=list(item.tracks); norm=lambda t:(t or '').strip().lower(); tcols=Track.__table__.columns.keys()
 if not cur and mbt:
  for t in mbt: s.add(Track(medium_id=item.id,**{k:v for k,v in t.items() if k in tcols and k not in ('id','medium_id')}))
 elif cur and [norm(t.title) for t in cur]==[norm(t['title']) for t in mbt]:
  for t,m in zip(cur,mbt):
   for k in ('number','length_ms','duration','recording_mbid','artist'):
    if getattr(t,k) in (None,'') and m.get(k) not in (None,''): setattr(t,k,m[k])
 s.commit()
 if not item.genre:
  try: fetch_genre_for(item,s)
  except Exception: logging.exception('Genre konnte nicht geladen werden')
 if not item.cover_path: fetch_cover_for(item,s)
 return True
def refresh_all_worker():
 s=Session()
 try:
  ids=[x.id for x in s.scalars(select(Medium).order_by(Medium.id)).all()]; REFRESH.update(total=len(ids),done=0,ok=0,fail=0,kind='Aktualisierung',failed=[])
  for i in ids:
   try: ok=refresh_item(s.get(Medium,i),s)
   except Exception: logging.exception('Aktualisierung fehlgeschlagen fuer Eintrag %s',i); s.rollback(); ok=False
   REFRESH['ok' if ok else 'fail']+=1; REFRESH['done']+=1
 finally:
  REFRESH['running']=False; REFRESH['finished']=time.time(); s.close()
def cover_all_worker():
 s=Session()
 try:
  ids=[x.id for x in s.scalars(select(Medium).where(or_(Medium.cover_path==None,Medium.cover_path=='')).order_by(Medium.id)).all()]; REFRESH.update(total=len(ids),done=0,ok=0,fail=0,kind='Cover',failed=[])
  for i in ids:
   x=s.get(Medium,i)
   try: ok=fetch_cover_for(x,s)
   except Exception: logging.exception('Cover fehlgeschlagen fuer Eintrag %s',i); s.rollback(); ok=False
   if not ok and len(REFRESH['failed'])<40: REFRESH['failed'].append({'id':x.id,'label':f'{x.artist or ""} – {x.title}'})
   REFRESH['ok' if ok else 'fail']+=1; REFRESH['done']+=1
 finally:
  REFRESH['running']=False; REFRESH['finished']=time.time(); s.close()
def start_cover_job():
 if REFRESH['running']: return False
 REFRESH.update(running=True,done=0,total=0,ok=0,fail=0); threading.Thread(target=cover_all_worker,daemon=True).start(); return True
def genre_all_worker():
 s=Session()
 try:
  ids=[x.id for x in s.scalars(select(Medium).where(or_(Medium.genre==None,Medium.genre=='')).order_by(Medium.id)).all()]; REFRESH.update(total=len(ids),done=0,ok=0,fail=0,kind='Genre',failed=[])
  for i in ids:
   try: ok=fetch_genre_for(s.get(Medium,i),s)
   except Exception: logging.exception('Genre fehlgeschlagen fuer Eintrag %s',i); s.rollback(); ok=False
   REFRESH['ok' if ok else 'fail']+=1; REFRESH['done']+=1
 finally:
  REFRESH['running']=False; REFRESH['finished']=time.time(); s.close()

INDEXES=[('ix_tracks_medium','tracks','medium_id'),('ix_media_artist','media','artist'),('ix_media_title','media','title'),('ix_media_genre','media','genre'),('ix_media_ownership','media','ownership'),('ix_media_source','media','source'),('ix_media_release','media','release_mbid'),('ix_media_rg','media','release_group_mbid'),('ix_audio_medium','audio_files','medium_id')]
def migrate_schema():
 """Fehlende Spalten in bestehender Datenbank ergaenzen (z.B. release_date)."""
 have={c['name'] for c in inspect(engine).get_columns('media')}; added=[]
 with engine.begin() as conn:
  for col in Medium.__table__.columns:
   if col.name not in have:
    conn.execute(text(f'ALTER TABLE media ADD COLUMN {col.name} {col.type.compile(dialect=engine.dialect)}')); added.append(col.name)
  conn.execute(text("UPDATE media SET ownership='cd' WHERE ownership IS NULL OR ownership=''"))
  conn.execute(text("UPDATE media SET ownership='digital' WHERE ownership='mp3'"))
  conn.execute(text("UPDATE media SET ownership='cd_digital' WHERE ownership='cd_mp3'"))
  for name,tbl,cols in INDEXES: conn.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON {tbl} ({cols})'))
  if IS_SQLITE: search.setup(conn)
 if 'release_date' in added:
  s=Session()
  for x in s.scalars(select(Medium)).all():
   try: x.release_date=((json.loads(x.raw_json or '{}').get('release-group') or {}).get('first-release-date')) or None
   except Exception: pass
  s.commit(); s.close()
migrate_schema()

# ---------------- Diskografie-Suche ----------------
MB_REL_INC='artist-credits+labels+recordings+release-groups+genres+tags+media+discids+isrcs'
def mb_search_artists(name):
 d,err=mb_get(f'https://musicbrainz.org/ws/2/artist?query={quote(chr(34)+name.replace(chr(34)," ")+chr(34))}&fmt=json&limit=8')
 if err or not d: return [],'MusicBrainz ist momentan nicht erreichbar. Bitte später erneut versuchen.'
 return d.get('artists',[]),''
def mb_release_groups(artist_mbid, kind='albums'):
 out=[]; off=0
 while off<300:
  typ='&type=album|ep' if kind in ('albums','studio') else ''
  d,err=mb_get(f'https://musicbrainz.org/ws/2/release-group?artist={artist_mbid}{typ}&fmt=json&limit=100&offset={off}')
  if err or not d: return out,'MusicBrainz ist momentan nicht erreichbar.' if not out else ''
  out+=d.get('release-groups',[]); off+=100
  if off>=d.get('release-group-count',0): break
 if kind=='studio': out=[g for g in out if g.get('primary-type')=='Album' and not g.get('secondary-types')]
 out.sort(key=lambda g:(g.get('first-release-date') or '9999',g.get('title','')))
 return out,''
_REL_CACHE={}
def mb_artist_releases(artist_mbid):
 c=_REL_CACHE.get(artist_mbid)
 if c and time.time()-c[0]<3600: return c[1]
 r=_mb_artist_releases(artist_mbid)
 if not r[2]: _REL_CACHE[artist_mbid]=(time.time(),r)
 return r
def _mb_artist_releases(artist_mbid):
 """Alle offiziellen Ausgaben eines Interpreten (max. 1500) mit Barcode, flach."""
 out=[]; off=0; truncated=False
 while True:
  d,err=mb_get(f'https://musicbrainz.org/ws/2/release?artist={artist_mbid}&status=official&inc=labels+media+release-groups&fmt=json&limit=100&offset={off}')
  if err or not d: return out,truncated,('MusicBrainz ist momentan nicht erreichbar.' if not out else '')
  for r in d.get('releases',[]):
   li=r.get('label-info') or []; fm=[m.get('format') or '?' for m in r.get('media',[])]; rg=r.get('release-group') or {}
   out.append({'id':r.get('id'),'title':r.get('title',''),'date':r.get('date',''),'country':r.get('country',''),'barcode':r.get('barcode',''),'label':', '.join(dict.fromkeys(x['label']['name'] for x in li if x.get('label'))),'catno':', '.join(dict.fromkeys(x['catalog-number'] for x in li if x.get('catalog-number'))),'format':' + '.join(fm),'tracks':sum(m.get('track-count',0) for m in r.get('media',[])),'is_cd':any('cd' in f.lower() for f in fm),'rg':rg.get('id',''),'type':rg.get('primary-type') or '','disambiguation':r.get('disambiguation',''),'l':(lambda c:c if 'A'<=c<='Z' else '#')(unicodedata.normalize('NFKD',(r.get('title','') or '').strip().lstrip('"\'([ '))[:1].upper())})
  off+=100
  if off>=d.get('release-count',0): break
  if off>=1500: truncated=True; break
 out.sort(key=lambda e:(e['title'].casefold(),e['date'] or '9999'))
 return out,truncated,''
def mb_editions(rg_mbid):
 d,err=mb_get(f'https://musicbrainz.org/ws/2/release?release-group={rg_mbid}&inc=labels+media+artist-credits&fmt=json&limit=100')
 if err or not d: return [],'MusicBrainz ist momentan nicht erreichbar.'
 out=[]
 for r in d.get('releases',[]):
  li=r.get('label-info') or []; fm=[m.get('format') or '?' for m in r.get('media',[])]
  out.append({'id':r.get('id'),'title':r.get('title',''),'date':r.get('date',''),'country':r.get('country',''),'barcode':r.get('barcode',''),'status':r.get('status',''),'packaging':r.get('packaging') or '',
   'label':', '.join(dict.fromkeys(x['label']['name'] for x in li if x.get('label'))),'catno':', '.join(dict.fromkeys(x['catalog-number'] for x in li if x.get('catalog-number'))),
   'format':' + '.join(fm),'tracks':sum(m.get('track-count',0) for m in r.get('media',[])),'is_cd':any('cd' in f.lower() for f in fm),'artist':artist_credit(r.get('artist-credit') or []),'disambiguation':r.get('disambiguation','')})
 out.sort(key=lambda e:(status_rank({'status':e['status']}),e['date'] or '9999'))
 return out,''
@app.get('/discography',response_class=HTMLResponse)
def disco_search(request:Request,artist:str=''):
 artists,error=(mb_search_artists(artist.strip()) if artist.strip() else ([],''))
 key=au.norm_full(artist); exact=[a for a in artists if au.norm_full(a.get('name'))==key]; other=[a for a in artists if a not in exact]
 return templates.TemplateResponse(request,'discography.html',ctx(request,view='artists',q=artist,exact=exact,other=other,error=error))
@app.get('/discography/artist/{mbid}',response_class=HTMLResponse)
def disco_artist(request:Request,mbid:str,name:str='',kind:str='albums'):
 kind=kind if kind in ('all','studio') else 'albums'; groups,error=mb_release_groups(mbid,kind); s=Session()
 have={x[0] for x in s.query(Medium.release_group_mbid).filter(Medium.release_group_mbid!=None).all()}; s.close()
 return templates.TemplateResponse(request,'discography.html',ctx(request,view='groups',name=name,mbid=mbid,kind=kind,groups=groups,have=have,error=error))
@app.get('/discography/artist/{mbid}/releases',response_class=HTMLResponse)
def disco_releases(request:Request,mbid:str,name:str=''):
 rels,truncated,error=mb_artist_releases(mbid); s=Session()
 have_rel={x[0] for x in s.query(Medium.release_mbid).filter(Medium.release_mbid!=None).all()}; have_bc={norm_bc(x[0]) for x in s.query(Medium.barcode).filter(Medium.barcode!=None).all()}; s.close()
 return templates.TemplateResponse(request,'discography.html',ctx(request,view='releases',name=name,mbid=mbid,rels=rels,truncated=truncated,have_rel=have_rel,have_bc=have_bc,error=error))
@app.get('/discography/group/{rgid}',response_class=HTMLResponse)
def disco_group(request:Request,rgid:str,title:str='',name:str='',mbid:str='',cds:str='1'):
 eds,error=mb_editions(rgid); s=Session()
 have_rel={x[0] for x in s.query(Medium.release_mbid).filter(Medium.release_mbid!=None).all()}; have_bc={norm_bc(x[0]) for x in s.query(Medium.barcode).filter(Medium.barcode!=None).all()}; s.close()
 only_cd=cds!='0'; shown=[e for e in eds if e['is_cd']] if only_cd else eds
 if only_cd and not shown: shown=eds; only_cd=False
 return templates.TemplateResponse(request,'discography.html',ctx(request,view='editions',title=title,name=name,mbid=mbid,rgid=rgid,eds=shown,total=len(eds),only_cd=only_cd,have_rel=have_rel,have_bc=have_bc,error=error))
@app.post('/discography/save')
def disco_save(release_mbid:str=Form(...),ownership:str=Form('cd'),back:str=Form('/media')):
 s=Session(); back=back if back.startswith('/') else '/media'
 if s.scalar(select(Medium).where(Medium.release_mbid==release_mbid)): return RedirectResponse('/media?message='+quote('Diese Ausgabe ist bereits in der Sammlung.'),303)
 d,err=mb_get(f'https://musicbrainz.org/ws/2/release/{release_mbid}?inc={MB_REL_INC}&fmt=json')
 if err or not d: return RedirectResponse(back+('&' if '?' in back else '?')+'message='+quote('MusicBrainz ist momentan nicht erreichbar.'),303)
 p=parse_release(d,''); p['ownership']=ownership; bc=clean_barcode(p.get('barcode'))
 if bc and s.scalar(select(Medium).where(Medium.barcode==bc)): return RedirectResponse('/media?message='+quote('Dieser Barcode ist bereits in der Sammlung.'),303)
 item=save_item(p,s)
 for fn in (fetch_cover_for,fetch_genre_for):
  try: fn(item,s)
  except Exception: logging.exception('Nachladen nach Diskografie-Auswahl fehlgeschlagen')
 return RedirectResponse(f'/media/{item.id}?message='+quote('Gespeichert.'),303)

SETTINGS_FILE=DATA/'settings.json'
def load_settings():
 try: return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
 except Exception: return {}
def save_settings(d):
 try: SETTINGS_FILE.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
 except Exception: logging.exception('Einstellungen konnten nicht gespeichert werden')
def get_lang(request):
 """Sprache: Cookie des Browsers, sonst die gespeicherte Voreinstellung (data/settings.json), sonst Deutsch."""
 c=(request.cookies.get('mediadb_lang') or request.cookies.get('musikdb_lang')) if request else None  # musikdb_lang: bis MusikDB 1.2
 if c in i18n.LANGS: return c
 l=load_settings().get('lang')
 return l if l in i18n.LANGS else i18n.DEFAULT
def ctx(request,**kw):
 lang=get_lang(request)
 return {'request':request,'lang':lang,'langs':i18n.LANGS,'_':partial(i18n.tr,lang),'_t':partial(i18n.tr_text,lang),'base':sec.get_base(request),'auth_on':SEC.auth_on,**kw}
@app.get('/lang/{code}')
def set_lang(request:Request,code:str,next:str='/'):
 if code not in i18n.LANGS: code=i18n.DEFAULT
 next=sec.strip_base(next,sec.get_base(request))
 if not next.startswith('/') or next.startswith('//') or '\\' in next: next='/'
 d=load_settings(); d['lang']=code; save_settings(d)
 r=RedirectResponse(next,303); r.set_cookie('mediadb_lang',code,max_age=60*60*24*365*5,samesite='lax'); return r
@app.get('/healthz')
def healthz(): return {'ok':True}
def _safe_next(n):
 n=n or '/media'
 return n if n.startswith('/') and not n.startswith('//') and '\\' not in n else '/media'
@app.get('/login',response_class=HTMLResponse)
def login_page(request:Request,next:str='/media',error:str=''):
 if not SEC.auth_on: return RedirectResponse(_safe_next(next),303)
 return templates.TemplateResponse(request,'login.html',ctx(request,next=_safe_next(next),error=error,login_page=True))
@app.post('/login')
def login(request:Request,password:str=Form(''),next:str=Form('/media')):
 nxt=_safe_next(next)
 if not SEC.auth_on: return RedirectResponse(nxt,303)
 if not SEC.password_ok(password):
  time.sleep(1.5); return RedirectResponse('/login?'+urlencode({'next':nxt,'error':'1'}),303)
 r=RedirectResponse(nxt,303); r.set_cookie(sec.COOKIE,SEC.make_token(),max_age=sec.MAX_AGE,httponly=True,samesite='lax'); return r
@app.get('/logout')
def logout():
 r=RedirectResponse('/login' if SEC.auth_on else '/media',303); r.delete_cookie(sec.COOKIE); return r
@app.get('/')
def home(): return RedirectResponse('/media',303)
@app.get('/add',response_class=HTMLResponse)
def add_page(request:Request): return templates.TemplateResponse(request,'scan.html',ctx(request))
@app.post('/scan/search',response_class=HTMLResponse)
def scan(request:Request,barcode:str=Form(...)):
 s=Session(); dup=s.scalar(select(Medium).where(Medium.barcode==clean_barcode(barcode))); candidates,error=search_mb(barcode); return templates.TemplateResponse(request,'candidates.html',ctx(request,barcode=barcode,candidates=candidates,error=error,duplicate=dup))
@app.get('/manual',response_class=HTMLResponse)
def manual(request:Request,barcode:str=''): return templates.TemplateResponse(request,'manual.html',ctx(request,item=type('X',(),{'barcode':barcode})() if barcode else None))

def find_digital_twin(s,artist,title,track_titles):
 """Schon per Audio-Import erfasster Nur-digital-Eintrag, der zu dieser neuen CD gehoert (gleicher Interpret, gleiche Titel)."""
 a=au.norm_full(artist); tb=au.norm_base(title); C=au.title_set(track_titles)
 for m in s.scalars(select(Medium).where(Medium.source=='files',Medium.ownership=='digital')).all():
  if au.norm_full(m.artist)!=a: continue
  F=au.title_set(t.title for t in m.tracks)
  if C and F:
   if C==F: return m
  elif au.norm_base(m.title)==tb: return m
 return None
def merge_digital_twin(s,twin,item):
 """Die neue CD uebernimmt die Dateien des digitalen Eintrags; der digitale Eintrag verschwindet (keine Doppelten)."""
 s.query(AudioFile).filter(AudioFile.medium_id==twin.id).update({AudioFile.medium_id:item.id})
 item.ownership='cd_digital'; item.file_formats=twin.file_formats
 if twin.notes and not item.notes: item.notes=twin.notes
 s.flush(); s.expire(twin); s.delete(twin); s.commit()
@app.post('/media/create')
def create(request:Request, ownership:str=Form('cd'), file_formats:str=Form(''), barcode:str=Form(''), title:str=Form(...), artist:str=Form(''), year:str=Form(''), release_date:str=Form(''), date:str=Form(''), artist_sort:str=Form(''), release_mbid:str=Form(''), release_group_mbid:str=Form(''), label:str=Form(''), genre:str=Form(''), styles:str=Form(''), format:str=Form(''), country:str=Form(''), catalog_number:str=Form(''), notes:str=Form(''), tracklist:str=Form(''), source:str=Form('manual'), source_id:str=Form('')):
 s=Session(); barcode=clean_barcode(barcode)
 if barcode and s.scalar(select(Medium).where(Medium.barcode==barcode)): return RedirectResponse('/media?message=Barcode bereits vorhanden',303)
 data=locals(); data['tracks']=[{'position':i+1,'disc_number':1,'number':str(i+1),'title':x.strip(),'duration':''} for i,x in enumerate(tracklist.splitlines()) if x.strip()]; twin=find_digital_twin(s,artist,title,[t['title'] for t in data['tracks']]); item=save_item(data,s)
 if twin: merge_digital_twin(s,twin,item)
 try: fetch_cover_for(item,s)
 except Exception: logging.exception('Cover-Download fehlgeschlagen')
 if not item.genre:
  try: fetch_genre_for(item,s)
  except Exception: logging.exception('Genre konnte nicht geladen werden')
 if not item.release_date:
  try: fetch_release_date_for(item,s)
  except Exception: logging.exception('Erscheinungsdatum konnte nicht geladen werden')
 return RedirectResponse(f'/media/{item.id}',303)
SORTS={'genre':('genre','artist','release_date'),'artist':('artist','release_date','title'),'title':('title','artist'),'year':('year','artist','title'),'release_date':('release_date','artist','title')}
def qs(**kw): return urlencode({k:v for k,v in kw.items() if v})
@app.get('/media',response_class=HTMLResponse)
def media(request:Request,q:str='',artist:str='',genre:str='',year:str='',sort:str='artist',dir:str='asc',view:str='all',message:str='',mode:str='',interpret:str=''):
 s=Session(); list_mode=bool(q or artist or genre or year or interpret or mode=='list'); view={'mp3':'digital'}.get(view,view); view=view if view in ('cd','digital') else 'all'; sort=sort if sort in SORTS else 'artist'; dir='desc' if dir=='desc' else 'asc'; stmt=select(Medium)
 if artist: stmt=stmt.where(or_(Medium.artist.ilike(f'%{artist}%'),Medium.tracks.any(Track.artist.ilike(f'%{artist}%'))))
 for col,val in [(Medium.genre,genre),(Medium.year,year)]:
  if val: stmt=stmt.where(col.ilike(f'%{val}%'))
 toks=q.split(); long_toks=[t for t in toks if len(t)>=search.MIN_LEN] if search.ENABLED else []
 if long_toks: stmt=stmt.where(Medium.id.in_(select(literal_column('rowid')).select_from(text(search.TABLE)).where(text(f'{search.TABLE} MATCH :fts_q').bindparams(fts_q=search.match_expr(long_toks)))))
 for tok in toks:
  if tok in long_toks: continue
  like=f'%{tok}%'; stmt=stmt.where(or_(*[getattr(Medium,c).ilike(like) for c in ('title','artist','barcode','genre','tags','styles','label','catalog_number','notes','year','release_date','file_formats')],Medium.tracks.any(or_(Track.title.ilike(like),Track.artist.ilike(like)))))
 if view=='cd': stmt=stmt.where(Medium.ownership.in_(['cd','cd_digital']))
 elif view=='digital': stmt=stmt.where(Medium.ownership=='digital')
 tabs={'all':0,'cd':0,'digital':0}
 for o,n in s.execute(select(Medium.ownership,func.count()).group_by(Medium.ownership)).all():
  o=o or 'cd'; tabs['all']+=n; tabs['cd']+=(n if o in ('cd','cd_digital') else 0); tabs['digital']+=(n if o=='digital' else 0)
 datekey=func.coalesce(func.nullif(Medium.release_date,''),func.nullif(Medium.year,''),'')
 def kx(name): return datekey if name=='release_date' else func.lower(func.coalesce(getattr(Medium,name),''))
 names=SORTS[sort]; first=kx(names[0])
 order=[case((first=='',1),else_=0), first.desc() if dir=='desc' else first]
 for n in names[1:]: order+=[case((kx(n)=='',1),else_=0), kx(n)]
 filt={'q':q,'artist':artist,'genre':genre,'year':year,'interpret':interpret,'mode':'list' if mode=='list' else '','view':'' if view=='all' else view}
 tab_links={k:'/media?'+qs(**{**filt,'view':'' if k=='all' else k},sort=sort,dir=dir) for k in ('all','cd','digital')}
 links={c:'/media?'+qs(**filt,sort=c,dir=('desc' if sort==c and dir=='asc' else 'asc')) for c in SORTS}
 items=s.scalars(stmt.order_by(*order)).all(); counts={}
 if interpret: ik=au.norm_full(interpret); items=[x for x in items if au.norm_full(x.artist or 'Ohne Künstler')==ik]
 if not list_mode:
  idx={}
  for x in items:
   nm=(x.artist or '').strip() or 'Ohne Künstler'; key=au.norm_full(nm) or nm.lower()
   e=idx.setdefault(key,{'names':{},'n':0,'dig':0,'covers':[]}); e['names'][nm]=e['names'].get(nm,0)+1; e['n']+=1
   if (x.ownership or 'cd')=='digital': e['dig']+=1
   if x.cover_path and len(e['covers'])<3: e['covers'].append(x.cover_path)
  arts=[]
  for key,e in idx.items():
   name=max(e['names'],key=e['names'].get); c=unicodedata.normalize('NFKD',key[:1].upper())[:1]
   arts.append({'name':name,'key':key,'n':e['n'],'dig':e['dig'],'cd':e['n']-e['dig'],'covers':e['covers'],'l':c if 'A'<=c<='Z' else '#','url':'/media?'+qs(interpret=name,view=filt['view'])})
  arts.sort(key=lambda a:(a['l']=='#',a['key']))
  firsts={}
  for a in arts: firsts.setdefault(a['l'],a['name'])
  return templates.TemplateResponse(request,'artists.html',ctx(request,arts=arts,firsts=firsts,abc=[chr(c) for c in range(65,91)]+['#'],total=len(items),view=view,tabs=tabs,tab_links=tab_links,message=message,q=q,artist=artist,genre=genre,year=year,sort=sort,dir=dir,mode='artists',interpret='',all_url='/media',refresh=dict(REFRESH,show_done=bool(not REFRESH['running'] and REFRESH['total'] and time.time()-REFRESH['finished']<600))))
 def letter(v):
  v=unicodedata.normalize('NFKD',(v or '').strip())[:1].upper()
  return v if 'A'<=v<='Z' else '#'
 abc_src='title' if sort=='title' else ('artist' if sort=='artist' else '')
 first_of={}
 if abc_src:
  for x in items: first_of.setdefault(letter(getattr(x,abc_src)),x.id)
 for x in items: k=(x.artist or '').strip().lower(); counts[k]=counts.get(k,0)+1
 return templates.TemplateResponse(request,'list.html',ctx(request,mode='list',interpret=interpret,items=items,counts=counts,first_of=first_of,abc=[chr(c) for c in range(65,91)]+['#'],abc_src=abc_src,letter=letter,q=q,artist=artist,genre=genre,year=year,sort=sort,dir=dir,links=links,all_url='/media?'+qs(sort=sort,dir=dir,view=filt['view']),view=view,tabs=tabs,tab_links=tab_links,message=message,refresh=dict(REFRESH,show_done=bool(not REFRESH['running'] and REFRESH['total'] and time.time()-REFRESH['finished']<600))))
@app.get('/media/{id}',response_class=HTMLResponse)
def detail(request:Request,id:int,message:str=''):
 s=Session(); item=s.get(Medium,id)
 if item: item.tracks  # Tracks laden, solange die Sitzung offen ist
 if not item: return RedirectResponse('/media',303)
 return templates.TemplateResponse(request,'detail.html',ctx(request,item=item,message=message))
@app.get('/media/{id}/edit',response_class=HTMLResponse)
def edit(request:Request,id:int):
 s=Session(); x=s.get(Medium,id)
 if not x: return RedirectResponse('/media',303)
 x.tracks  # Tracks laden, solange die Sitzung offen ist
 return templates.TemplateResponse(request,'manual.html',ctx(request,item=x,error=''))
@app.post('/media/{id}/update',response_class=HTMLResponse)
def update(request:Request,id:int,ownership:str=Form('cd'),file_formats:str=Form(''),barcode:str=Form(''),title:str=Form(...),artist:str=Form(''),year:str=Form(''),release_date:str=Form(''),label:str=Form(''),genre:str=Form(''),styles:str=Form(''),format:str=Form(''),country:str=Form(''),catalog_number:str=Form(''),notes:str=Form(''),tracklist:str=Form('')):
 s=Session(); x=s.get(Medium,id)
 if not x: return RedirectResponse('/media',303)
 barcode=clean_barcode(barcode); lines=[l.strip() for l in tracklist.splitlines() if l.strip()]
 fields=dict(ownership=norm_ownership(ownership),file_formats=norm_formats(file_formats),title=title.strip(),artist=artist.strip(),year=year.strip(),release_date=release_date.strip(),label=label.strip(),genre=genre.strip(),styles=styles.strip(),format=format.strip(),country=country.strip(),catalog_number=catalog_number.strip(),notes=notes)
 if barcode and s.scalar(select(Medium).where(Medium.barcode==barcode,Medium.id!=id)):
  snap=SimpleNamespace(id=id,barcode=barcode,tracks=[SimpleNamespace(title=t) for t in lines],**fields)
  return templates.TemplateResponse(request,'manual.html',ctx(request,item=snap,error='Dieser Barcode gehört bereits zu einem anderen Eintrag.'))
 x.barcode=barcode or None
 for k,v in fields.items(): setattr(x,k,v)
 if lines!=[t.title for t in x.tracks]:
  old={t.title:dict(disc_number=t.disc_number,number=t.number,length_ms=t.length_ms,duration=t.duration,recording_mbid=t.recording_mbid,artist=t.artist) for t in x.tracks}
  x.tracks.clear(); s.flush()
  for i,t in enumerate(lines):
   o=old.get(t,{}); x.tracks.append(Track(position=i+1,disc_number=o.get('disc_number') or 1,number=o.get('number') or str(i+1),title=t,length_ms=o.get('length_ms'),duration=o.get('duration') or '',recording_mbid=o.get('recording_mbid'),artist=o.get('artist')))
 s.commit(); return RedirectResponse(f'/media/{id}',303)
@app.get('/media/refresh-status')
def refresh_status(request:Request):
 return {'running':REFRESH['running'],'done':REFRESH['done'],'total':REFRESH['total'],'kind':i18n.tr_text(get_lang(request),REFRESH['kind'])}
@app.post('/media/refresh-all')
def refresh_all():
 if not REFRESH['running']:
  REFRESH.update(running=True,done=0,total=0,ok=0,fail=0); threading.Thread(target=refresh_all_worker,daemon=True).start()
 return RedirectResponse('/media',303)
@app.post('/media/genres/fetch-missing')
def fetch_missing_genres():
 if not REFRESH['running']:
  REFRESH.update(running=True,done=0,total=0,ok=0,fail=0); threading.Thread(target=genre_all_worker,daemon=True).start()
 return RedirectResponse('/media',303)
@app.post('/media/{id}/refresh')
def refresh_one(id:int):
 s=Session(); x=s.get(Medium,id); msg=''
 if x:
  try: msg='Von MusicBrainz aktualisiert.' if refresh_item(x,s) else 'Bei MusicBrainz wurde nichts gefunden.'
  except Exception: logging.exception('Aktualisierung fehlgeschlagen'); s.rollback(); msg='Aktualisierung fehlgeschlagen, Details im Log.'
 return RedirectResponse(f'/media/{id}?message={quote(msg)}',303)
# ---------------- Aehnliche Ausgabe bei MusicBrainz suchen und zuordnen ----------------
_STOP={'the','a','an','and','feat','featuring','ft','with','of','und','der','die','das'}
def _words(t): return [w for w in re.findall(r'\w+',au.norm_base(t or '')) if w not in _STOP and len(w)>1]
def mb_similar_search(artist,title):
    """Breite Suche nach aehnlichen Ausgaben (Titel und Interpret nur ungefaehr). Gibt Treffer mit Score zurueck, beste zuerst."""
    def q(v): return re.sub(r'["\\]',' ',str(v or '')).strip()
    tw=_words(title); aw=_words(artist); various=au.norm_artist(artist)=='various artists' or not aw
    qs=[]
    if title: qs.append(f'release:"{q(title)}"'+('' if various else f' AND artist:"{q(artist)}"'))
    if tw: qs.append('release:('+' '.join(tw)+')'+('' if various else ' AND artist:('+' '.join(aw)+')'))
    if tw and not various: qs.append('release:('+' '.join(tw)+')')
    if aw and not various: qs.append('artist:('+' '.join(aw)+')')
    found={}
    for query in qs:
        d,err=mb_get('https://musicbrainz.org/ws/2/release?query='+quote(query)+'&fmt=json&limit=25')
        for r in (d or {}).get('releases',[]) if d else []:
            if r.get('id') and r['id'] not in found: found[r['id']]=mb_cand(r)
    mine_t=set(tw); mine_a=au.norm_artist(artist); out=[]
    for c in found.values():
        ct=set(_words(c['title']))
        ov=len(mine_t&ct)/len(mine_t) if mine_t else 0
        ts=max(ov,au.similar(au.norm_base(title),au.norm_base(c['title'])))
        theirs=au.norm_artist(c['artist'])
        as_=1.0 if various else (1.0 if mine_a==theirs or mine_a in theirs or theirs in mine_a else au.similar(mine_a,theirs))
        c['score']=round(0.65*ts+0.35*as_,3); c['ts']=ts; c['as']=as_
        if ts>=0.3 and as_>=0.5: out.append(c)
    out.sort(key=lambda c:(-c['score'],)+_cand_sort(c))
    return out[:25]
# ---------------- Discogs als Zweitquelle (Link einfuegen, optional Suche mit Token) ----------------
DISCOGS_TOKEN=os.getenv('DISCOGS_TOKEN','').strip(); last_dc=0.0; dc_lock=threading.Lock()
def discogs_get(path,params=None):
    global last_dc
    with dc_lock:
        wait=(1.0 if DISCOGS_TOKEN else 2.5)-(time.time()-last_dc)
        if wait>0: time.sleep(wait)
        try:
            h={'User-Agent':os.getenv('MB_USER_AGENT','MediaDB/1.0 (contact@example.invalid)')}
            if DISCOGS_TOKEN: h['Authorization']=f'Discogs token={DISCOGS_TOKEN}'
            r=requests.get('https://api.discogs.com'+path,params=params,headers=h,timeout=15); last_dc=time.time(); r.raise_for_status(); return r.json(),None
        except Exception as e: last_dc=time.time(); return None,str(e)
def discogs_id(text):
    t=str(text or '').strip(); m=re.search(r'/release/(\d+)',t) or re.search(r'\[r(\d+)\]',t) or re.fullmatch(r'r?(\d+)',t)
    return m.group(1) if m else ''
def discogs_clean_artist(n): return re.sub(r'\s*\(\d+\)$','',n or '').strip()
def discogs_parse(d):
    arts=[discogs_clean_artist(a.get('name')) for a in d.get('artists',[])]
    bc=''
    for i in d.get('identifiers',[]):
        if (i.get('type') or '').lower()=='barcode':
            v=re.sub(r'\D','',i.get('value') or '')
            if len(v)>=8: bc=v; break
    fm=d.get('formats') or []
    fmt=' + '.join(((f.get('qty') if f.get('qty') not in (None,'1') else '') and f"{f.get('qty')}×" or '')+f.get('name','') for f in fm)
    lab=d.get('labels') or []
    tracks=[]; n=0
    for t in d.get('tracklist',[]):
        if t.get('type_','track')!='track' or not t.get('title'): continue
        n+=1; pos=str(t.get('position') or n); disc=1
        m=re.match(r'^(\d+)[-.]',pos)
        if m: disc=int(m.group(1))
        tracks.append({'position':n,'disc_number':disc,'number':pos,'title':t['title'],'duration':t.get('duration') or ''})
    imgs=d.get('images') or []; img=next((i for i in imgs if i.get('type')=='primary'),imgs[0] if imgs else {})
    return {'id':str(d.get('id','')),'artist':' / '.join(a for a in arts if a),'title':d.get('title',''),'year':str(d.get('year') or ''),'release_date':d.get('released') or '','country':d.get('country') or '','label':', '.join(dict.fromkeys(l.get('name','') for l in lab if l.get('name'))),'catalog_number':', '.join(dict.fromkeys(l.get('catno','') for l in lab if l.get('catno') and l.get('catno')!='none')),'format':fmt,'genre':', '.join(d.get('genres') or []),'styles':', '.join(d.get('styles') or []),'barcode':bc,'tracks':tracks,'image':img.get('uri') or img.get('resource_url') or d.get('thumb') or '','thumb':d.get('thumb') or img.get('uri150') or ''}
def discogs_search(artist,title):
    if not DISCOGS_TOKEN: return None,'kein Token'
    d,err=discogs_get('/database/search',{'type':'release','artist':artist or '','release_title':title or '','per_page':15})
    if err or not d: return [],err
    out=[]
    for r in d.get('results',[]):
        out.append({'id':str(r.get('id','')),'title':r.get('title',''),'year':r.get('year',''),'country':r.get('country',''),'format':', '.join(r.get('format') or []),'label':', '.join((r.get('label') or [])[:2]),'thumb':r.get('thumb','')})
    return out,None
def apply_discogs(item,s,rid):
    d,err=discogs_get(f'/releases/{rid}')
    if err or not d: return False
    p=discogs_parse(d)
    for k in ('artist','title','year','release_date','country','label','catalog_number','format','genre','styles'):
        if p.get(k) and not getattr(item,k): setattr(item,k,p[k])
    if p['genre'] and not item.genres: item.genres=p['genre']
    if p['barcode'] and not item.barcode and not s.scalar(select(Medium).where(Medium.barcode==p['barcode'])): item.barcode=p['barcode']
    if not item.tracks and p['tracks']:
        for t in p['tracks']: s.add(Track(medium_id=item.id,**t))
        item.track_count=item.track_count or len(p['tracks'])
    note=f"Discogs: https://www.discogs.com/release/{p['id']}"
    if note not in (item.notes or ''): item.notes=((item.notes+'\n') if item.notes else '')+note
    s.commit()
    if not item.cover_path:
        for url in (p['image'],p['thumb']):
            if not url: continue
            try:
                h={'User-Agent':os.getenv('MB_USER_AGENT','MediaDB/1.0 (contact@example.invalid)')}
                if DISCOGS_TOKEN: h['Authorization']=f'Discogs token={DISCOGS_TOKEN}'
                r=requests.get(url,headers=h,timeout=15)
                if r.status_code==200 and r.headers.get('Content-Type','').startswith('image/') and len(r.content)>500:
                    item.cover_path=save_cover_bytes(item.id,r.content,'png' if 'png' in r.headers['Content-Type'] else 'jpg'); item.cover_url=url; s.commit(); break
            except Exception: logging.exception('Discogs-Cover')
    if not item.genre:
        try: fetch_genre_for(item,s)
        except Exception: pass
    return True
@app.get('/media/{id}/discogs')
def discogs_page(request:Request,id:int,ref:str=''):
    s=Session(); x=s.get(Medium,id)
    if not x: return RedirectResponse('/media',303)
    rid=discogs_id(ref); p=None; err=''
    if ref and not rid: err='Das sieht nicht nach einem Discogs-Link aus. Erwartet wird z. B. https://www.discogs.com/release/553761-… oder nur die Nummer.'
    elif rid:
        d,e=discogs_get(f'/releases/{rid}')
        if e or not d: err='Discogs antwortet nicht oder kennt diese Nummer nicht ('+str(e)+').'
        else: p=discogs_parse(d)
    return templates.TemplateResponse(request,'discogs.html',ctx(request,item=x,ref=ref,p=p,err=err))
@app.post('/media/{id}/discogs/apply')
def discogs_apply(id:int,rid:str=Form(...)):
    s=Session(); x=s.get(Medium,id); msg='Eintrag nicht gefunden.'
    if x:
        try: msg='Von Discogs ergänzt (leere Felder, Titelliste, Cover).' if apply_discogs(x,s,discogs_id(rid)) else 'Discogs antwortet gerade nicht, bitte später erneut versuchen.'
        except Exception: logging.exception('Discogs-Uebernahme fehlgeschlagen'); s.rollback(); msg='Übernahme fehlgeschlagen, Details im Log.'
    return RedirectResponse(f'/media/{id}?message={quote(msg)}',303)
@app.get('/media/{id}/match')
def match_page(request:Request,id:int,artist:str=None,title:str=None):
    s=Session(); x=s.get(Medium,id)
    if not x: return RedirectResponse('/media',303)
    a=x.artist if artist is None else artist; t=x.title if title is None else title
    cands=mb_similar_search(a,t)
    dres,derr=discogs_search(a,t)
    return templates.TemplateResponse(request,'match.html',ctx(request,item=x,sa=a or '',st=t or '',cands=cands,dres=dres,derr=derr,has_token=bool(DISCOGS_TOKEN),dq=quote((a or '')+' '+(t or ''))))
@app.post('/media/{id}/match/apply')
def match_apply(id:int,release_mbid:str=Form(...)):
    s=Session(); x=s.get(Medium,id); msg='Eintrag nicht gefunden.'
    if x:
        d,err=mb_get(f'https://musicbrainz.org/ws/2/release/{release_mbid}?inc=release-groups&fmt=json')
        if err or not d: msg='MusicBrainz antwortet gerade nicht, bitte später erneut versuchen.'
        else:
            x.release_mbid=release_mbid; x.release_group_mbid=(d.get('release-group') or {}).get('id') or None
            bc=clean_barcode(d.get('barcode') or '')
            if bc and not x.barcode and not s.scalar(select(Medium).where(Medium.barcode==bc)): x.barcode=bc
            s.commit()
            try: refresh_item(x,s); msg='Ausgabe zugeordnet; fehlende Angaben, Titelliste, Genre und Cover wurden ergänzt.'
            except Exception: logging.exception('Zuordnung fehlgeschlagen'); s.rollback(); msg='Ausgabe zugeordnet, das Ergänzen ist aber fehlgeschlagen (siehe Log).'
    return RedirectResponse(f'/media/{id}?message={quote(msg)}',303)
@app.post('/media/dates/fetch-missing')
def fetch_missing_dates():
 s=Session(); ok=fail=0
 for x in s.scalars(select(Medium).where(or_(Medium.release_date==None,Medium.release_date==''))).all():
  try:
   if fetch_release_date_for(x,s): ok+=1
   else: fail+=1
  except Exception: fail+=1
 return RedirectResponse(f'/media?message={quote(f"Erscheinungsdatum geladen: {ok}, nicht gefunden: {fail}")}',303)
@app.post('/media/covers/fetch-missing')
def fetch_missing():
 start_cover_job(); return RedirectResponse('/media',303)
@app.post('/media/{id}/cover')
def refresh_cover(id:int):
 s=Session(); x=s.get(Medium,id)
 if x: fetch_cover_for(x,s)
 return RedirectResponse(f'/media/{id}',303)
@app.post('/media/{id}/delete')
def delete(id:int):
 s=Session(); x=s.get(Medium,id)
 if x:
  for f in (DATA/'covers').glob(f'{x.id}.*'): f.unlink()
  s.query(AudioFile).filter(AudioFile.medium_id==x.id).delete(); s.delete(x);s.commit()
 return RedirectResponse('/media',303)

# ---------------- Audio-Import ----------------
HOST_HOME=os.getenv('HOST_HOME','')
JOB={'state':'idle','folders':[],'done':0,'total':0,'albums':[],'error':'','result':None}
def audio_scan_worker(folders):
 """Liest Ordner ein und gleicht ab. Speichert nichts (Probelauf)."""
 s=Session()
 try:
  known={r[0] for r in s.query(AudioFile.path).all()}
  dir_medium={}
  for pth,mid in s.query(AudioFile.path,AudioFile.medium_id).all():
   if mid: dir_medium[os.path.dirname(pth)]=mid
  paths=[]
  for f in folders:
   for pth in au.collect_files(f):
    if pth not in known: paths.append(pth)
  JOB.update(total=len(paths),done=0)
  recs=[]
  for pth in paths:
   try: recs.append(au.read_tags(pth))
   except Exception: logging.exception('Datei nicht lesbar: %s',pth)
   JOB['done']+=1
  idx=au.index_media([(m.id,m.artist,m.title,len(m.tracks),m.ownership,[t.title for t in m.tracks]) for m in s.scalars(select(Medium)).all()])
  JOB['albums']=au.make_albums(au.group_files(recs,dir_medium),idx); JOB['state']='ready'
 except Exception as e:
  logging.exception('Audio-Scan fehlgeschlagen'); JOB.update(state='error',error=str(e))
 finally: s.close()
def apply_album(s,alb,choice):
 """Gibt 'attached', 'new' oder 'skipped' zurueck."""
 if choice=='skip' or not alb['files']: return 'skipped'
 fmts=alb['formats']
 if choice.startswith('attach:'):
  m=s.get(Medium,int(choice.split(':')[1]))
  if not m: return 'skipped'
  if (m.ownership or 'cd')=='cd': m.ownership='cd_digital'
  m.file_formats=norm_formats(f"{m.file_formats or ''}, {fmts}") or None; res='attached'
  if m.source=='files':
   have={au.norm_base(t.title) for t in m.tracks}; pos=len(m.tracks)
   for r in sorted(alb['files'],key=lambda r:(r['disc'] or 1,r['track'] or 999,r['path'])):
    k=au.norm_base(r['title'])
    if k in have: continue
    have.add(k); pos+=1; L=r['length']*1000 if r['length'] else None
    s.add(Track(medium_id=m.id,position=pos,disc_number=r['disc'] or 1,number=str(r['track'] or pos),title=r['title'],length_ms=L,duration=duration(L) if L else '',artist=r['artist'] or None))
   m.track_count=pos
 else:
  y=alb['year'] or ''
  m=Medium(title=alb['album'] or 'Unbekanntes Album',artist=alb['artist'],year=y or None,release_date=y or None,ownership='digital',genre=alb.get('genre') or None,genres=alb.get('genre') or None,file_formats=norm_formats(fmts) or None,source='files',release_group_type='Compilation' if au.norm_artist(alb['artist'])=='various artists' else None,track_count=alb['n'])
  s.add(m); s.flush(); seen=set(); i=-1
  for r in sorted(alb['files'],key=lambda r:(r['disc'] or 1,r['track'] or 999,r['path'])):
   k=au.norm_base(r['title'])
   if k in seen: continue
   seen.add(k); i+=1
   L=r['length']*1000 if r['length'] else None
   s.add(Track(medium_id=m.id,position=i+1,disc_number=r['disc'] or 1,number=str(r['track'] or i+1),title=r['title'],length_ms=L,duration=duration(L) if L else '',artist=r['artist'] or None))
  res='new'
 for r in alb['files']:
  s.add(AudioFile(path=r['path'],fmt=r['fmt'],artist=r['artist'],album=r['album'],title=r['title'],track_no=r['track'],disc_no=r['disc'],length_s=r['length'],medium_id=m.id))
 s.commit(); return res
def audio_apply_worker(choices):
 s=Session(); res={'attached':0,'new':0,'skipped':0,'files':0}
 try:
  JOB.update(state='applying',total=len(JOB['albums']),done=0)
  for alb in JOB['albums']:
   try:
    r=apply_album(s,alb,choices.get(alb['idx'],'skip')); res[r]+=1
    if r!='skipped': res['files']+=len(alb['files'])
   except Exception: logging.exception('Album nicht uebernommen: %s',alb.get('album')); s.rollback(); res['skipped']+=1
   JOB['done']+=1
  JOB.update(state='done',result=res,albums=[])
  if res['new'] or res['attached']:
   if not REFRESH['running']:
    REFRESH.update(running=True,done=0,total=0,ok=0,fail=0)
    try: cover_all_worker()
    except Exception: logging.exception('Cover-Nachladen nach Import fehlgeschlagen')
 except Exception as e:
  logging.exception('Audio-Import fehlgeschlagen'); JOB.update(state='error',error=str(e))
 finally: s.close()
@app.get('/audio',response_class=HTMLResponse)
def audio_page(request:Request):
 s=Session(); n_files=s.query(AudioFile).count(); n_media=s.query(AudioFile.medium_id).distinct().count(); s.close()
 albums=JOB['albums'] if JOB['state']=='ready' else []
 groups={k:[a for a in albums if a['status']==k] for k in ('review','match','known','new')}
 roots=[{'path':c,'label':h,'name':n,'ok':os.path.isdir(c)} for c,h,n in au.ROOTS]
 return templates.TemplateResponse(request,'audio.html',ctx(request,job=JOB,groups=groups,roots=roots,n_files=n_files,n_media=n_media,host_label=au.host_label))
@app.get('/audio/browse')
def audio_browse(request:Request,path:str=''):
 if not path: return JSONResponse({'path':'','label':'','parent':'','dirs':[{'name':n,'path':c,'label':h} for c,h,n in au.ROOTS if os.path.isdir(c)],'audio':0,'error':''})
 p=au.safe_dir(au.to_container_path(path,HOST_HOME))
 if not p: return JSONResponse({'path':path,'label':path,'parent':'','dirs':[],'audio':0,'error':i18n.tr_text(get_lang(request),'Ordner nicht gefunden oder nicht freigegeben.')})
 dirs,n,err=au.list_dirs(p); err=i18n.tr_text(get_lang(request),err) if err else err; roots=[c for c,_,_ in au.ROOTS]
 parent='' if p in roots else os.path.dirname(p)
 return JSONResponse({'path':p,'label':au.host_label(p),'parent':parent,'audio':n,'error':err,'dirs':[{'name':d,'path':os.path.join(p,d),'label':d} for d in dirs]})
@app.post('/audio/scan')
def audio_scan(folders:list[str]=Form([]),manual:str=Form('')):
 if JOB['state'] in ('scanning','applying'): return RedirectResponse('/audio',303)
 fl=[]
 for f in list(folders)+[x for x in manual.split('\n') if x.strip()]:
  p=au.safe_dir(au.to_container_path(f,HOST_HOME))
  if p and p not in fl: fl.append(p)
 if not fl:
  JOB.update(state='error',error='Kein gültiger Ordner ausgewählt.',albums=[]); return RedirectResponse('/audio',303)
 JOB.update(state='scanning',folders=fl,done=0,total=0,albums=[],error='',result=None)
 threading.Thread(target=audio_scan_worker,args=(fl,),daemon=True).start()
 return RedirectResponse('/audio',303)
@app.post('/audio/apply')
async def audio_apply(request:Request):
 if JOB['state']!='ready': return RedirectResponse('/audio',303)
 form=await request.form(max_fields=100000,max_files=0); choices={}
 for k,v in form.items():
  if k.startswith('d_') and k[2:].isdigit(): choices[int(k[2:])]=str(v)
 threading.Thread(target=audio_apply_worker,args=(choices,),daemon=True).start()
 return RedirectResponse('/audio',303)
@app.get('/audio/status')
def audio_status():
 return {'state':JOB['state'],'done':JOB['done'],'total':JOB['total']}
@app.post('/audio/reset')
def audio_reset():
 if JOB['state'] not in ('scanning','applying'): JOB.update(state='idle',albums=[],error='',result=None,done=0,total=0)
 return RedirectResponse('/audio',303)
EXCEL_FIELDS=['barcode','title','artist','artist_sort','artist_mbid','year','date','release_date','country','label','catalog_number','format','media_count','disc_count','track_count','status','packaging','language','script','release_mbid','release_group_mbid','release_group_type','asin','annotation','disambiguation','quality','genre','genres','tags','styles','notes','cover_path','cover_url','source','source_id','ownership','file_formats','created_at','tracks']
# ---------------- Datei-Import (Tabellen: xlsx, ods, csv) ----------------
from . import importer as im
IMP={'state':'idle','filename':'','rows':[],'headers':[],'has_header':True,'mapping':{},'backup':False,'items':[],'done':0,'total':0,'error':'','result':None}
INT_COLS={'media_count','disc_count','track_count'}
def mb_cand(r):
 li=r.get('label-info') or []; fm=[m.get('format') or '?' for m in r.get('media',[])]
 return {'id':r.get('id'),'title':r.get('title',''),'artist':artist_credit(r.get('artist-credit') or []),'date':r.get('date',''),'country':r.get('country',''),'barcode':r.get('barcode',''),'label':', '.join(dict.fromkeys(x['label']['name'] for x in li if x.get('label'))),'format':' + '.join(fm),'is_cd':any('cd' in f.lower() for f in fm),'status':r.get('status',''),'tracks':sum(m.get('track-count',0) for m in r.get('media',[]))}
def _cand_sort(c): return (status_rank({'status':c['status']}),0 if c['is_cd'] else 1,c['date'] or '9999')
def mb_find_by_title(artist,title):
 """Ausgaben zu Interpret + Albumtitel. Gibt (gute Treffer, aehnliche Treffer) zurueck, je nach Zuverlaessigkeit."""
 def q(v): return re.sub(r'["\\]',' ',str(v)).strip()
 various=au.norm_artist(artist)=='various artists' or not artist
 base=[f'release:"{q(title)}"']+([] if various else [f'artist:"{q(artist)}"'])
 rels=[]
 for extra in (' AND status:official',''):
  d,err=mb_get('https://musicbrainz.org/ws/2/release?query='+quote(' AND '.join(base)+extra)+'&fmt=json&limit=25')
  if d and d.get('releases'): rels=d['releases']; break
 tb=au.norm_base(title); mine=au.norm_artist(artist); good=[]; near=[]; seen=set()
 for r in rels:
  c=mb_cand(r)
  if not c['id'] or c['id'] in seen: continue
  seen.add(c['id']); theirs=au.norm_artist(c['artist'])
  a_ok=various or mine==theirs or mine in theirs or theirs in mine or au.similar(mine,theirs)>=0.85
  sim=au.similar(tb,au.norm_base(c['title']))
  if a_ok and sim>=0.85: good.append(c)
  elif a_ok and sim>=0.6: near.append(c)
 good.sort(key=_cand_sort); near.sort(key=_cand_sort); return good,near
def import_match_worker():
 s=Session()
 try:
  have_bc={norm_bc(b) for (b,) in s.query(Medium.barcode).filter(Medium.barcode!=None).all()}
  have_rel={b for (b,) in s.query(Medium.release_mbid).filter(Medium.release_mbid!=None).all()}
  have_at={}
  for m in s.scalars(select(Medium)).all(): have_at[(au.norm_artist(m.artist),au.norm_base(m.title))]=f"{m.artist or ''} – {m.title}".strip(' –')
  rows=IMP['rows'][1:] if IMP['has_header'] else IMP['rows']; hdr=IMP['headers']; items=[]; IMP.update(total=len(rows),done=0)
  for i,r in enumerate(rows):
   r=list(r)+['']*(len(hdr)+5-len(r))
   if IMP['backup']:
    d={str(hdr[k]).strip().lower():r[k] for k in range(len(hdr)) if hdr[k]}
    for k in list(d):
     if d[k]=='': d[k]=None
    for k in INT_COLS:
     try: d[k]=int(float(d[k])) if d.get(k) is not None else None
     except Exception: d[k]=None
    for k in ('cover_path','id','created_at'): d.pop(k,None)
    tr=str(d.pop('tracks','') or ''); d['tracks']=[{'position':n+1,'disc_number':1,'number':str(n+1),'title':x.strip(),'duration':''} for n,x in enumerate(tr.splitlines()) if x.strip()]
    bc=clean_barcode(d.get('barcode')); d['barcode']=bc or None
    it={'idx':i,'artist':d.get('artist') or '','title':d.get('title') or '','barcode':bc,'data':d,'cands':[],'note':''}
    if not it['title']: it.update(status='skip',default='skip',note='Ohne Titel')
    elif (bc and norm_bc(bc) in have_bc) or (d.get('release_mbid') and d['release_mbid'] in have_rel) or (au.norm_artist(it['artist']),au.norm_base(it['title'])) in have_at: it.update(status='exists',default='skip')
    else: it.update(status='full',default='full')
    items.append(it); IMP['done']+=1; continue
   g=lambda f:(r[IMP['mapping'][f]] if IMP['mapping'].get(f) is not None else '').strip()
   artist,title,bc,year=g('artist'),g('title'),clean_barcode(g('barcode')),g('year')[:4]
   it={'idx':i,'artist':artist,'title':title,'barcode':bc,'year':year,'cands':[],'note':'','data':None}
   if not title and not bc: it.update(status='skip',default='skip',note='Weder Titel noch Barcode'); items.append(it); IMP['done']+=1; continue
   if bc and norm_bc(bc) in have_bc: it.update(status='exists',default='skip',note='Barcode schon vorhanden')
   elif title and (au.norm_artist(artist),au.norm_base(title)) in have_at: it.update(status='exists',default='skip',note='Schon vorhanden als '+have_at[(au.norm_artist(artist),au.norm_base(title))])
   else:
    cands=[]
    if bc:
     hits,_,err=mb_releases_by_barcode(bc,15,official_only=True)
     cands=[mb_cand(x) for x in hits[:6] if x.get('id')]
    if cands: it.update(status='found',cands=cands,default='rel:'+cands[0]['id'])
    elif title:
     good,near=mb_find_by_title(artist,title)
     if good: it.update(status='found',cands=good[:6],default='rel:'+good[0]['id'],note=(f'{len(good)-1} weitere Ausgaben' if len(good)>1 else ''))
     elif near: it.update(status='unsure',cands=near[:6],default='skip',note='Titel nur ähnlich')
     else: it.update(status='nf',default='plain',note='Bei MusicBrainz nicht gefunden')
    else: it.update(status='nf',default='plain',note='Barcode bei MusicBrainz nicht gefunden, kein Titel')
   items.append(it); IMP['done']+=1
  IMP.update(items=items,state='ready')
 except Exception as e:
  logging.exception('Import-Abgleich fehlgeschlagen'); IMP.update(state='error',error=str(e))
 finally: s.close()
def import_apply_worker(choices):
 s=Session(); res={'new':0,'plain':0,'skipped':0}
 try:
  IMP.update(state='applying',total=len(IMP['items']),done=0)
  for it in IMP['items']:
   ch=choices.get(it['idx'],it['default'])
   try:
    if ch=='skip' or it['status'] in ('exists','skip'): res['skipped']+=1
    elif ch=='full':
     d=dict(it['data']); d['ownership']=norm_ownership(d.get('ownership')); save_item(d,s); res['new']+=1
    elif ch.startswith('rel:'):
     rel=ch[4:]
     if s.scalar(select(Medium).where(Medium.release_mbid==rel)): res['skipped']+=1
     else:
      d,err=mb_get(f'https://musicbrainz.org/ws/2/release/{rel}?inc={MB_REL_INC}&fmt=json')
      if err or not d: raise RuntimeError('MusicBrainz nicht erreichbar')
      p=parse_release(d,''); p['ownership']='cd'; bc=clean_barcode(p.get('barcode'))
      if bc and s.scalar(select(Medium).where(Medium.barcode==bc)): res['skipped']+=1
      else: save_item(p,s); res['new']+=1
    else:
     bc=it['barcode'] if it['barcode'] and not s.scalar(select(Medium).where(Medium.barcode==it['barcode'])) else None
     save_item({'title':it['title'] or 'Ohne Titel','artist':it['artist'],'year':it.get('year') or None,'barcode':bc,'ownership':'cd','source':'import','tracks':[]},s); res['plain']+=1
   except Exception:
    logging.exception('Zeile %s nicht importiert',it['idx']); s.rollback(); res['skipped']+=1
   IMP['done']+=1
  IMP.update(state='done',result=res,items=[])
  for fn in (cover_all_worker,genre_all_worker):
   if not REFRESH['running']:
    REFRESH.update(running=True,done=0,total=0,ok=0,fail=0)
    try: fn()
    except Exception: logging.exception('Nachladen nach Import fehlgeschlagen')
 except Exception as e:
  logging.exception('Import fehlgeschlagen'); IMP.update(state='error',error=str(e))
 finally: s.close()
@app.get('/import',response_class=HTMLResponse)
def import_page(request:Request):
 groups={k:[x for x in IMP['items'] if x['status']==k] for k in ('unsure','nf','found','full','exists','skip')} if IMP['state']=='ready' else {}
 cols=[{'i':i,'label':f"{im.col_letter(i)}: {(IMP['headers'][i] if IMP['has_header'] else (IMP['rows'][0][i] if IMP['rows'] else '')) or i18n.tr_text(get_lang(request),'(leer)')}"} for i in range(len(IMP['headers']))]
 preview=IMP['rows'][:6]
 return templates.TemplateResponse(request,'import.html',ctx(request,job=IMP,groups=groups,cols=cols,preview=preview,labels=im.LABELS))
@app.post('/import/upload')
async def import_upload(file:UploadFile=File(...)):
 if IMP['state'] in ('matching','applying'): return RedirectResponse('/import',303)
 rows,err=im.read_table(file.filename,await file.read())
 if err: IMP.update(state='error',error=err); return RedirectResponse('/import',303)
 ncol=max(len(r) for r in rows); rows=[list(r)+['']*(ncol-len(r)) for r in rows]
 headers=rows[0]; IMP.update(state='mapping',filename=file.filename,rows=rows,headers=headers,has_header=True,mapping=im.guess_mapping(headers),backup=im.is_backup(headers),items=[],error='',result=None,done=0,total=0)
 if IMP['backup']:
  IMP.update(state='matching'); threading.Thread(target=import_match_worker,daemon=True).start()
 return RedirectResponse('/import',303)
@app.post('/import/match')
async def import_match(request:Request):
 if IMP['state']!='mapping': return RedirectResponse('/import',303)
 f=await request.form(); has=f.get('header')=='1'; m={}
 for k in ('artist','title','barcode','year'):
  v=str(f.get('col_'+k) or ''); m[k]=int(v) if v.isdigit() else None
 if m['title'] is None and m['barcode'] is None:
  IMP.update(error='Bitte mindestens die Spalte für den Albumtitel oder den Barcode wählen.'); return RedirectResponse('/import',303)
 IMP.update(has_header=has,mapping=m,state='matching',error='',done=0,total=0)
 threading.Thread(target=import_match_worker,daemon=True).start(); return RedirectResponse('/import',303)
@app.post('/import/apply')
async def import_apply(request:Request):
 if IMP['state']!='ready': return RedirectResponse('/import',303)
 f=await request.form(); ch={int(k[2:]):str(v) for k,v in f.items() if k.startswith('d_') and k[2:].isdigit()}
 threading.Thread(target=import_apply_worker,args=(ch,),daemon=True).start(); return RedirectResponse('/import',303)
@app.get('/import/status')
def import_status():
 return {'state':IMP['state'],'done':IMP['done'],'total':IMP['total']}
@app.post('/import/reset')
def import_reset():
 if IMP['state'] not in ('matching','applying'): IMP.update(state='idle',rows=[],items=[],error='',result=None,done=0,total=0)
 return RedirectResponse('/import',303)
@app.get('/export',response_class=HTMLResponse)
def export_page(request:Request):
 s=Session(); n=s.query(Medium).count(); s.close()
 return templates.TemplateResponse(request,'export.html',ctx(request,n=n))
import csv, zipfile
from io import StringIO
from xml.sax.saxutils import escape as xml_escape
MD_FIELDS=[('artist','Interpret'),('title','Titel'),('year','Jahr'),('release_date','Erschienen'),('genre','Genre'),('ownership','Besitz'),('file_formats','Formate'),('label','Label'),('barcode','Barcode')]
def export_rows(view):
 s=Session(); stmt=select(Medium).order_by(Medium.id)
 if view=='cd': stmt=stmt.where(Medium.ownership.in_(['cd','cd_digital']))
 elif view=='digital': stmt=stmt.where(Medium.ownership=='digital')
 rows=[]
 for x in s.scalars(stmt):
  r=[]
  for f in EXCEL_FIELDS:
   if f=='tracks': r.append('\n'.join(t.title or '' for t in x.tracks))
   else:
    v=getattr(x,f); r.append('' if v is None else v)
  rows.append(r)
 s.close(); return rows
def _txt(v): return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(v))
def build_ods(header,rows):
 def cell(v):
  v=_txt(v)
  if v=='': return '<table:table-cell/>'
  return '<table:table-cell office:value-type="string">'+''.join(f'<text:p>{xml_escape(l)}</text:p>' for l in v.split('\n'))+'</table:table-cell>'
 body=''.join('<table:table-row>'+''.join(cell(v) for v in r)+'</table:table-row>' for r in [header]+rows)
 content=('<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2"><office:body><office:spreadsheet><table:table table:name="MediaDB">'+body+'</table:table></office:spreadsheet></office:body></office:document-content>')
 manifest='<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'
 out=BytesIO()
 with zipfile.ZipFile(out,'w') as z:
  z.writestr(zipfile.ZipInfo('mimetype'),'application/vnd.oasis.opendocument.spreadsheet',compress_type=zipfile.ZIP_STORED)
  z.writestr('META-INF/manifest.xml',manifest,compress_type=zipfile.ZIP_DEFLATED); z.writestr('content.xml',content,compress_type=zipfile.ZIP_DEFLATED)
 out.seek(0); return out
def build_markdown(view,lang='de'):
 s=Session(); stmt=select(Medium)
 if view=='cd': stmt=stmt.where(Medium.ownership.in_(['cd','cd_digital']))
 elif view=='digital': stmt=stmt.where(Medium.ownership=='digital')
 items=sorted(s.scalars(stmt).all(),key=lambda x:(au.norm_full(x.artist),x.release_date or x.year or '9999',x.title or ''))
 def c(v): return _txt(v if v is not None else '').replace('|','\\|').replace('\n',' ').strip()
 T=partial(i18n.tr_text,lang); lines=['# MediaDB','',T('§ Einträge, Stand §',len(items),f'{datetime.now():%d.%m.%Y}'),'','| '+' | '.join(T(h) for _,h in MD_FIELDS)+' |','|'+'|'.join(['---']*len(MD_FIELDS))+'|']
 for x in items: lines.append('| '+' | '.join(c(T(OWN_SHORT.get(x.ownership or 'cd','CD')) if f=='ownership' else getattr(x,f)) for f,_ in MD_FIELDS)+' |')
 s.close(); return '\n'.join(lines)+'\n'
@app.get('/export.xlsx')
@app.get('/export/download')
def export(request:Request,view:str='all',format:str='xlsx'):
 view=view if view in ('cd','digital') else 'all'
 if format=='md': return StreamingResponse(iter([build_markdown(view,get_lang(request)).encode('utf-8')]),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename=mediadb-musik.md'})
 rows=export_rows(view)
 if format=='csv':
  buf=StringIO(); w=csv.writer(buf,delimiter=';',quoting=csv.QUOTE_MINIMAL,lineterminator='\r\n'); w.writerow(EXCEL_FIELDS)
  for r in rows: w.writerow([_txt(v) for v in r])
  return StreamingResponse(iter([buf.getvalue().encode('utf-8-sig')]),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=mediadb-musik.csv'})
 if format=='ods': return StreamingResponse(build_ods(EXCEL_FIELDS,[[_txt(v) for v in r] for r in rows]),media_type='application/vnd.oasis.opendocument.spreadsheet',headers={'Content-Disposition':'attachment; filename=mediadb-musik.ods'})
 wb=Workbook(); ws=wb.active; ws.title='MediaDB'; ws.append(EXCEL_FIELDS)
 for r in rows: ws.append(r)
 out=BytesIO(); wb.save(out); out.seek(0); return StreamingResponse(out,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename=mediadb-musik.xlsx'})
