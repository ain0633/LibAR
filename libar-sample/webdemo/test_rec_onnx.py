# -*- coding: utf-8 -*-
"""rec v4 ONNX 파리티 검증 — 실측 라벨 크롭(정답 있는 meta)으로 ONNX 디코드 정확도 확인.
전처리 = PaddleOCR RecResizeImg [3,48,320]: h=48 keep-ratio, 우측 0패딩, (x/255-0.5)/0.5, BGR CHW."""
import io, sys, json, unicodedata, random
import cv2, numpy as np
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
SAMPLE = HERE.parent

# ── charset: inference.yml PostProcess.character_dict (YAML 리스트 두 곳 중 뒤쪽) ──
chars, in_pp, in_dict = [], False, False
for ln in io.open(SAMPLE/"korean_lowres_v4_rec_infer/inference.yml", encoding="utf-8"):
    if ln.startswith("PostProcess:"): in_pp = True; continue
    if in_pp:
        if ln.strip() == "character_dict:": in_dict = True; continue
        if in_dict:
            if ln.startswith("  - ") or ln.startswith("- "):
                c = ln.rstrip("\n")[4:] if ln.startswith("  - ") else ln.rstrip("\n")[2:]
                if c.startswith("'") and c.endswith("'") and len(c) >= 2: c = c[1:-1].replace("''", "'")
                if c.startswith('"') and c.endswith('"') and len(c) >= 2: c = c[1:-1]
                chars.append(c)
            elif ln.strip() and not ln.startswith("    "): break
print(f"charset {len(chars)}자")

import onnxruntime as ort
sess = ort.InferenceSession(str(HERE/"rec_v4.onnx"), providers=["CPUExecutionProvider"])
inp = sess.get_inputs()[0]
print("입력:", inp.name, inp.shape)

def preprocess(img):
    h, w = img.shape[:2]
    tw = min(320, max(8, int(round(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32)
    pad[:, :tw] = r
    return pad.transpose(2, 0, 1)[None]

def decode(logits, charset):
    # charset 후보: [blank]+dict / [blank]+dict+[space]
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for i, t in enumerate(idx):
        if t != prev and t != 0:
            out.append(charset[t-1] if t-1 < len(charset) else "?")
        prev = t
    return unicodedata.normalize("NFC", "".join(out))

# ── 샘플: meta에서 pair 크롭 40개 ──
rows = []
for ln in io.open(SAMPLE/"real_rec_data_v3/meta_train.txt", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) >= 2: rows.append((p[0], p[1]))
random.seed(3); random.shuffle(rows); rows = rows[:40]

cs_space = chars + [" "]
hit = tot = 0
for f, gt in rows:
    img = cv2.imdecode(np.fromfile(str(SAMPLE/"real_rec_data_v3"/f), dtype=np.uint8), 1)
    if img is None: continue
    logits = sess.run(None, {inp.name: preprocess(img)})[0][0]   # (T, C)
    if tot == 0: print("출력 (T,C):", logits.shape, "| dict:", len(chars))
    txt = decode(logits, cs_space)
    gtn = unicodedata.normalize("NFC", gt)
    ok = txt == gtn
    hit += ok; tot += 1
    if not ok: print(f"  ✗ gt={gtn!r} pred={txt!r} ({f})")
print(f"\n정확 일치 {hit}/{tot} = {hit/tot*100:.0f}%")
