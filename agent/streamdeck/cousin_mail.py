"""Durable receiving inbox; one serialized worker owns automatic picture printing."""
import base64
import io
import json
import os
from pathlib import Path
import re
import threading
import time
import wave
from PIL import Image, ImageDraw, ImageFont


def atomic_write(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    with temp.open('wb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    temp.replace(path)


class Receiver:
    def __init__(self, root, mailbox, family, media, cloud):
        self.root, self.mailbox, self.family, self.media, self.cloud = Path(root), mailbox, family, media, cloud
        self.people = {p['id']: p for p in family['children']}
        self.stop = threading.Event()
        self.pending = self.root / 'incoming-mail'
        self.pending.mkdir(exist_ok=True)
        self.notices = self.root / 'printer-notices'
        self.notices.mkdir(exist_ok=True)
        self.next_probe = 0
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.wait(1):
            if time.monotonic() >= self.next_probe:
                self.next_probe = time.monotonic() + 30
                if self.cloud.connected.is_set() and not self.cloud.printer_ready_ack:
                    from printer_readiness import printer_ready
                    if printer_ready():
                        try:
                            self.cloud.send({'type': 'printer_ready', 'ready': True,
                                             'firmware': os.environ.get('PAPERDROP_FIRMWARE_VERSION', 'unknown')})
                        except Exception:
                            pass
            for path in sorted(self.pending.glob('*.json')) + sorted(self.notices.glob('*.json')):
                try:
                    if path.parent == self.notices:
                        self.receive_notice(json.loads(path.read_text()))
                    else:
                        self.receive(json.loads(path.read_text()))
                    path.unlink(missing_ok=True)
                except Exception:
                    # Keep media for recovery; never lose a delivery on printer failure.
                    import logging
                    logging.warning('cousin_mail_pending id=%s', path.stem)
                    self.stop.wait(10)

    def receive(self, message):
        ident = message['id']
        if not re.fullmatch('[a-f0-9]{64}', ident):
            raise ValueError('Invalid mail ID')
        sender, recipient = self.people[message['sender']], self.people[message['recipient']]
        if recipient['house'] != self.family['station'] or sender['house'] == recipient['house']:
            raise ValueError('Wrong station')
        kind = message['kind']
        if kind not in ('voice', 'drawing'):
            raise ValueError('Invalid mail kind')
        existing = self.mailbox.get(ident)
        target = self.root / (ident + ('.wav' if kind == 'voice' else '.png'))
        if not existing:
            content = base64.b64decode(message['media'], validate=True)
            if len(content) > 3000000:
                raise ValueError('Mail too large')
            if kind == 'voice':
                with wave.open(io.BytesIO(content)) as wav:
                    if wav.getnchannels() not in (1, 2) or wav.getsampwidth() != 2 or not 0 < wav.getnframes()/wav.getframerate() <= 20:
                        raise ValueError('Invalid voice recording')
                atomic_write(target, content)
            else:
                # Recipient renders trusted family names onto the actual print, including after offline delivery.
                with Image.open(io.BytesIO(content)) as original:
                    if original.width * original.height > 16000000:
                        raise ValueError('Picture too large')
                    from print_layout import fit_width, MAX_PRINT_HEIGHT
                    art = fit_width(original, max_height=MAX_PRINT_HEIGHT - 112)
                canvas = Image.new('RGB', (576, art.height + 112), 'white')
                canvas.paste(art, ((576-art.width)//2, 100))
                draw = ImageDraw.Draw(canvas)
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
                draw.text((20, 10), 'To: ' + recipient['name'], font=font, fill='black')
                draw.text((20, 50), 'From: ' + sender['name'], font=font, fill='black')
                output = io.BytesIO()
                canvas.save(output, format='PNG')
                atomic_write(target, output.getvalue())
            self.mailbox.send(dict(id=ident, sender=sender['id'], recipient=recipient['id'], kind=kind,
                                   **{'audio' if kind == 'voice' else 'image': str(target)}, remote=True))
        if kind == 'voice':
            seen = any(m['id'] == ident and m['seen'] for m in self.mailbox.inbox(recipient['id']))
            self.cloud.mail_receipt(ident, 'read' if seen else 'received')
        else:
            try:
                self.media.print_image(target, ident)
            except Exception as exc:
                from pi_media import PrintOutcomeUnknown
                if isinstance(exc, PrintOutcomeUnknown):
                    self.cloud.mail_receipt(ident, 'failed')
                    # Retain the mailbox image and uncertain print receipt; do not resubmit paper.
                    return
                raise
            self.cloud.mail_receipt(ident, 'printed')

    def receive_notice(self, notice):
        ident = notice['id']
        if not re.fullmatch('[a-f0-9]{64}', ident) or self.family['station'] != 'portugal':
            raise ValueError('Invalid readiness notice')
        house = next(h for h in self.family['houses'] if h['id'] == notice['house'] and h['id'] != 'portugal')
        target = self.root / (ident + '-ready.png')
        if not target.exists():
            render_notice(target, house['name'], notice['firmware'])
        try:
            self.media.print_image(target, ident)
        except Exception as exc:
            from pi_media import PrintOutcomeUnknown
            if isinstance(exc, PrintOutcomeUnknown):
                self.cloud.mail_receipt(ident, 'failed', notice=True)
                return
            raise
        self.cloud.mail_receipt(ident, 'printed', notice=True)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)


def render_notice(target, house, firmware):
    canvas = Image.new('RGB', (576, 530), 'white')
    draw = ImageDraw.Draw(canvas)
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    large = ImageFont.truetype(font_path, 42)
    regular = ImageFont.truetype(font_path, 25)
    draw.rounded_rectangle((22, 20, 554, 507), radius=25, outline='black', width=4)
    def line(text, y, font):
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((576 - box[2] + box[0]) / 2, y), text, font=font, fill='black')
    line('PaperDrop', 45, large)
    draw.ellipse((238, 117, 338, 217), outline='black', width=5)
    draw.line([(258, 166), (280, 188), (318, 145)], fill='black', width=7)
    line(house, 238, large)
    line('Printer is ready', 300, regular)
    line('Online + paper loaded', 346, regular)
    line('Firmware ' + str(firmware)[:30], 412, regular)
    out = io.BytesIO()
    canvas.save(out, format='PNG')
    atomic_write(target, out.getvalue())
