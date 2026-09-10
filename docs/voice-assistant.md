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

Backend/frontend builds pass. Fourteen agent tests and twelve API tests cover owner access, disabled listening, wake boundaries, duplicate wakes, cancellation and speaker controls. A live Realtime smoke check returned PCM speech. A spoken drawing fixture went through Realtime function calling, moderation, Flare generation, and message delivery to a local test receiver (no physical print). The device's Vosk recognized a spoken wake fixture and rejected an ordinary greeting.

Live smoke command (uses the local backend key and incurs API usage):

```sh
PAPERDROP_LIVE_TEST=1 node backend/tests/realtime-live.cjs
```

Official references: [Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations), [Vosk model](https://alphacephei.com/vosk/models).

## Recovery and current device testing

Firmware 1.3.4 contains local AI-generated cedar error clips for missed requests, service errors, failed image creation, and failed printing. These clips play without another OpenAI call. The microphone is suppressed during announcements. The cloud exposes transient heard-request and spoken-reply captions in owner Settings; they are not written to the database or logs.

The end_conversation tool returns control to the local detector when asked to stop or wait for the keyword. The live spoken-stop fixture verified this transition. The user confirmed the physical wake phrase and opening greeting, but reported that their drawing request did not print; that physical acceptance remains unresolved after recovery changes. Do not describe the full hardware voice-to-print flow as proven solely by the local simulated drawing test.

BlueALSA now uses its documented scheduling configuration for HFP audio threads. The Pi still logged some mSBC packet loss during testing; the CVSD fallback produced silence and was reverted. Speech detection uses far-field noise reduction. This hardware combination still needs physical microphone and second-turn verification.

The four fallback audio assets were generated with gpt-4o-mini-tts-2025-12-15, cedar, raw PCM16 mono 24 kHz, with warm reassuring delivery and clear gentle pacing. They are AI-generated speech.

## Physical print accepted; repeat-cycle update

The user subsequently confirmed wake phrase -> spoken request -> desired physical image print. Device/cloud evidence includes messages 5651b465-b440-4bb2-9a44-18c152058213 (printed 10:39:43 UTC) and d770fe8f-84ce-4a08-a80f-fbd7f1ebb932 (printed 10:40:47 UTC). The previous unresolved physical-print note above is superseded by that confirmation.

The remaining reported problem was perceived freezing after completion. Logs showed return to wake mode, followed by another activation that captured nearby feedback. The detector now requires the full Hey Paper Drop phrase. It can restart an active conversation; session identifiers prevent a delayed end event from the old conversation from ending the new one. A standalone stop is also recognized locally during the listening turn. Drawing generation plays a local acknowledgement and another short progress clip after fifteen seconds if still working. Ordinary microphone audio is not uploaded during generation; local wake/stop recognition stays available between announcements.

Sixteen agent tests and twelve backend tests pass. The updated repeat-cycle behavior still requires a physical test. The user requested additional prerecorded routine phrases and a more youthful synthetic voice only after the whole functional cycle is reliable; those voice-style changes remain queued.


### 2026-09-10 receipt and repeat-wake follow-up

Production key ownership was checked without exposing the key: Nathan Hadlock, nathan@pelaterra.com; matching dashboard key Replit, project PT Agent, organization Impacto Pela Terra. Dashboard displayed $0.62 monthly spend on that key at approximately 14:17 UTC. The local test credential has the same masked suffix. This is reported key usage, not a complete per-device invoice: image usage showed zero despite successful physical prints.

Firmware 1.3.6 adds a cached prompt receipt acknowledgement, preserves microphone muting across queued speech clips, resets recognition after playback, and reopens capture/recognition after each completed conversation. It announces readiness after reopening. Existing drawing-start and 15-second progress clips remain. Audio health logs contain levels and counters only, no transcripts or recordings. Two real print acknowledgements were observed at 14:12 and 14:16 UTC before this update; user still reported missed repeated wakes and inaudible progress, so audible confirmation and repeat-wake acceptance remain required.


### 1.3.7 confirmation and playback troubleshooting

Observed two recent print cycles with only 26 and 38 uploaded 100ms microphone chunks. The previous 900ms silence threshold could end a child's request prematurely. Realtime now uses low-eagerness semantic turn detection, reads a staged drawing back, and requires a new explicitly affirmative transcribed turn before creating the identical staged image prompt. Corrections require a new read-back. No unconfirmed image is generated or printed.

Complete reply audio is buffered before Bluetooth playback to avoid feeding the speaker intermittent network chunks. Transcription receipt no longer queues a local phrase that mutes continuing user speech. Marin plus expressive storybook delivery replaces Cedar; local prompts use the same synthetic voice. A locally synthesized two-second pencil-stroke sound repeats with short listening gaps during generation. The local wake beep remains. Audible output and multi-cycle acceptance remain device tests, not inferred from process exit codes.

Fleet read-only check: Ale's PaperDrop online on 1.0.0; Daugherty's offline on 1.0.0; Test Device 88 offline with no firmware version. No update sent to these devices. Existing updater checks a supplied checksum and backs up application files, but does not validate post-restart cloud health or cover all system/dependency modifications in rollback. Fleet rollout should wait for updater capability verification and recovery testing with physical access.
