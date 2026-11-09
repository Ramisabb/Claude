"""Mixar röst + egen bakgrundsmusik + ljudeffekter (inga externa ljudfiler).

Användning: python3 ljud.py voice.json voice.wav ut_mix.wav ut_utan_musik.wav
Musiken sänks automatiskt (duckas) när presentatören pratar.
"""
import json
import sys
import wave

import numpy as np

SR = 44100
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def env_ad(n, attack=0.005, decay=2.5):
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-t * decay)


def tone(freq, dur, harm=(1, .35, .12, .05), decay=2.5, attack=0.005, detune=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k, a in enumerate(harm, start=1):
        s += a * np.sin(2 * np.pi * freq * k * (1 + detune) * t)
    return s * env_ad(n, attack, decay)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def lowpass_fast(x, cutoff):
    # enkel FIR-approximation (snabbare än loop för långa signaler)
    w = max(1, int(SR / cutoff / 2))
    k = np.ones(w) / w
    return np.convolve(x, k, mode='same')


def add(buf, sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[:j - i] * gain


# ---------------- musik ----------------
def music(total):
    n = int(total * SR)
    out = np.zeros(n)
    bpm = 92
    beat = 60 / bpm
    # Cmaj7 – Am7 – Fmaj7 – G6  (lugn, vänlig)
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 64]]
    roots = [48, 45, 41, 43]
    bar = 4 * beat
    nbars = int(total / bar) + 2
    for b in range(nbars):
        t0 = b * bar
        ch = chords[b % 4]
        # el-piano ackord slag 1 och "och" på 2
        for k, note in enumerate(ch):
            add(out, tone(midi(note), 2.4, decay=1.6, attack=0.01, detune=0.0015 * (k - 1.5)), t0 + 0.012 * k, 0.085)
            add(out, tone(midi(note), 1.2, decay=2.6, attack=0.01), t0 + 1.5 * beat + 0.01 * k, 0.045)
        # arpeggio (mjuk) på takt 3–4
        for k, note in enumerate([ch[0] + 12, ch[2] + 12, ch[1] + 12, ch[3] + 12]):
            add(out, tone(midi(note), 0.6, harm=(1, .2), decay=4.5), t0 + (2 + k * 0.5) * beat, 0.03)
        # bas
        for bb in (0, 2):
            add(out, tone(midi(roots[b % 4]), 1.2, harm=(1, .25), decay=2.2, attack=0.01), t0 + bb * beat, 0.16)
        # kick
        for bb in (0, 2):
            m = int(0.28 * SR); tt = np.arange(m) / SR
            f = 50 + 70 * np.exp(-tt * 25)
            kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 14)
            add(out, kick, t0 + bb * beat, 0.22)
        # hi-hat på åttondelar
        for e in range(8):
            m = int(0.04 * SR)
            hh = rng.standard_normal(m)
            hh = hh - np.concatenate([[0], hh[:-1]])
            hh *= np.exp(-np.arange(m) / SR * 90)
            add(out, hh, t0 + e * beat / 2 + 0.01, 0.018 if e % 2 else 0.01)
        # mjuk "snare"/klapp på 2 och 4
        for bb in (1, 3):
            m = int(0.18 * SR)
            sn = lowpass_fast(rng.standard_normal(m), 3000) * np.exp(-np.arange(m) / SR * 22)
            add(out, sn, t0 + bb * beat, 0.07)
    out = lowpass_fast(out, 9000)
    # fade
    fi = int(0.6 * SR); fo = int(2.0 * SR)
    out[:fi] *= np.linspace(0, 1, fi)
    out[-fo:] *= np.linspace(1, 0, fo) ** 1.5
    return out


# ---------------- effekter ----------------
def sfx(name):
    if name == 'whoosh':
        m = int(0.45 * SR); t = np.arange(m) / SR
        x = rng.standard_normal(m)
        x = lowpass_fast(x, 1800) * np.sin(np.pi * t / t[-1]) ** 2
        return x * 0.55
    if name == 'pop':
        m = int(0.09 * SR); t = np.arange(m) / SR
        f = 520 + 600 * t / t[-1]
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35) * 0.5
    if name == 'alarm':
        s = np.zeros(int(0.5 * SR))
        for k in range(2):
            b = tone(880, 0.13, harm=(1, .5, .25), decay=6)
            add(s, b, k * 0.2, 0.32)
        return s
    if name == 'stamp':
        m = int(0.35 * SR); t = np.arange(m) / SR
        th = np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 12)
        cl = lowpass_fast(rng.standard_normal(m), 2500) * np.exp(-t * 60)
        return (th * 0.8 + cl * 0.5)
    if name == 'ding':
        s = np.zeros(int(1.0 * SR))
        add(s, tone(1318, 1.0, harm=(1, .3, .1), decay=4), 0, 0.35)
        add(s, tone(1975, 0.8, harm=(1,), decay=5), 0, 0.12)
        return s
    if name == 'vibrate':
        m = int(0.42 * SR); t = np.arange(m) / SR
        x = np.sign(np.sin(2 * np.pi * 145 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 28 * t))
        x = lowpass_fast(x, 600) * np.minimum(1, np.minimum(t / 0.02, (t[-1] - t) / 0.03))
        return x * 0.35
    if name == 'click':
        m = int(0.03 * SR); t = np.arange(m) / SR
        return lowpass_fast(rng.standard_normal(m), 4000) * np.exp(-t * 200) * 0.6 + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 150) * 0.2
    if name == 'hangup':
        s = np.zeros(int(0.6 * SR))
        for k, f in enumerate((620, 480)):
            add(s, tone(f, 0.18, harm=(1, .3), decay=8), k * 0.17, 0.3)
        return s
    if name == 'sms':
        s = np.zeros(int(0.7 * SR))
        add(s, tone(1046, 0.4, harm=(1, .2), decay=7), 0, 0.33)
        add(s, tone(1568, 0.5, harm=(1, .2), decay=6), 0.12, 0.3)
        return s
    if name == 'nope':
        s = np.zeros(int(0.6 * SR))
        for k, f in enumerate((330, 247)):
            add(s, tone(f, 0.22, harm=(1, .6, .3, .15), decay=6), k * 0.16, 0.35)
        return s
    if name == 'success':
        s = np.zeros(int(1.2 * SR))
        for k, f in enumerate((523, 659, 784, 1046)):
            add(s, tone(f, 0.8, harm=(1, .3, .1), decay=4), k * 0.085, 0.24)
        return s
    if name == 'sparkle':
        s = np.zeros(int(1.0 * SR))
        for k in range(7):
            f = 1800 + 1600 * rng.random()
            add(s, tone(f, 0.35, harm=(1,), decay=10), k * 0.06, 0.08)
        return s
    if name == 'ringback':
        s = np.zeros(int(3.2 * SR))
        for k in range(2):
            add(s, tone(425, 1.0, harm=(1, .15), decay=0.4, attack=0.02), k * 1.6, 0.22)
        return s
    raise ValueError(name)


def write(path, x):
    x = np.clip(x, -1, 1)
    st = np.stack([x, x], axis=1)
    data = (st * 32767).astype('<i2').tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data)


def read_mono(path):
    with wave.open(path, 'rb') as w:
        assert w.getframerate() == SR, w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64) / 32768
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(axis=1)
    return a


def main():
    tl = json.load(open(sys.argv[1], encoding='utf-8'))
    total = tl['total']
    n = int(total * SR)
    voice = np.zeros(n)
    v = read_mono(sys.argv[2])[:n]
    voice[:len(v)] = v
    voice = voice / max(1e-9, np.max(np.abs(voice))) * 0.85
    fx = np.zeros(n)
    for name, t in tl['sounds']:
        add(fx, sfx(name), t, 0.55)
    mus = music(total)[:n]
    # duckning: följ röstens nivå (mjuk attack/release)
    hop = 441
    m = n // hop
    lvl = np.sqrt(np.mean(voice[:m * hop].reshape(m, hop) ** 2, axis=1))
    act = (lvl > 0.01).astype(float)
    k = np.ones(25) / 25  # ca 0,25 s utjämning
    act = np.clip(np.convolve(act, k, mode='same') * 1.6, 0, 1)
    gain = 1 - 0.68 * act
    gain = np.repeat(gain, hop)
    gain = np.concatenate([gain, np.full(n - len(gain), gain[-1] if len(gain) else 1)])
    mus = mus / max(1e-9, np.max(np.abs(mus))) * 0.42 * gain
    mix = voice + mus + fx
    mix = mix / max(1.0, np.max(np.abs(mix)) / 0.95)
    nomus = voice + fx
    nomus = nomus / max(1.0, np.max(np.abs(nomus)) / 0.95)
    write(sys.argv[3], mix)
    write(sys.argv[4], nomus)
    print('ok', round(total, 2), 's')


if __name__ == '__main__':
    main()
