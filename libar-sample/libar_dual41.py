# -*- coding: utf-8 -*-
"""2클래스 이중 인식(청구기호+제목)을 41권 카탈로그로. best.pt 검출 + PaddleOCR.
   OCR 결과를 shelf_4558.dualocr.json에 캐시 → 이후 카탈로그만 바꿔 즉시 재매칭 가능."""
import os, sys, time, json, difflib, unicodedata, re
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
CATALOG = sys.argv[1] if len(sys.argv) > 1 else "newton_41.csv"
THR = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
CACHE = HERE/"shelf_4558.dualocr.json"

def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()
def match_title(text, catalog, thr=0.45):
    t = ntitle(text)
    if len(t) < 2: return None, 0.0
    best, bs = None, 0.0
    for r in catalog:
        c = ntitle(r["title"])
        if not c: continue
        lm = difflib.SequenceMatcher(None, t, c).find_longest_match(0, len(t), 0, len(c))
        p = lm.size/min(len(t), len(c)) if min(len(t), len(c)) else 0
        s = 0.6*p + 0.4*difflib.SequenceMatcher(None, t, c).ratio()
        if s > bs: best, bs = r, s
    return (best, round(bs, 2)) if bs >= thr else (None, round(bs, 2))

def read_scaled(ocr, crop, maxside=1100):
    if crop.size == 0: return ""
    h, w = crop.shape[:2]; s = maxside/max(h, w)
    if s < 1: crop = cv2.resize(crop, (int(w*s), int(h*s)), interpolation=cv2.INTER_AREA)
    res = ocr.predict(crop)
    return "".join(res[0].get("rec_texts", [])) if res else ""

catalog = L.load_catalog(str(HERE/CATALOG)); shared = L.shared_prefix(catalog)
print(f"[장서] {len(catalog)}권 · 접두어 {shared}")
im = Image.open(HERE/"shelf_4558.jpg").convert("RGB")
bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR); H, W = bgr.shape[:2]

if CACHE.exists():
    books = json.load(open(CACHE, encoding="utf-8"))
    print(f"[OCR] 캐시 사용 ({CACHE.name}, {len(books)}권)")
else:
    m = YOLO(str(HERE/"best.pt"))
    r = m.predict(bgr, conf=0.5, iou=0.45, agnostic_nms=True, verbose=False)[0]
    labs = sorted([[int(v) for v in b.xyxy[0].tolist()] for b in r.boxes if m.names[int(b.cls)] == "call_label"],
                  key=lambda b: (b[0]+b[2])/2)
    print(f"[검출] call_label {len(labs)}권")
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                    use_doc_unwarping=False, use_textline_orientation=False)
    ytop = int(H*0.36); books = []
    t1 = time.time()
    for b in labs:
        x0, y0, x1, y1 = b; py = int((y1-y0)*0.15); px = int((x1-x0)*0.05)
        books.append({"box": b, "ctoks": L.read_label(ocr, bgr[max(0, y0-py):min(H, y1+py), max(0, x0-px):x1+px])})
    t_call = time.time()-t1
    t2 = time.time()
    for bk in books:
        x0, y0, x1, y1 = bk["box"]; cw = x1-x0; cx = (x0+x1)//2
        tx0 = cx-int(cw*0.35); tx1 = cx+int(cw*0.35); ty1 = y0-int((y1-y0)*0.4)
        tbox = [tx0, ytop, tx1, max(ytop+10, ty1)]; bk["tbox"] = tbox
        tc = bgr[tbox[1]:tbox[3], max(0, tx0):tx1]
        if tc.size: tc = cv2.rotate(tc, cv2.ROTATE_90_COUNTERCLOCKWISE)
        bk["ttext"] = read_scaled(ocr, tc)
    t_title = time.time()-t2
    json.dump(books, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[청구기호 OCR] {t_call:.0f}s · [제목 OCR] {t_title:.0f}s (캐시 저장)")

# ── 매칭 ──
for bk in books:
    crow, _ = L.match_tokens(bk["ctoks"], catalog, shared)
    trow, _ = match_title(bk["ttext"], catalog, THR)
    if crow and trow and crow["call_number"] == trow["call_number"]: row, how = crow, "이중확정"
    elif crow: row, how = crow, "청구기호"
    elif trow: row, how = trow, "제목복구"
    else: row, how = None, "미인식"
    bk.update(call=row["call_number"] if row else None, title=row["title"] if row else None,
              order=row["_order"] if row else None, how=how)

matched = [b for b in books if b["call"]]
mis = L.lis_misplaced([b["order"] for b in matched])
for b in books: b["status"] = "unknown" if b["call"] is None else "ok"
for i, b in enumerate(matched):
    if i in mis: b["status"] = "misplaced"
n_ok = sum(b["status"] == "ok" for b in books); n_mis = sum(b["status"] == "misplaced" for b in books)
n_dual = sum(b["how"] == "이중확정" for b in books); n_title = sum(b["how"] == "제목복구" for b in books)
mis_ratio = (n_mis/len(matched)*100) if matched else 0.0

cat_calls = [r["call_number"] for r in catalog]; found = {b["call"] for b in matched}
found_cat = [c for c in cat_calls if c in found]; missing_cat = [c for c in cat_calls if c not in found]

print(f"\n[커버리지] {len(catalog)}권 중 인식 {len(found_cat)}권 · 미인식 {len(missing_cat)}권")
print(f"[책등단위] 매칭 {len(matched)}/{len(books)} · 정상 {n_ok} · 오배열 {n_mis} · 이중확정 {n_dual} · 제목복구 {n_title}")
print(f"[오배열 비율] 인식 {len(matched)}권 중 {n_mis}권 = {mis_ratio:.1f}%")
if missing_cat:
    to = {r["call_number"]: r["title"] for r in catalog}
    print("[미인식]", ", ".join(f"{c}({to[c]})" for c in missing_cat))

# ── 렌더 ──
COL = {"ok": (40, 190, 90), "misplaced": (235, 60, 60), "unknown": (150, 150, 150)}
d = ImageDraw.Draw(im, "RGBA")
fb = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 52); fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34)
sf = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34)
for b in books:
    c = COL[b["status"]]; x0, y0, x1, y1 = b["box"]
    if "tbox" in b:
        tx0, ty0, tx1, ty1 = b["tbox"]; d.rectangle([tx0, ty0, tx1, ty1], outline=(50, 130, 240, 200), width=2)
    d.rectangle([x0, y0, x1, y1], outline=c+(255,), width=6 if b["status"] == "misplaced" else 4)
    if b["status"] == "misplaced": d.rectangle([x0, y0, x1, y1], fill=c+(70,))
    elif b["status"] == "ok": d.rectangle([x0, y0, x1, y1], fill=c+(40,))
    tag = b["call"].split("-")[-1] if b["call"] else "?"
    d.rectangle([x0, y0-50, x0+78, y0-4], fill=c+(240,)); d.text((x0+6, y0-48), tag, font=fs, fill=(255, 255, 255, 255))
d.rectangle([0, 0, W, 170], fill=(20, 30, 60, 235))
d.text((40, 26), f"LibAR 이중 인식 (best.pt)  |  41권 장서 · 제목임계값 {THR}", font=fb, fill=(255, 255, 255, 255))
d.text((40, 100), f"인식 {len(found_cat)}/{len(catalog)}권 · 정상 {n_ok} · 오배열 {n_mis} ({mis_ratio:.0f}%) · 이중확정 {n_dual} · 제목복구 {n_title}",
       font=sf, fill=(180, 210, 255, 255))
out = HERE/"out_ondevice"; out.mkdir(exist_ok=True)
p = out/f"shelf_4558_dual41_thr{int(THR*100)}.jpg"; im.save(p, quality=88)
print(f"[완료] {p}")
