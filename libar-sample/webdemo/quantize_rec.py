# -*- coding: utf-8 -*-
"""rec_v4.onnx 경량화: int8 동적 양자화 + fp16 — 40 크롭에서 fp32와 예측 일치율 비교."""
import io, sys, random, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
SAMPLE = HERE.parent
OUT = io.open(HERE/"quant_result.txt", "w", encoding="utf-8")

# int8 — onnx 셰이프 추론이 한글 경로에서 실패 → ASCII 임시 경로에서 작업
import shutil, tempfile
TMP = Path(tempfile.gettempdir())/"libar_quant"; TMP.mkdir(exist_ok=True)
shutil.copy(HERE/"rec_v4.onnx", TMP/"rec_v4.onnx")
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic(str(TMP/"rec_v4.onnx"), str(TMP/"rec_v4_int8.onnx"), weight_type=QuantType.QInt8)
shutil.copy(TMP/"rec_v4_int8.onnx", HERE/"rec_v4_int8.onnx")
# fp16 기각: 변환은 되나 ORT SimplifiedLayerNormFusion가 삽입 Cast 이름 못 찾고 초기화 크래시
has_fp16 = False

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
def S(p): return ort.InferenceSession(str(HERE/p), so, providers=["CPUExecutionProvider"])
sessions = {"fp32": S("rec_v4.onnx"), "int8": S("rec_v4_int8.onnx")}
if has_fp16: sessions["fp16"] = S("rec_v4_fp16.onnx")

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

rows = []
for ln in io.open(SAMPLE/"real_rec_data_v3/meta_train.txt", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) >= 2: rows.append((p[0], p[1]))
random.seed(3); random.shuffle(rows); rows = rows[:40]

preds = {k: [] for k in sessions}
for f, gt in rows:
    img = cv2.imdecode(np.fromfile(str(SAMPLE/"real_rec_data_v3"/f), dtype=np.uint8), 1)
    if img is None: continue
    x = preprocess(img)
    for k, s in sessions.items():
        preds[k].append(decode(s.run(None, {s.get_inputs()[0].name: x})[0][0]))

for k in [k for k in sessions if k != "fp32"]:
    same = sum(a == b for a, b in zip(preds["fp32"], preds[k]))
    OUT.write(f"{k} vs fp32: {same}/{len(preds['fp32'])} 일치\n")
    for (f, gt), a, b in zip(rows, preds["fp32"], preds[k]):
        if a != b: OUT.write(f"  ≠ gt={gt!r} fp32={a!r} {k}={b!r}\n")
import os
for p in ["rec_v4.onnx", "rec_v4_int8.onnx", "rec_v4_fp16.onnx"]:
    fp = HERE/p
    if fp.exists(): OUT.write(f"{p}: {fp.stat().st_size/1e6:.1f}MB\n")
OUT.close(); print("done")
