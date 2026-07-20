# -*- coding: utf-8 -*-
"""fp16(배포물) vs fp32 전체 평가셋 정확도 감사 — 변환 당시 표본 40개(36/40)의 전수 확장.
평가셋 = close 27 + low 43 + human76 + v8val 101 = 247줄 (공정 현장 val 전부).
사용: py -3.12 eval_fp16_full.py
"""
import io, json, unicodedata
import cv2, numpy as np
from pathlib import Path
import onnxruntime as ort

HERE = Path(__file__).parent
def nfc(s): return unicodedata.normalize("NFC", str(s)).replace(" ", "")

sets = {"close": [], "low": [], "human76": [], "v8val": []}
for l in io.open(HERE/"real_rec_data_v3/meta_val.txt", encoding="utf-8").read().splitlines():
    f, gt, g = l.split("\t")
    sets["close" if g == "close" else "low"].append(("real_rec_data_v3/"+f, gt))
for l in io.open(HERE/"real_rec_data_human/meta_human_val.txt", encoding="utf-8").read().splitlines():
    f, gt, g = l.split("\t")
    sets["human76"].append(("real_rec_data_human/"+f, gt))
for l in io.open(HERE/"real_rec_data_v8/meta_v8_val.txt", encoding="utf-8").read().splitlines():
    if not l.strip(): continue
    f, gt, g = l.split("\t")
    sets["v8val"].append(("real_rec_data_v8/"+f, gt))

chars = json.load(io.open(HERE/"webdemo/rec_charset.json", encoding="utf-8"))
so = ort.SessionOptions(); so.log_severity_level = 3
so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC   # 앱과 동일 (fp16 all=크래시)
S = {"fp32": ort.InferenceSession(str(HERE/"webdemo/rec_v4.onnx"), so, providers=["CPUExecutionProvider"]),
     "fp16": ort.InferenceSession(str(HERE/"webdemo/rec_v4_fp16.onnx"), so, providers=["CPUExecutionProvider"])}

def rec(sess, img):
    h, w = img.shape[:2]
    if h < 4 or w < 4: return ""
    tw = min(320, max(8, int(np.ceil(48*w/h))))
    r = cv2.resize(img, (tw, 48)).astype(np.float32)
    r = (r/255.0 - 0.5)/0.5
    pad = np.zeros((48, 320, 3), np.float32); pad[:, :tw] = r
    logits = sess.run(None, {sess.get_inputs()[0].name: pad.transpose(2, 0, 1)[None]})[0][0]
    idx = logits.argmax(axis=1)
    out, prev = [], -1
    for t in idx:
        if t != prev and t != 0: out.append(chars[t-1] if t-1 < len(chars) else "?")
        prev = t
    return nfc("".join(out))

print(f"{'그룹':8s} {'fp32':>8s} {'fp16':>8s}  출력차이(정오 무관)")
tot = {"fp32": 0, "fp16": 0, "n": 0, "diff": 0}
diffs = []
for g, items in sets.items():
    a = b = d = 0
    for f, gt in items:
        img = cv2.imdecode(np.fromfile(str(HERE/f), np.uint8), 1)
        r32, r16 = rec(S["fp32"], img), rec(S["fp16"], img)
        gtn = nfc(gt)
        a += r32 == gtn; b += r16 == gtn
        if r32 != r16: d += 1; diffs.append((g, gtn, r32, r16))
    tot["fp32"] += a; tot["fp16"] += b; tot["n"] += len(items); tot["diff"] += d
    print(f"{g:8s} {a:3d}/{len(items):<3d} {b:4d}/{len(items):<3d}  {d}건")
print(f"{'합계':8s} {tot['fp32']:3d}/{tot['n']:<3d} {tot['fp16']:4d}/{tot['n']:<3d}  {tot['diff']}건")
out = io.open(HERE/"eval_fp16_full.txt", "w", encoding="utf-8")
out.write(f"fp32 {tot['fp32']}/{tot['n']} vs fp16 {tot['fp16']}/{tot['n']} · 출력 상이 {tot['diff']}건\n\n")
for g, gt, r32, r16 in diffs: out.write(f"[{g}] GT={gt}  fp32={r32}  fp16={r16}\n")
out.close()
print("상세 -> eval_fp16_full.txt")
