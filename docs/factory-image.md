# PaperDrop automatic-update image

For the newer sanitized, manually accepted Raspberry Pi 5 installation, see
[working-pi-image.md](working-pi-image.md). That snapshot intentionally leaves
automatic firmware updates disabled until a controlled release. The historical
factory builder below still describes its original fixed baseline.

This image targets Raspberry Pi 4 and 5 (64-bit Raspberry Pi OS Lite). It contains
both the ordinary printer agent and the USB Stream Deck interface, all 420 spoken
prompts, Bluetooth audio, and Python dependencies. A USB Stream Deck present at
boot selects the button interface; otherwise the ordinary printer agent runs.

## Family setup

1. In PaperDrop, open the existing device's Settings. Download the PaperDrop image
   and its private recovery file. Recovery files expire after seven days.
2. Use Raspberry Pi Imager's **Use Custom** option to write the `.img.xz` file to a
   new card of at least 16 GB. Writing erases the selected card. Keep the old card.
3. Reinsert the newly written card into the computer. Copy
   `paperdrop-enrollment.json` into the `bootfs` drive, keeping that exact name.
4. Power off the Pi, swap cards, connect Ethernet if available, and power it on.
   For Wi-Fi, join **PaperDrop-Setup** (password `paperdrop-setup`) from a phone,
   open **http://10.42.0.1:8080**, and enter the home Wi-Fi and country code.
5. Once online, enrollment restores the same device/account/house. The app's
   Speaker & microphone settings pair the house's Bluetooth speaker and set volume.

The universal image contains no Wi-Fi passwords, SSH private keys, account tokens,
or device identities. Do not share a recovery file outside its household. A blank
image without a recovery file creates a new device, which needs claiming in the app.
Bluetooth pairing is stored on the card, so replacement cards need pairing once.

## Updates and recovery

`paperdrop-update.timer` checks `https://api.paperdrop.me/uploads/stable.json` after
boot and every five minutes with a small random delay. Uploading a firmware package
does not deploy it. The admin **Publish automatic update** action explicitly moves
the stable channel. Existing pre-image devices do not subscribe automatically.

The updater requires HTTPS on the trusted API origin, a SHA-256 checksum, a valid
managed-package format and bounded archive paths. It stages code and a separate
Python virtualenv, waits for an idle interface, and atomically switches `current`.
The new runtime must authenticate to the backend within three minutes. Otherwise
it switches back to the previous release and defers retries for six hours. A
pending verification interrupted by power loss is rolled back on the next check.
Device credentials, speaker settings and mailbox state live outside releases.
The backend `/app/uploads` volume must persist across deployments.

## Build and publish

Build on an arm64 Linux host or Docker Desktop on Apple Silicon. The factory
builder writes only a regular image file through a loop device; it never chooses
or writes a physical SD card. The official Raspberry Pi OS compressed-image
checksum is checked before modification.

```
python3 scripts/build_managed_release.py VERSION --speech-dir /path/to/speech
```

The speech authoring scripts and language inventory live under `agent/streamdeck`.
The bundler refuses an incomplete voice pack. `agent/factory/build-image.sh` and
`finalize-image.sh` document the build and inspection used for this image. The
current baseline is `2.0.0-20260921`; the first stable upgrade is `2.0.1-20260921`.
The baseline image's updater remains able to obtain subsequent published releases.

Image distribution uses checksum-addressed 32-MiB upload chunks and a final full
checksum check. `/uploads/image.json` points to the current downloadable image.
The image is not an email attachment; send its download link.

## Acceptance boundaries

Local tests cover checksum/origin rejection, unsafe archive rejection, atomic
switching, rollback on failed authentication, retry backoff, volume validation,
BlueALSA old/new volume formats, owner-only recovery and expired enrollment.
Image inspection verifies runtime imports, Python compilation, systemd units and
absence of baked credentials. These do not replace booting a newly written card
on the target Pi or a human listening to the connected speaker.
