"""Personalized collectible achievement cards; offline, 576px, monochrome.

Every earned card has a durable collection number and UUID-seeded illustration.
Retries reuse that same artwork and print ID rather than creating another prize.
"""
import io
import math
from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFont
import cairosvg
from languages import label

ROOT = Path(__file__).parent
FONTS = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
         '/System/Library/Fonts/Supplemental/Arial.ttf']
TITLES = {
 'en': ['SPACE EXPLORER','GARDEN DISCOVERER','OCEAN ADVENTURER','CASTLE DREAMER'],
 'fr': ['EXPLORATEUR SPATIAL','EXPLORATEUR DU JARDIN','AVENTURIER DES MERS','RÊVEUR DE CHÂTEAUX'],
 'de': ['WELTRAUMFORSCHER','GARTENENTDECKER','MEERESABENTEURER','SCHLOSSTRÄUMER'],
 'it': ['ESPLORATORE SPAZIALE','ESPLORATORE DEL GIARDINO','AVVENTURIERO DEL MARE','SOGNATORE DI CASTELLI'],
 'pt': ['EXPLORADOR ESPACIAL','EXPLORADOR DO JARDIM','AVENTUREIRO DO MAR','SONHADOR DE CASTELOS'],
}

def render_reward(reward, name, path):
    rng = random.Random(reward['id'])
    theme = (reward['number'] - 1) % 4
    language = reward['language']
    image = Image.new('RGB', (576, 840), 'white')
    d = ImageDraw.Draw(image)
    font_path = next((x for x in FONTS if Path(x).exists()), None)
    def text(words, y, size=32):
        while True:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size=size)
            if d.textbbox((0,0), words, font=font)[2] <= 496 or size <= 16: break
            size -= 1
        d.text((288,y),words,font=font,fill='black',anchor='mm')
    def star(x,y,r=22):
        pts=[(x+math.sin(n*math.pi/5)*(r if n%2==0 else r*.44),y-math.cos(n*math.pi/5)*(r if n%2==0 else r*.44)) for n in range(10)]
        d.polygon(pts,fill='white',outline='black',width=3)
    def icon(name, box):
        raw=cairosvg.svg2png(url=str(ROOT/'assets/icons'/f'{name}.svg'),output_width=box[2],output_height=box[3])
        art=Image.open(io.BytesIO(raw)).convert('RGBA')
        image.paste(art,box[:2],art)
    d.rounded_rectangle((16,16,560,824),radius=28,outline='black',width=4)
    text('PAPERDROP',52,22)
    text(label('Five stars!',language),105,46)
    for x in range(128,449,80): star(x,163,27)
    text(name,222,44)
    text(TITLES[language][theme],280,27)
    d.rounded_rectangle((40,318,536,656),radius=22,outline='black',width=3)
    animal = rng.choice(['Cat','Dog','Rabbit','Bird','Fish'])
    icon(animal,(197,411,182,182))
    # Different scenes, companions and ornaments on each collected achievement.
    if theme == 0:
        for x,y in [(85,365),(453,388),(105,576),(472,587)]: star(x+rng.randint(-15,15),y, rng.randint(13,24))
        d.ellipse((365,465,492,512),outline='black',width=3)
        d.ellipse((400,445,457,531),outline='black',width=3)
        d.arc((80,391,188,490),10,300,fill='black',width=4)
    elif theme == 1:
        for x in (65,402): icon('Flower2',(x,475-rng.randint(0,70),105,140))
        d.arc((52,582,527,707),180,355,fill='black',width=3)
        icon('Bird',(420,344,64,64))
    elif theme == 2:
        for y in (595,619):
            for x in range(58,500,74):d.arc((x,y,x+74,y+28),180,360,fill='black',width=3)
        for x,y in [(96,389),(442,386),(119,511),(469,520)]:
            r=rng.randint(9,18);d.ellipse((x-r,y-r,x+r,y+r),outline='black',width=3)
        icon('Fish',(65,440,88,88))
    else:
        for x in (64,423):
            d.rectangle((x,415,x+87,619),outline='black',width=3)
            d.polygon([(x-8,415),(x+43,355-rng.randint(0,20)),(x+95,415)],outline='black',width=4)
            d.rounded_rectangle((x+26,463,x+61,513),radius=16,outline='black',width=3)
        star(286,363,24)
    text(label({'colors':'Colors','letters':'Letters','numbers':'Numbers','riddles':'Riddles'}[reward['game']],language),695,30)
    text({'en':'I kept thinking and trying!','fr':'J’ai réfléchi et persévéré !','de':'Ich habe nachgedacht und geübt!','it':'Ho pensato e ci ho provato!','pt':'Pensei e continuei a tentar!'}[language],739,25)
    text({"en":"My collection","fr":"Ma collection","de":"Meine Sammlung","it":"La mia collezione","pt":"A minha coleção"}[language]+f" · {reward['number']:03d}",785,20)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    image.convert('1',dither=Image.Dither.NONE).save(path)
    return str(path)
