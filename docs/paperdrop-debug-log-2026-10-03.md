# PaperDrop Troubleshooting Log - 2026-10-03

## Latest Validated Results - 2026-10-09

- On October 8, the live software probe passed the production Stream Deck button/controller path: synthetic recording, real 15-second timer, backend transcription, moderation/image generation, review, preview/return, and simulated print submission. The backend transcribed the rocket prompt correctly; generation returned in about 14 seconds.
- A separate forced WebSocket disconnect test reauthenticated automatically. Normal runtime was restored afterward with `cloud_connected: true` and `device_connected: true`. These results validate the current release, not the original image's historical outage cause.
- Physical printing was intentionally skipped. The synthetic server message was marked failed with an explicit software-test explanation rather than falsely acknowledging a real print. No other household received a test message.
- Found and fixed locally a backend false-offline defect: stale relay activity could override a fresh local heartbeat. List/detail endpoints and displayed timestamps now choose the freshest valid activity. This is a confirmed code defect, but server deployment logs are needed to determine whether it caused the reported all-device outage.
- Backend build and all 65 backend tests passed, including new list/detail regression tests. Two firmware-upload tests initially failed under sandbox filesystem restrictions; all tests passed outside those restrictions. Previously, 41 Pi/controller tests passed on the device.
- Reusable probe: `scripts/check_streamdeck_workflow.py`. It substitutes prerecorded input and simulated printing, exercises the deployed backend, and restores the regular runtime. `--connection-only` tests recovery without image generation. Private fixtures/recovery files and screenshots are excluded from Git.
- On October 9, SSH did not respond at the previous Wi-Fi or direct Ethernet addresses. Remote main remained unchanged at `e0a8ad9`. Hold deployment-triggering pushes until management access is restored; the previous tests do not prove present connectivity.
- Still open: intermittent physical/network reachability, initial USB hot-plug enumeration failure, actual hardware printing/drawing acceptance, and server-side confirmation of the all-offline incident. Bluetooth and microphone playback are deferred at the user's request. Automatic firmware updates were disabled on the Pi.

## Clean OS Reinstallation Check - 2026-10-08

### Installation Progress

- Console logs showed repeated Ethernet DHCP activation failures on the direct laptop cable and Wi-Fi association/credential retries. `throttled=0x0` showed no recorded undervoltage/throttling flags.
- A separate `laptop-direct` NetworkManager profile with IPv4 disabled and IPv6 link-local enabled provided SSH access; its IPv6 address changed after activation, so rediscovery was necessary.
- SSH public-key access is confirmed. Pi runs 64-bit Debian 13 / Python 3.13; privileged installation and outbound HTTPS work.
- Installed checksum-verified published managed release `2.1.3-20261004`, its Python dependencies, system dependencies, managed service units, and BlueALSA configuration. Python imports, compilation, dependency consistency, and systemd unit checks passed.
- Confirmed release includes microphone signal validation, Bluetooth playback padding, and Stream Deck recording diagnostics. System-Python speaker status reports Bluetooth powered and audio ready. The helper intentionally uses system Python for the OS-provided D-Bus module.
- Added the SSH user to the audio group; new login sessions receive access.
- Recovery enrollment returned HTTP 403. Backend defines this as invalid/expired recovery; a fresh owner-issued recovery file is needed. Runtime and update timer remain inactive pending identity restoration.
- Printer, USB microphone, and Stream Deck are currently disconnected, so physical function checks remain pending.
- Updated recovery file redeemed successfully; restored Ale's existing device `PD-780420ea` without creating a new account/device.
- Enabled enrollment/runtime services and automatic-update timer. Runtime authenticated to the backend, exchanged device hello/heartbeat, and wrote a healthy marker for release `2.1.3-20261004`.
- Current mode is ordinary printer runtime because the Stream Deck is disconnected. Printer, microphone, speaker pairing, and Stream Deck drawing acceptance tests remain pending reconnection.
- User reports all devices shown offline after a friend's deployment. Direct Wi-Fi SSH still works; Ale's runtime remains on `2.1.3-20261004`, authenticated and sending 30-second heartbeats. This does not establish that the server persists those heartbeats or that the browser uses the same backend.
- Temporarily stopped `paperdrop-update.timer` before further deployment checks; no update service was active. Timer remains enabled for boot, so this pause ends on reboot unless changed. No code or firmware deployment performed.
- Remote main still matches `e0a8ad9`. Investigate deployed frontend API target, backend heartbeat/database errors, and relay configuration before attributing the all-offline display to Pi firmware.
- After peripherals were reattached, Linux initially still detected only the keyboard receiver. One controlled reboot recovered enumeration of Epson TM-T20III, KTMicro microphone, and Stream Deck Mini. No undervoltage/throttling flags were recorded; the reason hot-plug enumeration failed is not yet established.
- Disabled automatic-update timer across reboots during investigation. PaperDrop started after the network-online wait, selected Stream Deck mode, opened all six keys, detected the printer, and reported `cloud_connected: true` and `device_connected: true` in its local companion state.
- Direct two-second USB microphone capture succeeded. Companion key rendering returned a valid 240x240 PNG. Ran 41 isolated Pi/controller tests against installed release code: all passed, with test-resource warnings about unclosed SQLite connections.
- Bluetooth pairing/playback, audible microphone-test playback, real paper output, and complete recorded drawing generation remain unvalidated on this clean installation. Startup logged `speaker_cue_unavailable` because no speaker is selected yet.
- Reboot cleared the previous sudo authorization cache: further privileged operations now need an interactive password. SSH and unprivileged diagnostics continue working.

- User installed a clean Raspberry Pi OS image with password SSH enabled.
- Refreshed remote Git references: local `main` matches `origin/main` at `e0a8ad9`; troubleshooting commit `73bffeb` is an ancestor of remote main.
- Previous Pi address `192.168.3.247` timed out on SSH. A TCP port-22 sweep of `192.168.3.1` through `.254` found no accepting SSH endpoint. The default `raspberrypi.local` hostname did not resolve.
- At the initial discovery check, installation was pending access. The later installation and successful enrollment are recorded above.
- Use the managed runtime dependencies and units under `agent/factory` for installation; the root-level `install_paperdrop.sh` sets up an older printer-only service.

## Original Summary

This is a concise, shareable log of the troubleshooting performed on Ale's PaperDrop Raspberry Pi. It intentionally omits private keys, passwords, device secrets, enrollment-token contents, and full raw logs.

## Initial Symptoms

- The PaperDrop device appeared online in the app.
- Printing from the app failed.
- Bluetooth speaker setup showed no speakers, even while nearby Bluetooth speakers were in pairing mode.
- Downloading Agent, System, and Wi-Fi logs from the app failed.
- SSH initially failed because the supplied factory image did not expose working SSH access.

## Hardware Isolation

- A clean Raspberry Pi OS image was flashed and booted successfully after resolving SD-card seating and HDMI adapter issues.
- The clean image confirmed that the Raspberry Pi, SD card, HDMI output, network access, and SSH path were basically functional.
- This made a hardware-only failure less likely and shifted focus back to the PaperDrop factory image and runtime configuration.

## Factory Image Debug Access

- The supplied PaperDrop factory image was copied to a clean Raspberry Pi OS system and modified as a disk image.
- Controlled SSH debug access was added:
  - created a `paperdrop` Linux user;
  - installed SSH public-key login for that user;
  - generated fresh SSH host keys;
  - enabled `ssh.service` at boot;
  - disabled SSH password login and root SSH login.
- The PaperDrop application/runtime code was not modified.
- The personalized image was recompressed, copied back to Windows, verified by checksum, flashed, and booted.

## Findings After SSH Into PaperDrop Image

- `paperdrop-runtime.service` is running.
- The image updated itself to managed release `2.1.2-20260930-b8a344f46c56`.
- USB detects the expected attached devices:
  - Epson TM-T20III printer;
  - KTMicro USB microphone;
  - Elgato Stream Deck Mini.
- Because the Stream Deck is attached, the runtime selected Stream Deck/button mode.
- The printer is detected repeatedly in service logs.
- Bluetooth service and BlueALSA are running, but no paired or connected speaker is visible.
- App log download likely fails because Stream Deck mode does not appear to expose the same legacy `fetch_logs` path as the ordinary printer agent.

## Current Working Hypotheses

- Printing may be a mode/behavior mismatch: with the Stream Deck connected, the device runs the Stream Deck runtime, which does not appear to automatically print ordinary incoming app messages the same way the legacy printer agent does.
- The speaker issue is still open: Bluetooth is powered, but the app scan finds no pairing-mode speakers. Next diagnostics should focus on `speaker_manager.py`, BlueZ scan behavior, adapter pairable/discovering state, and backend/app speaker command events.
- Log download is likely a software/API mismatch in Stream Deck mode: the ordinary `ws_agent.py` handles `fetch_logs`, while the Stream Deck cloud path handles speaker/update/test events but does not appear to handle the same log-fetch request.

## Follow-Up Findings

- A longer direct `bluetoothctl` scan found `SoundCore 2`.
- PaperDrop's own speaker scanner then reported the speaker as an audio device.
- PaperDrop's Python speaker helper failed during its `connect` flow with `org.bluez.Error.InvalidArguments`.
- Manual `bluetoothctl trust` and `bluetoothctl connect` succeeded.
- Direct BlueALSA playback as root succeeded, confirming the Pi can output audio to the speaker.
- `/etc/paperdrop/speaker.json` was written manually to select the SoundCore speaker, and the app then showed it as connected.
- Two ordinary app-sent image messages reached the Pi, but Stream Deck mode saved them under `/var/lib/paperdrop/streamdeck/pending-cloud-mail/` instead of printing them.
- `/etc/paperdrop/mode` is `auto`; because the Stream Deck is attached, `runtime.py` selects the Stream Deck runtime instead of the ordinary `ws_agent.py` printer runtime.
- Forcing `/etc/paperdrop/mode` to `printer` and restarting `paperdrop-runtime.service` switched the runtime to `src/ws_agent.py`.
- In forced printer mode, app log download reached the Pi as `fetch_logs` and was handled by `ws_agent.py`.
- In forced printer mode, a normal app-sent image arrived as `new_message`, printed successfully on the Epson printer, and reported `printed` status.
- The app UI confirmed this: log download completed, and the Activity feed showed the message status as `Printed`.

## Recommended Fixes

- Add `fetch_logs` support to the Stream Deck runtime path, or route log-download requests to a shared handler used by both `ws_agent.py` and `streamdeck/pi_cloud.py`.
- Decide expected behavior for app-sent ordinary messages while in Stream Deck/button mode:
  - either document that they are staged but not auto-printed;
  - or add an explicit print path/status response for normal app messages in Stream Deck mode.
- For a quick isolation test, temporarily force ordinary printer mode by writing `printer` to `/etc/paperdrop/mode` and restarting `paperdrop-runtime.service`; this should run `ws_agent.py`, which supports ordinary printing and log download. Revert to `auto` afterward to restore Stream Deck/button behavior.
- The isolation test confirmed ordinary printer mode works for both app log download and app-to-printer image printing. The durable fix should bring equivalent support into Stream Deck mode, or make the product explicitly choose between printer mode and button mode.
- Fix the Bluetooth speaker helper so app-based connect works without manual `bluetoothctl` fallback. The likely area is the direct BlueZ `ConnectProfile`/profile-management flow in `speaker_manager.py`; manual BlueZ connection and BlueALSA playback both work.
- Improve speaker scan reliability by allowing longer discovery or returning named candidate devices once BlueZ resolves them, since a short scan initially returned no audio devices while a longer scan found `SoundCore 2`.

## Repository Fix Drafted

- A dedicated branch, `ale-troubleshooting`, was created for the troubleshooting fixes.
- Stream Deck/auto mode was updated to handle app log downloads with a `fetch_logs` response path.
- Stream Deck/auto mode was updated so ordinary app-sent image messages can print through the guarded Pi printer path instead of only being staged as pending cloud mail.
- Stream Deck speaker command handling was expanded to include the same app actions as the ordinary printer agent, including `microphone_test` and `play`.
- Bluetooth speaker connection logic was changed to prefer generic BlueZ device connect behavior, with a `bluetoothctl connect` fallback, instead of relying on profile-specific `ConnectProfile`/`DisconnectProfile` calls that triggered `org.bluez.Error.InvalidArguments`.
- Stream Deck microphone capture was changed to auto-detect the actual ALSA USB microphone card. On Ale's Pi the card is `Microphone`, while the previous default expected `Device`.
- The app microphone test was changed to fall back to the PaperDrop USB microphone when Bluetooth HFP microphone capture is unavailable, then play the recording through the selected Bluetooth speaker.
- Microphone-test errors in the settings UI were moved beside the microphone-test button instead of appearing near the top of the speaker section.
- Stream Deck drawing failures now preserve and log the backend error message instead of only showing a generic failure.
- Backend recorded voice handling was updated so Stream Deck button-initiated recorded drawing can proceed even when wake-phrase listening is off. Wake-phrase/live voice remains gated by `voiceEnabled`.
- Local focused tests cover the new Stream Deck print/log/speaker command behavior and the safer Bluetooth connect behavior.

## Current Status After Remote Testing

- Confirmed fixed on Ale's Pi:
  - auto mode selects Stream Deck mode when the Stream Deck is attached;
  - ordinary app messages print in Stream Deck mode;
  - app Agent/System/Wi-Fi log downloads work;
  - Epson printer, Stream Deck Mini, SoundCore speaker, and USB microphone are detected;
  - SoundCore scan/connect/status/test sound works;
  - PaperDrop USB microphone recording works;
  - app microphone test returns success using the PaperDrop USB microphone fallback.
- Still open:
  - Stream Deck voice drawing reaches recording and generation, but the deployed backend returns `Voice listening is unavailable.`;
  - the backend fix for button-initiated recorded drawing is in branch `ale-troubleshooting`, but must be built and deployed to the server before the Pi can use it;
  - app microphone test reports success, but user hears only a short burst instead of the recorded voice, so capture level and Bluetooth playback formatting still need direct validation;
  - local backend build/test could not be run in this Windows workspace because `npm` failed fetching Prisma with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`.
- Additional microphone-test fix drafted:
  - A2DP microphone-test playback now adds the same short silence lead-in and tail used by Stream Deck media playback, because some Bluetooth speakers wake late and clip the beginning of short recordings.
  - Microphone-test recording now checks RMS/peak levels after capture and reports a clearer failure if ALSA produced only silence or a very low signal.
  - A direct Pi-side microphone probe was added at `scripts/paperdrop_mic_check.py`; it records a WAV, reports RMS/peak levels, saves the raw and normalized files under `/tmp`, and can play the normalized WAV through the selected Bluetooth speaker.
- Additional microphone access finding:
  - The KTMicro USB microphone is present in `/proc/asound/cards` and `lsusb`.
  - The SSH debug user `paperdrop` is not in the Linux `audio` group, while `/dev/snd/*` is owned by `root:audio`.
  - Therefore direct interactive `arecord` over SSH fails without `sudo`, even though the PaperDrop runtime can still access audio when run with service privileges.
  - For manual interactive validation, run the diagnostic with `sudo python3 /tmp/paperdrop_mic_check.py --seconds 5` or add the debug user to the `audio` group and start a new login session.
  - The direct diagnostic recording/playback was later confirmed to work, which proves the USB microphone, ALSA capture path, Bluetooth speaker, and BlueALSA playback path are basically functional.
- Additional Stream Deck drawing diagnostics drafted:
  - Stream Deck Pi recording now logs `mic_recording_finished` with duration, RMS, peak, and byte count after every captured prompt.
  - Too-short or too-quiet Stream Deck recordings now raise an error with a user-facing message instead of a generic failure.
  - Recording startup failures now preserve the concrete exception message in the Stream Deck error hint and log `recording_start_failed`.
  - Backend recorded drawing now logs start/request failures on the server side, so a server operator can distinguish configuration, transcription, moderation, image generation, and database/delivery failures.
- Deployment note:
  - The live Pi is running managed release `2.1.2-20260930-b8a344f46c56` as `root` from `/opt/paperdrop/releases/...`.
  - The SSH debug user cannot read or update that release tree without `sudo`, so code fixes in this branch must be deployed through the normal update pipeline or installed with a privileged hotfix/restart on the Pi.
- Manual follow-up:
  - after backend deployment, retry Stream Deck voice drawing without enabling wake-phrase listening;
  - verify the app microphone test is audible enough in the room, since the Pi can confirm command success but not human audibility;
  - if playback is still only a burst, retrieve `/tmp/paperdrop-mic-check.wav` from the Pi and inspect whether the recording itself contains speech.

## Next Diagnostic Steps

- Watch runtime logs while triggering app actions:

  ```sh
  journalctl -u paperdrop-runtime.service -f
  ```

- In the app, try:
  - refreshing speaker scan;
  - downloading Agent/System/Wi-Fi logs;
  - sending one print/message.

- Run direct speaker diagnostics over SSH:

  ```sh
  bluetoothctl scan on
  bluetoothctl devices
  /opt/paperdrop/current/venv/bin/python /opt/paperdrop/current/src/speaker_manager.py scan
  ```

- Compare app-request behavior with code:
  - confirm whether Stream Deck mode receives `fetch_logs` requests and ignores them;
  - confirm whether speaker scan commands reach `pi_cloud.py`;
  - confirm whether ordinary messages are saved under Stream Deck pending-mail folders instead of printed.

- Decide whether to fix runtime behavior, force ordinary printer mode for testing, or add missing log/speaker handlers to Stream Deck mode.
