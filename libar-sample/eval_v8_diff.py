# -*- coding: utf-8 -*-
"""v8 승패 내역: v8val 101줄에서 v4↔v8 판독이 갈린 항목 + 해상도 분포."""
import io, json, unicodedata
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent
def nfc(s): return unicodedata.normalize("NFC", str(s)).replace(" ", "")

items = []
for l in io.open(HERE/"real_rec_data_v8/meta_v8_val.txt", encoding="utf-8").read().splitlines():
    if not l.strip(): continue
    f, gt, g = l.split("\t")
    items.append(("real_rec_data_v8/"+f, gt, g))

import onnxruntime as ort
so = ort.SessionOptions(); so.log_severity_level = 3
rsess = ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"])
rin = rsess.get_inputs()[0].name
chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))
def rec_v4(img):
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

from paddleocr import TextRecognition
v8 = TextRecognition(model_dir="korean_lowres_v8_rec_infer", model_name="korean_PP-OCRv5_mobile_rec")
def rec_v8(img):
    r = v8.predict(img)
    return nfc(r[0]["rec_text"]) if r else ""

wins, losses, hs = [], [], []
for f, gt, tag in items:
    img = cv2.imdecode(np.fromfile(str(HERE/f), np.uint8), 1)
    hs.append(img.shape[0])
    g = nfc(gt); a, b = rec_v4(img), rec_v8(img)
    if (a == g) != (b == g):
        (wins if b == g else losses).append((f.split("/")[-1], img.shape[0], tag, g, a, b))

out = io.open(HERE/"eval_v8_diff.txt", "w", encoding="utf-8")
out.write(f"높이 중앙값 {int(np.median(hs))}px / v8 승 {len(wins)} / v8 패 {len(losses)}\n\n")
for title, rows in [("v8만 맞음", wins), ("v8만 틀림", losses)]:
    out.write(f"== {title} ({len(rows)}) ==\n")
    for f, h, tag, g, a, b in rows:
        out.write(f"{h:4d}px {tag:6s} GT={g}  v4={a}  v8={b}  [{f}]\n")
    out.write("\n")
out.close()
print("done -> eval_v8_diff.txt")
