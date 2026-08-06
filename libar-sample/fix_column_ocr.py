# -*- coding: utf-8 -*-
"""수정안 검증: spine 중앙만 타이트 크롭 + 토큰 x위치 필터로 이웃 스티커 배제.
   평가(GT 없이도 견고한 2지표):
     ① 카탈로그(59권) 실재 권차 적중 spine 수
     ② 권차 시퀀스의 정렬 일관성 (LIS 길이 / 적중 수) — 서가는 실제 거의 정렬 상태
   비교: 기존 tokens.json(구 크롭) vs 새 중앙크롭+x필터
"""
import os, sys, json, re, time
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

catalog = L.load_catalog(str(HERE/"books_4558.csv"))
VOLS = {r["_toks"][-1] for r in catalog}          # 실재 권차 집합
spines = json.load(open(HERE/"shelf_4558.tokens.json", encoding="utf-8"))
bgr = cv2.cvtColor(np.array(Image.open(HERE/"shelf_4558.jpg").convert("RGB")), cv2.COLOR_RGB2BGR)
H, W = bgr.shape[:2]

def lis_len(seq):
    if not seq: return 0
    L_ = [1]*len(seq)
    for i in range(len(seq)):
        for j in range(i):
            if seq[j] <= seq[i]: L_[i] = max(L_[i], L_[j]+1)
    return max(L_)

NOISE = re.compile(r"^(4?08|88|884|8|0|40|408)$")
def extract_vol(toks_bottom_first):
    """하단부터, 잡음(접두어 파편) 아닌 1~3자리 숫자 중 카탈로그 실재 권차 우선."""
    cands = []
    for t in toks_bottom_first:
        for n in re.findall(r"\d{1,3}", t):
            if NOISE.match(n): continue
            cands.append(n)
    for c in cands:
        if c in VOLS: return c, True
    return (cands[0], False) if cands else (None, False)

def evaluate(name, vol_list):
    hits = [v for v, ok in vol_list if v and ok]
    seq = [int(v) for v, ok in vol_list if v and ok]
    l = lis_len(seq)
    print(f"[{name}] 권차추출 {sum(1 for v,_ in vol_list if v)}/{len(vol_list)} · "
          f"카탈로그 적중 {len(hits)} · 고유 {len(set(hits))} · LIS {l}/{len(seq)} "
          f"(정렬일관성 {l/len(seq)*100 if seq else 0:.0f}%)")
    return hits

# ── 기존 방식 (tokens.json의 ctoks는 상단→하단 정렬이므로 뒤집어 하단우선) ──
old = []
for s in spines:
    v = extract_vol(list(reversed(s["toks"])))
    old.append(v)
evaluate("기존 크롭", old)

# ── 새 방식: 중앙 70% 크롭 + poly x필터 ──
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False)
new = []
t0 = time.time()
detail = []
for s in spines:
    x0, y0, x1, y1 = s["box"]; h = y1-y0; w = x1-x0
    cx0 = x0 + int(w*0.15); cx1 = x1 - int(w*0.15)
    cy0 = y0 + int(h*0.72); cy1 = min(H, y1)
    crop = bgr[cy0:cy1, cx0:cx1]
    if crop.size == 0:
        new.append((None, False)); continue
    if crop.shape[0] < 120 or crop.shape[1] < 120:
        crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
    res = ocr.predict(crop)
    toks = []
    if res:
        r = res[0]
        cw = crop.shape[1]
        for t, p in zip(r.get("rec_texts", []), r.get("rec_polys", [])):
            xs = [q[0] for q in p]; ys = [q[1] for q in p]
            xc = sum(xs)/len(xs)
            if 0.10*cw <= xc <= 0.90*cw:          # 중앙 컬럼만
                toks.append((sum(ys)/len(ys), L.nn(t)))
    toks.sort(key=lambda z: -z[0])                 # 하단 우선
    v = extract_vol([t for _, t in toks if t])
    new.append(v)
    detail.append({"box": s["box"], "toks": [t for _, t in toks], "vol": v[0], "in_cat": v[1]})
print(f"(재OCR {time.time()-t0:.0f}s)")
evaluate("중앙크롭+x필터", new)

json.dump(detail, open(HERE/"fix_column_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n--- 새 방식 spine별 권차 ---")
print(" ".join((v or "?") + ("" if ok else "*") for v, ok in new))
print("(*=카탈로그에 없는 값, ?=추출실패)")
