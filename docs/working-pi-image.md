# Validated-device image snapshot

Download the compressed image, checksum, and build metadata from the
[working Pi image preview release](https://github.com/hadlocna/PaperDrop/releases/tag/working-pi-2026-10-09).
Use this release download rather than assuming the web app's older image-download
link already points at this snapshot. Recovery JSON still comes from your own device settings.

The 2026-10-09 working-device image uses the tested Raspberry Pi 5 installation:
64-bit Raspberry Pi OS / Debian 13 (Trixie), managed runtime
`2.1.3-20261004`, USB printer + Stream Deck auto mode, system-Python D-Bus,
BlueALSA A2DP playback configuration, and the installed speech pack.
Installed Python application sources were compared with `main` at `e78ea5b`.
The web/server fixes are deployed separately; they are not programs running in the image.

This is a sanitized filesystem snapshot, not a raw clone of the SD card.
Enrollment/device identity, Wi-Fi passwords/profiles, Bluetooth bonds, account
password hashes, SSH keys, user files, logs, and mailbox/test recordings are excluded.
The per-device 2.4 GHz/BSSID workaround is deliberately not distributed.
Automatic firmware updates remain disabled. Wake-word operation is not part of
the accepted Stream Deck configuration; no additional offline wake model is added.
Original Imager cloud-init provisioning is disabled; PaperDrop's enrollment and
network setup helpers own first boot instead.

## Restore your device

1. Download the `.img.xz` and its SHA-256 file from the image release. Verify the
   checksum, for example with `Get-FileHash -Algorithm SHA256 IMAGE.img.xz`.
2. In Raspberry Pi Imager choose **Use Custom** and the compressed image, then
   flash a card of at least 16 GB. This erases that card. Keep your working card
   until you have tested the replacement.
3. Download a **fresh** `paperdrop-enrollment.json` from your device's settings
   in the PaperDrop web app. It expires after seven days. Copy it to the card's
   `bootfs` drive before first boot. Never upload it to GitHub or share it.
4. Optionally copy your SSH **public** key into a file named
   `paperdrop-authorized-keys` on `bootfs`. This explicitly enables key-only SSH
   for user `paperdrop` and passwordless sudo for that maintenance account. No
   default password, private key, or authorized public key ships in the image.
5. Connect Ethernet to a router for initial setup, or join the Pi's
   **PaperDrop-Setup** network (password `paperdrop-setup`) and open
   `http://10.42.0.1:8080` to enter Wi-Fi details and the correct country.
   A direct laptop Ethernet cable alone does not provide Internet/DHCP.
6. Confirm your existing device appears online. Pair the Bluetooth speaker again
   using **Scan for speakers** or **Refresh**. Re-select language/volume as needed.
7. Test ordinary printing, Stream Deck drawing, incoming voice/picture mail,
   browser log downloads, and microphone playback. A source-device test and
   image filesystem/import checks do not replace this newly flashed-card test.

Without recovery JSON a new device identity is generated and must be claimed.
No shared household identity is baked into the download. The original desktop
auto-login and account passwords are disabled in the distributed snapshot.
Maintenance access requires your optional public key; a desktop password must
be set separately through that maintenance account if desktop login is wanted.
The image root partition is 7.5 GiB; use `sudo raspi-config` to expand it if needed.

## Rebuild from a working Pi

Use a Linux root environment (native ARM64 or WSL/Linux x86 with
`qemu-user-static`) with `sfdisk`, `dosfstools`, `e2fsprogs`, `zerofree`, `xz`, and SSH.
Keep at least 12 GB free on the build host. No physical target disk is used.

On the source Pi, copy and start the exporter:

```sh
sudo systemd-run --unit=paperdrop-image-export --collect -p RuntimeMaxSec=1800 \
  /bin/bash /path/to/export-working-system.sh
```

The exporter waits for its reader, stops PaperDrop only during capture, excludes
private/volatile files before sending bytes, and restores the runtime on exit.
Do not install OS packages or change configuration during capture. The source
must already have the factory enrollment/setup helpers installed.

On the build host, create a private JSON file containing an SSH argument list,
with no password, for example `["ssh", "-i", "/private/path/key", "paperdrop@PI_IP"]`.
Then run from the repository:

```sh
sudo python3 scripts/build_working_pi_image.py \
  --ssh-command-file /private/path/ssh-command.json \
  --output artifacts/images/paperdrop-working-YYYYMMDD.img \
  --revision SOURCE_CODE_COMMIT
```

The builder refuses an existing output, creates an MBR/FAT/ext4 image, sanitizes
accounts and first-boot settings, verifies absence of private state, checks ARM
runtime imports, checks ext4 and clears freed filesystem blocks, and writes
`.img.xz`, `.sha256`, and build metadata sidecars.
Check `/run/paperdrop-image/result` on the source: `0` means successful export
and restoration. Confirm the normal runtime/server connection afterward.
Keep image binaries out of Git; attach them to a labeled preview release.
Do not move the managed firmware stable channel merely to distribute this image.
