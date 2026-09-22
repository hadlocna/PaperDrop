"""Child-independent rounds with four answers, Repeat and visible Home."""
import random
import string
from riddles import RIDDLES, ANSWERS

COLORS = {'red':'#e87c71', 'blue':'#87bde1', 'green':'#85b8a2', 'yellow':'#f0cb86', 'purple':'#b6a0d5'}

def number_questions():
    return [(n+1, f'What number comes after {n}?') for n in range(10)] + [
        (a+b,f'What is {a} plus {b}?') for a in range(1,6) for b in range(a,6)]

def new_round(kind, previous=None):
    if kind=='riddles':
        target, words = random.choice([r for r in RIDDLES if r[0] != previous])
        prompt = words[0]
        pool = list(ANSWERS)
    elif kind=='letters':
        pool=list(string.ascii_uppercase)
        target=random.choice([x for x in pool if x!=previous])
        prompt=f'Can you find the letter {target}?'
    elif kind=='numbers':
        target,prompt=random.choice([q for q in number_questions() if q[0]!=previous])
        pool=list(range(11))
    elif kind=='colors':
        pool=list(COLORS)
        target=random.choice([x for x in pool if x!=previous])
        prompt=f'Can you find {target}?'
    else:
        raise ValueError('Unknown game')
    choices=random.sample([x for x in pool if x!=target],3)+[target]
    random.shuffle(choices)
    return dict(kind=kind,target=target,prompt=prompt,choices=choices)

def voice_phrases():
    return ([f'Can you find the letter {x}?' for x in string.ascii_uppercase]
            +[q[1] for q in number_questions()]
            +[f'Can you find {x}?' for x in COLORS]+[r[1][0] for r in RIDDLES])
