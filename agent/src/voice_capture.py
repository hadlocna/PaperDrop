"""Bounded in-memory request recording; never captures before the local greeting ends."""
import audioop
import io
import wave


class RequestCapture:
    def __init__(self, now):
        self.started = now
        self.last_speech = None
        self.speech_seconds = 0
        self.audio = bytearray()

    def add(self, data, now):
        self.audio.extend(data)
        if audioop.rms(data, 2) >= 80:
            self.last_speech = now
            self.speech_seconds += len(data) / 32000
        if now - self.started >= 45:
            return 'too_long'  # Never send a request truncated at the recording limit.
        if self.speech_seconds >= 0.5 and now - self.last_speech >= 4:
            return 'complete'
        if now - self.started >= 15 and self.speech_seconds < 0.5:
            return 'no_request'
        return 'listening'

    def wav(self):
        target = io.BytesIO()
        with wave.open(target, 'wb') as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(self.audio)
        return target.getvalue()
