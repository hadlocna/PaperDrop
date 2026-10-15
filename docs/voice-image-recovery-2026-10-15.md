# Recorded drawing connection recovery

## Observed failure

Alma and Theodore (`PD-883bfd8f`) was running managed runtime
`2.1.3-20261004`. On 15 October, the device recorded 15-second requests at
18:06 and 18:10 in its local log, then reported `PaperDrop backend is unavailable`
or `Backend connection interrupted`. The same period includes WebSocket
keepalive timeouts and DNS lookup errors. NetworkManager logs show association
changes between the router's 2.4 GHz and 5 GHz radios and DHCP restarts.
This establishes connection loss as the failure in those attempts; it does not
establish the cause of the router/radio instability.

A separate live image request succeeded using the existing local credential
and the unchanged `gpt-image-2.5-flare` settings. No model or key replacement
was needed.

## Recovery behavior

The Pi now waits up to 45 seconds for connectivity before uploading a completed
recording. Updated button clients negotiate resumable sessions. A transient
disconnect preserves the backend's existing request for its original three-minute
deadline, rather than aborting transcription or generation immediately.

After reconnecting, the Pi resumes the same session ID. The backend acknowledges
whether audio is still needed, whether work is in progress, or replays the completed
picture with its original message ID. The Pi only uploads again when an idle
acknowledgement proves generation has not started. Completed pictures still go
to preview and require the child's print confirmation.

The client waits at most 155 seconds after its first session start. Explicit Stop
still cancels; legacy clients retain their previous disconnect behavior. Expired
sessions and backend restarts require an explicit retry instead of silently
starting another paid request. Ownership is rechecked before resuming or delivering.
Sessions and completed results remain in memory only, within the existing deadline.

## Validation

- Backend TypeScript build and all 73 backend tests passed.
- All 100 Stream Deck tests passed, including real local WebSocket exchanges
  with the compiled backend. Disconnects before upload, during transcription,
  and during image completion all recovered; a second drawing and explicit
  print-review flow completed without duplicate generation or print jobs.
- Expiring the backend session during a disconnect produced a retry error and
  no second paid request.
- A live recorded-request test used the bundled example WAV, real transcription,
  moderation and image generation, and fixture device/database boundaries.
  Disconnecting after transcription still replayed one valid PNG after reconnect:
  one transcription, one image request, one message; 17.5 seconds total.
  No physical print was sent by this test.

## Installation

Both the cloud backend and managed device runtime must contain this change for
automatic resume. The device package is `2.2.1-20261015`, built with the verified
515-clip speech pack from `v2.2.0-20261014`.

Pushing main does not install device firmware. The existing stable manifest was
still `2.1.3-20261004` during diagnosis. Stable publication offers the update to
all compatible managed devices with update timers enabled. Do not describe the
Lisbon device as updated until its reported version and fresh authenticated
heartbeat confirm installation. Physical microphone-to-preview and paper output
remain separate acceptance checks.
