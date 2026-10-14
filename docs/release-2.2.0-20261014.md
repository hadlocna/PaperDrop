# PaperDrop 2.2.0 release handoff

GitHub release: https://github.com/hadlocna/PaperDrop/releases/tag/v2.2.0-20261014

Source: `e96423454a5d2a12a86be24741c3837f84796204`.
Package: `paperdrop-2.2.0-20261014.tar.gz` (94,744,752 bytes).
SHA256: `cd896971e70a519229001f7e67932b6252d80568d4ae7394d952e0a12c3303e2`.
Format: 2, managed runtime. All 515 required speech clips are included.

Improvements: per-child 10/15/30/60-second recording limits, revised personal menu,
cousin inbox with unread envelopes and counters, buffered incoming pictures with
manual Print/Print Again, localized mail notifications, voice pause/resume/stop,
media-specific replies, persistent read states and safe print retry identities.

The user's Düsseldorf Pi has these application changes installed and accepted.
CI passed on the release source, as did 87 isolated device tests and five updater
tests. The complete package's automatic activation has not yet been tested.

## Administrator publication

1. Download the archive from the GitHub release and verify its SHA256.
2. Review and pilot-test the complete package, including dependency installation,
   microphone, speaker, Stream Deck, mail buffering/printing and rollback.
3. With `PAPERDROP_ADMIN_PASSWORD` set securely in the local environment, run
   `python scripts/upload_managed_release.py <archive>`. This registers the package
   in production firmware storage but does not distribute it.
4. Publish using `POST https://api.paperdrop.me/api/admin/firmware/publish`, header
   `x-admin-password` containing the admin credential, and JSON body
   `{"version":"2.2.0-20261014","format":2}`. Preserve the existing stable manifest
   and package before publication. Do not expose credentials in shell history.
5. Read `https://api.paperdrop.me/uploads/stable.json` and verify the version,
   checksum and actual uploaded URL. The manifest attached on GitHub is build
   metadata; the administrator's publication selects the actual storage URL.
6. Monitor installations and device health; the stable channel applies globally
   to compatible managed devices with their update timer enabled. Legacy devices
   use a separate OTA path and require compatibility review.

The managed timer checks 30 seconds after boot and approximately every five
minutes thereafter. It defers during active interactions, checks archive integrity,
installs into a separate release directory and switches after preparation.
Failed authenticated health rolls back to the preceding runtime. Offline devices
retry after connectivity returns. Uploading to GitHub or pushing main alone does
not trigger installation; explicit stable-manifest publication does.

The Düsseldorf Pi timer was enabled on 14 October 2026. Its first check deferred
with a network URLError, and the next check was scheduled normally. Existing
working application code stayed in place. No production stable release was
published because the user does not have administrator access.
