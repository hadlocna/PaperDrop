# Pi-owned Stream Deck demonstration

The installed mode runs `paperdrop-streamdeck.service` on the Lisbon Pi with the Stream Deck connected directly by USB. The Pi owns button input and artwork, USB microphone capture, Bluetooth speaker playback, backend requests, and Epson printing. No laptop service or bridge is needed. It starts automatically when the Pi boots and detects the Stream Deck again after USB reconnection.

The optional diagnostic companion is loopback-only on the Pi at port 8766. The former laptop bridge is disabled. To inspect it temporarily from a laptop, forward that port with SSH; this is not needed for normal operation.

## Try the drawing

1. Tap bottom-right **Draw & Print**, listen to the spoken instruction, wait for red, then speak into the **USB microphone attached to the Pi**, then tap **Done**. Holding and releasing also works. Maximum recording length is 15 seconds.
2. The Pi submits that WAV through its existing authenticated backend connection.
   The backend transcribes, moderates and calls **gpt-image-2.5-flare**, with **low** quality for this button demo. No API key was copied to the Pi.
3. The image appears on the upper-middle **Picture** key. Tap it to enlarge across
   all six keys; tap again to return. **Nothing has printed yet.**
4. Press the green bottom-right **Print** key. The Pi prints that exact image to
   its USB Epson TM-T20III, then returns a completion screen. Home starts again.

## Try a practice voice note

Home → Ohio → Andi opens the voice/drawing choices directly.
Postcards are attributed to the sending house: Lisbon, Ohio, or Düsseldorf.
No sender-face selection is needed.
Tap **Talk**, wait for red, speak into the Pi microphone, then tap **Done**.
Tap **Listen** to hear it on the SoundCore 2, then **Send** to save it.
This is a practice mailbox on this Pi, not a delivery to Ohio.

To try the receiving side, use the companion's grown-up selector to switch to
Ohio, select Andi and tap the bottom-left voice-note key. Playback comes from
the Pi. Return the selector to Portugal afterwards.

## Send a real drawing

Home → Düsseldorf → Laure → Draw. Tap, describe the picture into the Pi microphone, then tap Done. Review it and press Send. The image is rendered with “To: Laure / From: Lisbon” and sent to **Ale’s PaperDrop**, her real printer. Ohio maps to **Daugherty’s PaperDrop**; it queues while offline. The sending house comes from the authenticated physical device.

The screen distinguishes queued, sent, printing, and device-confirmed printed. A printer acknowledgement is not a human observation of the paper. Retries use the same persistent message ID so they do not print again. An uncertain dispatch remains pending for investigation rather than being blindly resent.

Voice notes remain a local practice mailbox. Real remote voice delivery is not included in this demo.

## Games

Choose a local child, then Games, then Colors, Letters, or Numbers. Correct answers earn one of five stars; number choices include counting dots. Incorrect choices are gently eliminated. Hear repeats the question, correct answers advance automatically after the spoken reward, and five stars unlock an animated celebration and Play again. There is always a Home button.

## Operation and recovery

- Pi code: `/opt/paperdrop/streamdeck`; private media/state:
  `/var/lib/paperdrop/streamdeck` (root only). The backend key stays on the backend.
- USB capture uses `plughw:CARD=Device,DEV=0`. Playback uses the existing selected
  Bluetooth speaker from `/etc/paperdrop/speaker.json`, via A2DP. Audio is explicitly resampled to stereo 44.1 kHz with a short silent
  lead-in. The previous hands-free profile is disconnected. The saved speaker
  reconnects automatically and negotiates stereo SBC.
- Cached voice guidance from the existing prototype is on the Pi. New uncached
  phrases are silent until added to the voice pack; there is no robotic local fallback.
- The demo service is enabled on boot; the original wake-word agent is disabled while this mode is selected.
- `Start.command` starts the Pi controller remotely; it does not install a laptop service.
- `Restore Pi Wake Word.command` stops/disables the Pi controller, restores the
  previous Pi agent and switches the laptop back to the local prototype.
- The button demo and original Pi wake-word agent are mutually exclusive. The
  demo uses the existing device registration; it does not create a new device.
- Bridge loss cancels a held microphone recording. Buttons never replay after a
  failed request. An image being generated can finish and wait for review.
- Printer receipts are written and flushed before USB transmission. A repeated
  completed job is ignored; an uncertain job is blocked, avoiding duplicate paper.
  USB completion still requires human observation of the physical paper.
- Unrelated cloud mail is retained under `pending-cloud-mail` during this demo;
  it is not automatically printed. Fleet OTA/admin commands are not implemented
  by this dedicated demo connection. Restore the ordinary agent for those.
- Voice mail and print receipts survive restart; unsent active drafts do not yet
  restore their screen after restart. Do not restart during a child's draft.

## Verification, 21 September 2026

Live: Pi detects USB microphone and Epson; selected SoundCore 2 connected.
Physical Stream Deck key events reached the Pi. A spoken drawing request captured
on the Pi produced a unicorn riding a turtle via the backend in 17.18 seconds.
The returned image appeared in print review, with no auto-print. A subsequent
physical Print press completed one Epson USB image-and-cut job. The user confirmed the physical drawing/print worked. They reported garbled
speaker output; the initial mono resampling did not resolve it. Stereo SBC
negotiation and matching WAV conversion were then applied; audibility is
tracked separately in the task.

Tests cover explicit print confirmation, stale held keys, repeated cycles, failed
print retry without regeneration, cloud session/job correlation, cancellation on
bridge loss, and suppression of duplicate or uncertain USB prints.

Developer tests (from this directory):

```sh
.venv/bin/python -m unittest -v test_controller test_animation_demo test_printer test_pi
```

Pi dependencies in addition to its existing agent environment: `streamdeck==0.10.0`, `libhidapi-libusb0`, `cairosvg`,
`fonts-dejavu-core`, `libcairo2`. `websockets` and `python-escpos` are
already installed with the Pi agent. Keep OS packages on the Pi and the laptop
virtualenv separate.

Backend revision `e345309` deployed successfully. The previously saved Laure drawing was submitted once and received a durable queued receipt, awaiting her device reconnecting. The final voice pack and stereo playback are installed; the speaker was disconnected during final verification, so fresh listening acceptance remains open.

Direct USB migration: installed StreamDeck 0.10.0 and libhidapi-libusb0 on the Pi, removed --no-device from its enabled service, and disabled the macOS bridge LaunchAgent. Live state confirms runtime=pi, button_transport=usb, device_connected=true, cloud_connected=true. SoundCore 2 reconnected; the direct-USB button test captured microphone audio, generated a drawing in 15.14 seconds, showed print review, and completed an Epson USB job after the user pressed Print. Human confirmation of paper and sound remains separate. All 29 controller tests pass.

## Five language voice interface

Tap your face, then the globe button (showing your current language). Choose English, Français, Deutsch, Italiano, or Português. The sixth key goes back without changing anything. Portuguese is European Portuguese. Each child’s choice is stored in the Pi mailbox database; selecting another child restores their own language. Home drawing and house messaging use the last selected language, including after reboot.

The language applies to spoken guidance, all game questions and rewards, and the main button labels. Cousin names and house names stay unchanged. Existing recorded voice messages play in their original language. The diagnostic companion still has some English explanatory text. Spoken guidance is AI-generated using OpenAI’s Marin voice and cached on the Pi; language selection makes no API request and needs no laptop or API key on the device.

Correct game answers advance automatically after their reward finishes. Home cancels the pending round, so a game cannot reopen after leaving it. After five stars, Play again begins a fresh game.

Language release verification: all 410 unique required cached WAVs validated and present on the Pi; all 33 controller/language/media tests pass. Live USB controller selection switched to French and rendered “Jeux”, then returned to English. The live game check stopped safely when the physical screen changed; automatic progression and cancellation passed the timer-driven tests.

## Recording guidance — 21 September 2026

Drawing and voice-note buttons play a cached Marin instruction in the selected
language before opening the microphone. The countdown starts only after capture
is ready. Releasing the button during the instruction keeps tap-to-record armed;
Delete cancels without starting capture. Missing or failed guidance shows an error
instead of silently starting the clock. Ten new voice clips cover both actions in
all five languages. All 35 local tests pass, including prompt timing/cancellation.
The Lisbon Pi received controller/media/catalogue changes and the ten clips;
physical listening acceptance remains separate.
