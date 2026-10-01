"""Builds the printed-paper assets used in the video from PaperDrop's own code.

- Print styles: runs frontend/src/utils/dithering.ts (via Node type stripping)
  on the Lisbon artwork at the real 576-dot print width.
- Prize card: renders agent/streamdeck/rewards.py exactly as the Pi does.
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
OUT = HERE / 'assets' / 'generated'
OUT.mkdir(parents=True, exist_ok=True)

# --- Print styles -----------------------------------------------------------
src = Image.open(REPO / 'agent/streamdeck/assets/locations/portugal.png').convert('RGBA')
src = src.crop((0, 40, 1254, 1040))  # tram + skyline, skip most of the empty cobbles
w = 576
h = round(src.height * w / src.width)
src = src.resize((w, h), Image.LANCZOS)
raw = OUT / 'src.rgba'
raw.write_bytes(src.tobytes())
runner = OUT / 'dither_runner.mts'
runner.write_text(f'''
import {{ applyDitherStyle }} from {json.dumps(str(REPO / 'frontend/src/utils/dithering.ts'))};
import {{ readFileSync, writeFileSync }} from 'node:fs';
const buf = readFileSync({json.dumps(str(raw))});
for (const style of ['none', 'photo', 'vintage', 'newspaper', 'comic']) {{
  const data = new Uint8ClampedArray(buf);
  applyDitherStyle({{ data, width: {w}, height: {h} }} as any, style as any);
  writeFileSync({json.dumps(str(OUT))} + '/' + style + '.rgba', data);
}}
''')
subprocess.run(['node', '--experimental-strip-types', '--no-warnings', str(runner)], check=True)
for style in ['none', 'photo', 'vintage', 'newspaper', 'comic']:
    p = OUT / f'{style}.rgba'
    img = Image.frombytes('RGBA', (w, h), p.read_bytes()).convert('L')
    if style == 'none':  # B&W: the app's hard threshold, applied after this helper
        img = img.point(lambda v: 0 if v < 128 else 255)
    img.save(OUT / f'style-{style}.png')
    p.unlink()
raw.unlink(); runner.unlink()

# --- Prize cards ------------------------------------------------------------
sys.path.insert(0, str(REPO / 'agent' / 'streamdeck'))
from rewards import render_reward  # noqa: E402
for n, (lang, game) in enumerate([('en', 'letters'), ('fr', 'numbers'), ('de', 'riddles'), ('pt', 'colors')], 1):
    render_reward({'id': f'video-demo-{n}', 'number': n, 'language': lang, 'game': game}, 'MIA', OUT / f'prize-{n}.png')
print('ok', sorted(p.name for p in OUT.iterdir()))

# --- Printer-ready notice and labelled family postcard ----------------------
from cousin_mail import render_notice  # noqa: E402
sys.path.insert(0, str(REPO / 'agent' / 'src'))
from print_layout import fit_width, MAX_PRINT_HEIGHT  # noqa: E402
from PIL import ImageDraw, ImageFont  # noqa: E402
render_notice(OUT / 'ready-ohio.png', 'Ohio', '2.1.1')
# Same layout cousin_mail.receive() renders onto an incoming picture.
with Image.open(REPO / 'frontend/src/assets/rocket-boy.png') as original:
    art = fit_width(original.convert('RGB'), max_height=MAX_PRINT_HEIGHT - 112)
canvas = Image.new('RGB', (576, art.height + 112), 'white')
canvas.paste(art, ((576 - art.width) // 2, 100))
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
draw.text((20, 10), 'To: Mia', font=font, fill='black')
draw.text((20, 50), 'From: Grandma', font=font, fill='black')
canvas.convert('L').point(lambda v: 0 if v < 160 else 255).save(OUT / 'postcard.png')  # thermal: pure black on white
print('notice + postcard ok')
