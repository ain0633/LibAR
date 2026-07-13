# -*- coding: utf-8 -*-
"""파리티: 같은 크롭에 Paddle TextRecognition vs ONNX — 예측이 서로 같은지(변환 무결성)."""
import io, sys, json, unicodedata, random
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
SAMPLE = HERE.parent
OUT = io.open(HERE/"parity_result.txt", "w", encoding="utf-8")

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
cs = chars + [" "]

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
sess = ort.InferenceSession(str(HERE/"rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
iname = sess.get_inputs()[0].name

def preprocess(img):
    h, w = img.shape[:2]
    tw = min(320, max(8, int(np.ceil(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32)
    pad[:, :tw] = r
    return pad.transpose(2, 0, 1)[None]

def decode(logits):
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for t in idx:
        if t != prev and t != 0: out.append(cs[t-1] if t-1 < len(cs) else "?")
        prev = t
    return unicodedata.normalize("NFC", "".join(out))

import os
os.chdir(SAMPLE)   # Paddle C++ 로더가 한글 절대경로를 못 읽음 — 상대경로로
from paddleocr import TextRecognition
rec = TextRecognition(model_name="korean_PP-OCRv5_mobile_rec",
                      model_dir="korean_lowres_v4_rec_infer")

rows = []
for ln in io.open(SAMPLE/"real_rec_data_v3/meta_train.txt", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) >= 2: rows.append((p[0], p[1]))
random.seed(3); random.shuffle(rows); rows = rows[:40]

same = tot = 0
for f, gt in rows:
    img = cv2.imdecode(np.fromfile(str(SAMPLE/"real_rec_data_v3"/f), dtype=np.uint8), 1)
    if img is None: continue
    o_txt = decode(sess.run(None, {iname: preprocess(img)})[0][0])
    p_res = rec.predict(img)
    p_txt = unicodedata.normalize("NFC", p_res[0]["rec_text"]) if p_res else ""
    eq = o_txt == p_txt
    same += eq; tot += 1
    mark = "=" if eq else "≠"
    OUT.write(f"{mark} gt={gt!r:20s} paddle={p_txt!r:20s} onnx={o_txt!r}\n")
OUT.write(f"\n일치 {same}/{tot}\n")
OUT.close()
print("done")
