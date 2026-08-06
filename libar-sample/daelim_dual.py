# -*- coding: utf-8 -*-
"""대림 이중 인식 — 기존 청구기호 결과(daelim_82.json)에 '제목 복구' 패스 추가.
   제목 기둥 = 라벨 박스 위 세로 영역(행 간격으로 높이 추정) → 90°회전 OCR → 456권 제목 퍼지 매칭.
   결합: 청구기호 매칭 유지 + 미매칭은 제목으로 복구(이중확정 표기)."""
import os, sys, json, re, csv, time, difflib, unicodedata
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

SRC = HERE.parent/"대림데이터"/"KakaoTalk_20260707_135237882.jpg"
RES = HERE.parent/"대림데이터"/"results"/"daelim_82.json"

def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()

cat = []
for r in csv.DictReader(open(HERE/"daelim_catalog.csv", encoding="utf-8-sig")):
    main = r["title"].split(":")[0].strip()
    cat.append({"call": r["call_number"], "t": ntitle(main), "title": main})

def match_title(text, thr=0.55):
    t = ntitle(text)
    if len(t) < 3: return None, 0.0
    best, bs = None, 0.0
    for c in cat:
        if not c["t"]: continue
        lm = difflib.SequenceMatcher(None, t, c["t"]).find_longest_match(0, len(t), 0, len(c["t"]))
        p = lm.size/min(len(t), len(c["t"]))
        s = 0.6*p + 0.4*difflib.SequenceMatcher(None, t, c["t"]).ratio()
        if s > bs: best, bs = c, s
    return (best, bs) if bs >= thr else (None, bs)

im = Image.open(SRC).convert("RGB")
bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR); H, W = bgr.shape[:2]
rows = json.load(open(RES, encoding="utf-8"))
print(f"[입력] 라벨 {len(rows)} · 기존 매칭 {sum(1 for r in rows if r['call'])}")

# 행 높이: band별 라벨 y0의 중앙값 간격
ys = sorted({r["box"][1] for r in rows})
bands_y = {}
for r in rows: bands_y.setdefault(r["band"], []).append(r["box"][1])
band_top = {b: int(np.median(v)) for b, v in bands_y.items()}
tops = sorted(band_top.values())
gaps = [b-a for a, b in zip(tops, tops[1:]) if b-a > 300]
ROWH = int(np.median(gaps)) if gaps else 650
print(f"[행 간격] {ROWH}px")

from paddleocr import PaddleOCR
ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False)
t0 = time.time(); n_rec = 0; n_dual = 0
for r in rows:
    x0, y0, x1, y1 = r["box"]
    ty0 = max(0, y0-int(ROWH*0.78)); ty1 = y0-8
    tc = bgr[ty0:ty1, max(0, x0-5):x1+5]
    r["ttext"] = ""
    if tc.size:
        tc = cv2.rotate(tc, cv2.ROTATE_90_COUNTERCLOCKWISE)
        tc = cv2.resize(tc, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
        res = ocr.predict(tc)
        r["ttext"] = " ".join(res[0].get("rec_texts", [])) if res else ""
    trow, sc = match_title(r["ttext"])
    if trow:
        if r["call"] and r["call"] == trow["call"]:
            r["how"] = "이중확정"; n_dual += 1
        elif not r["call"]:
            r["call"] = trow["call"]; r["how"] = "제목복구"; r["score"] = round(sc, 2); n_rec += 1
    elif r["call"]:
        r.setdefault("how", "청구기호")
print(f"[제목 패스] {time.time()-t0:.0f}s · 제목복구 +{n_rec} · 이중확정 {n_dual}")
matched = sum(1 for r in rows if r["call"])
print(f"[최종] 매칭 {matched}/{len(rows)} ({matched/len(rows)*100:.0f}%)  (청구기호 단독이었던 27 → {matched})")
uniq = len({r["call"] for r in rows if r["call"]})
print(f"[고유 도서] {uniq}권")

d = ImageDraw.Draw(im)
try: fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 24)
except Exception: fs = None
for r in rows:
    c = (150,150,150) if not r["call"] else ((50,130,240) if r.get("how")=="제목복구" else (40,190,90))
    d.rectangle(r["box"], outline=c, width=4)
p = HERE/"out_ondevice"/"daelim_82_dual.jpg"
im.save(p, quality=86)
json.dump(rows, open(HERE/"out_ondevice"/"daelim_82_dual.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[완료] {p} (초록=청구기호 · 파랑=제목복구 · 회색=미인식)")
