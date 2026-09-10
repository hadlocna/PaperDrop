"""Local wake phrase; bounded cloud conversations over the authenticated device socket.

No microphone audio leaves the device before a wake event. No recordings are saved.
"""
import asyncio
import base64
import json
import logging
import re
import time
import uuid
from pathlib import Path
from speaker_control import lock, run_speaker

log = logging.getLogger('Voice')
SETTINGS = Path('/etc/paperdrop/voice.json')
MODEL = Path('/opt/paperdrop-models/vosk-model-small-en-us-0.15')


def is_wake_phrase(text):
    return bool(re.search(r'\bhey\s+paper\s*drop\b', text.lower()))


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
        self.drawing = False
        self.session_id = None
        self.last_progress = 0
        self.receipt_announced = False
        self.announce_ready = False
        self.ready = False
        self.speaking = False
        self.mute_until = 0
        self.player = None
        self.play_task = None
        self.output = asyncio.Queue(maxsize=200)
        self.finish = False
        self.recognizer = None
        self.last_reply = ''
        self.last_heard = ''
        self.last_notice = None
        self.microphone_level = 0
        self.sent_chunks = 0
        self.played_replies = 0
        self.session_started = 0
        self.last_activity = time.monotonic()

    async def send(self, event):
        if event.get('type') in ('voice_start', 'voice_audio', 'voice_stop'):
            event['session_id'] = self.session_id
        await self.ws.send(json.dumps(event))

    def status(self):
        return {'ok': True, 'enabled': self.enabled, 'state': self.state, 'error': self.error,
                'wakePhrase': 'Hey Paper Drop', 'ready': MODEL.exists(),
                'lastHeard': self.last_heard, 'lastReply': self.last_reply, 'microphoneLevel': self.microphone_level, 'sentChunks': self.sent_chunks,
                'playedReplies': self.played_replies, 'speaking': self.speaking, 'sessionActive': self.active}

    async def start(self):
        if self.enabled and (self.task is None or self.task.done()):
            self.state = 'starting'
            self.task = asyncio.create_task(self.supervise())

    async def supervise(self):
        """Recover capture failures without waiting for the cloud heartbeat."""
        while self.enabled:
            await self.listen()
            if self.enabled:
                await asyncio.sleep(2)

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

    async def wake(self, restart=False):
        if self.active:
            if not restart:
                return
            await self.send({'type': 'voice_stop'})
        self.session_id = uuid.uuid4().hex
        self.drawing = False
        self.active = True
        self.ready = False
        self.finish = False
        self.receipt_announced = False
        self.state = 'connecting'
        self.error = None
        self.last_heard = self.last_reply = ''
        self.session_started = time.monotonic()
        self.last_activity = time.monotonic()
        await self.queue_clip('voice-wake.pcm')
        await self.send({'type': 'voice_start'})
        log.info('Wake phrase detected; opening voice conversation')

    async def queue_clip(self, filename):
        path = Path(__file__).with_name(filename)
        if path.exists() and self.play_task and not self.play_task.done():
            self.speaking = True
            await self.output.put(base64.b64encode(path.read_bytes()).decode())
            await self.output.put(None)

    async def notice(self, reason='error'):
        if (self.last_notice is not None and time.monotonic() - self.last_notice < 10) or not self.play_task or self.play_task.done():
            return
        filenames = {'error': 'voice-error.pcm', 'no-request': 'voice-no-request.pcm',
                     'image': 'voice-image-error.pcm', 'print': 'voice-print-error.pcm'}
        self.last_notice = time.monotonic()
        await self.queue_clip(filenames.get(reason, 'voice-error.pcm'))

    async def event(self, data):
        kind = data['type']
        if data.get('session_id') and data['session_id'] != self.session_id:
            return
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
        elif kind == 'voice_notice':
            await self.notice(data.get('reason', 'error'))
        elif kind == 'voice_heard':
            self.last_heard = data.get('text', '')
            heard = self.last_heard.strip().lower().strip('.!?')
            if self.active and not self.drawing and not self.receipt_announced and heard and heard not in ('stop', 'be quiet', 'go to sleep'):
                self.receipt_announced = True
                await self.queue_clip('voice-received.pcm')
        elif kind == 'voice_reply':
            self.last_reply = data.get('text', '')
        elif kind == 'voice_progress':
            state = data.get('state', 'talking')
            if state == 'drawing' and not self.drawing:
                self.drawing = True
                self.last_progress = time.monotonic()
                await self.queue_clip('voice-drawing.pcm')
            elif state == 'talking':
                self.drawing = False
            self.state = 'drawing' if self.drawing else state
        elif kind == 'voice_finish':
            self.drawing = False
            self.finish = True
        elif kind in ('voice_end', 'voice_error'):
            self.drawing = False
            if kind == 'voice_error':
                await self.notice('error')
            self.active = False
            self.ready = False
            self.finish = False
            if data.get('error'):
                self.error = data['error']
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
                        code = await asyncio.wait_for(self.player.wait(), 15)
                        if code:
                            raise RuntimeError('Bluetooth voice playback failed')
                        self.played_replies += 1
                        self.player = None
                    conversion = None
                    self.speaking = not self.output.empty()
                    if self.recognizer:
                        self.recognizer.Reset()
                    if self.active and self.state != 'drawing':
                        self.state = 'listening_for_request'
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
            self.recognizer = KaldiRecognizer(model, 16000, json.dumps(['hey paper drop', 'stop', '[unk]']))
            # Voice owns audio while enabled so pairing/test commands cannot tear down capture.
            async with lock:
                info = await run_speaker('microphone_ready')
                if not info.get('ok'):
                    raise RuntimeError(info.get('error', 'Microphone unavailable'))
                pcm = 'plug:{SLAVE="' + info['pcm'] + '"}'
                recorder = await asyncio.create_subprocess_exec('arecord', '-q', '-D', pcm, '-t', 'raw', '-f', 'S16_LE', '-r', '16000', '-c', '1',
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                self.play_task = asyncio.create_task(self.playback(pcm))
                self.state = 'listening'
                self.error = None
                if self.announce_ready:
                    self.announce_ready = False
                    await self.queue_clip('voice-ready.pcm')
                conversion = None
                diagnostics_at = 0
                while True:
                    data = await asyncio.wait_for(recorder.stdout.readexactly(3200), 5)
                    now = time.monotonic()
                    self.microphone_level = audioop.rms(data, 2)
                    if now - diagnostics_at >= 10:
                        diagnostics_at = now
                        log.info('Audio health: state=%s active=%s speaking=%s level=%d uploaded=%d replies=%d',
                                 self.state, self.active, self.speaking, self.microphone_level,
                                 self.sent_chunks, self.played_replies)
                    if self.active and now - self.session_started > 120:
                        await self.notice('image' if self.state == 'drawing' else 'no-request')
                        await self.send({'type': 'voice_stop'})
                        self.active = self.ready = False
                        self.state = 'listening'
                        self.recognizer.Reset()
                    if self.play_task.done():
                        await self.play_task
                    if self.finish and not self.speaking and self.output.empty() and now >= self.mute_until:
                        await self.send({'type': 'voice_stop'})
                        self.active = self.ready = self.finish = False
                        self.announce_ready = True
                        # Start a fresh recorder and decoder after every completed flow.
                        # The ready cue is played only once capture has reopened.
                        return
                    if self.drawing and not self.speaking and now - self.last_progress > 15:
                        self.last_progress = now
                        await self.queue_clip('voice-working.pcm')
                    if self.speaking or now < self.mute_until:
                        conversion = None
                        continue
                    final = self.recognizer.AcceptWaveform(data)
                    result = json.loads(self.recognizer.Result() if final else self.recognizer.PartialResult())
                    phrase = result.get('text', result.get('partial', ''))
                    if is_wake_phrase(phrase):
                        self.recognizer.Reset()
                        await self.wake(restart=True)
                        conversion = None
                        continue
                    if self.active and final and phrase.strip() == 'stop':
                        await self.send({'type': 'voice_stop'})
                        self.active = self.ready = self.drawing = False
                        self.state = 'listening'
                        self.recognizer.Reset()
                        continue
                    if self.active:
                        if now - self.last_activity > 40 and not self.drawing:
                            await self.notice('no-request')
                            await self.send({'type': 'voice_stop'})
                            self.active = self.ready = False
                            self.state = 'listening'
                            self.recognizer.Reset()
                        elif self.ready and not self.drawing:
                            audio, conversion = audioop.ratecv(data, 2, 1, 16000, 24000, conversion)
                            self.sent_chunks += 1
                            await self.send({'type': 'voice_audio', 'audio': base64.b64encode(audio).decode()})
                            if self.microphone_level > 250:
                                self.last_activity = now
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.state = 'error'
            self.error = f'Microphone or voice audio unavailable: {type(error).__name__}. Reconnecting automatically.'
            log.warning('Voice failed: %s', error)
        finally:
            self.active = self.ready = self.drawing = self.finish = False
            self.microphone_level = 0
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
