# -*- coding: utf-8 -*-
"""시각 진단: v3 박스 → 크롭/격리 라벨/줄 크롭을 타일로 저장."""
import io, json
import cv2, numpy as np
from pathlib import Path
def isolate_label(crop):
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:,:,1] < 70) & (hsv[:,:,2] > 135)).astype(np.uint8)
    def longest(frac, thr):
        best = (0, 0); cur = None
        for i, g in enumerate(list(frac > thr) + [False]):
            if g and cur is None: cur = i
            if not g and cur is not None:
                if i-cur > best[1]-best[0]: best = (cur, i)
                cur = None
        return best
    r0, r1 = longest(mask.mean(axis=1), 0.4)
    if r1-r0 < 8: return crop, mask
    c0, c1 = longest(mask[r0:r1].mean(axis=0), 0.5)
    if c1-c0 < 8: return crop[r0:r1], mask[r0:r1]
    return crop[r0:r1, c0:c1], mask[r0:r1, c0:c1]

def split_trim_lines(label):
    g = cv2.cvtColor(label, cv2.COLOR_BGR2GRAY)
    thr = cv2.threshold(g, 0, 255, cv2.THRESH_OTSU)[0]
    ink = g < thr
    frac = ink.mean(axis=1)
    segs, start = [], None
    h = len(frac)
    for y in range(h+1):
        on = y < h and frac[y] > 0.06
        if on and start is None: start = y
        if not on and start is not None:
            if segs and start - segs[-1][1] <= 2: segs[-1][1] = y
            else: segs.append([start, y])
            start = None
    out = []
    minh = max(6, int(h*0.10))
    for a, b in segs:
        if b-a < minh: continue
        col = ink[a:b].mean(axis=0)
        xs = np.where(col > 0.04)[0]
        if len(xs) == 0: continue
        x0, x1 = max(0, xs[0]-2), min(label.shape[1], xs[-1]+3)
        if x1-x0 < 4: continue
        pad = max(1, (b-a)//8)
        out.append(label[max(0,a-pad):min(h,b+pad), x0:x1])
    return out

HERE = Path(__file__).parent
img = cv2.imdecode(np.fromfile(str(HERE/"demo/demo1.jpg"), dtype=np.uint8), 1)
H, W = img.shape[:2]

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
ysess = ort.InferenceSession(str(HERE.parent/"call_label_yolo3/best.onnx"), so,
                             providers=["CPUExecutionProvider"])
r_ = 1280/max(H, W)
canvas = np.full((1280, 1280, 3), 114, np.uint8)
canvas[:int(H*r_), :int(W*r_)] = cv2.resize(img, (int(W*r_), int(H*r_)))
x_ = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)/255.0
out_ = ysess.run(None, {"images": x_})[0][0]
boxes = sorted([tuple(b[:4]/r_) for b in out_ if b[4] >= 0.25])[:12]

tiles = []
for (x0, y0, x1, y1) in boxes:
    x0, y0, x1, y1 = max(0,int(x0)), max(0,int(y0)), min(W,int(x1)), min(H,int(y1))
    crop = img[y0:y1, x0:x1]
    label, _ = isolate_label(crop)
    big = cv2.resize(label, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
    lines = split_trim_lines(big)
    col = [cv2.copyMakeBorder(cv2.resize(crop, (140, int(crop.shape[0]*140/crop.shape[1]))),
                              2,2,2,2, cv2.BORDER_CONSTANT, value=(0,0,255))]
    col.append(cv2.copyMakeBorder(cv2.resize(label, (140, max(20,int(label.shape[0]*140/label.shape[1])))),
                              2,2,2,2, cv2.BORDER_CONSTANT, value=(0,255,0)))
    for l in lines[:4]:
        col.append(cv2.copyMakeBorder(cv2.resize(l, (140, max(12,int(l.shape[0]*140/l.shape[1])))),
                              2,2,2,2, cv2.BORDER_CONSTANT, value=(255,0,0)))
    h = sum(c.shape[0] for c in col)
    tile = np.full((h, 148, 3), 255, np.uint8)
    y = 0
    for c in col:
        tile[y:y+c.shape[0], :c.shape[1]] = c; y += c.shape[0]
    tiles.append(tile)
mh = max(t.shape[0] for t in tiles)
out = np.full((mh, sum(t.shape[1] for t in tiles)+len(tiles)*4, 3), 255, np.uint8)
x = 0
for t in tiles:
    out[:t.shape[0], x:x+t.shape[1]] = t; x += t.shape[1]+4
cv2.imencode('.jpg', out)[1].tofile(str(HERE/"debug_crops.jpg"))
print("saved debug_crops.jpg")
