# -*- coding: utf-8 -*-
"""fp16 변환 + 최적화 레벨 낮춰 세션 생성 → fp32 파리티 (int8 기각 후 재도전)."""
import io, sys, random, unicodedata, shutil, tempfile
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
SAMPLE = HERE.parent
OUT = io.open(HERE/"fp16_result.txt", "w", encoding="utf-8")

TMP = Path(tempfile.gettempdir())/"libar_quant"; TMP.mkdir(exist_ok=True)
import onnx
from onnxconverter_common import float16
m = onnx.load(str(TMP/"rec_v4.onnx"))
m16 = float16.convert_float_to_float16(m, keep_io_types=True)
onnx.save(m16, str(TMP/"rec_v4_fp16.onnx"))
shutil.copy(TMP/"rec_v4_fp16.onnx", HERE/"rec_v4_fp16.onnx")

import onnxruntime as ort
res = {}
for lvl_name, lvl in [("disable", ort.GraphOptimizationLevel.ORT_DISABLE_ALL),
                      ("basic", ort.GraphOptimizationLevel.ORT_ENABLE_BASIC)]:
    so = ort.SessionOptions(); so.log_severity_level = 3
    so.graph_optimization_level = lvl
    try:
        res[lvl_name] = ort.InferenceSession(str(HERE/"rec_v4_fp16.onnx"), so,
                                             providers=["CPUExecutionProvider"])
        OUT.write(f"fp16 세션 OK (opt={lvl_name})\n")
    except Exception as e:
        OUT.write(f"fp16 세션 실패 (opt={lvl_name}): {str(e)[:100]}\n")
sess16 = res.get("basic") or res.get("disable")
if sess16 is None:
    OUT.write("fp16 전면 기각\n"); OUT.close(); sys.exit()

so = ort.SessionOptions(); so.log_severity_level = 3
sess32 = ort.InferenceSession(str(HERE/"rec_v4.onnx"), so, providers=["CPUExecutionProvider"])

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

same = tot = 0
for f, gt in rows:
    img = cv2.imdecode(np.fromfile(str(SAMPLE/"real_rec_data_v3"/f), dtype=np.uint8), 1)
    if img is None: continue
    x = preprocess(img)
    a = decode(sess32.run(None, {sess32.get_inputs()[0].name: x})[0][0])
    b = decode(sess16.run(None, {sess16.get_inputs()[0].name: x})[0][0])
    same += a == b; tot += 1
    if a != b: OUT.write(f"  ≠ gt={gt!r} fp32={a!r} fp16={b!r}\n")
OUT.write(f"fp16 vs fp32: {same}/{tot} 일치 · 크기 {(HERE/'rec_v4_fp16.onnx').stat().st_size/1e6:.1f}MB\n")
OUT.close(); print("done")
