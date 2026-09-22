"""Compose cached speech with a quiet, playful three-note star sparkle."""
import audioop
import hashlib
import math
from pathlib import Path
import struct
import wave

RATE = 24000
STAR_DURATION = .8

def star_frames():
    frames=[]
    notes=[(0,659.25),(.17,830.61),(.34,1318.51)]
    for n in range(int(RATE*STAR_DURATION)):
        t=n/RATE; value=0
        for start,freq in notes:
            age=t-start
            if 0 <= age < .42:
                envelope=min(age/.008,1)*math.exp(-age*10)
                value += .18*envelope*(math.sin(2*math.pi*freq*age)+.2*math.sin(4*math.pi*freq*age))
        frames.append(struct.pack('<h',int(max(-.8,min(.8,value))*32767)))
    return b''.join(frames)

def combine(paths, destination, star=False):
    data=star_frames() if star else b''
    for path in paths:
        with wave.open(str(path),'rb') as wav:
            raw=wav.readframes(min(wav.getnframes(),wav.getframerate()*30))
            width,channels,rate=wav.getsampwidth(),wav.getnchannels(),wav.getframerate()
        if channels==2:raw=audioop.tomono(raw,width,.5,.5)
        elif channels!=1:raise ValueError('Unsupported cue channels')
        if width!=2:raw=audioop.lin2lin(raw,width,2)
        if rate!=RATE:raw,_=audioop.ratecv(raw,2,1,rate,RATE,None)
        data+=raw+b'\0'*int(RATE*.15)*2
    destination=Path(destination);destination.parent.mkdir(exist_ok=True,parents=True)
    temporary=destination.with_suffix('.tmp')
    with wave.open(str(temporary),'wb') as out:
        out.setparams((1,2,RATE,0,'NONE','not compressed'));out.writeframes(data)
    temporary.replace(destination)
    return destination
