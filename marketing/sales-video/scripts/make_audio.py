"""Original soundtrack + sound effects for the sales video, synthesized from scratch.

120 BPM upbeat pop in D major (D-A-Bm-G), with the sound effects placed from
out/cues.json (exported from video.js) so every pop, print and wipe lands on picture.
"""
import json, wave
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt

HERE = Path(__file__).resolve().parent.parent
SR = 44100
cues = json.loads((HERE / 'out' / 'cues.json').read_text())
DUR = cues['DURATION']
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)
BEAT = 0.5

def hz(m): return 440 * 2 ** ((m - 69) / 12)
def env_exp(n, k): return np.exp(-np.arange(n) / SR * k)
def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, btype=kind, fs=SR, output='sos'), x)
def add(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0: return
    if i < 0: sig = sig[-i:]; i = 0
    sig = sig[:N - i]
    L[i:i + len(sig)] += sig * gain * (1 - max(0, pan))
    R[i:i + len(sig)] += sig * gain * (1 + min(0, pan))
def tt(d): return np.arange(int(d * SR)) / SR

# ---- Instruments -----------------------------------------------------------
def kick():
    t = tt(.4); f = 48 + 110 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7.5) + .3 * np.exp(-t * 300) * rng.standard_normal(len(t))
def clap():
    t = tt(.28); n = rng.standard_normal(len(t))
    e = np.exp(-t * 22) + .6 * sum(np.exp(-np.clip(t - d, 0, None) * 160) * (t >= d) for d in (0, .011, .022))
    return filt(n, 'bandpass', [900, 5000]) * e * .9
def hat(open_=False):
    t = tt(.2 if open_ else .05); n = filt(rng.standard_normal(len(t)), 'highpass', 7500)
    return n * np.exp(-t * (18 if open_ else 90))
def pluck(m, d=.45, bright=1.0):
    t = tt(d); f = hz(m)
    s = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (6 + 5 * k)) for k, a in ((1, 1), (2, .5 * bright), (3, .25 * bright), (4, .12 * bright)))
    return s * (1 - np.exp(-t * 900))
def bass(m, d=.24):
    t = tt(d); f = hz(m)
    saw = 2 * ((f * t) % 1) - 1
    s = filt(saw, 'lowpass', 900) * .7 + .6 * np.sin(2 * np.pi * f * t)
    return s * np.exp(-t * 6) * (1 - np.exp(-t * 600))
def bell(m, d=.6):
    t = tt(d); f = hz(m)
    return (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)) * np.exp(-t * 7)
def pad(ms, d):
    t = tt(d); s = np.zeros(len(t))
    for m in ms:
        for det in (-.08, .08):
            f = hz(m + det); s += 2 * ((f * t) % 1) - 1
    s = filt(s, 'lowpass', 1400) / (2 * len(ms))
    a = np.minimum(1, t / .3) * np.minimum(1, (d - t) / .3)
    return s * a
def noise_sweep(d, f0, f1, rise=True):
    t = tt(d); n = rng.standard_normal(len(t)); out = np.zeros(len(t)); seg = 512
    for i in range(0, len(t), seg):
        p = i / len(t); f = f0 * (f1 / f0) ** p
        out[i:i + seg] = filt(n[max(0, i - 2048):i + seg], 'bandpass', [f * .6, min(f * 1.6, 20000)])[-len(n[i:i + seg]):]
    e = np.sin(np.pi * np.linspace(0, 1, len(t))) ** 1.5 if not rise else np.linspace(0, 1, len(t)) ** 2
    return out * e

# ---- Song ------------------------------------------------------------------
# D  A  Bm  G — one chord per bar (2 s)
CHORDS = [(62, 66, 69), (61, 64, 69), (62, 66, 71), (62, 67, 71)]
ROOTS = [38, 33, 35, 31]
def bar_of(t): return int(t // 2) % 4
def section(t):
    if t < 2: return 'intro'
    if t < 4: return 'intro2'
    if t < 8: return 'build'
    if 52 <= t < 55: return 'break'
    if t >= 60: return 'end'
    return 'full'

beats = int(DUR / BEAT)
for b in range(beats):
    t = b * BEAT; sec = section(t); ch = CHORDS[bar_of(t)]; root = ROOTS[bar_of(t)]
    if sec in ('intro2', 'build', 'full'):
        add(kick(), t, .95)
    if sec in ('full',) and b % 2 == 1: add(clap(), t, .55, .05)
    if sec in ('build',) and b % 2 == 1 and t >= 4: add(clap(), t, .4)
    if sec in ('intro2', 'build', 'full'):
        add(hat(), t, .18, -.3); add(hat(True), t + .25, .2, .3)
        if sec == 'full': add(hat(), t + .125, .08, -.3); add(hat(), t + .375, .08, .3)
    if sec in ('intro', 'intro2', 'build', 'full', 'break'):
        # Offbeat chord plucks: the bouncy "skank".
        for m, pan in zip(ch, (-.35, 0, .35)):
            add(pluck(m + 12, .35), t + .25, .16 if sec != 'break' else .1, pan)
    if sec in ('build', 'full'):
        pat = [0, 0, 12, 0] if b % 2 == 0 else [0, 7, 12, 7]
        for k, off in enumerate(pat):
            add(bass(root + off), t + k * .125, .38 if k % 2 == 0 else .26)
# Snare roll into the drop
for k in range(16):
    t = 7.0 + k * .0625; add(clap(), t, .1 + .35 * k / 16)
# Pads: intro, breakdown and the end chord
for t0, d in ((0, 4), (52, 3)):
    for b in range(int(d / 2) + (1 if d % 2 else 0)):
        tb = t0 + b * 2; add(pad([m - 12 for m in CHORDS[bar_of(tb)]] + [CHORDS[bar_of(tb)][0]], min(2, t0 + d - tb)), tb, .5)
# Bell arpeggios over the "anything" and games sections, and the end card
for t0, t1 in ((16, 20), (39, 47), (55, 60)):
    t = t0; k = 0
    while t < t1:
        ch = CHORDS[bar_of(t)]; seq = [ch[0], ch[1], ch[2], ch[1] + 12, ch[2], ch[1], ch[0] + 12, ch[2]]
        add(bell(seq[k % 8] + 12, .35), t, .09, .4 if k % 2 else -.4); t += .25; k += 1
# Ending: big D chord + crash
for m in (50, 62, 66, 69, 74, 78):
    add(pluck(m, 2.0, .7), 60.0, .25)
add(kick(), 60.0, 1.0)
crash = filt(rng.standard_normal(int(2.5 * SR)), 'highpass', 4000) * env_exp(int(2.5 * SR), 2.2)
add(crash, 60.0, .25)
for t in (8.0, 20.0, 26.0, 34.0, 39.0, 47.0, 55.0):
    add(crash[:SR], t, .18)

# Sidechain duck everything melodic against the kick pattern
music = np.stack([L, R]); L[:] = 0; R[:] = 0
duck = np.ones(N)
for b in range(beats):
    t = b * BEAT
    if section(t) in ('intro2', 'build', 'full'):
        i = int(t * SR); n = min(int(.3 * SR), N - i)
        duck[i:i + n] = np.minimum(duck[i:i + n], 1 - .45 * np.exp(-np.arange(n) / SR * 10))

# ---- Sound effects -----------------------------------------------------------
def sfx(c):
    k = c['type']; d = c.get('d', 0)
    if k == 'pop':
        t = tt(.09); f = 500 + 1400 * (t / .09)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 45) * .55
    if k == 'tick':
        t = tt(.03); return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 160) * .4
    if k == 'click':
        t = tt(.05); return (np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 120) + .3 * rng.standard_normal(len(t)) * np.exp(-t * 400)) * .45
    if k == 'whoosh':
        return noise_sweep(.5, 400, 6000, rise=False) * .5
    if k == 'riser':
        t = tt(d); s = noise_sweep(d, 300, 9000) * .5
        return s + .15 * np.sin(2 * np.pi * np.cumsum(200 + 1200 * (t / d) ** 2) / SR) * (t / d)
    if k == 'hit':
        n = int(.4 * SR); k_ = kick()[:n]
        return k_ * .8 + filt(rng.standard_normal(n), 'highpass', 3000) * env_exp(n, 9) * .35
    if k == 'stamp':
        t = tt(.25); thump = np.sin(2 * np.pi * np.cumsum(70 + 90 * np.exp(-t * 40)) / SR) * np.exp(-t * 16)
        return thump * .9 + filt(rng.standard_normal(len(t)), 'bandpass', [300, 3000]) * np.exp(-t * 40) * .5
    if k == 'print':
        # Thermal printer: stepper whine + paper rasp, chopped into feed steps.
        t = tt(d); motor = np.sign(np.sin(2 * np.pi * 180 * t)) * .25 + np.sin(2 * np.pi * 540 * t) * .3
        rasp = filt(rng.standard_normal(len(t)), 'bandpass', [1500, 7000]) * .6
        chop = .55 + .45 * (np.sin(2 * np.pi * 24 * t) > -.2)
        e = np.minimum(1, t / .03) * np.minimum(1, (d - t) / .05)
        return filt(motor + rasp, 'lowpass', 8000) * chop * e * .32
    if k == 'scribble':
        t = tt(d); n = filt(rng.standard_normal(len(t)), 'bandpass', [2000, 6500])
        am = np.abs(np.sin(2 * np.pi * 9 * t + 2 * np.sin(2 * np.pi * 3 * t)))
        return n * am * np.minimum(1, (d - t) / .05) * .35
    if k == 'sparkle':
        out = np.zeros(int(.7 * SR))
        for j, m in enumerate((86, 90, 93)):
            s = bell(m, .5); i = int(j * .07 * SR); out[i:i + len(s)] += s[:len(out) - i]
        return out * .32
    if k == 'ding':
        return (bell(93, 1.2) + .5 * bell(98, 1.2)) * .35
    if k == 'beep':
        t = tt(.14); return np.sin(2 * np.pi * 1046 * t) * np.minimum(1, (0.14 - t) / .02) * .3
    if k == 'buzz':
        out = np.concatenate([pluck(55, .18, .2), pluck(51, .3, .2)]); return out * .5
    raise ValueError(k)

fx = np.zeros((2, N))
for i, c in enumerate(cues['cues']):
    s = sfx(c); pan = ((i * 37) % 7 - 3) / 10
    j = int(c['t'] * SR); s = s[:N - j]
    fx[0, j:j + len(s)] += s * (1 - max(0, pan)); fx[1, j:j + len(s)] += s * (1 + min(0, pan))

mix = music * duck * 0.9 + fx
mix = np.tanh(mix * 1.1) / np.tanh(1.1)
fade = np.minimum(1, (DUR - np.arange(N) / SR) / .6); mix *= fade
mix /= np.max(np.abs(mix)) / .89
out = HERE / 'out' / 'music.wav'
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix.T * 32767).astype('<i2').tobytes())
print('audio ->', out)
