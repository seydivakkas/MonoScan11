#!/usr/bin/env python3
"""Render the approved MonoScan11 UI-WF-1.0 *design concepts* locally.

These are NOT simulator captures, photos, test outcomes, or screenshots of a running iOS app.
Requires Pillow; independent of Xcode, macOS and ARKit.
"""
from __future__ import annotations
import math, json, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "screenshots"
SIZE = (828,1792); S=2
COLORS = dict(bg="#071521", bg2="#0B1B2A", card="#102639", card2="#173249", edge="#25475A", cyan="#28D4E9", cyan2="#17ABC9", white="#EDF8FF", secondary="#9BB2C2", quiet="#6C879A", green="#56E3A8", amber="#FFC27D", red="#FF7A88", blue="#7BC3FF", dark="#06111D")
def locate_fonts():
    """Prefer Windows system fonts when run on Windows; support Linux/macOS."""
    win = Path(os.environ.get('WINDIR','C:/Windows')) / 'Fonts'
    pairs = [
        (win/'segoeui.ttf', win/'segoeuib.ttf'),
        (win/'arial.ttf', win/'arialbd.ttf'),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
        (Path('/Library/Fonts/Arial.ttf'),Path('/Library/Fonts/Arial Bold.ttf')),
    ]
    for reg,bold in pairs:
        if reg.exists() and bold.exists():return str(reg),str(bold)
    # Pillow's font search can still resolve these names on some systems.
    for reg,bold in [('DejaVuSans.ttf','DejaVuSans-Bold.ttf'),('arial.ttf','arialbd.ttf')]:
        try:
            ImageFont.truetype(reg,16);ImageFont.truetype(bold,16)
            return reg,bold
        except OSError: pass
    raise RuntimeError('Türkçe glif içeren Segoe UI, Arial veya DejaVu Sans fontu gerekir.')

FREG,FBOLD=locate_fonts()

def font(n, bold=False): return ImageFont.truetype(FBOLD if bold else FREG, round(n*S))

def rgb(v):
    v=COLORS.get(v,v)
    return tuple(bytes.fromhex(v.lstrip('#'))) if isinstance(v,str) and v.startswith('#') else v

class UI:
    def __init__(self,kind='page',active=None):
        self.im=Image.new('RGB',SIZE,rgb('bg'))
        self.d=ImageDraw.Draw(self.im)
        for y in range(SIZE[1]):
            a=y/(SIZE[1]-1)
            base=(7+int(3*a),21+int(10*a),33+int(13*a))
            self.d.line((0,y,SIZE[0],y),fill=base)
        self._halo(720,230,310, (16,92,120,45))
        self.active=active
        self.status()
        if active: self.nav(active)
    def _halo(self,x,y,r,shade):
        layer=Image.new('RGBA',SIZE,(0,0,0,0)); t=ImageDraw.Draw(layer)
        t.ellipse((x-r,y-r,x+r,y+r),fill=shade)
        layer=layer.filter(ImageFilter.GaussianBlur(150))
        self.im=Image.alpha_composite(self.im.convert('RGBA'),layer).convert('RGB'); self.d=ImageDraw.Draw(self.im)
    def rect(self,x,y,w,h,fill='card',radius=14,stroke=None,width=1):
        b=(round(x*S),round(y*S),round((x+w)*S),round((y+h)*S))
        self.d.rounded_rectangle(b,radius=radius*S,fill=rgb(fill),outline=rgb(stroke) if stroke else None,width=width*S)
    def line(self,xy,color='edge',width=1): self.d.line([(round(x*S),round(y*S)) for x,y in xy],fill=rgb(color),width=width*S,joint='curve')
    def circle(self,cx,cy,r,fill='card',outline=None,width=1):
        self.d.ellipse(((cx-r)*S,(cy-r)*S,(cx+r)*S,(cy+r)*S),fill=rgb(fill) if fill else None,outline=rgb(outline) if outline else None,width=width*S)
    def txt(self,s,x,y,size=14,color='white',bold=False,align='left'):
        s=str(s); f=font(size,bold)
        if align!='left':
            tw=self.d.textbbox((0,0),s,font=f)[2]/S
            x=x-tw/2 if align=='center' else x-tw
        self.d.text((round(x*S),round(y*S)),s,font=f,fill=rgb(color),stroke_width=0)
    def wrapped(self,s,x,y,maxw,size=14,color='secondary',leading=1.40,bold=False,maxlines=10):
        f=font(size,bold); words=s.split(); lines=[]; a=''
        for w in words:
            b=(a+' '+w).strip()
            if self.d.textlength(b,font=f) > maxw*S and a: lines.append(a); a=w
            else:a=b
        if a:lines.append(a)
        for i,l in enumerate(lines[:maxlines]):self.txt(l,x,y+i*size*leading,size,color,bold)
        return y+min(len(lines),maxlines)*size*leading
    def icon(self,key,x,y,sz=20,c='cyan'):
        # centred basic line icons (not platform asset glyphs)
        k=key; w=1.8; c=rgb(c)
        u=sz/2
        def line(xy,width=w):self.d.line([((x+px)*S,(y+py)*S) for px,py in xy],fill=c,width=round(width*S),joint='curve')
        def rr(dx,dy,ww,hh,rad=3):self.d.rounded_rectangle(((x+dx)*S,(y+dy)*S,(x+dx+ww)*S,(y+dy+hh)*S),radius=rad*S,outline=c,width=2*S)
        if k in ['back','chevron']:
            line([(u+3,3),(u-4,u),(u+3,sz-3)])
        elif k=='next':line([(u-4,3),(u+4,u),(u-4,sz-3)])
        elif k=='camera':
            rr(2,6,sz-4,sz-9,3);rr(6,3,sz-12,5,2);self.d.ellipse(((x+u-4)*S,(y+u-3)*S,(x+u+4)*S,(y+u+5)*S),outline=c,width=2*S)
        elif k=='folder':
            line([(3,7),(9,7),(11,10),(sz-3,10),(sz-3,sz-4),(3,sz-4),(3,7)])
        elif k=='cube':
            line([(u,2),(sz-3,7),(sz-3,sz-5),(u,sz-1),(3,sz-5),(3,7),(u,2),(u,sz-1)])
            line([(3,7),(u,12),(sz-3,7)])
        elif k=='scan':
            for ax,ay,bx,by in [(3,9,3,3),(3,3,9,3),(sz-9,3,sz-3,3),(sz-3,3,sz-3,9),(3,sz-9,3,sz-3),(3,sz-3,9,sz-3),(sz-9,sz-3,sz-3,sz-3),(sz-3,sz-9,sz-3,sz-3)]: line([(ax,ay),(bx,by)])
            self.circle(x+u,y+u,2,'cyan')
        elif k=='check':line([(3,u),(u-2,sz-4),(sz-3,4)])
        elif k=='x':line([(4,4),(sz-4,sz-4)]);line([(sz-4,4),(4,sz-4)])
        elif k=='info':
            self.circle(x+u,y+u,u-2,None,'cyan',2);self.txt('i',x+u,y+2,sz*.67,'cyan',True,'center')
        elif k=='warn':
            line([(u,2),(sz-2,sz-3),(2,sz-3),(u,2)]);line([(u,7),(u,sz-9)]);self.circle(x+u,y+sz-5,1.2,'cyan')
        elif k=='home':line([(3,u),(u,3),(sz-3,u)]);line([(6,u-1),(6,sz-3),(sz-6,sz-3),(sz-6,u-1)])
        elif k=='book':line([(u,4),(u,sz-3)]);line([(u,5),(3,3),(3,sz-5),(u,sz-3),(sz-3,sz-5),(sz-3,3),(u,5)])
        elif k=='gear':
            self.circle(x+u,y+u,u-4,None,'cyan',2);self.circle(x+u,y+u,2.5,None,'cyan',2)
            for a in range(0,360,45):
                sn,cs=math.sin(math.radians(a)),math.cos(math.radians(a));line([(u+(u-3)*cs,u+(u-3)*sn),(u+u*cs,u+u*sn)])
        elif k=='image':rr(2,3,sz-4,sz-6);line([(4,sz-6),(u-2,u+1),(u+2,u+4),(sz-4,sz-8)]);self.circle(x+sz-7,y+8,2,'cyan')
        elif k=='export':line([(u,2),(u,sz-7)]);line([(u-5,7),(u,2),(u+5,7)]);line([(4,sz-10),(4,sz-3),(sz-4,sz-3),(sz-4,sz-10)])
        elif k=='more':
            for xx in [5,u,sz-5]:self.circle(x+xx,y+u,1.7,'cyan')
        elif k=='search':self.circle(x+u-3,y+u-2,u-6,None,'cyan',2);line([(u+2,u+3),(sz-2,sz-2)])
        elif k=='trash':rr(6,7,sz-12,sz-11,1);line([(4,5),(sz-4,5)]);line([(u-3,3),(u+3,3)])
        elif k=='clock':self.circle(x+u,y+u,u-2,None,'cyan',2);line([(u,u),(u,u-5),(u+3,u+2)])
        elif k=='shield':
            line([(u,2),(sz-3,5),(sz-4,u+5),(u,sz-2),(4,u+5),(3,5),(u,2)])
        elif k=='plus':line([(u,3),(u,sz-3)]);line([(3,u),(sz-3,u)])
        elif k=='file':
            line([(5,2),(sz-8,2),(sz-3,7),(sz-3,sz-2),(5,sz-2),(5,2)]);line([(sz-8,2),(sz-8,7),(sz-3,7)])
        elif k=='spark':
            line([(u,2),(u+3,u-3),(sz-2,u),(u+3,u+3),(u,sz-2),(u-3,u+3),(2,u),(u-3,u-3),(u,2)])
        else:self.circle(x+u,y+u,3,'cyan')
    def header(self,title,back=True,right=None):
        if back:self.icon('back',20,66,24)
        self.txt(title,207,68,16,'white',True,'center')
        if right:self.icon(right,367,67,22)
    def status(self):
        self.txt('9:41',28,15,13,'white',True)
        self.d.rounded_rectangle((158*S,0,255*S,31*S),radius=17*S,fill=(3,10,17))
        # status bar antenna, Wi-Fi, battery visual placeholders
        for i,h in enumerate([5,8,11,14]):self.rect(332+i*4.3,28-h,2.5,h,'white',1)
        self.txt('◕',361,12,13,'white')
        self.rect(380,16,22,11,'white',3);self.rect(402,19,2,5,'white',1)
        self.rect(384,18,14,7,'bg',1)
    def nav(self,active):
        self.rect(0,814,414,82,'bg2',0)
        self.line([(0,815),(414,815)],'edge')
        arr=[('home','Ana Sayfa'),('folder','Taramalar'),('book','Rehber'),('gear','Ayarlar')]
        for j,(ic,lab) in enumerate(arr):
            xx=52+103*j
            self.icon(ic,xx-11,830,22,'cyan' if lab==active else 'quiet')
            self.txt(lab,xx,859,10,'cyan' if lab==active else 'secondary',align='center')
        self.rect(158,888,98,4,'white',3)
    def homebar(self): self.rect(158,886,98,4,'white',3)
    def button(self,label,y=757,kind='primary',x=20,w=374,ic=None,h=50):
        fill='cyan' if kind=='primary' else 'card2' if kind=='secondary' else 'card' if kind=='disabled' else 'bg2'
        self.rect(x,y,w,h,fill,12, 'cyan' if kind=='secondary' else None)
        color='dark' if kind=='primary' else 'quiet' if kind=='disabled' else 'white'
        self.txt(label,x+w/2,y+14 if h==50 else y+h/2-8,15,color,True,align='center')
        if ic: self.icon(ic,x+w-30,y+h/2-10,20,'dark' if kind=='primary' else 'cyan')
    def card(self,x,y,w,h,title,sub=None,icon=None):
        self.rect(x,y,w,h,'card',14,'edge')
        if icon:self.icon(icon,x+15,y+14,25)
        tx=x+(52 if icon else 16)
        self.txt(title,tx,y+13,15,'white',True)
        if sub:self.wrapped(sub,tx,y+39,w-(tx-x)-14,11,'secondary')
    def tag(self,label,x,y,w=None,active=False,color=None):
        if w is None:w=max(62,14+len(label)*7.3)
        col=color or ('cyan' if active else 'secondary')
        self.rect(x,y,w,29,'card2' if active else 'card',9,'cyan' if active else 'edge')
        self.txt(label,x+w/2,y+7,10,col,True if active else False,align='center')
    def footer(self,txt=None):
        if txt:self.wrapped(txt,22,729,370,11,'secondary')
        self.homebar()
    def save(self,path):self.im.save(path,optimize=True)

# illustrative technical geometry, not a real scan
def orb(ui,cx=207,cy=355,r=120):
    ui.d.ellipse(((cx-r)*S,(cy-r*.53)*S,(cx+r)*S,(cy+r*.53)*S),outline=rgb('cyan2'),width=2*S)
    for j in range(8):
        a=j*math.tau/8;dx=math.cos(a)*r;dy=math.sin(a)*r*.53
        ui.circle(cx+dx,cy+dy,12,'card2','cyan',1)
        ui.icon('camera',cx+dx-8,cy+dy-8,16)
    ui.rect(cx-40,cy-58,80,103,'card2',7,'edge')
    ui.line([(cx-40,cy-58),(cx-18,cy-77),(cx+58,cy-59),(cx+40,cy-58)],'secondary')
    ui.line([(cx+40,cy-58),(cx+58,cy-59),(cx+58,cy+26),(cx+40,cy+45)],'edge')
    ui.txt('NESNE',cx,cy-7,13,'white',True,'center')

def isometric_cube(ui,cx,cy,k=1):
    poly=[[(cx,cy-65*k),(cx+80*k,cy-23*k),(cx,cy+20*k),(cx-80*k,cy-23*k)],[(cx-80*k,cy-23*k),(cx,cy+20*k),(cx,cy+112*k),(cx-80*k,cy+67*k)],[(cx+80*k,cy-23*k),(cx,cy+20*k),(cx,cy+112*k),(cx+80*k,cy+67*k)]]
    for p,fill in zip(poly,['#2B7191','#144E70','#0C3654']):
        ui.d.polygon([(int(x*S),int(y*S)) for x,y in p],fill=rgb(fill))
        ui.d.line([(int(x*S),int(y*S)) for x,y in p+[p[0]]],fill=rgb('cyan'),width=2*S)
    ui.circle(cx,cy+25*k,21*k,'bg2','cyan',2)
    ui.circle(cx,cy+25*k,9*k,'cyan2')
    for j in range(36):
        a=j*2.399; rr=110*k+((j*9)%23)*k
        x=cx+math.cos(a)*rr;y=cy+math.sin(a)*rr*.9
        ui.circle(x,y,1.2,'cyan2')

def pseudo_scene(ui,x=15,y=140,w=384,h=550):
    # A stylized conceptual camera subject; never presented as a real-world capture.
    ui.rect(x,y,w,h,'#223646',18)
    d=ui.d
    for row in range(340):
        shade=(50+row//17,66+row//20,76+row//25)
        d.line(((x+2)*S,(y+row)*S,(x+w-2)*S,(y+row)*S),fill=shade,width=2)
    d.polygon([((x+2)*S,(y+370)*S),((x+w-2)*S,(y+370)*S),((x+w-2)*S,(y+h-2)*S),((x+2)*S,(y+h-2)*S)],fill=rgb('#475360'))
    # bookshelf
    ui.rect(x+w-104,y+75,93,275,'#1A2F3F',7)
    for shelf in range(3):
        ui.line([(x+w-98,y+154+shelf*65),(x+w-17,y+154+shelf*65)],'#768995',3)
        for p in range(4):ui.rect(x+w-90+p*19,y+112+shelf*65,12,39,'#687A84',2)
    # table/plant
    ui.rect(x+43,y+366,w-78,16,'#7F7D77',3)
    ui.rect(x+58,y+382,9,125,'#6D706E',3);ui.rect(x+w-75,y+382,9,125,'#6D706E',3)
    ui.rect(x+63,y+324,57,42,'#9D9B92',6)
    for a in [-60,-35,20,55]:
        ui.line([(x+92,y+330),(x+92+a*.65,y+241+abs(a))],'#7CA798',3)
        ui.circle(x+92+a*.65,y+241+abs(a),11,'#80A999')
    # vase central
    cx=x+206
    ui.d.ellipse(((cx-69)*S,(y+300)*S,(cx+69)*S,(y+323)*S),fill=rgb('#F4E7D4'))
    d.polygon([(int(px*S),int(py*S)) for px,py in [(cx-25,y+133),(cx+24,y+133),(cx+28,y+170),(cx+42,y+184),(cx+62,y+224),(cx+67,y+277),(cx+55,y+308),(cx-53,y+308),(cx-67,y+277),(cx-64,y+223),(cx-42,y+184),(cx-28,y+170)]],fill=rgb('#E3D7C3'))
    ui.d.ellipse(((cx-28)*S,(y+124)*S,(cx+28)*S,(y+144)*S),fill=rgb('#E8DDC9'),outline=rgb('#C2B9A7'),width=3*S)
    ui.d.ellipse(((cx-19)*S,(y+128)*S,(cx+19)*S,(y+137)*S),fill=rgb('#68737C'))
    # capture overlay corner brackets
    for a,b,dx,dy in [(x+39,y+105,1,1),(x+w-40,y+105,-1,1),(x+39,y+394,1,-1),(x+w-40,y+394,-1,-1)]:
        ui.line([(a+dx*22,b),(a,b),(a,b+dy*22)],'cyan',3)
    ui.txt('GÖRSEL TEMSİLİ',x+15,y+h-31,10,'white',True)

def gallerytile(ui,x,y,w,h,idx):
    colors=['#31485B','#455461','#243E52','#495359','#304E57','#263C52']
    ui.rect(x,y,w,h,colors[idx%6],9)
    ui.rect(x+5,y+h-30,w-10,23,'#20323B',6)
    cx=x+w/2
    ui.d.ellipse(((cx-16)*S,(y+20)*S,(cx+16)*S,(y+31)*S),fill=rgb('#DDD0BF'))
    ui.d.polygon([(int(xx*S),int(yy*S)) for xx,yy in [(cx-15,y+25),(cx+15,y+25),(cx+26,y+57),(cx+25,y+h-35),(cx-25,y+h-35),(cx-26,y+57)]],fill=rgb('#D4C8B9'))
    ui.txt(str(idx+1).zfill(2),x+9,y+h-26,11,'white',True)

def render_all():
    OUT.mkdir(parents=True,exist_ok=True)
    M={}
    def make(name,ui):M[name]=ui;ui.save(OUT/name)

    u=UI(); isometric_cube(u,207,355,1.07)
    u.txt('MonoScan11',207,545,35,'cyan',True,'center')
    u.txt('LiDAR olmadan, görüntülerden 3D.',207,605,16,'white',align='center')
    u.txt('Araştırma prototipi',207,807,13,'secondary',align='center');u.txt('v0.1',207,832,12,'quiet',align='center');u.homebar()
    make('01-splash-screen.png',u)

    u=UI();u.txt('Atla',368,66,14,'cyan',align='right');u.txt('1 / 3',207,77,12,'cyan',True,'center')
    u.txt('MonoScan11',24,159,21,'cyan',True);u.txt('Nasıl Çalışır?',24,193,29,'white',True)
    u.wrapped('LiDAR kullanmadan çoklu görüntü ve hareket verisiyle 3D hazırlığı.',24,247,357,14)
    for y,ic,title,sub in [(353,'camera','Görüntüleri yakala','Farklı açılardan fotoğraf topla.'),(460,'scan','Kamera hareketini kaydet','ARKit takibiyle poz bilgisi topla.'),(567,'cube',"Windows'ta 3D oluştur",'COLMAP ile rekonstrüksiyon yap.')]:u.card(22,y,370,93,title,sub,ic)
    u.button('İleri',767);u.txt('●  ○  ○',207,830,16,'cyan',align='center');u.homebar()
    make('02-onboarding-how-it-works.png',u)

    u=UI();u.icon('back',20,66,22);u.txt('2 / 3',207,77,12,'cyan',True,'center');u.txt('Atla',386,68,14,'cyan',align='right')
    u.txt('Doğru Çekim',24,139,29,'white',True);u.wrapped('Daha iyi sonuçlar için farklı açılardan çek.',24,188,359,14)
    orb(u,207,382,119)
    for y,title in [(510,'Yavaş hareket et'),(556,'Karelerde örtüşme bırak'),(602,'Sabit ışık kullan'),(648,'Yansımalı yüzeylerden kaçın')]:
        u.circle(37,y+12,12,'card2','edge');u.icon('check',29,y+4,16);u.txt(title,60,y+2,15)
    u.button('İleri',767);u.txt('○  ●  ○',207,830,16,'cyan',align='center');u.homebar()
    make('03-onboarding-capture-rules.png',u)

    u=UI();u.icon('back',20,66,22);u.txt('3 / 3',207,77,12,'cyan',True,'center');u.txt('Çıktılar ve Sonraki Adım',24,148,22,'white',True)
    u.wrapped('Fotoğraflar ve kayıtlı oturum verileri tek pakette toplanır.',24,202,360,14)
    for y,lab,ic in [(317,'Görüntüler','image'),(384,'Oturum metaverisi','file'),(451,'Poz verileri (varsa)','scan')]:u.card(32,y,350,54,lab,icon=ic)
    u.icon('next',190,529,34);u.rect(119,578,176,88,'card2',16,'cyan');u.icon('file',144,605,32);u.txt('ZIP Paketi',197,613,18,'white',True)
    u.wrapped("3D model iPhone'da değil, Windows'ta hesaplanır.",32,699,346,13,'secondary')
    u.button('Başla',781);u.homebar()
    make('04-onboarding-outputs.png',u)

    u=UI(active='Ana Sayfa');u.txt('MonoScan11',22,77,26,'cyan',True);u.icon('info',366,82,24);u.txt('iPhone 11 · Kamera tabanlı tarama',22,115,12,'secondary')
    u.rect(20,169,374,215,'card',18,'edge');u.icon('scan',336,193,40)
    u.txt('Yeni Tarama',40,196,24,'white',True)
    u.wrapped('Bir nesne veya mekân bölümü için görüntü topla.',40,245,270,13)
    u.button('Tarama Başlat',308,x=38,w=338,h=55)
    u.card(20,406,179,132,'Projelerim','Önceki çekimler','folder');u.card(213,406,181,132,'Dışa Aktarımlar','Veri paketleri','export')
    u.txt('Son Projeler',23,586,19,'white',True)
    u.icon('folder',178,645,44,'quiet');u.txt('Henüz tarama yok.',207,717,15,'secondary',align='center');u.txt('İlk taramanı başlat.',207,745,12,'quiet',align='center')
    make('05-home-dashboard.png',u)

    u=UI();u.header('Yeni Tarama')
    u.txt('Proje adı',22,144,15,'white',True);u.rect(20,180,374,55,'card',12,'edge');u.txt('Çalışma masası',34,196,14,'white')
    u.txt('Tarama hedefi',22,265,16,'white',True)
    for j,(lab,ic) in enumerate([('Küçük nesne','cube'),('Büyük nesne','scan'),('Mekân bölümü','home')]):
        x=20+j*128;u.rect(x,302,119,109,'card2' if j==0 else 'card',13,'cyan' if j==0 else 'edge');u.icon(ic,x+45,317,30);u.txt(lab,x+60,373,11,'white',True,'center')
    u.txt('Çekim modu',22,452,16,'white',True)
    u.rect(20,489,374,83,'card2',12,'cyan');u.icon('camera',34,509,26);u.txt('Kamera + ARKit takibi',76,503,14,'white',True);u.txt('Poz takibi desteklenirse kaydedilir',76,533,11,'secondary')
    u.rect(20,584,374,74,'card',12,'edge');u.icon('image',34,607,24);u.txt('Fotoğraf dizisi',76,603,14,'white',True);u.txt('Fotoğraf toplama modu',76,630,11,'secondary')
    u.wrapped('Öneri: farklı açılardan 30–60 fotoğraf. Tam 3D model Windows’ta üretilir.',22,694,370,12,'secondary')
    u.button('Çekime Geç',781);u.homebar()
    make('06-new-scan-setup.png',u)

    u=UI();u.header('Çekim Hazırlığı')
    u.card(20,149,374,170,'Kamera erişimi','Fotoğraf çekebilmek için kamera erişimi gereklidir.','camera')
    u.tag('Erişimi kontrol et',78,250,190,active=True)
    u.card(20,347,374,165,'ARKit izleme','Cihaz uygunluğu ve oturum başlangıcı kontrol edilir.','scan')
    u.tag('Oturum başlatılmadı',78,446,188)
    u.rect(20,561,374,116,'card2',13);u.icon('shield',37,586,27)
    u.wrapped('Fotoğraflar yerel saklanır. ZIP dışa aktarımı için tüm fotoğraf arşivine erişim zorunlu değildir.',78,577,282,12)
    u.button('Kamera Aç',751,'disabled');u.txt('Geri Dön',207,819,13,'secondary',align='center');u.homebar()
    make('07-permissions-screen.png',u)

    u=UI();pseudo_scene(u,x=9,y=125,w=396,h=598)
    u.icon('x',23,70,23);u.txt('Yeni Tarama',207,68,16,'white',True,'center');u.icon('info',368,70,22)
    u.tag('Takip: bekleniyor',20,143,176);u.tag('Kare: 0',305,143,87)
    u.txt('Nesnenin çevresinden yavaşça ilerle',207,657,13,'white',True,'center')
    u.rect(0,724,414,172,'bg',0)
    u.icon('image',42,775,31);u.circle(207,786,40,'bg2','white',4);u.circle(207,786,28,'white')
    u.icon('check',348,775,29);u.txt('Bitir',362,810,11,'white',align='center')
    u.txt('Farklı açılardan fotoğraf topla',207,848,11,'secondary',align='center');u.homebar()
    make('08-live-capture-screen.png',u)

    u=UI();u.header('Çekim Kontrolü')
    u.icon('warn',25,151,31);u.txt('Çekim değerlendirmesi',71,158,18,'white',True)
    u.wrapped('Görüntü sayısını ve kayıt durumunu kontrol et. Kalite puanı henüz hesaplanmıyor.',25,216,365,13)
    u.card(20,305,374,118,'Takip sınırlı olabilir','ARKit izleme sınırlanırsa, kamerayı yavaş hareket ettir ve dokulu yüzeylere yönelt.','warn')
    u.card(20,438,374,115,'Farklı açılar önemli','Ardışık görüntülerde ortak ayrıntıları koru ve nesnenin çevresini dolaş.','camera')
    u.card(20,568,374,103,'Kayıt durumunu kontrol et','Kaydedilemeyen kareler sayaca eklenmemelidir.','info')
    u.button('Çekime Dön',737);u.button('Mevcut Çekimle Devam Et',800,'secondary');u.homebar()
    make('09-capture-quality-feedback.png',u)

    u=UI();u.header('Çekim Özeti',False,'check')
    u.rect(20,142,374,108,'card',15,'edge');u.icon('cube',39,162,34);u.txt('Örnek tarama',89,158,21,'white',True);u.txt('Görüntü kaydı tamamlandı',89,201,12,'green')
    for i,(ic,l,v) in enumerate([('image','Kayıtlı fotoğraf','Örnek: 36'),('clock','Çekim süresi','Örnek: 02:15'),('scan','Kamera pozu','Veri varsa')]):
        y=279+i*87;u.card(20,y,374,73,l,icon=ic);u.txt(v,378,y+22,12,'cyan',True,'right')
    u.rect(20,568,374,89,'card2',14);u.icon('info',36,589,25);u.wrapped('Bu bir 3D model sonucu değildir. Model Windows bilgisayarında üretilir.',77,580,300,12)
    u.button('Kareleri İncele',688,'secondary');u.button('Dışa Aktar',757);u.homebar()
    make('10-session-summary.png',u)

    u=UI();u.header('Fotoğraflar',True,'more');u.txt('Örnek çekim · Görsel taslağı',22,127,13,'secondary')
    for idx in range(15):
        rr,cc=divmod(idx,3);gallerytile(u,20+cc*129,169+rr*113,117,101,idx)
    u.txt('Kareye dokun: büyüt · Uzun bas: seç',207,755,12,'secondary',align='center');u.button('Seç',786,'secondary');u.homebar()
    make('11-frame-gallery.png',u)

    u=UI();u.header('Seyrek Önizleme',True,'info')
    u.rect(20,145,374,480,'bg2',15,'edge')
    # A coordinate grid with no faked 3D data points.
    for j in range(8):
        y=222+j*47;u.line([(42,y),(370,y)],'#173348',1)
    for j in range(7):
        x=52+j*52;u.line([(x,173),(x,584)],'#173348',1)
    u.icon('scan',168,300,80,'quiet')
    u.txt('Seyrek nokta verisi yok',207,421,17,'white',True,'center')
    u.wrapped('Gerçek ARKit özellik noktaları varsa bu alanda gösterilir.',57,468,304,12,'secondary')
    u.rect(20,651,374,82,'card2',13);u.wrapped('Bu görünüm bir yüzey veya yoğun 3D mesh modeli değildir.',40,667,335,12)
    u.button('Veri Paketini Dışa Aktar',775);u.homebar()
    make('12-sparse-preview.png',u)

    u=UI();u.header('Dışa Aktar')
    u.rect(20,146,374,462,'card',15,'edge');u.icon('file',330,166,32)
    u.txt('Tarama Veri Paketi',40,175,20,'white',True)
    u.txt('Gerçek kayıtlar ZIP içine alınır',40,220,12,'secondary')
    for j,(ic,tx,sub) in enumerate([('image','images/','Kaydedilen fotoğraflar'),('file','session.json','Oturum bilgileri'),('file','frames.json','Kare metaverileri'),('scan','poses.json','Yalnız varsa kamera pozları')]):
        y=276+j*69;u.line([(36,y-8),(377,y-8)],'edge');u.icon(ic,40,y+5,24);u.txt(tx,84,y,15,'white',True);u.txt(sub,84,y+26,11,'secondary')
    u.rect(20,632,374,85,'card2',12);u.icon('info',37,657,25)
    u.wrapped('ZIP paketini Windows’a aktar. COLMAP ile rekonstrüksiyon yap.',76,645,303,12)
    u.button('ZIP Paketi Oluştur',766);u.homebar()
    make('13-export-package-screen.png',u)

    u=UI(active='Taramalar');u.txt('Taramalar',22,79,27,'white',True);u.icon('plus',362,84,25)
    u.rect(20,146,374,49,'card',11,'edge');u.icon('search',31,156,24);u.txt('Projelerde ara',72,160,14,'quiet')
    for x,w,label in [(20,76,'Tümü'),(101,80,'Taslak'),(185,102,'Tamamlanan'),(291,103,'Dışa aktar')]:u.tag(label,x,220,w,label=='Tümü')
    u.rect(20,290,374,337,'card',15,'edge')
    u.icon('folder',170,353,72,'quiet');u.txt('Henüz proje yok',207,462,19,'white',True,'center')
    u.wrapped('Başlamak için yeni bir tarama projesi oluştur.',57,511,302,13,'secondary')
    u.button('Yeni Tarama',676);make('14-projects-list.png',u)

    u=UI();u.header('Proje Detayları',True,'more')
    u.rect(20,146,374,182,'card',15,'edge');u.icon('folder',35,185,53);u.txt('Örnek proje taslağı',110,174,19,'white',True);u.txt('Durum: Taslak',110,221,13,'secondary')
    u.txt('Proje bilgileri',23,366,18,'white',True)
    for j,(l,v) in enumerate([('Çekim modu','Kamera + ARKit'),('Fotoğraflar','Henüz veri yok'),('Poz bilgisi','Henüz veri yok')]):
        y=408+j*55;u.rect(20,y,374,48,'card',11);u.txt(l,35,y+13,13,'secondary');u.txt(v,378,y+13,12,'white',True,'right')
    u.txt('Proje notu',23,592,16,'white',True);u.rect(20,628,374,76,'card',11,'edge');u.txt('Not ekle...',35,651,13,'quiet')
    u.button('Fotoğraflar',727,'secondary');u.button('Dışa Aktar (veri yok)',789,'disabled');u.homebar()
    make('15-project-detail.png',u)

    u=UI(active='Rehber');u.txt('Çekim Rehberi',22,80,26,'white',True)
    u.rect(20,144,374,292,'card',15,'edge');orb(u,207,289,90)
    u.txt('Nesneyi farklı açılardan görüntüle',207,398,12,'white',True,'center')
    for y,ic,title,sub in [(462,'check','İyi çekim','Dokulu, sabit, net yüzey'),(556,'warn','Zor çekim','Parlak, saydam veya boş yüzey')]:u.card(20,y,374,80,title,sub,ic)
    u.txt('Sık Sorulan Sorular',22,665,17,'white',True)
    u.rect(20,699,374,45,'card',9);u.txt('LiDAR gerekiyor mu?   Hayır.',34,711,13,'white')
    u.button('Yeni Tarama',757);make('16-help-capture-guide.png',u)

    u=UI(active='Ayarlar');u.txt('Ayarlar',22,80,27,'white',True)
    for y,title,rows in [(141,'ÇEKİM',[('Varsayılan mod','Kamera + ARKit'),('Çekim ipuçları','Planlandı')]),(309,'DEPOLAMA',[('Yerel depolama','Cihazda'),('Geçici ZIP temizleme','Onay gerekir')]),(476,'GİZLİLİK',[('Veriler cihazında saklanır',''),('Paylaşım kullanıcı seçimiyle','')]),(643,'HAKKINDA',[('MonoScan11','v0.1-alpha'),('Açık kaynak lisansları','')])]:
        u.txt(title,22,y,12,'secondary',True)
        for i,(a,b) in enumerate(rows):
            yy=y+26+i*63;u.rect(20,yy,374,58,'card',11,'edge');u.txt(a,35,yy+15,12,'white',True);u.txt(b,378,yy+19,10,'cyan',False,'right')
    make('17-settings-screen.png',u)

    u=UI();u.header('Hata ve Kurtarma',False)
    u.txt('Sorunu göster, veriyi koru',22,130,20,'white',True)
    error_cards=[('Kamera erişimi gerekli','Ayarları Aç','red'),('Depolama yetersiz','Alanı Kontrol Et','amber'),('Az sayıda görüntü var','Çekime Dön','amber'),('AR takip sınırlı','Yavaş Hareket Et','blue'),('Paket oluşturulamadı','Tekrar Dene','red')]
    for i,(title,action,cl) in enumerate(error_cards):
        y=194+i*116;u.rect(20,y,374,101,'card',12,'edge')
        u.circle(44,y+31,15,'card2',cl);u.txt('!',44,y+17,19,cl,True,'center')
        u.txt(title,73,y+17,15,'white',True);u.rect(73,y+57,290,31,'card2',8)
        u.txt(action,218,y+63,12,'cyan',True,'center')
    u.homebar();make('18-error-states.png',u)

    # Contact sheet, five hundred pixel thumbnails, all screens organized by stable ID.
    thumbw=214;thumbh=463;gap=30;labelh=39;cols=6;rows=3
    canvas=Image.new('RGB',(cols*(thumbw+gap)+gap,rows*(thumbh+labelh+gap)+150),rgb('dark'));draw=ImageDraw.Draw(canvas)
    draw.text((gap,28),'MonoScan11  |  iPhone 11 UI Konseptleri',font=ImageFont.truetype(FBOLD,33),fill=rgb('white'))
    draw.text((gap,79),'UI-WF-1.0  •  18 ekran  •  Gerçek cihaz ekran görüntüsü değildir',font=ImageFont.truetype(FREG,18),fill=rgb('secondary'))
    for j,name in enumerate(M):
        col,rr=j%cols,j//cols;xx=gap+col*(thumbw+gap);yy=140+rr*(thumbh+labelh+gap)
        frame=M[name].im.resize((thumbw,thumbh),Image.Resampling.LANCZOS)
        canvas.paste(frame,(xx,yy));draw.rounded_rectangle((xx-2,yy-2,xx+thumbw+2,yy+thumbh+2),radius=12,outline=rgb('edge'),width=3)
        draw.text((xx,yy+thumbh+10),name[:2]+'  '+name[3:-4].replace('-',' '),font=ImageFont.truetype(FREG,15),fill=rgb('secondary'))
    canvas.save(OUT/'contact-sheet.png',optimize=True)
    manifest={'contract':'UI-WF-1.0','disclaimer':'Arayüz konseptleri; gerçek iPhone uygulamasından alınmış ekran görüntüleri değildir.','size_px':[828,1792],'screens':[{'id':i+1,'file':v,'kind':'concept_mockup'} for i,v in enumerate(M)]}
    (ROOT/'docs/ui/screens.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Rendered {len(M)} individual iPhone 11 PNG concepts + one contact sheet to {OUT}')

if __name__=='__main__': render_all()
