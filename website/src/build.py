"""Baut die Projektseite in website/dist/ (zum Hochladen per FTP) und website/preview.html (nur Vorschau, Google Fonts).
Aufruf im Projektordner:  python3 website/src/build.py"""
import shutil, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; WEB=HERE.parent; ROOT=WEB.parent; DIST=WEB/'dist'
VERSION=(ROOT/'VERSION').read_text().strip()
src=(HERE/'index.src.html').read_text(encoding='utf-8')
legal=(HERE/'impressum.src.html').read_text(encoding='utf-8')

# EAN-13 Barcode (Beispielnummer 4006381333931) als SVG
L=['0001101','0011001','0010011','0111101','0100011','0110001','0101111','0111011','0110111','0001011']
R=[''.join('1' if c=='0' else '0' for c in x) for x in L]; G=[x[::-1] for x in R]
PAR=['LLLLLL','LLGLGG','LLGGLG','LLGGGL','LGLLGG','LGGLLG','LGGGLL','LGLGLG','LGLGGL','LGGLGL']
code='4006381333931'
bits='101'+''.join((L if PAR[int(code[0])][i]=='L' else G)[int(c)] for i,c in enumerate(code[1:7]))+'01010'+''.join(R[int(c)] for c in code[7:])+'101'
guard=set(range(0,3))|set(range(45,50))|set(range(92,95)); rects=[]; i=0
while i<95:
    if bits[i]=='1':
        j=i
        while j<95 and bits[j]=='1' and ((j in guard)==(i in guard)): j+=1
        rects.append(f'<rect x="{i+11}" y="0" width="{j-i}" height="{74 if i in guard else 66}"/>'); i=j
    else: i+=1
ean=(f'<svg class="ean" viewBox="0 0 117 82" role="img" aria-label="EAN-13 {code}"><g class="bars">{"".join(rects)}</g>'
     f'<g class="digits"><text x="5" y="80">{code[0]}</text><text x="35" y="80">{code[1:7]}</text><text x="82" y="80">{code[7:]}</text></g></svg>')
src=src.replace('<!--EAN-->',ean).replace('MediaDB 1.0.0 · GPL-3.0',f'MediaDB {VERSION} · GPL-3.0')

FONTS=[('Instrument','InstrumentSerif-Regular.ttf','400','normal'),('Instrument','InstrumentSerif-Italic.ttf','400','italic'),
  ('Inter','Inter-Variable.ttf','100 900','normal'),('Inter','Inter-VariableItalic.ttf','100 900','italic'),
  ('Archivo','Archivo-Variable.ttf','100 900','normal'),('GeistMono','GeistMono-Variable.ttf','100 900','normal')]
local='<style>'+''.join(f"@font-face{{font-family:{a};src:url('fonts/{f}') format('truetype');font-weight:{w};font-style:{s};font-display:swap}}" for a,f,w,s in FONTS)+'</style>'
google=('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600&family=Geist+Mono:wght@400;600&family=Instrument+Serif:ital@0;1&family=Inter:wght@400;600&display=swap">')

split=src.index('<div class="shell">')
head, body = src[:split], src[split:]
style=head[head.index('<style>\n/*'):]           # gemeinsame Gestaltung
script=body[body.index('<script>'):]            # Sprache und Farbschema

def page(title, desc, inner_head, inner_body):
    return ('<!doctype html>\n<html lang="de" data-lang="de">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            f'<title>{title}</title>\n<meta name="description" content="{desc}">\n'+inner_head+'</head>\n<body>\n'+inner_body+'\n</body>\n</html>\n')

DIST.mkdir(exist_ok=True)
desc='MediaDB – selbst gehostete Datenbank für CDs und Musikdateien, bald auch Filme und Serien. Läuft im Heimnetz, Daten bleiben bei dir.'
(DIST/'index.html').write_text(page('MediaDB',desc,local+'\n'+style,body),encoding='utf-8')
legal_body=('<div class="shell">\n<nav aria-label="Navigation"><a class="brand" href="index.html">Media<em>DB</em></a>'
            '<a class="back" href="index.html">← Zur Startseite</a>'
            '<div class="pill"><button type="button" id="theme" aria-label="Farbschema wechseln">◐ Theme</button></div></nav>\n'
            +legal+'\n<footer><span class="sp">MediaDB · GPL-3.0</span><a href="index.html">Startseite</a><span>Keine Cookies, kein Tracking</span></footer>\n</div>\n'+script)
(DIST/'impressum.html').write_text(page('Impressum · MediaDB','Impressum und Datenschutzerklärung der Projektseite MediaDB.',local+'\n'+style,legal_body),encoding='utf-8')
(DIST/'fonts').mkdir(exist_ok=True)
for _,f,_,_ in FONTS: shutil.copy2(ROOT/'static'/'fonts'/f,DIST/'fonts'/f)
shutil.copy2(HERE/'LIZENZEN-SCHRIFTEN.txt',DIST/'fonts'/'LIZENZEN.txt')
(WEB/'preview.html').write_text(head.replace('<!--FONTS-->',google)+body,encoding='utf-8')
# Zip zum Hochladen: Inhalt von dist/ direkt im Hauptverzeichnis der Zip
z=WEB/f'mediadb-website-{VERSION}.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(DIST.rglob('*')):
        if f.is_file(): zf.write(f,f.relative_to(DIST).as_posix())
print('fertig:',z)
