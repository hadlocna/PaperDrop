"""Cache warm spoken guidance. No microphone recordings are used here."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from media import ROOT, client
from games import voice_phrases


def phrases():
    family=json.loads((ROOT/'family.json').read_text())
    lines=[
        'Choose your face. Then choose a cousin’s house.',
        'No mail yet.',
        'Here is your picture. Tap any button to go back.',
        'Tap any button to go back.',
        'Here is your picture. Tap any button to see the send button.',
        'Listen to your note, then press the green button to send.',
        'I am making your picture. The buttons are resting.',
        'Your postcard is saved in the test mailbox.',
        'Oops. Please try again.',
        'There is a postcard for you. Press play to listen, or the picture to see it.',
    ]
    for p in family['children']:
        lines += [f'{p["name"]}. Choose a cousin’s house.',
                  f'For {p["name"]}. Hold the microphone to talk. Hold the pencil to draw.']
    lines += [f'Who in {h["name"]}?' for h in family['houses']]
    lines += ['Choose your face to play or send a postcard.', 'Choose a cousin’s house.',
              'Let’s play! Choose colors, letters, or numbers.', 'You found it! Great job! Tap next to play again.']
    lines += [f'Hello {p["name"]}. Choose cousins, games, letters, or numbers.' for p in family['children']]
    lines += voice_phrases() + ['Have another try. '+p for p in voice_phrases()]
    lines += ['Choose your face to learn, a house to send, or hold the pencil to draw and print.',
              'Who is sending? Choose your face.', 'Your picture is ready. Sending it to the printer.',
              'Your picture has been sent to the printer.']
    lines += [f'Hello {p["name"]}. Choose letters, numbers, or a postcard.' for p in family['children']]
    return lines


def main():
    root=ROOT/'.state/speech';root.mkdir(parents=True,exist_ok=True)
    def generate(text):
        path=root/(hashlib.sha256(text.encode()).hexdigest()+'.wav')
        if path.exists():return
        ai=client()
        result=ai.audio.speech.create(model='gpt-4o-mini-tts',voice='marin',input=text,response_format='wav',
            instructions='Speak warmly and playfully to children aged three to seven. Natural, friendly, gentle enthusiasm. Clear and concise; never babyish or robotic. English. Pronounce Düsseldorf naturally.')
        temp=path.with_suffix('.tmp')
        temp.write_bytes(result.content)
        temp.replace(path)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(generate,phrases()))
    print(f'Cached {len(phrases())} spoken prompts using Marin.')


if __name__=='__main__':main()
