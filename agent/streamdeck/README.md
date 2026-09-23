## Current Pi controls

Tap a cousin’s face → globe to choose English, Français, Deutsch, Italiano, or Português (Portugal). The Pi remembers each child’s preference. Games and all spoken guidance follow that choice, with cached AI-generated Marin speech. A correct game answer earns a star and automatically starts the next round after the feedback finishes; Home cancels it.

# Current demo: Pi controller + laptop button bridge

See [PI-DEMO.md](PI-DEMO.md) for the installed Pi-owned voice → backend Flare →
button preview → explicit Print flow and practice audio messaging.
`Start.command` now starts that bridge. The historical laptop-only notes below
include the superseded automatic-print behavior; they do not describe Pi mode.

---

# PaperDrop Cousins — six-key device prototype

A working local bench for the connected Stream Deck Mini. Physical keys and the
laptop companion share a single controller and renderer. Real microphone capture,
spoken guidance, transcription and image creation; local test mailboxes.

## Try it

Open <http://127.0.0.1:8766>. The Stream Deck is the child's interface; the browser
is an optional larger image viewer and a grown-up station switcher.

1. Home: **Alma / Theodore / Margaux** above **Ohio / Düsseldorf / Draw & Print**.
   A child's face carries their unread-mail badge.
2. A face opens **Letters / Numbers / blank** above **latest voice note / latest
   picture / Home**. Received items show the sender's face and a microphone or
   pencil badge; empty slots stay dark. Voice starts on tap; picture opens the
   six-key preview. These show the newest item of each type, including after reading.
3. The two house buttons go directly to the cousin picker. If no sender has been
   selected yet, choosing a cousin asks who is sending. The chosen identity stays
   selected until changed or the station is switched.
4. Hold **Draw & Print** at home, wait for red, speak, and release. The drawing is
   created and automatically sent to the **Portugal PaperDrop Epson**. No cousin,
   Send, or confirmation menu. Repeated presses while processing are ignored.
5. If the Epson is disconnected, the picture remains in the active draft and
   **Retry** attempts printing that image without generating it again. Delivery
   uncertainty blocks resubmission to avoid duplicate paper output.
6. Sending to cousins still uses the local test mailbox. Use the companion station
   selector to test the receiving child's latest voice/picture buttons.

### Family

| House | Children |
| --- | --- |
| Portugal | Alma, Theodore, Margaux |
| Ohio | Andi, Sloan, Roux |
| Düsseldorf | Elise, Laure |

All names and houses are in `family.json`. All eight cousins have illustrated transparent PNG portraits
under `assets/portraits/`. Original portraits are retained alongside the cutouts.
When a child names one or more cousins in a drawing request, image generation
uses their portraits as face references, including on the Pi's backend route.
Location artwork lives under `assets/locations/`. The renderer preserves portrait
alpha when placing faces over location art and uses a dark display behind face keys.

## Why this layout

Home keeps children, distant houses, and local drawing directly accessible. A
child's personal screen has only learning and their latest received items, with
sender faces visible. No separate Games, Cousins, or My Mail menu. Games retain
four answers, Repeat, and Home. Image preview and explicit send remain for cousin
messages; home Draw & Print automatically prints locally.

## Scope and data

- **Cousin messaging is local bench only.** `Mailbox.send()` returns `saved_locally`, not delivered or
  printed. Ohio and Düsseldorf are simulated on this laptop. No family device IDs
  or remote accounts have been guessed or configured.
- Voice-note audio stays local. Drawing audio is sent to OpenAI for transcription,
  then moderation and image generation, following the existing
  `backend/src/services/recordedVoice.ts` pipeline and thermal-art style.
- Uses the existing `backend/.env` key in memory, or `OPENAI_API_KEY`. No credential
  is copied into this directory, the browser, logs, or the LaunchAgent.
- Generated images and audio, local SQLite mailboxes, cached speech and diagnostic
  previews are in ignored `.state/`. Sent mail survives restart. Unsent drafts are
  not yet restored after restart; do not restart during a child's session.
- The microphone opens only while a recording key is held, including its short
  amber startup. Delete cancels capture; input is capped at 15 seconds. Camera is
  unused. No always-on listening.
- One generation at a time, no automatic API retries, and at most 20 drawing
  attempts per process per hour. API calls have a 90-second timeout per request;
  transcription, moderation and image creation can together take longer.
- Incoming badges update without interrupting an active draft. Playback is local
  to the laptop speakers. This is not a private/authenticated child account system.

## Running and restoring

The installed macOS LaunchAgent is `com.paperdrop.cousins-streamdeck`. It restarts
the controller after a crash and runs at login. The old
`com.paperdrop.streamdeck-soundboard` job is disabled while this test owns the USB
device; its files and original plist are unchanged.

- **Start.command** installs/restarts this prototype.
- **Restore Previous.command** stops it and re-enables the previous prototype.
- Logs: `.state/controller.log`; current key image: `.state/deck-preview.png`.

Fresh setup (Python 3.11, macOS, Homebrew hidapi/cairo/ffmpeg):

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python prepare_voice.py
.venv/bin/python manage.py
```

`PAPERDROP_MICROPHONE` may select another AVFoundation microphone by its exact
device name. The default is `MacBook Pro Microphone`. `PAPERDROP_IMAGE_MODEL`
overrides the existing PaperDrop default `gpt-image-2.5-flare`.

Developer checks:

```sh
.venv/bin/python -m unittest -v test_controller.py
.venv/bin/python app.py --no-device --port 8767 --state-dir /tmp/paperdrop-bench
```

The companion binds only to loopback, validates Host/Origin and requires a custom
header on mutations. It exposes no arbitrary file paths or credentials.

## Before connecting real houses

The existing production message route targets a printer device and its authorized
adult owner; it does not model child recipients or a voice mailbox. A production
transport needs an authorized family/house/child mapping, voice storage and playback
on each station, per-child receipts/read state, idempotent remote send, offline
queueing, and explicit quiet-hour/printing rules. `store.py` is the isolated local
transport boundary to replace, not an unguarded call to a production printer.

This change does not deploy backend, frontend or Raspberry Pi firmware. Child
usability and the feel of the real key mosaic still need your physical test.

## Verification — 17 September 2026

- Twelve automated interaction/storage tests pass, covering every child, sender
  selection, recipient-specific badges, completed-playback read receipts, reply
  targeting, duplicate sends, held keys across transitions, generation mashing,
  draft deletion, short-recording cancellation/retry, and failed-save retry.
- The USB device was enumerated as Stream Deck Mini with six 80×80 displays; the
  running controller connected and wrote the rendered interface to all six keys.
- The actual microphone produced a valid mono WAV and reached voice review. The
  readiness probe detected live audio after about half a second. A quiet capture
  was correctly rejected instead of being sent for transcription.
- A synthetic spoken request passed real transcription, moderation and image
  creation, returning a snail with a letter. Test media is local under
  `.state/verification/`; this does not represent a message from any cousin.
- Initial home, recipient picker, compose, waiting, mosaic and review renders were
  inspected. Browser selection of Alma → Ohio → Andi reached the same physical
  controller. Remote delivery and printing were not tested or enabled.

Icons: Lucide, ISC license included in `assets/icons/LICENSE`.

## Updated Epson integration

Draw & Print uses the existing authenticated PaperDrop admin relay, restricted to
Portugal device PD-883bfd8f. It checks for the Epson USB vendor before dispatch.
A success means the device accepted the message, not verified paper output.
Local receipts suppress duplicate submissions, including unknown delivery outcomes.
No Brother queue is used. The relay does not create a normal web-app message-history
record; it is a bench integration, not a new production messaging API.

Live check during this update: PaperDrop answered printer_status through the cloud,
but its USB inventory contained no Epson. Reconnect/power on the Epson before
physical testing. UI, drawing and retry paths are available now. Sixteen tests pass,
including latest-by-type selection and guarded printer delivery.

## Animated feedback and example receiving flow

Unread envelopes gently bounce twice every four seconds. Microphone/playback borders
pulse (activity, not measured loudness). A pencil travels across the bottom row while
generating; this is indeterminate activity, not a completion percentage. Images fade
in over 0.7 seconds; success checks bounce briefly. Text and controls stay fixed.
Idle screens without mail stay still. Only changed USB keys are rewritten, at up to
five animation frames per second.

Two clearly synthetic local examples are provided for Alma: a narrated voice sample
attributed to Andi and a snail image attributed to Elise. These are not real messages
from those children. Tap Alma, then bottom-left for voice or bottom-middle for the
picture. Voice unread clears after completed playback; picture unread clears on open.

The companion's **Show sample mail for Alma** resets only those two example records
to unread/recent. Other messages are unchanged. It is available only from Home or
a child's screen, so it cannot interrupt a draft. Twenty tests pass, including sample
isolation and separation of animation from button behavior.
