"""Local wake phrase; bounded cloud conversations over the authenticated device socket.

No microphone audio leaves the device before a wake event. No recordings are saved.
"""
import asyncio
import base64
import collections
import json
import logging
import re
import sys
import time
from pathlib import Path
from speaker_control import lock, run_speaker

log = logging.getLogger('Voice')
SETTINGS = Path('/etc/paperdrop/voice.json')
MODEL = Path('/opt/paperdrop-models/vosk-model-small-en-us-0.15')


def is_wake_phrase(text):
    return bool(re.search(r'\b(?:hey\s+)?paper\s*drop\b', text.lower()))


class VoiceAssistant:
    def __init__(self, websocket):
        self.ws = websocket
        try:
            self.enabled = json.loads(SETTINGS.read_text()).get('enabled') is True
        except (OSError, ValueError):
            self.enabled = False
        self.state = 'off'
        self.error = None
        self.task = None
        self.active = False
        self.ready = False
        self.speaking = False
        self.mute_until = 0
        self.player = None
        self.play_task = None
        self.output = asyncio.Queue(maxsize=200)
        self.finish = False
        self.recognizer = None
        self.last_activity = time.monotonic()

    async def send(self, event):
        await self.ws.send(json.dumps(event))

    def status(self):
        return {'ok': True, 'enabled': self.enabled, 'state': self.state, 'error': self.error,
                'wakePhrase': 'Hey Paper Drop', 'ready': MODEL.exists()}

    async def start(self):
        if self.enabled and (self.task is None or self.task.done()):
            self.task = asyncio.create_task(self.listen())

    async def stop(self):
        self.active = False
        self.ready = False
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        self.state = 'off'

    async def control(self, data):
        try:
            action = data.get('action')
            if action in ('enable', 'disable', 'status'):
                # Backend owner setting is authoritative, including after a restart.
                enabled = data.get('enabled') is True
                if enabled != self.enabled or action != 'status':
                    await self.stop()
                    self.enabled = enabled
                    SETTINGS.write_text(json.dumps({'enabled': enabled}))
                    SETTINGS.chmod(0o600)
                    await self.start()
                if action == 'disable':
                    await self.send({'type': 'voice_stop'})
            elif action == 'wake':
                if not self.enabled or self.state == 'error':
                    raise RuntimeError('Enable voice listening with a connected microphone first.')
                await self.wake()
            result = self.status()
        except Exception as error:
            result = {'ok': False, 'error': str(error)}
        await self.send({**result, 'type': 'voice_result', 'request_id': data.get('request_id')})

    async def wake(self):
        if self.active:
            return
        self.active = True
        self.ready = False
        self.finish = False
        self.state = 'connecting'
        self.last_activity = time.monotonic()
        await self.send({'type': 'voice_start'})
        log.info('Wake phrase detected; opening voice conversation')

    async def event(self, data):
        kind = data['type']
        if kind == 'voice_ready':
            self.ready = True
            self.state = 'talking'
        elif kind == 'voice_output' and self.active:
            self.speaking = True
            if self.output.full():
                self.error = 'Audio playback could not keep up. Please try again.'
                await self.send({'type': 'voice_stop'})
                self.active = False
                return
            self.output.put_nowait(data.get('audio'))
        elif kind == 'voice_output_done':
            await self.output.put(None)
        elif kind == 'voice_progress':
            self.state = data.get('state', 'talking')
        elif kind == 'voice_finish':
            self.finish = True
        elif kind in ('voice_end', 'voice_error'):
            self.active = False
            self.ready = False
            self.finish = False
            self.error = data.get('error')
            self.state = 'listening' if self.enabled else 'off'
            if self.recognizer:
                self.recognizer.Reset()

    async def playback(self, pcm):
        import audioop
        conversion = None
        try:
            while True:
                chunk = await self.output.get()
                if chunk is None:
                    if self.player:
                        self.player.stdin.close()
                        await asyncio.wait_for(self.player.wait(), 15)
                        self.player = None
                    conversion = None
                    self.speaking = False
                    self.mute_until = time.monotonic() + 0.6
                    self.last_activity = time.monotonic()
                    continue
                self.speaking = True
                if not self.player:
                    self.player = await asyncio.create_subprocess_exec('aplay', '-q', '-D', pcm, '-t', 'raw', '-f', 'S16_LE', '-r', '16000', '-c', '1',
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    # Short lead-in keeps the first syllable from being lost by the speaker.
                    self.player.stdin.write(b'\0' * 9600)
                audio, conversion = audioop.ratecv(base64.b64decode(chunk, validate=True), 2, 1, 24000, 16000, conversion)
                self.player.stdin.write(audio)
                await asyncio.wait_for(self.player.stdin.drain(), 8)
        finally:
            if self.player and self.player.returncode is None:
                self.player.kill()
                await self.player.wait()
            self.player = None

    async def listen(self):
        recorder = None
        try:
            import audioop
            from vosk import Model, KaldiRecognizer, SetLogLevel
            if not MODEL.exists():
                raise RuntimeError('Wake phrase support needs a device update.')
            SetLogLevel(-1)
            self.state = 'starting'
            model = await asyncio.to_thread(Model, str(MODEL))
            self.recognizer = KaldiRecognizer(model, 16000, json.dumps(['hey paper drop', 'paper drop', '[unk]']))
            # Voice owns audio while enabled so pairing/test commands cannot tear down capture.
            async with lock:
                info = await run_speaker('microphone_ready')
                if not info.get('ok'):
                    raise RuntimeError(info.get('error', 'Microphone unavailable'))
                pcm = 'plug:' + info['pcm']
                recorder = await asyncio.create_subprocess_exec('arecord', '-q', '-D', pcm, '-t', 'raw', '-f', 'S16_LE', '-r', '16000', '-c', '1',
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                self.play_task = asyncio.create_task(self.playback(pcm))
                self.state = 'listening'
                self.error = None
                conversion = None
                while True:
                    data = await asyncio.wait_for(recorder.stdout.readexactly(3200), 5)
                    now = time.monotonic()
                    if self.play_task.done():
                        await self.play_task
                    if self.finish and not self.speaking and self.output.empty() and now >= self.mute_until:
                        await self.send({'type': 'voice_stop'})
                        self.active = self.ready = self.finish = False
                        self.state = 'listening'
                        self.recognizer.Reset()
                    if self.speaking or now < self.mute_until:
                        conversion = None
                        continue
                    if self.active:
                        if now - self.last_activity > 40 and self.state != 'drawing':
                            await self.send({'type': 'voice_stop'})
                            self.active = self.ready = False
                            self.state = 'listening'
                            self.recognizer.Reset()
                        elif self.ready:
                            audio, conversion = audioop.ratecv(data, 2, 1, 16000, 24000, conversion)
                            await self.send({'type': 'voice_audio', 'audio': base64.b64encode(audio).decode()})
                            if audioop.rms(data, 2) > 250:
                                self.last_activity = now
                    else:
                        final = self.recognizer.AcceptWaveform(data)
                        result = json.loads(self.recognizer.Result() if final else self.recognizer.PartialResult())
                        if is_wake_phrase(result.get('text', result.get('partial', ''))):
                            self.recognizer.Reset()
                            await self.wake()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state = 'error'
            self.error = f'Microphone or voice audio unavailable: {type(error).__name__}. Check the speaker and toggle listening off and on.'
            log.warning('Voice failed: %s', error)
        finally:
            self.active = self.ready = False
            if recorder and recorder.returncode is None:
                recorder.kill()
                await recorder.wait()
            if self.play_task:
                self.play_task.cancel()
                await asyncio.gather(self.play_task, return_exceptions=True)
            self.speaking = False
            while not self.output.empty():
                self.output.get_nowait()
            try:
                await self.send({'type': 'voice_stop'})
            except Exception:
                pass
