"""Explicitly synthetic local postcards for demonstrating the received flow."""
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parent

def reset_examples(mailbox):
    audio=ROOT/'assets/demo/example-voice.wav'
    picture=ROOT/'assets/demo/snail.png'
    picture_audio=ROOT/'assets/demo/example-picture.wav'
    if not audio.exists() or not picture.exists() or not picture_audio.exists():
        raise ValueError('Example assets are not ready')
    messages=[
        dict(id='demo-alma-voice-andy',sender='andy',recipient='alma',kind='voice',audio=str(audio),demo=True),
        dict(id='demo-alma-picture-elise',sender='elise',recipient='alma',kind='drawing',audio=str(picture_audio),image=str(picture),demo=True)
    ]
    with mailbox.lock,mailbox.db:
        for message in messages:
            old=mailbox.db.execute('SELECT payload FROM mail WHERE id=?',(message['id'],)).fetchone()
            if old and not json.loads(old[0]).get('demo'):
                raise ValueError('Refusing to overwrite a real postcard')
            mailbox.db.execute('''INSERT INTO mail(id,sender,recipient,created,seen,payload)
                VALUES(?,?,?,?,0,?) ON CONFLICT(id) DO UPDATE SET seen=0,created=excluded.created''',
                (message['id'],message['sender'],message['recipient'],time.time(),json.dumps(message)))
    return 2
