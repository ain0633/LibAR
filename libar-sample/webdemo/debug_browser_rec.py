# -*- coding: utf-8 -*-
"""브라우저 인식 경로의 파이썬 재현 — demo1 박스에서 줄분할→rec을 돌려 실패 원인 진단.
비교축: (A) 현행 = 박스 원본 크기 그대로 줄분할→rec (B) ×3 업스케일 후 (C) 파이프라인 실측 read."""
import io, sys, json, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
OUT = io.open(HERE/"debug_rec.txt", "w", encoding="utf-8")

chars = json.load(io.open(HERE/"rec_charset.json", encoding="utf-8"))  # 마지막이 공백
import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
sess = ort.InferenceSession(str(HERE/"rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
iname = sess.get_inputs()[0].name

def rec_line(img):
    h, w = img.shape[:2]
    tw = min(320, max(8, int(np.ceil(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32); pad[:, :tw] = r
    logits = sess.run(None, {iname: pad.transpose(2, 0, 1)[None]})[0][0]
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for t in idx:
        if t != prev and t != 0: out.append(chars[t-1] if t-1 < len(chars) else "?")
        prev = t
    return unicodedata.normalize("NFC", "".join(out))

def split_lines(gray):  # libar_rec.js splitLines와 동일 (Otsu + 행 잉크 비율)
    h, w = gray.shape
    thr, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)[0], None
    frac = (gray < thr).mean(axis=1)
    segs, start = [], None
    for y in range(h+1):
        on = y < h and frac[y] > 0.05
        if on and start is None: start = y
        if not on and start is not None:
            if segs and start - segs[-1][1] <= 2: segs[-1][1] = y
            else: segs.append([start, y])
            start = None
    out = [s for s in segs if s[1]-s[0] >= 6]
    return out if out else [[0, h]]

img = cv2.imdecode(np.fromfile(str(HERE/"demo/demo1.jpg"), dtype=np.uint8), 1)  # 한글 경로
H, W = img.shape[:2]
# 박스는 브라우저와 동일하게 v3 ONNX에서 (demo1.json 박스는 v2 책등 기둥이라 다름)
ysess = ort.InferenceSession(str(HERE.parent/"call_label_yolo3/best.onnx"), so,
                             providers=["CPUExecutionProvider"])
r_ = 1280/max(H, W)
canvas = np.full((1280, 1280, 3), 114, np.uint8)
canvas[:int(H*r_), :int(W*r_)] = cv2.resize(img, (int(W*r_), int(H*r_)))
x_ = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)/255.0
out_ = ysess.run(None, {"images": x_})[0][0]
pipe = json.load(io.open(HERE/"demo/demo1.json", encoding="utf-8"))
def near(b):  # 가장 겹치는 파이프라인 행 (실측 read 비교용)
    cx, cy = (b[0]+b[2])/2, (b[1]+b[3])/2
    best = min(pipe, key=lambda p: abs((p["box"][0]+p["box"][2])/2 - cx) + abs((p["box"][1]+p["box"][3])/2 - cy))
    return best
rows = [{"box": list((b[:4]/r_).astype(float)), "v3": True} for b in out_ if b[4] >= 0.25]
rows = [{**near(z["box"]), "box": z["box"]} for z in rows]

n_show = 0
for r in rows:
    if n_show >= 25: break
    x0, y0, x1, y1 = [int(v) for v in r["box"]]
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(H, y1)
    if x1-x0 < 8 or y1-y0 < 8: continue
    crop = img[y0:y1, x0:x1]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # (A) 현행
    ra = [rec_line(crop[a:b]) for a, b in split_lines(gray)]
    # (B) ×3 업스케일 후 분할·rec
    big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
    gb = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    rb = [rec_line(big[a:b]) for a, b in split_lines(gb)]
    OUT.write(f"box {x0},{y0} {x1-x0}x{y1-y0} | 실측read={r['read']!r} call={r['call']}\n")
    OUT.write(f"   A(현행)={' / '.join(ra)!r}\n   B(x3)  ={' / '.join(rb)!r}\n")
    n_show += 1
OUT.close(); print("done")
