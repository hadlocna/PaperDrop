# Update distribution review — 13 October 2026

GitHub main commits trigger application checks, not device release publication.
The currently published managed stable manifest was read from the production API:
version `2.1.3-20261004`, published 4 October 2026. No new firmware was published
or deployed during this review. The Düsseldorf Pi update timer remains disabled.

Managed devices use `agent/factory/paperdrop-update.timer`: first check 30 seconds
after boot, then every five minutes with up to 15 seconds randomized delay.
`agent/src/auto_update.py` reads `/uploads/stable.json` from the production API.
Only enabled timers consume this channel; offline devices can check after they
reconnect. The factory image enables this timer by default, but field devices may
have different settings or use the older agent.

Build a unique format-2 version with `scripts/build_managed_release.py`, including
the full required speech cache in all five languages. Upload with
`scripts/upload_managed_release.py`; upload alone does not publish. The admin
`POST /firmware/publish` endpoint explicitly selects the stable version after
checking the archive version, format, HTTPS origin and checksum. This is a global
channel, with no per-device pilot targeting in the manifest reader.

The updater checks SHA256, archive safety, free space and dependencies before
switching releases. It waits for an idle interface and uses an update lock. It
requires authenticated runtime health within roughly three minutes, then retains
the active and preceding release. Failed activation rolls back, with a six-hour
cooldown for the failed checksum. Interrupted activation also restores the prior
release on the next check. Health does not establish that every child interaction
works, so a complete package still needs hardware acceptance before publication.

There is also an older explicitly commanded OTA path in `ws_agent.py` and
`ota-update.sh`, reached by admin deploy/update endpoints. It is distinct from the
managed stable timer; do not assume those commands provide the same package layout
or rollback guarantees. Inventory each field device's runtime, version, timer and
connectivity before choosing a distribution path.

Recommendation: leave stable publication unchanged until a uniquely versioned
full package (including the recent upstream changes) passes a pilot installation,
recording, playback, notifications, deferred printing and rollback checks. Preserve
the current known-good stable manifest/package for recovery. Publishing the older
manifest can revert enabled managed devices because the updater compares version
equality, not semantic ordering; locally disabled timers need manual intervention.
No new SD image is required for compatible managed devices.

Latest UI adjustment was installed manually on the Düsseldorf Pi: printer icon for
incoming Print/Print Again and local picture Print, unread count on cousin portraits
and a closed envelope with `1` per unread item, open envelope without a count for
read items. All 87 staged tests passed and the rendered icons were inspected.
Live read envelopes have count zero and the live incoming action uses Printer.
