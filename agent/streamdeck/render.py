"""One renderer for physical keys and the laptop companion. Lucide ISC icons."""
import io
import math
from pathlib import Path
import time
from PIL import Image, ImageDraw, ImageFont, ImageOps
import cairosvg

ROOT = Path(__file__).resolve().parent
SIZE = 240
CREAM, INK = '#faf5e9', '#373448'
FONT = '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf'
if not Path(FONT).exists():
    FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


class Renderer:
    def __init__(self, family):
        self.family = family
        self.people = {p['id']:p for p in family['children']}
        self.houses = {h['id']:h for h in family['houses']}
        self.icons = {}
        self.portraits = {}
        self.pictures = {}
        for path in (ROOT/'assets/icons').glob('*.svg'):
            raw = cairosvg.svg2png(url=str(path), output_width=144, output_height=144)
            self.icons[path.stem] = Image.open(io.BytesIO(raw)).convert('RGBA')

    def icon(self, image, name, box=(60,26,180,146)):
        if not name:
            return
        source = self.icons[name]
        icon = source.resize((box[2]-box[0],box[3]-box[1]), Image.Resampling.LANCZOS)
        image.paste(icon,box[:2],icon)

    def portrait(self, ident):
        if ident not in self.portraits:
            p = self.people[ident]
            path = ROOT/'assets/portraits'/p.get('portrait','missing.png')
            if path.is_file():
                with Image.open(path) as im:
                    image = ImageOps.fit(im.convert('RGBA'), (SIZE,SIZE))
            else:
                image = Image.new('RGBA',(SIZE,SIZE),(0,0,0,0))
                self.icon(image,p['icon'],(40,28,200,188))
            self.portraits[ident] = image
        return self.portraits[ident].copy()

    def picture(self, path):
        if path not in self.pictures:
            with Image.open(path) as im:
                self.pictures[path] = im.convert('RGB').copy()
            if len(self.pictures)>20:
                del self.pictures[next(iter(self.pictures))]
        return self.pictures[path]

    def label(self,image,text):
        if not text:
            return
        draw = ImageDraw.Draw(image)
        size = 32
        font = ImageFont.truetype(FONT,size)
        while draw.textbbox((0,0),text,font=font)[2]>220 and size>20:
            size-=1
            font=ImageFont.truetype(FONT,size)
        draw.rounded_rectangle((4,187,236,236),radius=10,fill=CREAM)
        draw.text((120,211),text,font=font,fill=INK,anchor='mm')

    def key(self, spec):
        if not any(spec.get(k) for k in ('label','icon','person','house','image','mosaic','symbol')):
            return Image.new('RGB',(SIZE,SIZE),'#111015')
        if spec.get('mosaic'):
            canvas = Image.new('RGB',(SIZE*3,SIZE*2),'white')
            source = ImageOps.contain(self.picture(spec['mosaic']),(SIZE*3,SIZE*2))
            canvas.paste(source,((canvas.width-source.width)//2,(canvas.height-source.height)//2))
            i=spec['piece']; x,y=(i%3)*SIZE,(i//3)*SIZE
            return canvas.crop((x,y,x+SIZE,y+SIZE))
        image = Image.new('RGB',(SIZE,SIZE),spec.get('color',CREAM))
        if spec.get('person'):
            image = Image.new('RGB',(SIZE,SIZE),'#111015')
            portrait = self.portrait(spec['person'])
            image.paste(portrait,(0,0),portrait)
        elif spec.get('house'):
            house = self.houses[spec['house']]
            artwork = ROOT/'assets/locations'/house.get('artwork','missing.png')
            if artwork.is_file():
                image = ImageOps.fit(self.picture(str(artwork)),(SIZE,SIZE))
            else:
                image = Image.new('RGB',(SIZE,SIZE),house['color'])
                self.icon(image,'Home',(90,13,150,73))
            members = [p['id'] for p in self.family['children'] if p['house']==spec['house']]
            size=82; step=74; start=(SIZE-(step*(len(members)-1)+size))//2
            for i,p in enumerate(members):
                portrait=self.portrait(p).resize((size,size),Image.Resampling.LANCZOS)
                image.paste(portrait,(start+i*step,114),portrait)
        elif spec.get('image'):
            picture = ImageOps.contain(self.picture(spec['image']),(SIZE,183))
            image.paste(picture,((SIZE-picture.width)//2,0))
        elif spec.get('symbol'):
            draw=ImageDraw.Draw(image)
            text=spec['symbol']
            font=ImageFont.truetype(FONT,100 if len(text)<3 else 78)
            draw.text((120,90 if spec.get('dots') is not None else 112),text,font=font,fill=INK,anchor='mm')
            if spec.get('dots') is not None:
                for i in range(spec['dots']):
                    x=43+(i%6)*30; y=150+(i//6)*25
                    draw.ellipse((x-7,y-7,x+7,y+7),fill=INK)
        else:
            if spec.get('icon')=='Loader2':
                icon=self.icons['Loader2'].rotate(-int(time.monotonic()*120)%360)
                image.paste(icon,(48,22),icon)
            else:
                self.icon(image,spec.get('icon'))
        if spec.get('stars') is not None:
            star_draw=ImageDraw.Draw(image)
            for index in range(5):
                cx=48+index*36;cy=163
                points=[(cx+math.sin(n*math.pi/5)*(14 if n%2==0 else 6),cy-math.cos(n*math.pi/5)*(14 if n%2==0 else 6)) for n in range(10)]
                star_draw.polygon(points,fill='#e8ad33' if index<spec['stars'] else '#e0d9ca',outline=INK)
        self.label(image,spec.get('label',''))
        draw=ImageDraw.Draw(image)
        if spec.get('selected'):
            draw.rounded_rectangle((5,5,234,234),radius=20,outline='#de8f30',width=12)
        if spec.get('badge'):
            # A gentle double bounce once every four seconds; never flashes.
            phase=spec.get('_time',0)%4
            bounce=int(9*abs(math.sin(phase*math.pi*2))) if phase<1 else 0
            draw.rounded_rectangle((166,14-bounce,236,86-bounce),radius=18,fill='#e46f53')
            self.icon(image,'Mail',(176,23-bounce,225,72-bounce))
        if spec.get('type_badge'):
            draw.rounded_rectangle((5,5,81,81),radius=15,fill=CREAM)
            self.icon(image,spec['type_badge'],(15,15,71,71))
        if spec.get('disabled'):
            image=Image.blend(image,Image.new('RGB',image.size,CREAM),.24)
        if spec.get('_pulse'):
            inset=7+int(5*(1+math.sin(spec['_time']*math.pi)))
            ImageDraw.Draw(image).rounded_rectangle((inset,inset,239-inset,239-inset),radius=20,outline='#e46f53',width=7)
        if spec.get('_success'):
            self.icon(image,'Check',(88,12,150,74))
        return image

    def animated(self,snapshot):
        if snapshot['mode']=='game_win':return True
        if snapshot['busy'] or any(t.get('badge') for t in snapshot['tiles']):
            return True
        reveal=(snapshot['mode'] in ('sent','print_done','preview') or
                (snapshot['mode']=='game' and any(t.get('selected') for t in snapshot['tiles'])))
        return reveal and (getattr(self,'_marker',None)!=(snapshot['revision'],snapshot['mode'])
                           or time.monotonic()-self._entered<1.1)

    def keys(self,snapshot):
        now=time.monotonic()
        marker=(snapshot['revision'],snapshot['mode'])
        if getattr(self,'_marker',None)!=marker:
            self._marker,self._entered=marker,now
        elapsed=now-self._entered
        specs=[dict(t,_time=now) for t in snapshot['tiles']]
        if snapshot['mode'] in ('arming','recording','playing'):
            for t in specs:
                if t.get('icon')=='Mic' or t.get('label')=='Talk now' or t.get('type_badge')=='Mic':
                    t['_pulse']=True
        keys=[self.key(t) for t in specs]
        if snapshot['mode']=='generating':
            # Pencil moves across the bottom row. This is activity, not a fake ETA.
            canvas=Image.new('RGB',(720,240),'#f0cb86')
            draw=ImageDraw.Draw(canvas)
            x=int((now%3)/3*610)+24
            draw.line((24,150,x,150),fill=INK,width=7)
            self.icon(canvas,'Pencil',(x-8,55,x+72,135))
            for i in range(3):
                keys[i+3]=canvas.crop((i*240,0,(i+1)*240,240))
            self.label(keys[1],'Drawing')
        if snapshot['mode']=='preview' and elapsed<.7:
            keys=[Image.blend(Image.new('RGB',im.size,'white'),im,min(1,elapsed/.7)) for im in keys]
        if snapshot['mode']=='game_win':
            for i,im in enumerate(keys[:4]):
                draw=ImageDraw.Draw(im)
                for n in range(12):
                    x=(n*47+i*23)%230; y=int((now*50+n*31)%180)
                    draw.ellipse((x,y,x+8,y+8),fill=['#e89179','#85b8a2','#b6a0d5'][n%3])
        if snapshot['mode'] in ('sent','print_done') or (snapshot['mode']=='game' and any(t.get('selected') for t in specs)):
            for i,t in enumerate(specs):
                if t.get('selected') or t.get('icon')=='Check':
                    lift=int(12*abs(math.sin(min(elapsed,1)*math.pi*2))) if elapsed<1 else 0
                    self.icon(keys[i],'Check',(92,14-lift,150,72-lift))
        return keys

    def contact_sheet(self, keys):
        canvas=Image.new('RGB',(788,528),INK)
        for i,im in enumerate(keys):
            canvas.paste(im,(14+(i%3)*260,14+(i//3)*260))
        return canvas


def png(image):
    output=io.BytesIO()
    image.save(output,format='PNG')
    return output.getvalue()
