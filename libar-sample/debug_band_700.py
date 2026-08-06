# -*- coding: utf-8 -*-
"""700번대 검정 밴드 검출 진단: 스케일별 후보 밴드와 숫자 앵커 수."""
import sys, io
import cv2, numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

bgr = cv2.imdecode(np.fromfile("../대림데이터/700번대/KakaoTalk_20260708_164051931.jpg", dtype=np.uint8), 1)
H, W = bgr.shape[:2]

def black_mask(hsv):
    return (hsv[:, :, 1] < 60) & (hsv[:, :, 2] < 80)

def find_bands(small):
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    rowfrac = black_mask(hsv).mean(axis=1)
    thr = max(0.04, float(np.percentile(rowfrac, 90)) * 0.5)
    on = rowfrac > thr
    bands_, st, rejected = [], None, []
    for i, g in enumerate(list(on) + [False]):
        if g and st is None: st = i
        elif not g and st is not None:
            if bands_ and st - bands_[-1][1] < 12: bands_[-1] = (bands_[-1][0], i)
            elif 10 <= i - st <= 90: bands_.append((st, i))
            else: rejected.append((st, i, i - st))
            st = None
    return bands_, rejected, thr

def digit_blobs(by0, by1):
    bh = by1 - by0
    if bh < 8: return []
    hsvb = cv2.cvtColor(bgr[by0:by1], cv2.COLOR_BGR2HSV)
    bmask = black_mask(hsvb).astype(np.uint8)
    wmask = ((hsvb[:, :, 1] < 90) & (hsvb[:, :, 2] > 130)).astype(np.uint8)
    band_d = cv2.dilate(bmask, np.ones((9, 9), np.uint8), iterations=2)
    ncc, _, stats, cent = cv2.connectedComponentsWithStats((wmask & band_d), 8)
    out = []
    for i in range(1, ncc):
        x, y, w, h, area = stats[i]
        if 0.25*bh <= h <= 0.8*bh and 0.08*bh <= w <= 0.6*bh and area >= 0.02*bh*bh:
            out.append(int(cent[i][0]))
    return sorted(out)

for s in (1.0, 0.45, 0.35, 0.25):
    small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else bgr
    bands, rejected, thr = find_bands(small)
    full = [(int(a/s), int(b/s)) for a, b in bands]
    print(f"scale={s} thr={thr:.3f}")
    for (a, b) in full:
        print(f"  통과 밴드 {a}-{b} (h={b-a}) 앵커={len(digit_blobs(a, b))}")
    for (a, b, h) in rejected[:6]:
        print(f"  [길이컷] {int(a/s)}-{int(b/s)} (h_small={h})")
