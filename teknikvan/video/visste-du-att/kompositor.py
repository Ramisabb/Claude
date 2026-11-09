"""Lägger Teknikväns karaktär (porträttet) i videon med läppsynk och små huvudrörelser.

Användning:
  python3 kompositor.py video <voice.json> <bakgrund.mp4> <ut.mp4>
  python3 kompositor.py test  <voice.json> <bakgrund.png> <ut.png> <tid>

Munnen animeras genom att underkäken (läpp, pipskägg, haka) förskjuts längs ansiktets
lutning i takt med röstens styrka, och munhålan (mörk, med en antydan av tänder) ritas i öppningen.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
W, H = 1080, 1920
SCALE = 0.62          # porträttets skala i bilden
X0, Y0 = -97, 1180    # porträttets övre vänstra hörn i bilden
DMAX = 30.0           # max munöppning (px i porträttet)
LEVELS = 36
# ögon i porträttet (förlängda koordinater): centrum, lutning, halvbredd, halvhöjd
EYES = [
    {'c': (1060.0, 393.0), 'ang': 21.5, 'a': 57.0, 'b': 23.0},
    {'c': (1236.0, 469.0), 'ang': 22.0, 'a': 39.0, 'b': 20.0},
]


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def eout(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


class Karaktar:
    def __init__(self):
        img = cv2.imread(str(HERE / 'bilder' / 'karaktar.png'), cv2.IMREAD_UNCHANGED)
        self.rgba = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA).astype(np.float32)
        self.K = json.load(open(HERE / 'bilder' / 'karaktar.json'))
        L = np.array(self.K['left'], float); R = np.array(self.K['right'], float)
        self.c = (L + R) / 2
        self.t = (R - L) / np.linalg.norm(R - L)
        n = np.array([-self.t[1], self.t[0]])
        self.n = n if n[1] > 0 else -n
        self.hw = np.linalg.norm(R - L) / 2
        hw = self.hw
        corners = [self.c + u * self.t + v * self.n for u in (-2.9 * hw, 2.9 * hw) for v in (-80, 300)]
        lo = np.floor(np.min(corners, 0)).astype(int); hi = np.ceil(np.max(corners, 0)).astype(int)
        self.x0, self.y0 = max(0, lo[0]), max(0, lo[1])
        self.x1, self.y1 = min(self.rgba.shape[1], hi[0]), min(self.rgba.shape[0], hi[1])
        self.base = self.premul(self.rgba)
        self.rgba_blur = cv2.GaussianBlur(self.rgba, (0, 0), 2.4)
        self.levels = [self.mouth(DMAX * i / (LEVELS - 1)) for i in range(LEVELS)]

    @staticmethod
    def premul(a):
        out = a.copy()
        out[..., :3] *= a[..., 3:4] / 255.0
        return out

    def mouth(self, d):
        """Returnerar förmultiplicerad RGBA-lapp för munområdet med öppning d."""
        x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
        if d < 0.3:
            return self.base[y0:y1, x0:x1].copy()
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        px, py = xs - self.c[0], ys - self.c[1]
        tv, nv, hw = self.t, self.n, self.hw
        u = px * tv[0] + py * tv[1]
        v = px * nv[0] + py * nv[1]
        g = np.clip(1 - (u / hw) ** 2, 0, 1) ** 0.65
        a0, b0 = 0.16 * d * g, 0.84 * d * g

        def gj(vs):  # käkprofil: bredare längre ner (hela hakan följer med)
            hwv = np.minimum(hw * (1 + np.clip(vs, 0, None) / 110.0), hw * 2.6)
            return np.clip(1 - (u / hwv) ** 2, 0, 1) ** 0.65

        def fl(vs):
            return 1 - smoothstep(165, 260, vs)

        def fu(vs):
            return 1 - smoothstep(0, 55, -vs)

        lower, upper = v >= b0, v <= -a0
        vl = v.copy()
        for _ in range(5):
            vc = np.maximum(vl, 0)
            vl = v - 0.84 * d * gj(vc) * fl(vc)
        vu = v.copy()
        for _ in range(4):
            vu = v + a0 * fu(np.minimum(vu, 0))
        vs = np.where(lower, vl, np.where(upper, vu, 0.0))
        sx = (self.c[0] + u * tv[0] + vs * nv[0]).astype(np.float32)
        sy = (self.c[1] + u * tv[1] + vs * nv[1]).astype(np.float32)
        patch = cv2.remap(self.rgba, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # munhåla
        gap = a0 + b0
        w = np.clip((v + a0) / np.maximum(gap, 1e-3), 0, 1)
        inside = np.clip(np.minimum(v + a0, b0 - v) + 0.5, 0, 1) * (gap > 0.6)
        dark = np.array([38, 11, 10], np.float32); lip = np.array([112, 44, 40], np.float32)
        edge = np.minimum(w, 1 - w)
        col = lip + (dark - lip) * smoothstep(0, 0.32, edge)[..., None]
        teeth = smoothstep(5, 13, gap) * (1 - smoothstep(0.1, 0.36, w)) * np.clip(1 - (u / (0.62 * hw)) ** 4, 0, 1)
        tcol = np.array([220, 210, 201], np.float32) * (0.62 + 0.38 * smoothstep(0.0, 0.1, w))[..., None]  # skugga under överläppen
        col = col + (tcol - col) * (teeth * 0.78)[..., None]
        tongue = smoothstep(9, 18, gap) * smoothstep(0.55, 0.8, w) * (1 - smoothstep(0.93, 1.0, w)) * np.clip(1 - (u / (0.7 * hw)) ** 2, 0, 1)
        col = col + (np.array([150, 62, 58], np.float32) - col) * (tongue * 0.55)[..., None]
        patch[..., :3] = patch[..., :3] + (col - patch[..., :3]) * inside[..., None]
        patch[..., 3] = np.maximum(patch[..., 3], inside * 255)
        return self.premul(patch)

    def frame_image(self, d, blink=0.0):
        i = int(round(np.clip(d / DMAX, 0, 1) * (LEVELS - 1)))
        img = self.base.copy()
        img[self.y0:self.y1, self.x0:self.x1] = self.levels[i]
        if blink > 0.02:
            self.blink(img, blink)
        return img

    def blink(self, img, c):
        """Ögonlocket: huden ovanför ögat dras ner över ögat (c = 0 öppet … 1 stängt)."""
        for E in EYES:
            cx, cy = E['c']; th = math.radians(E['ang']); a, b = E['a'], E['b']
            tv = (math.cos(th), math.sin(th)); nv = (-math.sin(th), math.cos(th))
            m = int(a + 20)
            x0, x1, y0, y1 = int(cx - m), int(cx + m), int(cy - m), int(cy + m)
            ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            u = (xs - cx) * tv[0] + (ys - cy) * tv[1]
            v = (xs - cx) * nv[0] + (ys - cy) * nv[1]
            h = b * np.sqrt(np.clip(1 - (u / a) ** 2, 0, 1))
            edge_v = -h + 2 * h * c * 0.93
            f_lid = np.clip(edge_v - v + 0.5, 0, 1) * smoothstep(-h - 9, -h + 3, v) * smoothstep(0.5, 5.0, h)
            rel = np.clip((v + h) / np.maximum(edge_v + h, 1e-3), 0, 1)
            vs = -h - 20 + rel * 10
            sx = (cx + u * tv[0] + vs * nv[0]).astype(np.float32)
            sy = (cy + u * tv[1] + vs * nv[1]).astype(np.float32)
            lid = 0.65 * cv2.remap(self.rgba_blur, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE) + \
                  0.35 * cv2.remap(self.rgba, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            lid[..., :3] *= (1 - 0.10 * rel)[..., None]
            lash = np.clip(1 - np.abs(v - edge_v) / 2.0, 0, 1) * smoothstep(1.0, 6.0, h) * min(1.0, c * 4) * 0.8
            reg = img[y0:y1, x0:x1]
            reg[..., :3] = reg[..., :3] + (lid[..., :3] - reg[..., :3]) * f_lid[..., None]
            reg[..., :3] = reg[..., :3] + (np.array([40, 26, 20], np.float32) - reg[..., :3]) * (lash * 0.85)[..., None]


class Animator:
    def __init__(self, data):
        self.D = data
        self.env = np.array(data['env'], np.float32)
        self.fps = data.get('fps', 30)
        self.subs = data['subs']
        self.k = Karaktar()
        self.pivot = np.array(self.k.K['pivot'], float)
        self.blinks = []
        b, i = 1.6, 0
        while b < data['total'] + 5:
            self.blinks.append(b)
            x = math.sin(i * 127.1 + 311.7) * 43758.5453; i += 1
            b += 2.8 + 1.8 * (x - math.floor(x))

    def blink_at(self, t):
        for b in self.blinks:
            p = (t - b) / 0.17
            if 0 <= p < 1:
                return eout(p / 0.4) if p < 0.4 else 1 - ((p - 0.4) / 0.6) ** 2
        return 0.0

    def env_at(self, t):
        i = int(t * self.fps)
        return float(self.env[min(max(i, 0), len(self.env) - 1)]) if len(self.env) else 0.0

    def talk_at(self, t):
        return float(np.mean([self.env_at(t + k / self.fps) for k in range(-6, 7)]))

    def layer(self, t):
        e = self.env_at(t)
        d = DMAX * min(1.0, max(0.0, e)) ** 0.85
        img = self.k.frame_image(d, self.blink_at(t))
        talk = min(1.0, self.talk_at(t) * 2)
        rot = talk * 1.1 * math.sin(t * 1.9) + 0.5 * math.sin(t * 0.7)
        sub = next((s for s in self.subs if s['start'] <= t < s['end']), None)
        nod = math.sin(min(1.0, max(0.0, (t - sub['start']) / 0.35)) * math.pi) * 3 if sub else 0.0
        breathe = math.sin(t * 2.1)
        enter = (1 - eout((t - 0.25) / 0.8)) * 760
        sc = SCALE * (1 + 0.003 * breathe)
        dst = np.array([X0 + self.pivot[0] * SCALE, Y0 + self.pivot[1] * SCALE + enter + breathe * 2 + nod + e * 1.5])
        M = cv2.getRotationMatrix2D((float(self.pivot[0]), float(self.pivot[1])), rot, sc)
        M[:, 2] += dst - self.pivot
        return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    def composite(self, bg, t, ytop=1050):
        lay = self.layer(t)
        region = lay[ytop:]
        a = region[..., 3:4] / 255.0
        out = bg.copy()
        out[ytop:] = np.clip(bg[ytop:].astype(np.float32) * (1 - a) + region[..., :3], 0, 255).astype(np.uint8)
        return out


def main():
    mode = sys.argv[1]
    data = json.load(open(sys.argv[2], encoding='utf-8'))
    an = Animator(data)
    if mode == 'test':
        bg = cv2.cvtColor(cv2.imread(sys.argv[3]), cv2.COLOR_BGR2RGB)
        out = an.composite(bg, float(sys.argv[5]))
        cv2.imwrite(sys.argv[4], cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
        return
    src, dst = sys.argv[3], sys.argv[4]
    fps = an.fps
    rd = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    wr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', dst], stdin=subprocess.PIPE)
    n = W * H * 3
    i = 0
    while True:
        buf = rd.stdout.read(n)
        if len(buf) < n:
            break
        bg = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        wr.stdin.write(an.composite(bg, i / fps).tobytes())
        i += 1
        if i % 300 == 0:
            print(f'{Path(dst).name}: ruta {i}', flush=True)
    wr.stdin.close(); wr.wait(); rd.wait()
    print('klar', dst, i, 'rutor')


if __name__ == '__main__':
    main()
