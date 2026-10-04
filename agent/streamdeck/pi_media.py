"""Pi-owned microphone, speaker, AI requests and guarded USB printing."""
import audioop
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import wave

from media import Media


class PrintOutcomeUnknown(RuntimeError):
    public_message = 'The print result is uncertain. Check the paper before making a new drawing. This picture will not be sent twice.'


class PiMedia(Media):
    from printer_readiness import PRINTER_LOCK as _printer_lock
    local_printer = True
    def __init__(self, root):
        super().__init__(root)
        from pi_cloud import Cloud
        self.cloud = Cloud(self.root, self)
        self.shutdown = threading.Event()
        threading.Thread(target=self.reconnect_speaker, daemon=True).start()

    def reconnect_speaker(self):
        while not self.shutdown.wait(15):
            if self.recording or (self.player and self.player.poll() is None):
                continue
            try:
                subprocess.run(['/usr/bin/python3', str(Path(__file__).with_name('pi_speaker.py'))],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            except (OSError, subprocess.SubprocessError):
                pass

    def stop_audio(self):
        with self.audio_lock:
            previous = self.player
            super().stop_audio()
            if previous and previous.poll() is None:
                try:
                    previous.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    previous.kill()
                    previous.wait()

    def draw(self, audio, target, progress):
        return self.cloud.draw(audio, target, progress)

    def close(self):
        if hasattr(self, 'receiver'):
            self.receiver.close()
        self.shutdown.set()
        super().close()
        self.cloud.close()

    def discard_image(self, path):
        mapping = Path(path).with_suffix('.cloud.json')
        if mapping.exists():
            ident = json.loads(mapping.read_text())['message_id']
            # Preserve an already-completed print status when leaving its preview.
            receipt = self.root / 'print-receipts' / (Path(path).stem + '.json')
            if not receipt.exists():
                self.cloud.status(ident, 'failed', 'Picture discarded before printing')
            mapping.unlink()

    def playback_command(self, path):
        pcm = os.environ.get('PAPERDROP_PLAYBACK_PCM')
        if not pcm:
            settings = json.loads(Path('/etc/paperdrop/speaker.json').read_text())
            pcm = 'bluealsa:DEV=' + settings['address'] + ',PROFILE=a2dp'
        # Match the explicitly negotiated stereo SBC connection. Normalize WAV
        # lengths too: cached API WAVs can have streaming-size headers.
        import hashlib
        source = Path(path)
        cache = self.root / 'playback'
        cache.mkdir(exist_ok=True)
        ident = hashlib.sha256(source.read_bytes()).hexdigest()
        target = cache / (ident + '-44100-stereo.wav')
        if not target.exists():
            with wave.open(str(source), 'rb') as wav:
                channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
                data = wav.readframes(min(wav.getnframes(), rate*60))
            if channels == 2:
                data = audioop.tomono(data, width, .5, .5)
            elif channels != 1:
                raise RuntimeError('Unsupported speaker audio channels')
            if width != 2:
                data = audioop.lin2lin(data, width, 2)
            if rate != 44100:
                data, _ = audioop.ratecv(data, 2, 1, rate, 44100, None)
            data = audioop.tostereo(data, 2, 1, 1)
            with wave.open(str(target), 'wb') as out:
                out.setparams((2,2,44100,0,'NONE','not compressed'))
                out.writeframes(b'\0'*70560 + data + b'\0'*26460)
        return ['aplay', '-q', '-D', pcm, str(target)]

    def cue(self, text):
        import hashlib
        self.stop_audio()
        token = self.generation
        def run():
            path = (Path(__file__).parent / 'speech' if (Path(__file__).parent / 'speech').exists() else self.root / 'speech') / (hashlib.sha256(text.encode()).hexdigest() + '.wav')
            try:
                with self.audio_lock:
                    if token != self.generation or self.recording:
                        return
                    if not path.exists():
                        # No robotic synthesized fallback in the child-facing flow.
                        import logging
                        logging.warning('uncached_guidance_skipped')
                        return
                    if token != self.generation:
                        return
                    self.player = subprocess.Popen(self.playback_command(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                import logging
                logging.warning('speaker_cue_unavailable')
        threading.Thread(target=run, daemon=True).start()

    def play(self, path):
        self.stop_audio()
        with self.audio_lock:
            self.player = proc = subprocess.Popen(self.playback_command(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            if proc.wait(timeout=30):
                raise RuntimeError('Pi speaker unavailable')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def capture_pcm(self):
        configured = os.environ.get('PAPERDROP_CAPTURE_PCM')
        if configured:
            return configured
        try:
            cards = Path('/proc/asound/cards').read_text(errors='ignore')
        except OSError:
            cards = ''
        for card in ('Microphone', 'Device'):
            if f'[{card}' in cards:
                return f'plughw:CARD={card},DEV=0'
        return 'default'

    def start_recording(self, path):
        self.stop_audio()
        self.record_ready = threading.Event()
        ready = self.record_ready
        self.record_error = None
        self.capture_done = threading.Event()
        with self.audio_lock:
            self.recording = proc = subprocess.Popen([
                'arecord', '-q', '-D', self.capture_pcm(),
                '-t', 'raw', '-f', 'S16_LE', '-c', '1', '-r', '24000', '-d', '15'
            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        def capture():
            try:
                with wave.open(str(path), 'wb') as wav:
                    wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                    while True:
                        chunk = proc.stdout.read(2400)
                        if not chunk:
                            break
                        wav.writeframes(chunk)
                        ready.set()
            except Exception as exc:
                self.record_error = type(exc).__name__
            finally:
                self.capture_done.set()
        threading.Thread(target=capture, daemon=True).start()

    def finish_recording(self, path):
        with self.audio_lock:
            proc, self.recording = self.recording, None
        if not proc:
            raise RuntimeError('No recording')
        try:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
            proc.wait(timeout=4)
            if not self.capture_done.wait(3) or self.record_error:
                raise RuntimeError('Pi microphone failed')
            with wave.open(str(path)) as wav:
                duration = wav.getnframes() / wav.getframerate()
                frames = wav.readframes(wav.getnframes())
            if duration < .6 or audioop.rms(frames, 2) < 45:
                raise RuntimeError('Recording was too short or silent')
            return round(duration, 2)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def attach_mailbox(self, mailbox, family):
        from cousin_mail import Receiver
        self.receiver = Receiver(self.root, mailbox, family, self, self.cloud)
        mailbox.on_read = lambda message: self.cloud.mail_receipt(message['id'], 'read') if message.get('remote') and message['kind'] == 'voice' else None

    def send_mail(self, draft, family):
        people = {p['id']: p for p in family['children']}
        if draft['sender'] not in people or people[draft['sender']]['house'] != family['station']:
            raise RuntimeError('Choose your own face before sending mail')
        return self.cloud.send_mail(dict(draft, house=people[draft['recipient']]['house']))

    def send_drawing(self, draft, family):
        from PIL import Image, ImageDraw, ImageFont
        if draft['sender'] != family['station']:
            raise RuntimeError('Return to your home station before sending a real postcard')
        people={p['id']:p for p in family['children']}
        houses={h['id']:h for h in family['houses']}
        recipient=people[draft['recipient']]
        draft=dict(draft,house=recipient['house'])
        target=self.root/(draft['id']+'-postcard.png')
        if not target.exists():
            with Image.open(draft['image']) as original:
                artwork=original.convert('RGB')
                artwork=artwork.resize((576,round(artwork.height*576/artwork.width)),Image.Resampling.LANCZOS)
            canvas=Image.new('RGB',(576,artwork.height+112),'white')
            canvas.paste(artwork,(0,100))
            draw=ImageDraw.Draw(canvas)
            font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',30)
            draw.text((20,10),'To: '+recipient['name'],font=font,fill='black')
            draw.text((20,50),'From: '+houses[draft['sender']]['name'],font=font,fill='black')
            draw.line((20,92,556,92),fill='black',width=2)
            canvas.save(target)
        return self.cloud.send_postcard(draft,target)

    def delivery_status(self, ident):
        with self.cloud.lock:
            return dict(self.cloud.deliveries.get(ident,{}))

    def print_image(self, path, ident):
        from contextlib import nullcontext
        from update_guard import acquire
        with self._printer_lock, (acquire() if os.environ.get("PAPERDROP_FIRMWARE_VERSION") else nullcontext()):
            return self._print_image(path, ident)

    def _print_image(self, path, ident):
        from PIL import Image
        from escpos.printer import Usb
        receipts = self.root / 'print-receipts'
        receipts.mkdir(exist_ok=True)
        receipt = receipts / (ident + '.json')
        if receipt.exists():
            result = json.loads(receipt.read_text())
            if result['status'] == 'printed':
                return result
            raise PrintOutcomeUnknown()
        # Open the real target before marking an attempt. Never fall back to mock output.
        printer = Usb(0x04b8, 0x0e28, profile='TM-T20II', auto_detach_kernel_driver=True)
        try:
            with Image.open(path) as source:
                from print_layout import fit_width, FRAGMENT_HEIGHT
                img = fit_width(source).convert('1')
            # Persist before the first byte is sent; interrupted jobs cannot auto-reprint.
            with receipt.open('x') as out:
                json.dump({'id': ident, 'status': 'uncertain'}, out)
                out.flush()
                os.fsync(out.fileno())
            try:
                printer.image(img, impl='bitImageRaster', fragment_height=FRAGMENT_HEIGHT)
                printer.cut()
            except Exception as exc:
                raise PrintOutcomeUnknown() from exc
            result = {'id': ident, 'status': 'printed', 'hardware_confirmation': 'USB write completed; paper requires observation'}
            temp = receipt.with_suffix('.tmp')
            with temp.open('w') as out:
                json.dump(result, out)
                out.flush()
                os.fsync(out.fileno())
            temp.replace(receipt)
            mapping = Path(path).with_suffix('.cloud.json')
            if mapping.exists():
                self.cloud.status(json.loads(mapping.read_text())['message_id'], 'printed')
            return result
        finally:
            printer.close()
