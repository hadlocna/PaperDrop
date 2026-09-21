"""One-time authoring of the Pi's cached guidance using the existing voice pack."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from media import client, ROOT
from languages import DRAW_PROMPT, TALK_PROMPT, LANGUAGES, translate

PHRASES = [
    'Choose a house to send a postcard, or tap the pencil to draw and print.',
    'Here is your picture. Press the green button to print, or the picture to look closer.',
    'Your picture is on its way.',
    'Your practice voice note is saved.',
    'You earned a star! Tap next for another adventure.',
    'Five stars! Amazing exploring. Tap play again for a new adventure.',
    'Let us try another one. Listen carefully.',
    'Tap the red button when you are finished talking.',
]
PHRASES += [translate(phrase, lang) for lang in LANGUAGES for phrase in (DRAW_PROMPT, TALK_PROMPT)]
family=json.loads((ROOT/'family.json').read_text())
PHRASES += [f'For {p["name"]}. Tap the microphone to talk, or the picture to draw. Tap again when you are done.' for p in family['children']]

def main():
    root=ROOT/'.state/speech';root.mkdir(parents=True,exist_ok=True)
    def generate(text):
        path=root/(hashlib.sha256(text.encode()).hexdigest()+'.wav')
        if path.exists():return
        result=client().audio.speech.create(model='gpt-4o-mini-tts',voice='marin',input=text,response_format='wav',
            instructions='Speak warmly and playfully to children aged three to seven. Natural, friendly, gentle enthusiasm. Clear and concise; never babyish or robotic. English. Pronounce Düsseldorf naturally.')
        path.write_bytes(result.content)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(generate,PHRASES))
    print('Pi guidance pack ready:',len(PHRASES),'phrases')
if __name__=='__main__':main()
