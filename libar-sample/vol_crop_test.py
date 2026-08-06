# -*- coding: utf-8 -*-
"""가설 검증: 권차 숫자 영역만 타이트 크롭 + 업스케일 → 재OCR 시 권차 정확도 상승?
   베이스라인(라벨 전체 OCR): 권차 정확도 35% (18/51)
   변형 A: 라벨 하단 45%만 크롭
   변형 B: A + 4배 업스케일(LANCZOS)
"""
import os, sys, json, re, time
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

GT = json.load(open(HERE/"shelf_4558.labels.json", encoding="utf-8"))
OCR_CACHE = json.load(open(HERE/"shelf_4558.dualocr.json", encoding="utf-8"))
for o in OCR_CACHE:
    x0, y0, x1, y1 = o["box"]; o["cx"] = (x0+x1)/2

from PIL import Image
bgr = cv2.cvtColor(np.array(Image.open(HERE/"shelf_4558.jpg").convert("RGB")), cv2.COLOR_RGB2BGR)
H, W = bgr.shape[:2]

from paddleocr import PaddleOCR
ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False)

def read_digits(crop):
    if crop.size == 0: return []
    res = ocr.predict(crop)
    if not res: return []
    texts = res[0].get("rec_texts", [])
    return [n for t in texts for n in re.findall(r"\d{1,3}", t)]

def vol_crop(box, upscale):
    x0, y0, x1, y1 = box; h = y1-y0; w = x1-x0
    # 라벨 하단 45% (권차 줄) + 좌우 12% 인셋(이웃 침범 방지)
    cy0 = y0 + int(h*0.55); cy1 = min(H, y1 + int(h*0.06))
    cx0 = x0 + int(w*0.12); cx1 = x1 - int(w*0.12)
    c = bgr[cy0:cy1, cx0:cx1]
    if upscale and c.size:
        c = cv2.resize(c, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)
    return c

results = {"A(하단크롭)": [], "B(크롭+4x)": []}
t0 = time.time()
for g in GT:
    o = min(OCR_CACHE, key=lambda o: abs(o["cx"]-g["x"]))
    exp = g["call_number"].split("-")[-1]
    for name, up in [("A(하단크롭)", False), ("B(크롭+4x)", True)]:
        cand = read_digits(vol_crop(o["box"], up))
        results[name].append((g["call_number"], exp, cand, exp in cand))
print(f"[OCR 완료] {time.time()-t0:.0f}s\n")

print(f"베이스라인(라벨 전체 OCR): 18/51 = 35.3%\n")
for name, rows in results.items():
    ok = sum(1 for *_, hit in rows if hit)
    print(f"=== 변형 {name}: {ok}/{len(rows)} = {ok/len(rows)*100:.1f}% ===")
    for cn, exp, cand, hit in rows:
        mark = "O" if hit else "X"
        print(f"  {mark} {cn:13} 기대 {exp:>3} → {cand}")
    print()
json.dump({k: [(c, e, cd, h) for c, e, cd, h in v] for k, v in results.items()},
          open(HERE/"vol_crop_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
