"""Play installed assets through the production player without cloud/API calls.

Stop paperdrop-ws-agent before running; restart it afterward. Does not open a mic.
A successful process exit does not establish that the speaker was audible.
"""
import argparse
import asyncio
import base64
import json
import logging
from pathlib import Path
from voice_assistant import VoiceAssistant

CLIPS = ('voice-wake.pcm', 'voice-nathan.pcm', 'voice-scribble.pcm')


async def run(pcm, continuous):
    voice = VoiceAssistant(None)
    voice.play_task = asyncio.create_task(voice.playback(pcm))
    try:
        if continuous:
            audio = b''.join(Path(__file__).with_name(name).read_bytes() + b'\0' * 12000 for name in CLIPS)
            await voice.output.put(('continuous-wake-greeting-progress', base64.b64encode(audio).decode()))
            await voice.output.put(None)
            expected = 1
        else:
            for name in CLIPS:
                await voice.queue_clip(name)
            expected = 3
        async def completed():
            while voice.played_replies < expected:
                if voice.play_task.done():
                    await voice.play_task
                await asyncio.sleep(.1)
        await asyncio.wait_for(completed(), 40)
        print(json.dumps({'processCompletedClips': voice.played_replies, 'audibility': 'requires human confirmation', 'lastPlayback': voice.audio_diagnostics}))
    finally:
        voice.play_task.cancel()
        await asyncio.gather(voice.play_task, return_exceptions=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcm', required=True)
    parser.add_argument('--continuous', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args.pcm, args.continuous))
