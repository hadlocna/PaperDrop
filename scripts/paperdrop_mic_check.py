#!/usr/bin/env python3
"""Record from PaperDrop's microphone, measure levels, and optionally play it back."""
import argparse
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave


def capture_pcm():
    configured = os.environ.get('PAPERDROP_CAPTURE_PCM')
    if configured:
        return configured
    try:
        cards = Path('/proc/asound/cards').read_text(errors='ignore')
    except OSError:
        cards = ''
    for card in ('Microphone', 'Device'):
        if f'[{card}' in cards:
            return f'plughw:CARD={card},DEV=0'
    return 'default'


def read_samples(path):
    with wave.open(str(path), 'rb') as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.getnframes()
        data = wav.readframes(frames)
    if width != 2:
        raise RuntimeError(f'Unsupported sample width: {width}')
    samples = []
    step = 2 * channels
    for index in range(0, len(data), step):
        left = struct.unpack_from('<h', data, index)[0]
        if channels == 2 and index + 3 < len(data):
            right = struct.unpack_from('<h', data, index + 2)[0]
            samples.append((left + right) // 2)
        else:
            samples.append(left)
    return channels, rate, frames, samples


def level_stats(samples):
    if not samples:
        return {'rms': 0, 'peak': 0, 'rmsPercent': 0, 'peakPercent': 0}
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    peak = max(abs(sample) for sample in samples)
    return {
        'rms': round(rms, 1),
        'peak': peak,
        'rmsPercent': round(100 * rms / 32768, 2),
        'peakPercent': round(100 * peak / 32768, 2),
    }


def normalize_for_a2dp(source, target):
    _, rate, _, samples = read_samples(source)
    if rate != 44100 and samples:
        output_length = max(1, round(len(samples) * 44100 / rate))
        resampled = []
        for out_index in range(output_length):
            position = out_index * (len(samples) - 1) / max(1, output_length - 1)
            low = int(position)
            high = min(low + 1, len(samples) - 1)
            fraction = position - low
            resampled.append(round(samples[low] * (1 - fraction) + samples[high] * fraction))
        samples = resampled
    data = bytearray()
    for sample in samples:
        packed = struct.pack('<h', max(-32768, min(32767, int(sample))))
        data.extend(packed)
        data.extend(packed)
    lead_in = b'\0' * int(44100 * 0.4 * 4)
    tail = b'\0' * int(44100 * 0.15 * 4)
    with wave.open(str(target), 'wb') as out:
        out.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
        out.writeframes(lead_in + data + tail)


def selected_speaker_address():
    try:
        settings = json.loads(Path('/etc/paperdrop/speaker.json').read_text())
        value = settings.get('address')
        return value if isinstance(value, str) and value else None
    except (OSError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=5)
    parser.add_argument('--rate', type=int, default=24000)
    parser.add_argument('--pcm', default=None)
    parser.add_argument('--speaker', default=None)
    parser.add_argument('--no-playback', action='store_true')
    parser.add_argument('--out', default='/tmp/paperdrop-mic-check.wav')
    parser.add_argument('--playback-out', default='/tmp/paperdrop-mic-check-playback.wav')
    args = parser.parse_args()

    pcm = args.pcm or capture_pcm()
    out = Path(args.out)
    playback = Path(args.playback_out)
    print(f'Recording {args.seconds}s from {pcm} to {out}...')
    result = subprocess.run([
        'arecord', '-q', '-D', pcm, '-f', 'S16_LE', '-r', str(args.rate), '-c', '1',
        '-d', str(args.seconds), str(out),
    ], capture_output=True, text=True, timeout=args.seconds + 10)
    if result.returncode:
        print(result.stderr.strip() or 'arecord failed', file=sys.stderr)
        return result.returncode

    channels, rate, frames, samples = read_samples(out)
    stats = level_stats(samples)
    duration = round(frames / rate, 2) if rate else 0
    print(json.dumps({
        'recorded': str(out),
        'channels': channels,
        'rate': rate,
        'durationSeconds': duration,
        **stats,
    }, indent=2))

    normalize_for_a2dp(out, playback)
    print(f'Normalized Bluetooth playback WAV: {playback}')
    if args.no_playback:
        return 0

    speaker = args.speaker or selected_speaker_address()
    if not speaker:
        print('No selected Bluetooth speaker found; skipping playback.', file=sys.stderr)
        return 2
    print(f'Playing through Bluetooth speaker {speaker}...')
    result = subprocess.run([
        'aplay', '-q', '-D', f'bluealsa:DEV={speaker},PROFILE=a2dp', str(playback),
    ], capture_output=True, text=True, timeout=args.seconds + 15)
    if result.returncode:
        print(result.stderr.strip() or 'aplay failed', file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
