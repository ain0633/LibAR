# -*- coding: utf-8 -*-
"""밴드 선택 회귀 확인 — daelim_closeup.py의 검출부와 동일 로직 (OCR 없이)."""
import sys, io
import cv2, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HUES = {"파랑": (90, 135), "초록": (35, 85), "노랑": (18, 35),
        "보라": (135, 168), "빨강": [(0, 12), (168, 180)], "검정": None}

def hue_mask(hsv, hue):
    rng = HUES[hue]
    if rng is None:
        return hsv[:, :, 2] < 60
    if isinstance(rng, list):
        hm = np.zeros(hsv.shape[:2], bool)
        for h0, h1 in rng: hm |= (hsv[:, :, 0] >= h0) & (hsv[:, :, 0] <= h1)
    else:
        hm = (hsv[:, :, 0] >= rng[0]) & (hsv[:, :, 0] <= rng[1])
    return hm & (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 60)

def find_bands(small, hue):
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    rowfrac = hue_mask(hsv, hue).mean(axis=1)
    thr = max(0.04, float(np.percentile(rowfrac, 90)) * 0.5)
    on = rowfrac > thr
    bands_, st = [], None
    for i, g in enumerate(list(on) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            if bands_ and st - bands_[-1][1] < 12: bands_[-1] = (bands_[-1][0], i)
            elif 10 <= i - st <= 90: bands_.append((st, i))
            st = None
    return [b for b in bands_ if 10 <= b[1]-b[0] <= 110]

def digit_blobs(bgr, by0, by1, hue):
    bh = by1 - by0
    if bh < 8: return []
    hsvb = cv2.cvtColor(bgr[by0:by1], cv2.COLOR_BGR2HSV)
    bmask = hue_mask(hsvb, hue).astype(np.uint8)
    band_d = cv2.dilate(bmask, np.ones((9, 9), np.uint8), iterations=2)
    if HUES[hue] is None:
        vals = hsvb[:, :, 2][band_d.astype(bool)]
        otsu = cv2.threshold(vals.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0] if vals.size else 110
        vthr = max(100, int(otsu))
    else:
        vthr = 130
    wmask = ((hsvb[:, :, 1] < 90) & (hsvb[:, :, 2] > vthr)).astype(np.uint8)
    ncc, _, stats, cent = cv2.connectedComponentsWithStats((wmask & band_d), 8)
    out = []
    for i in range(1, ncc):
        x, y, w, h, area = stats[i]
        if 0.25*bh <= h <= 0.8*bh and 0.08*bh <= w <= 0.6*bh and area >= 0.02*bh*bh:
            out.append(float(cent[i][0]))
    out.sort()
    return [d for j, d in enumerate(out) if j == 0 or d-out[j-1] >= bh*0.25]

def validate(bgr, bands_o, hue):
    bd = {b: digit_blobs(bgr, *b, hue) for b in bands_o}
    ok = [b for b in bands_o if len(bd[b]) >= 3 and b[0] >= (b[1]-b[0])]
    if ok:
        hmax = max(b-a for a, b in ok)
        ok = [b for b in ok if b[1]-b[0] >= hmax*0.3]
    return ok, bd

PHOTOS = [("800광각", "../대림데이터/KakaoTalk_20260707_135237882.jpg"),
          ("800근접", "../대림데이터/KakaoTalk_20260707_184409459.jpg"),
          ("600근접", "../대림데이터/600번대/KakaoTalk_20260708_163804413.jpg"),
          ("700근접", "../대림데이터/700번대/KakaoTalk_20260708_164051931.jpg")]

for name, path in PHOTOS:
    bgr = cv2.imdecode(np.fromfile(path, dtype=np.uint8), 1)
    best = (None, None, [], {}, -1)
    for hue in HUES:
        for s in (1.0, 0.45, 0.35, 0.25):
            small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else bgr
            cand = [(int(a/s), int(b/s)) for a, b in find_bands(small, hue)]
            ok, bd = validate(bgr, cand, hue)
            score = sum(len(bd[b]) for b in ok)
            if score > best[4]: best = (hue, s, ok, bd, score)
    hue_sel, scale, bands, band_digits, score = best
    if hue_sel and HUES[hue_sel] is None:  # 하단 트리밍
        tb = []
        for (a, b) in bands:
            hsvb = cv2.cvtColor(bgr[a:b], cv2.COLOR_BGR2HSV)
            wrows = ((hsvb[:, :, 1] < 90) & (hsvb[:, :, 2] > 110)).sum(axis=1)
            nz = np.where(wrows > bgr.shape[1] * 0.005)[0]
            b2 = min(b, max(a + 20, a + int(nz[-1]) + 8)) if len(nz) else b
            tb.append((a, b2))
        bands = tb
        band_digits = {nb: digit_blobs(bgr, *nb, hue_sel) for nb in bands}
    print(f"{name}: {hue_sel} scale={scale} 밴드 {[(b, len(band_digits[b])) for b in bands]}")
