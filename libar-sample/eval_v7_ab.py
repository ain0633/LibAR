# -*- coding: utf-8 -*-
"""v7 로컬 A/B: val 3분할(close/low/field)을 v4(배포 onnx)와 v6(paddle 추론)로 채점.
human val = 공정 평가셋 — human이 오르고 close·low가 안 떨어져야 채택.
사용: py -3.12 eval_v7_ab.py   (libar-sample 안에서 — paddle 한글 경로 함정)
"""
import io, json, unicodedata, sys
import cv2, numpy as np
from pathlib import Path

HERE = Path(__file__).parent

def nfc(s): return unicodedata.normalize("NFC", str(s)).replace(" ", "")

# ── val 3분할 로드 ──
sets = {"close": [], "low": [], "human": []}
for l in io.open(HERE/"real_rec_data_v3/meta_val.txt", encoding="utf-8").read().splitlines():
    f, gt, g = l.split("\t")
    sets["close" if g == "close" else "low"].append(("real_rec_data_v3/"+f, gt))
for l in io.open(HERE/"real_rec_data_human/meta_human_val.txt", encoding="utf-8").read().splitlines():
    f, gt, g = l.split("\t")
    sets["human"].append(("real_rec_data_human/"+f, gt))

imgs = {}
for g, items in sets.items():
    for f, gt in items:
        imgs[f] = cv2.imdecode(np.fromfile(str(HERE/f), np.uint8), 1)

# ── v4: 배포 onnx (변환기와 동일 하니스) ──
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

# ── v6: paddle 추론 (rec 단독) ──
from paddleocr import TextRecognition
# 폴더명의 'v7'을 paddlex가 PP-OCRv6으로 오추론 — 모델명 명시 필수
v7 = TextRecognition(model_dir="korean_lowres_v7_rec_infer", model_name="korean_PP-OCRv5_mobile_rec")
def rec_v7(img):
    r = v7.predict(img)
    return nfc(r[0]["rec_text"]) if r else ""

print("그룹      v4          v7")
res = {}
for g, items in sets.items():
    a = sum(1 for f, gt in items if rec_v4(imgs[f]) == nfc(gt))
    b = sum(1 for f, gt in items if rec_v7(imgs[f]) == nfc(gt))
    res[g] = (a, b, len(items))
    print(f"{g:8s} {a:3d}/{len(items):<3d}    {b:3d}/{len(items):<3d}   {'▲' if b > a else '▼' if b < a else '='}")

ok = res["human"][1] > res["human"][0] and res["close"][1] >= res["close"][0] and res["low"][1] >= res["low"][0]
print("판정 1차:", "통과 — human 상승·close/low 유지" if ok else "게이트 미달 (v5와 동일 잣대)")
