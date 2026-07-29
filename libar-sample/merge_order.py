# -*- coding: utf-8 -*-
"""순서 추론 자동 정답(order_labels_*.json) → 학습쌍 병합 (tag=order).
정답 생성 = 위치+카탈로그(모델 무관, 유일 후보 게이트 100% 실측) — 선택 편향 없음.
줄 분해·짝짓기 게이트는 merge_labels(human)와 동일 기준.
사용: py -3.12 merge_order.py
"""
import io, json, glob, re, zipfile, difflib, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE/"real_rec_data_order"
(OUT/"crops").mkdir(parents=True, exist_ok=True)

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
rsess = ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
dsess = ort.InferenceSession(str(HERE/"webdemo/det_mobile.onnx"), so, providers=["CPUExecutionProvider"])
rin, din = rsess.get_inputs()[0].name, dsess.get_inputs()[0].name
chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
def nfc(s): return unicodedata.normalize("NFC", str(s))
def sim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()

def rec_line(img):
    h, w = img.shape[:2]
    if h < 4 or w < 4: return ""
    tw = min(320, max(8, int(np.ceil(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32); pad[:, :tw] = r
    logits = rsess.run(None, {rin: pad.transpose(2, 0, 1)[None]})[0][0]
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for t in idx:
        if t != prev and t != 0: out.append(chars[t-1] if t-1 < len(chars) else "?")
        prev = t
    return nfc("".join(out))

def det_lines(img):
    h, w = img.shape[:2]
    sc = min(1.0, 960/max(h, w))
    nh, nw = max(32, int(round(h*sc/32))*32), max(32, int(round(w*sc/32))*32)
    rs = cv2.resize(img, (nw, nh)).astype(np.float32)/255.0
    rs = (rs - MEAN)/STD
    prob = dsess.run(None, {din: rs.transpose(2, 0, 1)[None]})[0][0, 0]
    n, lab, stats, _ = cv2.connectedComponentsWithStats((prob > 0.3).astype(np.uint8), 8)
    out = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if area < 12 or bw < 4 or bh < 4: continue
        if float(prob[lab == i].mean()) < 0.6: continue
        px, py = int(bh*0.45), int(bh*0.28)
        cy0, cy1 = int(max(0, y-py)*h/nh), int(np.ceil(min(nh, y+bh+py)*h/nh))
        cx0, cx1 = int(max(0, x-px)*w/nw), int(np.ceil(min(nw, x+bw+px)*w/nw))
        out.append((cy0, img[cy0:cy1, cx0:cx1]))
    return sorted(out, key=lambda t: t[0])

meta_path = OUT/"meta_order.txt"
have = set()
if meta_path.exists():
    for ln in io.open(meta_path, encoding="utf-8"):
        have.add(ln.split("\t")[0])
meta = io.open(meta_path, "a", encoding="utf-8")
n_pair = 0
for jf in sorted(glob.glob(str(HERE/"order_labels_*.json"))):
    for r in json.load(io.open(jf, encoding="utf-8")):
        ztag, fname, call = r["ztag"], r["file"], nfc(r["call"])
        try:
            with zipfile.ZipFile(HERE/f"수집조각/libar_crops_{ztag}.zip") as z:
                raw = z.read(fname)
        except Exception: continue
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
        if img is None: continue
        big = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
        cands = [p.split("=")[0] for p in call.split("-")[:2]]
        cands = [p for p in cands if len(p) >= 2]
        for li, (y0, line) in enumerate(det_lines(big)):
            read = rec_line(line)
            if len(read) < 2: continue
            if re.match(r"^[vcVC]\.?\d", read): continue
            best = max(cands, key=lambda p: sim(read, p), default=None)
            s = sim(read, best) if best else 0
            if best is None or s < 0.35 or (len(read) < 3 and s < 0.6): continue
            digits = sum(c.isdigit() for c in read) / len(read)
            if re.search(r"[가-힣]", best) and digits > 0.7: continue
            if best[0].isdigit() and "." in best and "." not in read and s < 0.7: continue
            name = f"crops/{ztag}_{Path(fname).stem}_{li}_{re.sub(r'[^0-9A-Za-z가-힣.]', '', best)}.jpg"
            if name in have: continue
            cv2.imencode(".jpg", line, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(str(OUT/name))
            meta.write(f"{name}\t{best}\torder\n")
            have.add(name); n_pair += 1
meta.close()
print(f"[병합] order 학습쌍 {n_pair}줄 → {OUT}/meta_order.txt")
