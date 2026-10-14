# PaperDrop runtime safety corrections

The October 14 release has two reproduced failure paths: a failed print
receipt callback can turn Retry into a second copy, and microphone readiness
failure leaves capture running. This patch preserves the completed print
attempt until receipt acknowledgement succeeds and cancels capture before
showing the readiness error. A retry waits for the old process and Pi WAV
writer to stop. Failed process or writer-thread launches remain retryable.

The patch changes six runtime/test files and this document. It does not change
the updater, dependency manifests, services, factory image, backend, frontend,
release publishing or deployment configuration. Existing receipt IDs and
additive mailbox schema remain compatible. Reverting does not undo recorded
mailbox state; take a state backup before a device pilot.

## Independent local validation

On the reviewed patch, 145 Python tests passed: 94 device fixtures, five
existing updater fixtures, and 46 other agent fixtures. All 68 backend tests
and 12 frontend tests passed; both application builds passed. Eight backend
HTTP tests and eight additional WiFi portal HTTP tests use review-only
in-memory transports because sockets are unavailable in the review sandbox.
Two drawing integration cases use JSON standard input/output in place of
WebSockets. Three independent failure/behavior checks pass, including the
original duplicate-copy and capture-timeout reproductions. These are fixture
results, not native Pi, audio, physical-print or network-transport acceptance.

The release package checksum, 127 comparable source files, format-2 layout
and all 515 required offline speech clips were independently verified before
these changes. The package candidate must be rebuilt from the reviewed head,
given its own checksum, and tested as a complete package before publication.

## Updater work is separate

The expanded updater proposal is excluded from this patch. Independent review
found that its synthetic first-frame render misses actual portrait/location
assets, rollback does not establish local runtime readiness, optional cleanup
can roll back a healthy release, and recovery can interrupt active work.
Existing devices also run their old independent helper during their first
update. Packaging a new helper alone cannot protect that activation. The
proposal needs revision and a native disposable-image pilot before any claim
of fleet recovery safety. The cause of previous bricking is not established.

## Conditions before main or activation

Review this exact diff and confirm remote deployment settings before pushing
or merging. The checked-in CI workflow tests/builds; stable publication is a
separate authenticated action. Render settings for the existing services have
not been independently inspected. Agent-only changes are outside the declared
backend/frontend root directories, but that does not establish all live
automation settings.

Before activation, name one non-production spare Pi or disposable cloned SD
image. Keep the global stable manifest unchanged. Inventory its current
version, runtime layout, helper version, Python, available disk and service
configuration. Preserve a boot-tested old image, code/dependencies, SQLite,
receipts and configuration. Verify manual offline restoration before testing
full-package installation, reboot and interrupted activation. Synthetic capture
may be used only in the explicitly authorized isolated environment; real
household audio and physical printing require separate scope. Production
households, stable publication and fleet rollout remain outside this review.
