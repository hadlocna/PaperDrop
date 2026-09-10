# PaperDrop audio troubleshooting

Do not treat an `aplay` exit code or reply counter as evidence that sound was audible.

The agent logs named clips at queue, Bluetooth open, write, and process completion. `voice_result.audioDiagnostics` exposes the latest clip, stage, PCM route, byte count, duration, elapsed time, and error. Request capture logs duration and speech duration, followed by transcription and print completion markers. Microphone audio and prompt text are not included in these new diagnostics.

For an isolated local test, stop `paperdrop-ws-agent`, run `/opt/paperdrop/venv/bin/python /opt/paperdrop/voice_audio_test.py --pcm '<verified ALSA PCM>'`, and always restart the service afterward. Use a shell EXIT trap for restoration. The test plays the installed wake, greeting, and progress assets using the production player, without opening the microphone or making API calls. `--continuous` joins the clips in one stream to compare output reopening. Obtain human confirmation of each sound before changing transport behavior.

On 2026-09-10 the three supplied files had valid nonzero audio and the device player completed each with exit 0. Audibility remains unconfirmed. Separately, the Pi kernel logged USB over-current changes followed by printer disconnection; `lsusb` showed only root hubs. The preceding image job failed with USB printer not found. Restore USB detection before spending more image calls on an end-to-end print test.

The diagnostic patch was installed only on Alma and Theodore using SSH with `/opt/paperdrop/voice_assistant.py.pre-diagnostics` as a backup. This was an application-file patch on firmware 1.3.9, not a fleet OTA or cloud release. The service was restarted and must be checked independently from audio and physical print acceptance.
