# Per-child recording time

Installed and tested on Ale's Pi on 12 October 2026; server deployment follows the approved push.

Personal screen: clock / Choose time replaces the direct language button.
Clock screen: 10s, 15s, 30s, 60s, language, Back. Selecting a duration saves it
for that child and returns to their personal screen. Existing language choices
remain available. Default recording time is 30 seconds; drawing without a
selected child also uses 30 seconds. Tap to start and tap red Done to stop,
or wait for the automatic stop. Existing hold/release interaction is retained.

The selection controls countdown, completion timer and microphone capture.
Both drawing requests and voice notes use it. Playback permits complete notes
up to 60 seconds rather than stopping at the former 30-second playback timeout.
The new preferences have a separate SQLite table, preserving existing language,
mail and reward data. Updated receiving firmware accepts 60-second voice mail.

Ten offline prompts were built and validated on the Pi by joining the existing
Marin recording instructions with its already-recorded red-button stop instruction,
in English, French, German, Italian and European Portuguese. No microphone or
device credential was used to author these clips. The optional TTS generator also
supports authoring just these prompts, but no fresh API recordings were generated.

Validation: 71 isolated Pi tests passed, excluding the drawing test that requires
a local Node backend fixture unavailable on the Pi. TypeScript compilation and
all 66 backend tests passed, plus an added full-minute drawing test passed in the
ten-test recorded-voice suite, including a 60-second offline voice queue regression
and rejection of recordings exceeding that duration. Child preference persistence,
each timer duration, countdown, automatic stop and stale timeout callbacks are
covered. Live microphone, physical buttons and physical printing need acceptance
after activation. Live companion actions on the installed runtime verified all
four choices, persistence, child isolation, language navigation and return Home.
Rendered menus were visually checked in all five languages and fit six keys.
An installed-controller probe exercised the actual default 30-second timer,
production backend generation, review/preview and simulated print completion.
Normal runtime was restored and reauthenticated. It did not use the physical
microphone or emit paper; the owner's physical acceptance remains separate.

Staging on the Pi: `/tmp/paperdrop-recording-timer`; running installation was
updated at 19:02 CEST. Original files are retained at
`/var/lib/paperdrop/maintenance/recording-timer-20261012-190222`.
The staged `install.sh` is reproduced in `scripts/install_recording_timer.sh`.
It requires root and an idle Home/personal screen, saves original code, installs
only six application files and ten speech clips, and restarts the runtime. On
installation/startup error it restores original code. It does not change automatic
update settings, firmware manifests or release version. A maintenance backup is
retained under `/var/lib/paperdrop/maintenance`.

Deploy backend changes before activation: old drawing upload limits reject long
recordings, and old family-mail validation rejects voice notes over 20 seconds.
Receiving stations also need the receiving/playback changes for longer mail;
they must not be updated without owner authorization. Their old code otherwise
retains rejected queued envelopes but cannot consume them. Roll out compatible
recipient software before using longer voice messages to those houses.

Owner approved server deployment, installation, and committing/pushing after
device tests. Pi authentication succeeded through the local SSH installer.
Automatic updates remain disabled/inactive; the stable manifest and firmware
version label are unchanged. No new Pi image is requested for this change.
