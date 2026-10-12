"""Reuse the existing Marin voice pack to add stop instructions in five languages."""
import argparse
import hashlib
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent' / 'streamdeck'))
from audio_cues import combine
from languages import DRAW_PROMPT, TALK_PROMPT, LANGUAGES, STOP_GUIDANCE, translate


def build(source, output):
    clips = []
    for language in LANGUAGES:
        for prompt in (DRAW_PROMPT, TALK_PROMPT):
            original = prompt.removesuffix(' ' + STOP_GUIDANCE['en'])
            texts = (translate(original, language), STOP_GUIDANCE[language])
            inputs = [source / (hashlib.sha256(text.encode()).hexdigest() + '.wav') for text in texts]
            destination = output / (hashlib.sha256(translate(prompt, language).encode()).hexdigest() + '.wav')
            combine(inputs, destination)
            with wave.open(str(destination)) as wav:
                duration = wav.getnframes() / wav.getframerate()
                if not 0 < duration < 30:
                    raise ValueError('Guidance exceeds startup playback limit')
            clips.append(destination.name)
    print('Validated recording guidance:', len(clips), 'clips in five languages')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
