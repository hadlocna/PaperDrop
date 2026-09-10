# PaperDrop OTA acceptance — 2026-09-10

## Repository and existing work

Fast-forwarded main from 96e17c5 to 95ebe05b1cb821ece7d8d31b3b418c849f3c7356 (image dithering filters). HEAD matches origin/main. Preserved all pre-existing tracked modifications and untracked files.

The repository already contains cloud OTA commands, firmware upload/deploy routes, device diagnostics, and agent update handling. Existing uncommitted laptop changes add a separate systemd OTA process, rollback handling, installer/provisioning fixes, firmware checksum calculation, and admin UI changes. The connected device already matched the local ws_agent.py and ota-update.sh before testing.

## Device repair

Target: PD-883bfd8f, paperdrop-fd8f.lan, Epson TM-T20III USB printer. The cloud record is named Alma and Theodore. Initially the agent repeatedly disconnected with code 4003, secret mismatch. Restored the existing registered cloud credential on this device and restarted its agent. Ownership and device code were preserved. The previous device configuration is backed up on the device at /etc/paperdrop/device.json.pre-ota-repair; do not copy its contents into reports.

## Live acceptance evidence

- Built firmware from the existing local agent/src tree with scripts/build_firmware_release.py.
- Version: 1.1.0-ota.20260910.
- Archive SHA256: de7aa0a387be00e208db30bd6be6cae140fb9742590fb82e6e627d07681aa631.
- Uploaded through the production firmware API; release ID 9c01c701-5a1c-474e-a228-83ec26bbcb8d.
- Sent update through the production device update API to this device only; accepted request fa2db47e-3497-4ac2-b918-0dba5488cb14.
- Device verified SHA256, restarted its agent, and completed OTA successfully at 09:32:09 UTC. The separate systemd OTA unit exited successfully.
- Production API reports the device online with version 1.1.0-ota.20260910 after restart and subsequent heartbeats.
- Sent a bordered smiley-face raster image through the production messages endpoint using a short-lived owner token generated inside the backend. No token was exported or saved.
- Print job 98302408-5dd7-49fd-8f2e-b7aff5356a8d reached the device, was resized to 576x300, and completed successfully. The production database stores status printed and printedAt 2026-09-10T09:32:50.275Z.
- A subsequent cloud printer_status command succeeded and detected the Epson printer.

## Checks and limits

Frontend and backend production builds pass. bash -n agent/src/ota-update.sh and git diff --check pass. The user confirmed the smiley-face image printed clearly and works great.

This proves a successful OTA and cloud image print on the connected device. It does not validate failure rollback, interrupted downloads, BLE onboarding, the other fleet devices, or the latest image-filter UI in production. No fleet-wide deployment was performed. The tested firmware includes pre-existing uncommitted local changes; it is not reproduced by checking out origin/main alone. No commits or pushes were made during this run.

## Standalone device update and image-model migration

The user confirmed the device was unplugged from the laptop and running on its own power and Wi-Fi before this test. All subsequent OTA and print operations used the production cloud API, without SSH.

- Added the installed firmware version to diagnostic test receipts.
- Release: 1.1.1-ota.20260910, ID 0af235b2-8065-413b-a7b7-9cbbc4ed3132.
- Package SHA256: 1441aee498ed74771804e485515b0c9e35bef9a5a57de3e403a4948e0c1eecb1.
- Cloud OTA request 68eb8e87-6ea5-4391-9b06-560ee2ba5b20 was accepted.
- Device returned online with firmware 1.1.1-ota.20260910 and a fresh heartbeat at 09:38:02 UTC.
- Cloud test-print request 47e2a386-e811-41c8-b5de-b817085de3af returned ok=true.

Image generation migrated from dall-e-3 to gpt-image-2.5-flare, using medium quality, opaque PNG output, and the existing base64 response contract. GPT-4o prompt preparation is unchanged. Official model and parameter reference: https://developers.openai.com/api/docs/guides/image-generation . Production model lookup succeeded. A direct production-account generation returned a valid 845278-byte PNG in 13.093 seconds.

Commit b965a7519f944c184e728487969b05cdb02bca5c contains only this turn's model migration and firmware-receipt line. HEAD, origin/main, and git ls-remote matched after push. The earlier uncommitted work remains separate. Backend build, Python syntax parsing, and diff whitespace checks passed. Coolify deployment jgos04w8w0wwcgwsogcck8g0 was triggered by the push; application endpoint acceptance is pending below.

## Bluetooth speaker follow-up

Later work supersedes the initial no-commit and cloud-only statements above: Bluetooth diagnostics used SSH over Wi-Fi, while firmware installation continued through cloud OTA. Commit e34f2d2 added speaker and explicit five-second local microphone test controls. The live app generated output/images/theodore-lizard.png using Flare. A short-lived owner token was temporarily stored locally for API validation.

SoundCore 2 paired and bonded successfully after temporarily enabling Pairable during outgoing pairing, restoring its previous value afterward. The user reported a silent greeting and later confirmed hearing the test beep. Both hands-free and A2DP profiles were initially active; disconnecting hands-free left A2DP available. Firmware 1.2.3 explicitly selects A2DP for playback and restores it after microphone testing, and replaces the beep with a soft four-note chime. Cloud reports firmware 1.2.3 online. Its package SHA256 is 1f4bad7d7a26924686ac0338fa8cbe49b65ba23cb5ce72a17836370deb994355.

Eight agent tests and six speaker API tests pass. Physical confirmation of the full greeting and new chime remains pending. Microphone recording has not been physically validated. Lizard message cd971e5a-68ed-4056-bb7c-ef35f101ae3e remains unsent to the printer after an initial WebSocket size failure; the agent now accepts frames up to 16 MiB. Replay that same message only after audible greeting confirmation, avoiding duplicate creation.
