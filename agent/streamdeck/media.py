"""macOS bench audio and PaperDrop's existing OpenAI drawing pipeline."""
import audioop
import base64
import hashlib
import logging
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import wave


ROOT = Path(__file__).resolve().parent


def client():
    from dotenv import dotenv_values
    from openai import OpenAI
    # Read only the needed credential. Never copy it into the prototype or logs.
    key = os.environ.get('OPENAI_API_KEY') or dotenv_values(ROOT.parents[1] / 'backend' / '.env').get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('PaperDrop API key is unavailable')
    return OpenAI(api_key=key, timeout=90, max_retries=0)


class Media:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.audio_lock = threading.RLock()
        self.player = None
        self.generation = 0
        self.recording = None
        self.record_ready = threading.Event()
        self.starts = []

    def stop_audio(self):
        with self.audio_lock:
            self.generation += 1
            if self.player and self.player.poll() is None:
                self.player.terminate()
            self.player = None

    def start_guidance(self, text):
        """Start cached guidance synchronously so cancellation cannot race launch."""
        self.stop_audio()
        path = (ROOT / 'speech' if (ROOT / 'speech').exists() else self.root / 'speech') / (hashlib.sha256(text.encode()).hexdigest() + '.wav')
        with self.audio_lock:
            command = self.playback_command(path) if hasattr(self, 'playback_command') else ['/usr/bin/afplay', str(path)]
            if not path.exists():
                raise RuntimeError('Recording guidance is missing')
            self.player = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return self.player

    def cue_duration(self, text):
        path=(ROOT/'speech' if (ROOT/'speech').exists() else self.root/'speech')/(hashlib.sha256(text.encode()).hexdigest()+'.wav')
        try:
            with wave.open(str(path)) as wav:
                data=wav.readframes(min(wav.getnframes(),wav.getframerate()*20))
                return len(data)/(wav.getframerate()*wav.getnchannels()*wav.getsampwidth())
        except (OSError,wave.Error):return 1.7

    def cue(self, text):
        self.stop_audio()
        token = self.generation
        def run():
            path = (ROOT / 'speech' if (ROOT / 'speech').exists() else self.root / 'speech') / (hashlib.sha256(text.encode()).hexdigest() + '.wav')
            with self.audio_lock:
                if token != self.generation or self.recording:
                    return
                if path.exists():
                    self.player = subprocess.Popen(['/usr/bin/afplay', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    self.player = subprocess.Popen(['/usr/bin/say', '-r', '175', text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        threading.Thread(target=run, daemon=True).start()

    def cue_sequence(self, texts, star=False):
        """One cancellable playback: feedback cannot cut off its following question."""
        from audio_cues import combine
        import json
        self.stop_audio()
        token = self.generation
        def run():
            try:
                speech = ROOT/'speech' if (ROOT/'speech').exists() else self.root/'speech'
                paths = [speech/(hashlib.sha256(text.encode()).hexdigest()+'.wav') for text in texts]
                # Never quietly skip the question if its cached recording is missing.
                if any(not path.exists() for path in paths):
                    logging.warning('game_cue_missing')
                    return
                ident = hashlib.sha256(json.dumps([texts,star]).encode()).hexdigest()
                path = self.root/'game-cues'/(ident+'.wav')
                with self.audio_lock:
                    if token != self.generation or self.recording:return
                    if not path.exists():combine(paths,path,star=star)
                    command = self.playback_command(path) if hasattr(self,'playback_command') else ['/usr/bin/afplay',str(path)]
                    self.player = subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except (OSError, ValueError, wave.Error, subprocess.SubprocessError):
                logging.warning('game_cue_unavailable')
        threading.Thread(target=run,daemon=True).start()

    def play(self, path):
        self.stop_audio()
        with self.audio_lock:
            proc = subprocess.Popen(['/usr/bin/afplay', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.player = proc
        if proc.wait(timeout=25) != 0:
            raise RuntimeError('Playback did not finish')

    def start_recording(self, path):
        self.stop_audio()
        self.record_ready = threading.Event()
        ready = self.record_ready
        ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
        with self.audio_lock:
            log = open(self.root / 'microphone.log', 'ab')
            self.recording = subprocess.Popen([
                ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-stats_period', '0.1', '-progress', 'pipe:1', '-f', 'avfoundation',
                '-i', ':' + os.environ.get('PAPERDROP_MICROPHONE', 'MacBook Pro Microphone'),
                '-t', '15', '-ac', '1', '-ar', '24000', str(path)
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
            log.close()
            proc = self.recording
        def watch():
            for line in proc.stdout:
                if line.startswith(b'out_time_us='):
                    try:
                        if int(line.split(b'=')[1]) > 0:
                            ready.set()
                    except ValueError:
                        pass
        threading.Thread(target=watch,daemon=True).start()

    def wait_recording_ready(self):
        if not self.record_ready.wait(6):
            raise RuntimeError('Microphone did not become ready')

    def finish_recording(self, path):
        with self.audio_lock:
            proc, self.recording = self.recording, None
        if not proc:
            raise RuntimeError('No recording')
        try:
            if proc.poll() is None:
                try:
                    proc.stdin.write(b'q\n')
                    proc.stdin.flush()
                except BrokenPipeError:
                    pass
                proc.wait(timeout=4)
            else:
                proc.wait(timeout=4)
            if proc.returncode != 0:
                raise RuntimeError('Microphone unavailable')
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

    def draw(self, audio, target, progress):
        now = time.monotonic()
        self.starts = [t for t in self.starts if now - t < 3600]
        if len(self.starts) >= 20:
            raise RuntimeError('Drawing limit reached; try again later')
        self.starts.append(now)
        ai = client()
        progress('Listening to your idea…')
        with open(audio, 'rb') as recording:
            result = ai.audio.transcriptions.create(model='gpt-4o-mini-transcribe', file=recording)
        prompt = result.text.strip()
        if not 4 <= len(prompt) <= 1500:
            raise RuntimeError('Please describe your picture again')
        moderation = ai.moderations.create(model='omni-moderation-latest', input=prompt)
        if any(r.flagged for r in moderation.results):
            raise RuntimeError('Please try a different picture')
        progress('Drawing your picture…')
        # Keep the same model and thermal-art contract as recordedVoice.ts.
        result = ai.images.generate(
            model=os.environ.get('PAPERDROP_IMAGE_MODEL', 'gpt-image-2.5-flare'),
            prompt=f"Create the child's requested artwork: {prompt}. Honor the requested format: a comic, map, puzzle, card, poster or illustration. "
                   'Family-friendly monochrome artwork on white paper, readable at 576 dots wide. '
                   'Use confident contours, clear focal points, generous spacing, small black accents and sparse hatching where useful. '
                   'Avoid dense dark backgrounds, muddy gray washes and tiny details. Use coloring-page style only if requested. '
                   'Preserve requested subjects and captions; do not invent greetings or personal details.',
            n=1, size='1024x1024', quality=os.environ.get('PAPERDROP_IMAGE_QUALITY', 'medium'), output_format='png', background='opaque')
        if not result.data or not result.data[0].b64_json:
            raise RuntimeError('No picture returned')
        from PIL import Image
        import io
        raw = base64.b64decode(result.data[0].b64_json)
        with Image.open(io.BytesIO(raw)) as image:
            image.convert('RGB').save(target)
        return prompt

    def close(self):
        self.stop_audio()
        with self.audio_lock:
            if self.recording and self.recording.poll() is None:
                self.recording.terminate()
                self.recording.wait(timeout=4)
            self.recording = None

    def print_image(self, path, ident):
        from printer import print_image
        return print_image(path,ident,self.root)
