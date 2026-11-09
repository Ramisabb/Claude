"""Läser in rösten (Piper, sv_SE-nst-medium) och bygger tidslinjen för ett avsnitt.

Användning: python3 rost.py avsnitt.json <avsnitt> <röstmodell.onnx> <utmapp>
Skriver: <utmapp>/voice.wav (44,1 kHz), voice.json (tidslinje + munrörelser), undertexter.srt
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from piper import PiperVoice, SynthesisConfig

FPS = 30
LENGTH_SCALE = 0.93   # < 1 = lite snabbare tal
LINE_PAUSE = 0.24
SCENE_TAIL = 0.35
END_HOLD = 2.2

CONTAINER = {'alert': 'phone', 'sms': 'phone', 'update': 'phone', 'bankcall': 'phone', 'bankid': 'phone',
             'callback': 'phone', 'call': 'laptop', 'cta': 'end'}


def synth(voice, text):
    cfg = SynthesisConfig(length_scale=LENGTH_SCALE, noise_scale=0.6, noise_w_scale=0.75)
    parts, sr = [], 22050
    for ch in voice.synthesize(text, syn_config=cfg):
        sr = ch.sample_rate
        parts.append(ch.audio_int16_array.astype(np.float32) / 32768)
        parts.append(np.zeros(int(0.12 * sr), np.float32))  # kort paus mellan meningar
    a = np.concatenate(parts[:-1]) if parts else np.zeros(1, np.float32)
    # trimma tystnad i början/slutet
    thr = 0.02 * np.max(np.abs(a))
    nz = np.where(np.abs(a) > thr)[0]
    a = a[max(0, nz[0] - int(0.03 * sr)): nz[-1] + int(0.06 * sr)]
    return a, sr


def silences(a, sr, min_len=0.07):
    hop = int(0.01 * sr)
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    quiet = rms < 0.06 * rms.max()
    res, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) * 0.01 >= min_len and i > 0 and j < n:
                res.append((i + j) / 2 * 0.01)
            i = j
        else:
            i += 1
    return res


def chunk_times(subs, dur, sil):
    w = np.array([len(s) + 4 for s in subs], float)
    est = np.cumsum(w)[:-1] / w.sum() * dur
    bounds, last = [], 0.0
    for e in est:
        cands = [s for s in sil if abs(s - e) < 0.45 and s > last + 0.25]
        b = min(cands, key=lambda s: abs(s - e)) if cands else e
        b = max(b, last + 0.3)
        bounds.append(b)
        last = b
    edges = [0.0] + bounds + [dur]
    return [(edges[i], edges[i + 1]) for i in range(len(subs))]


def ref(r, sc):
    if r[0] == 'start':
        return sc['start'] + r[1]
    line = sc['lines'][r[0]]
    return line['chunks'][r[1]]['start'] + r[2]


def main():
    eps = json.load(open(sys.argv[1], encoding='utf-8'))
    ep = eps[sys.argv[2]]
    voice = PiperVoice.load(sys.argv[3])
    out = Path(sys.argv[4]); out.mkdir(parents=True, exist_ok=True)

    t = 0.0
    scenes, segs, subs = [], [], []
    prev_cont = None
    for si, s in enumerate(ep['scenes']):
        cont = CONTAINER[s['kind']]
        sc = {'kind': s['kind'], 'container': cont, 'title': bool(s.get('title')), 'start': t, 'lines': []}
        lead = 1.75 if sc['title'] else (0.6 if cont != prev_cont else 0.4)
        t += s.get('lead', lead)
        for li, L in enumerate(s['lines']):
            a, sr = synth(voice, L['say'])
            dur = len(a) / sr
            segs.append((t, a, sr))
            ct = chunk_times(L['subs'], dur, silences(a, sr))
            chunks = [{'txt': txt, 'start': t + c0, 'end': t + c1} for txt, (c0, c1) in zip(L['subs'], ct)]
            sc['lines'].append({'start': t, 'end': t + dur, 'chunks': chunks})
            subs.extend(chunks)
            t += dur + L.get('pause', LINE_PAUSE)
        t += s.get('tail', SCENE_TAIL)
        sc['end'] = t
        # händelser
        ev = {}
        if s['kind'] == 'alert':
            ev['alarm'] = sc['start'] + (1.75 if sc['title'] else 0.6)
        if s['kind'] == 'call':
            ev['card'] = sc['start'] + 0.7
        if s['kind'] == 'sms':
            ev['bubble'] = sc['start'] + 0.75
        if s['kind'] == 'bankcall':
            ev['ring'] = sc['start'] + (1.75 if sc['title'] else 0.6)
        for k, r in s.get('events', {}).items():
            ev[k] = ref(r, sc)
        sc['events'] = ev
        st = []
        for k, x in enumerate(s.get('stickers', [])):
            st.append({'t0': ref(x['at'], sc), 'html': x['html'], 'style': x.get('style', 'gold'), 'dur': x.get('dur')})
        for k in range(len(st)):
            st[k]['t1'] = st[k + 1]['t0'] - 0.05 if k + 1 < len(st) else sc['end'] - 0.1
            if st[k]['dur']:
                st[k]['t1'] = min(st[k]['t1'], st[k]['t0'] + st[k]['dur'])
        sc['stickers'] = st
        scenes.append(sc)
        prev_cont = cont
    total = t + END_HOLD

    # samla röstspåret (22,05 kHz) och räkna ut munrörelser
    sr = segs[0][2]
    track = np.zeros(int(total * sr) + sr, np.float32)
    for t0, a, _ in segs:
        i = int(t0 * sr)
        track[i:i + len(a)] += a
    track = track[:int(total * sr)]
    hop = sr // FPS
    nfr = int(total * FPS)
    rms = np.array([np.sqrt(np.mean(track[i * hop:(i + 1) * hop] ** 2)) for i in range(nfr)])
    ref95 = np.percentile(rms[rms > 0.01 * rms.max()], 92)
    env = np.clip(rms / ref95, 0, 1.2) ** 0.7
    env = np.convolve(env, [0.25, 0.5, 0.25], mode='same')
    env[env < 0.07] = 0

    raw = out / 'voice22.wav'
    with wave.open(str(raw), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(track / max(1e-9, np.abs(track).max()) * 0.9, -1, 1) * 32767).astype('<i2').tobytes())
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(raw), '-af', 'highpass=f=70,aresample=44100:resampler=soxr', '-ar', '44100', str(out / 'voice.wav')], check=False)
    if not (out / 'voice.wav').exists():
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(raw), '-af', 'highpass=f=70', '-ar', '44100', str(out / 'voice.wav')], check=True)
    raw.unlink()

    # ljudeffekter
    snd = []
    first = scenes[0]
    if first['title']:
        snd += [['whoosh', first['start'] + 0.05], ['pop', first['start'] + 1.55], ['whoosh', first['start'] + 1.3]]
    for i, sc in enumerate(scenes):
        ev = sc['events']
        if i > 0 and sc['container'] != scenes[i - 1]['container']:
            snd.append(['whoosh', sc['start']])
        k = sc['kind']
        if k == 'alert':
            snd += [['alarm', ev['alarm']], ['alarm', ev['alarm'] + 1.6]]
            if 'stamp' in ev: snd.append(['stamp', ev['stamp']])
            if 'close' in ev: snd += [['whoosh', ev['close']], ['ding', ev['close'] + 0.25]]
        if k == 'call':
            x = ev['card']
            while x < ev.get('decline', sc['end']) - 0.3:
                snd.append(['vibrate', x]); x += 1.6
            if 'decline' in ev: snd += [['click', ev['decline']], ['hangup', ev['decline'] + 0.1]]
        if k == 'sms':
            snd.append(['sms', ev['bubble']])
            if 'nope' in ev: snd.append(['nope', ev['nope']])
        if k == 'update':
            if 'tap' in ev: snd.append(['click', ev['tap']])
            if 'done' in ev: snd.append(['success', ev['done']])
        if k == 'bankcall':
            x = ev['ring']
            while x < ev.get('answer', sc['end']) - 0.3:
                snd.append(['vibrate', x]); x += 1.6
            if 'answer' in ev: snd.append(['click', ev['answer']])
            for q in ('q1', 'q2'):
                if q in ev: snd.append(['pop', ev[q]])
        if k == 'bankid':
            if 'stamp' in ev: snd += [['stamp', ev['stamp']], ['hangup', ev['stamp'] + 0.15]]
        if k == 'callback':
            if 'card' in ev: snd.append(['whoosh', ev['card']])
            if 'dial' in ev: snd += [['click', ev['dial']], ['ringback', ev['dial'] + 0.5]]
        if k == 'cta':
            snd.append(['sparkle', sc['start'] + 0.3])
            if 'pulse' in ev: snd.append(['click', ev['pulse']])
        for stk in sc['stickers']:
            snd.append(['pop', stk['t0']])

    data = {'episode': sys.argv[2], 'total': total, 'fps': FPS, 'scenes': scenes, 'subs': subs,
            'env': [round(float(x), 3) for x in env], 'sounds': snd, 'endcard': ep.get('endcard', {})}
    json.dump(data, open(out / 'voice.json', 'w', encoding='utf-8'), ensure_ascii=False)

    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s_, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s_:02},{ms:03}"
    with open(out / 'undertexter.srt', 'w', encoding='utf-8') as f:
        for i, c in enumerate(subs, 1):
            f.write(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['txt']}\n\n")
    print(f"{sys.argv[2]}: {total:.1f} s, {len(subs)} textbitar, {len(snd)} ljudeffekter")


if __name__ == '__main__':
    main()
