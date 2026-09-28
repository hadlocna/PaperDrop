"""Durable receiving inbox; one serialized worker owns automatic picture printing."""
import base64
import io
import json
import os
from pathlib import Path
import re
import threading
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
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while not self.stop.wait(1):
            for path in sorted(self.pending.glob('*.json')):
                try:
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
                    art = original.convert('RGB')
                    art.thumbnail((576, 2200))
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

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
