"""Frilägger Teknikväns karaktärsporträtt (lila bakgrund -> genomskinlig) och förlänger tröjan åt sidorna.

Användning: python3 karaktar_prep.py <porträtt.png> <ut.png> <ut.json>
JSON:en innehåller munnens position i den nya bilden (för läppsynk).
"""
import json
import sys

import numpy as np
from PIL import Image, ImageFilter

EXT_X = 420     # px tröja som läggs till på varje sida
EXT_Y = 90      # px nedåt
# Munnen i originalbilden (mätt): mungipor och läppsöm
MOUTH_L = (582, 570)
MOUTH_R = (745, 630)
CHIN_V = 180     # avstånd från läppsöm till hakans nederkant (längs normalen)
NECK_PIVOT = (600, 980)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def main():
    im = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(np.float32)
    H, W, _ = im.shape
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    lum = (r + g + b) / 3
    # sannolik bakgrund: ljus, lågmättad lavendel (blå > röd >= grön-ish)
    likely_bg = (lum > 175) & (b > r + 4) & (b > g + 4) & (np.abs(r - g) < 22)
    # skatta bakgrundsfärgen lokalt (kraftigt utjämnad bild av bg-pixlarna)
    bg_img = np.where(likely_bg[..., None], im, 0)
    w = likely_bg.astype(np.float32)
    global box
    def box(a, r, axis):
        c = np.cumsum(np.pad(a, [(r + 1, r) if i == axis else (0, 0) for i in range(a.ndim)], mode='edge'), axis=axis)
        n = a.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        return (hi - lo) / (2 * r + 1)

    def blur(a, rad):
        r = max(1, int(rad * 0.9))
        a = a.astype(np.float32)
        for _ in range(3):
            a = box(box(a, r, 0), r, 1)
        return a
    bg_est = np.stack([blur(bg_img[..., c], 60) for c in range(3)], -1)
    w_est = blur(w, 60)[..., None]
    mean_bg = im[likely_bg].mean(axis=0)
    bg_est = np.where(w_est > 0.02, bg_est / np.maximum(w_est, 1e-3), mean_bg)
    # alfa från färgavstånd till bakgrunden
    d = np.sqrt(((im - bg_est) ** 2).sum(-1))
    a = smoothstep(10, 46, d)
    # behåll bara den största sammanhängande förgrunden + fyll hål (glasögon, ansikte)
    from collections import deque
    fg = a > 0.5
    lab = np.zeros(fg.shape, np.int32)
    best, best_n, cur = 0, 0, 0
    for sy in range(0, H, 6):
        for sx in range(0, W, 6):
            if fg[sy, sx] and lab[sy, sx] == 0:
                cur += 1; n = 0
                q = deque([(sy, sx)]); lab[sy, sx] = cur
                while q:
                    y, x = q.popleft(); n += 1
                    for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                        if 0 <= yy < H and 0 <= xx < W and fg[yy, xx] and lab[yy, xx] == 0:
                            lab[yy, xx] = cur; q.append((yy, xx))
                if n > best_n:
                    best, best_n = cur, n
    main_fg = lab == best
    # hål = bakgrundspixlar som inte når bildkanten
    bgmask = ~main_fg
    reach = np.zeros_like(bgmask)
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if bgmask[y, x] and not reach[y, x]:
                reach[y, x] = True; q.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if bgmask[y, x] and not reach[y, x]:
                reach[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= yy < H and 0 <= xx < W and bgmask[yy, xx] and not reach[yy, xx]:
                reach[yy, xx] = True; q.append((yy, xx))
    holes = bgmask & ~reach
    # stora hål (t.ex. bakgrund sedd genom glasögonen) ska vara genomskinliga; små hål (ögonvitor) fylls
    hl = np.zeros(holes.shape, np.int32); hid = 0; big = np.zeros_like(holes)
    for sy, sx in zip(*np.where(holes)):
        if hl[sy, sx]:
            continue
        hid += 1; comp = [(sy, sx)]; hl[sy, sx] = hid; q = deque([(sy, sx)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < H and 0 <= xx < W and holes[yy, xx] and not hl[yy, xx]:
                    hl[yy, xx] = hid; q.append((yy, xx)); comp.append((yy, xx))
        if len(comp) > 1200:
            ys, xs = zip(*comp); big[list(ys), list(xs)] = True
    holes = holes & ~big
    # alfa: mjuk kant runt huvudkomponenten, hål fylls
    near = blur((main_fg | holes).astype(np.float32) * 255, 3) / 255
    alpha = np.where(holes, 1.0, np.minimum(a, np.clip(near * 1.6, 0, 1)))
    alpha = np.where(big, a * 0.15, alpha)
    # stramare kant i håret: ta bort svag lila slöja
    alpha = np.where(alpha < 0.98, smoothstep(0.12, 0.9, alpha), alpha)
    alpha = np.where(main_fg & (a > 0.98), 1.0, alpha)
    # ta bort lila ton i kantpixlar
    am = np.maximum(alpha[..., None], 1e-3)
    col = np.clip((im - (1 - alpha[..., None]) * bg_est) / am, 0, 255)
    col = np.where(alpha[..., None] > 0.97, im, col)
    opaque = (alpha > 0.95).astype(np.float32)
    den = blur(opaque, 5)
    prop = np.stack([blur(col[..., c] * opaque, 5) for c in range(3)], -1) / np.maximum(den[..., None], 1e-3)
    edge = (alpha < 0.95) & (den > 0.02)
    col = np.where(edge[..., None], prop * 0.9 + col * 0.1, col)

    # förläng tröjan: kopiera kantkolumnernas färg utåt där kanten är förgrund
    NW, NH = W + 2 * EXT_X, H + EXT_Y
    out = np.zeros((NH, NW, 4), np.float32)
    out[:H, EXT_X:EXT_X + W, :3] = col
    out[:H, EXT_X:EXT_X + W, 3] = alpha * 255
    for side in ('L', 'R'):
        xs = slice(EXT_X, EXT_X + 12) if side == 'L' else slice(EXT_X + W - 12, EXT_X + W)
        edge_a = np.median(out[:H, xs, 3], axis=1)
        rows = np.where(edge_a > 200)[0]
        if not len(rows):
            continue
        top = int(rows.min())
        edge_c = np.median(out[:H, xs, :3], axis=1)
        edge_c[:top + 8] = edge_c[min(H - 1, top + 8)]
        edge_c = np.stack([box(edge_c[:, c], 45, 0) for c in range(3)], -1)
        shirt = np.median(out[top + 60:H, xs, :3].reshape(-1, 3), axis=0)
        yy = np.arange(H, dtype=np.float32)
        cols = range(0, EXT_X) if side == 'L' else range(EXT_X + W, NW)
        for x in cols:
            dist = (EXT_X - x) if side == 'L' else (x - (EXT_X + W - 1))
            y_top = top + 0.32 * dist + 0.0009 * dist * dist      # axeln sluttar mjukt nedåt
            a_col = np.clip(yy - y_top + 0.5, 0, 1) * 255
            mix = smoothstep(0, 140, dist)
            c = edge_c * (1 - mix) + shirt[None, :] * mix
            c = c * (1 - 0.14 * dist / EXT_X)
            out[:H, x, :3] = c
            out[:H, x, 3] = a_col
    # förläng nedåt
    out[H:, :, :] = out[H - 1:H, :, :]

    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA').save(sys.argv[2])
    mouth = {
        'left': [MOUTH_L[0] + EXT_X, MOUTH_L[1]], 'right': [MOUTH_R[0] + EXT_X, MOUTH_R[1]],
        'chin_v': CHIN_V, 'pivot': [NECK_PIVOT[0] + EXT_X, NECK_PIVOT[1]],
        'size': [NW, NH], 'orig_offset': [EXT_X, 0], 'orig_size': [W, H],
    }
    json.dump(mouth, open(sys.argv[3], 'w'), indent=1)
    print('ok', NW, NH, 'förgrund', round(float((alpha > 0.5).mean()), 3))


if __name__ == '__main__':
    main()
