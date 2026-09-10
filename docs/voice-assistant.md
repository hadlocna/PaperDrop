# PaperDrop voice prototype

Say **Hey Paper Drop**, wait for “I'm here! What would you like me to draw?”, then ask for a picture. One drawing is generated and sent to the printer per conversation. Say the wake phrase again for another picture. The short **brrk** sound plays when a speaker connects and from Play test sound.

In device Settings, the owner can enable/disable **Hey Paper Drop** or use **Try a conversation** to bypass the wake detector. Turn voice listening off before changing speakers or running the separate audio tests. The status refreshes every ten seconds.

## Audio path

- Vosk small English 0.15 detects the phrase locally at 16 kHz. It is a vocabulary-constrained recognizer, not a trained production wake-word model; children's voices and noisy rooms still need field testing.
- The Anker SoundCore 2 exposes HFP mSBC at 16 kHz. Wait for codec negotiation before opening its PCM. ALSA plug conversion supports an 8 kHz fallback codec as well. Listening uses the hands-free audio profile; music-only A2DP cannot capture its microphone.
- The device resamples input to mono PCM16 24 kHz and sends it over its existing authenticated cloud WebSocket only after waking. The cloud opens OpenAI Realtime (`gpt-realtime-2.1`, cedar) with the server API key. That key stays in the backend.
- Incoming Realtime audio is streamed to the speaker. Input is suppressed during playback and briefly afterward to avoid self-triggering. This prototype takes turns; it does not support interrupting a spoken answer.
- A `create_picture` function moderates the request, generates thermal line art with `gpt-image-2.5-flare`, stores a normal Message, and sends it to this device. Standard print acknowledgements update its status. A sent message is not proof of a physical print.
- Each conversation is capped at two minutes, with an idle timeout on the device, one image, and twenty session starts per hour per backend process. The rate limit resets on backend restart; use a shared persistent limiter before broad rollout.
- Wake detection and conversation audio stay in memory. PaperDrop does not store audio or transcripts. Generated images are stored in the ordinary message history. OpenAI processing remains subject to the account's configured data controls.

## Validation

Backend/frontend builds pass. Thirteen agent tests and ten API tests cover owner access, disabled listening, wake boundaries, duplicate wakes, cancellation and speaker controls. A live Realtime smoke check returned PCM speech. A spoken drawing fixture went through Realtime function calling, moderation, Flare generation, and message delivery to a local test receiver (no physical print). The device's Vosk recognized a spoken wake fixture and rejected an ordinary greeting.

Live smoke command (uses the local backend key and incurs API usage):

```sh
PAPERDROP_LIVE_TEST=1 node backend/tests/realtime-live.cjs
```

Official references: [Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations), [Vosk model](https://alphacephei.com/vosk/models).
