# PaperDrop sales video

A 62-second, 1920×1080 / 30 fps product video covering the features added since the
original launch page. It uses the brand from `frontend/src/pages/Marketing.tsx`: cream
`#FAF9F6`, ink `#3D405B`, coral `#E07A5F`, mustard `#F2CC8F`, sage `#81B29A`, Nunito +
Gloria Hallelujah, offset "sticker" shadows, the smiling printer, the logo, and
stop-motion jitter.

**Output:** `paperdrop-sales.mp4`

## Running order

| Time | Scene | Feature |
| --- | --- | --- |
| 0–4 s | Messages you can hold | Hook: the printer prints "Love you!" |
| 4–8 s | …just got a whole lot more magical | Brand kicker |
| 8–16 s | Just say it | "Hey PaperDrop" voice drawing: confirm, then print |
| 16–20 s | Comics. Maps. Mazes. Cards. Posters. Stories. | Wider range of AI thermal artwork |
| 20–26 s | Photos that pop on paper | 5 print styles: Photo, Vintage, Newspaper, Comic, B&W |
| 26–34 s | Send love across the world | Family Mail: voice notes and pictures between houses, mailbox, auto-printed To/From postcards, offline queue |
| 34–39 s | Six big buttons | Kids' button interface: faces, houses, tap to draw and print |
| 39–47 s | Games that teach, prizes that print | Colors, Letters, Numbers and the new Riddles; 5 languages; stars; collectible prize cards |
| 47–52 s | Built to just work | No duplicate prints, offline queue, managed updates, printer-ready notice, full-width prints, Bluetooth speaker and volume |
| 52–55 s | No ink. Ever. | Thermal |
| 55–62 s | Make their day | CTA: paperdrop.me |

## Real product output, not mock-ups

The printed paper in the video comes from the product's own code:

- **Print styles:** `frontend/src/utils/dithering.ts` applied to the Lisbon artwork at 576 dots wide.
- **Prize cards:** `agent/streamdeck/rewards.py`.
- **"Printer is ready" notice:** `render_notice()` in `agent/streamdeck/cousin_mail.py`.
- **To/From postcard:** the same layout `cousin_mail.receive()` prints.
- **Riddle text, languages and icons:** `agent/streamdeck/riddles.py` and the Stream Deck's Lucide icons.

The demo names are made up (Mia, Grandma, Grandpa, Leo). No real family names or
child portraits are used.

## Rebuild

Requirements: Python 3 with `numpy scipy pillow cairosvg`, Node 22+ with Playwright and
Chromium, and `ffmpeg`.

```sh
cd marketing/sales-video
python3 scripts/make_assets.py      # printed-paper assets from PaperDrop's own code
python3 scripts/make_icons.py       # icons.js from the Stream Deck icon set
node scripts/render.mjs --cues      # export the sound-effect timeline
python3 scripts/make_audio.py       # synthesize the original soundtrack and SFX -> out/music.wav
node scripts/render.mjs             # render frames and mux -> out/paperdrop-sales.mp4
```

- **Preview live:** open `index.html` in a browser. It plays in real time; add `?t=30` to freeze on a single frame.
- **Grab stills:** `node scripts/render.mjs --stills 1,9.5,30`.

Every frame is a pure function of time (`window.seek(t)` in `video.js`), so frames render
deterministically and in parallel. To change timing, edit a scene's start and end in `video.js`
and re-export the cues so the audio follows.

The soundtrack is synthesized from scratch in `make_audio.py` (120 BPM, D–A–Bm–G), so
there is nothing to license. There is no voiceover, which keeps the video usable with
the sound off.
