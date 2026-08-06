# -*- coding: utf-8 -*-
"""대림 파이프라인 (사진 1장 베이스라인) — 색 검출 → OCR → 일반 청구기호 매칭 → 행별 LIS → AR.
   청구기호 형식: 843-바66ㄷ(-v.2)  = 분류-저자기호(-권차)
   사용: python daelim_pipeline.py [사진경로]
"""
import os, sys, json, re, time, difflib, unicodedata
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from daelim_detect import detect_labels
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent/"대림데이터"/"KakaoTalk_20260707_135237882.jpg"

def nn(s): return re.sub(r"[^0-9A-Za-z가-힣.]", "", unicodedata.normalize("NFC", str(s)))

# ── 카탈로그 ──
import csv
cat = []
for r in csv.DictReader(open(HERE/"daelim_catalog.csv", encoding="utf-8-sig")):
    call = r["call_number"].strip()
    parts = call.split("-")
    if len(parts) < 2: continue
    cls, author = parts[0].strip(), parts[1].strip()
    vol = parts[2] if len(parts) > 2 else ""
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", cls)     # '양843' → 843
    clsnum = m.group(1) if m else cls
    cat.append({"call": call, "cls": clsnum, "author": nn(author), "vol": vol,
                "title": r["title"], "status": r["status"]})
by_cls = {}
for c in cat: by_cls.setdefault(c["cls"], []).append(c)
print(f"[카탈로그] {len(cat)}권 · 분류 {sorted(by_cls, key=str)[:8]}...")

# ── 검출 ──
im = Image.open(SRC).convert("RGB")
bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
labels, bands = detect_labels(bgr)
print(f"[검출] 라벨줄 {len(bands)} · 라벨 {len(labels)}")

def band_of(b):
    yc = (b[1]+b[3])/2
    for i, (y0, y1) in enumerate(bands):
        if y0-160 <= yc <= y1+40: return i
    return -1

# ── OCR ──
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                use_doc_unwarping=False, use_textline_orientation=False)
t0 = time.time()
reads = []
for (x0, y0, x1, y1) in labels:
    pad = 4
    crop = bgr[max(0, y0-pad):y1+pad, max(0, x0-pad):x1+pad]
    if crop.size == 0: reads.append(""); continue
    up = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)
    res = ocr.predict(up)
    txt = " ".join(res[0].get("rec_texts", [])) if res else ""
    reads.append(txt)
print(f"[OCR] {len(labels)}개 → {time.time()-t0:.0f}s")

# ── 매칭: 분류 + 저자기호 퍼지 ──
def match(txt):
    t = nn(txt)
    mcls = re.search(r"8[234]\d(\.\d+)?", t)      # 이 구간은 83x/84x
    cands = []
    if mcls and mcls.group(0) in by_cls:
        cands = by_cls[mcls.group(0)]
        clsv = mcls.group(0)
    else:
        cands = cat; clsv = None
    # 저자기호 후보: 한글+숫자(+한글) 패턴
    ma = re.findall(r"[가-힣][\d]{1,3}[가-힣]?", t)
    best, bs = None, 0.0
    for c in cands:
        s = 0.0
        for a in ma:
            s = max(s, difflib.SequenceMatcher(None, a, c["author"]).ratio())
        if clsv and s > 0: s += 0.15                # 분류 일치 보너스
        if s > bs: best, bs = c, s
    return (best, bs) if bs >= 0.62 else (None, bs)

rows_out = []
matched = 0
for i, (b, txt) in enumerate(zip(labels, reads)):
    row, sc = match(txt)
    rows_out.append({"box": list(b), "band": band_of(b), "read": txt,
                     "call": row["call"] if row else None,
                     "title": row["title"][:20] if row else None,
                     "status_cat": row["status"] if row else None, "score": round(sc, 2)})
    if row: matched += 1
print(f"[매칭] {matched}/{len(labels)} ({matched/len(labels)*100:.0f}%)")
uniq = len({r['call'] for r in rows_out if r['call']})
print(f"[고유 도서] {uniq}권 (카탈로그 456권 중, 사진에 보이는 범위 내)")

# ── 행별 순서(LIS) ──
def sortkey(call):
    p = call.split("-"); cls = re.sub(r"^[가-힣A-Z]+", "", p[0])
    vol = 0
    if len(p) > 2:
        mv = re.search(r"\d+", p[2]); vol = int(mv.group(0)) if mv else 0
    return (float(cls) if re.match(r"^[\d.]+$", cls) else 999, p[1] if len(p) > 1 else "", vol)

import libar_ondevice as L
n_mis = 0
for bi in range(len(bands)):
    seq = [r for r in rows_out if r["band"] == bi and r["call"]]
    seq.sort(key=lambda r: r["box"][0])
    keys = [sortkey(r["call"]) for r in seq]
    mis = L.lis_misplaced(keys)
    for j, r in enumerate(seq):
        r["mis"] = j in mis
        if j in mis: n_mis += 1
print(f"[오배열 의심] {n_mis}건 / 매칭 {matched}건")

# ── AR 렌더 ──
d = ImageDraw.Draw(im, "RGBA")
try: fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)
except Exception: fs = ImageFont.load_default()
for r in rows_out:
    x0, y0, x1, y1 = r["box"]
    if r["call"] is None: c = (150, 150, 150)
    elif r.get("mis"): c = (235, 60, 60)
    else: c = (40, 190, 90)
    d.rectangle([x0, y0, x1, y1], outline=c+(255,), width=4)
    if r["call"]:
        tag = r["call"].split("-")[1][:5]
        d.rectangle([x0, y0-30, x0+70, y0-2], fill=c+(235,))
        d.text((x0+3, y0-30), tag, font=fs, fill=(255, 255, 255, 255))
out = HERE/"out_ondevice"; out.mkdir(exist_ok=True)
p = out/f"daelim_{SRC.stem[-2:]}_ar.jpg"
im.save(p, quality=87)
json.dump(rows_out, open(out/f"daelim_{SRC.stem[-2:]}_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[완료] {p}")
