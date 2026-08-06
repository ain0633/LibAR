# -*- coding: utf-8 -*-
"""41권(ISBN 확보) 장서 카탈로그로 shelf_4558 인식 커버리지 확인 + AR 오버레이 생성.
   캐시된 shelf_4558.tokens.json(책등 box+OCR토큰)을 재사용 → 재인식 없이 매칭/렌더."""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import libar_ondevice as L

if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

catalog = L.load_catalog(str(HERE/"newton_41.csv"))
shared = L.shared_prefix(catalog)
print(f"[장서] {len(catalog)}권 · 공통 접두어(자동) {shared}")

books = json.load(open(HERE/"shelf_4558.tokens.json", encoding="utf-8"))
print(f"[책등] 캐시 {len(books)}개")

for bk in books:
    row, sc = L.match_tokens(bk["toks"], catalog, shared)
    bk["call_number"] = row["call_number"] if row else None
    bk["title"] = row["title"] if row else None
    bk["order"] = row["_order"] if row else None

matched = [b for b in books if b["call_number"]]
mis = L.lis_misplaced([b["order"] for b in matched])
for b in books: b["status"] = "unknown" if b["call_number"] is None else "ok"
for i, b in enumerate(matched):
    if i in mis: b["status"] = "misplaced"

# ── 41권 커버리지 ──
cat_calls = [r["call_number"] for r in catalog]
found = {b["call_number"] for b in matched}
found_cat = [c for c in cat_calls if c in found]
missing_cat = [c for c in cat_calls if c not in found]
n_ok = sum(b["status"] == "ok" for b in books)
n_mis = sum(b["status"] == "misplaced" for b in books)

mis_ratio = (n_mis / len(matched) * 100) if matched else 0.0
print(f"\n[커버리지] 41권 중 인식 {len(found_cat)}권 · 미인식 {len(missing_cat)}권")
print(f"[책등단위] 매칭 {len(matched)}/{len(books)} · 정상 {n_ok} · 오배열 {n_mis}")
print(f"[오배열 비율] 인식 {len(matched)}권 중 {n_mis}권 오배열 = {mis_ratio:.1f}%")
if missing_cat:
    title_of = {r["call_number"]: r["title"] for r in catalog}
    print("\n[미인식 41권 목록]")
    for c in missing_cat:
        print(f"  - {c}  {title_of[c]}")

# ── AR 오버레이 ──
im = Image.open(HERE/"shelf_4558.jpg").convert("RGB"); W, H = im.size
d = ImageDraw.Draw(im, "RGBA")
COL = {"ok": (40, 190, 90), "misplaced": (235, 60, 60), "unknown": (150, 150, 150)}
fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34)
bf = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 52)
sf = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34)
for b in books:
    c = COL[b["status"]]; x0, y0, x1, y1 = b["box"]
    w = 6 if b["status"] == "misplaced" else (4 if b["status"] == "ok" else 2)
    d.rectangle([x0, y0, x1, y1], outline=c + (255,), width=w)
    if b["status"] == "ok": d.rectangle([x0, y0, x1, y1], fill=c + (45,))
    tag = b["call_number"].split("-")[-1] if b["call_number"] else "?"
    d.rectangle([x0, y0 - 50, x0 + 78, y0 - 4], fill=c + (240,))
    d.text((x0 + 6, y0 - 48), tag, font=fs, fill=(255, 255, 255, 255))
# 배너
d.rectangle([0, 0, W, 170], fill=(20, 30, 60, 235))
d.text((40, 26), f"LibAR × 정보나루  |  41권 장서 카탈로그 인식", font=bf, fill=(255, 255, 255, 255))
d.text((40, 100), f"인식 {len(found_cat)}/41권  ·  정상 {n_ok}  ·  오배열 {n_mis} ({mis_ratio:.0f}%)  ·  초록=인식 / 빨강=오배열 / 회색=미인식",
       font=sf, fill=(180, 210, 255, 255))
out = HERE/"out_ondevice"; out.mkdir(exist_ok=True)
p = out/"shelf_4558_ar41.jpg"
im.save(p, quality=88)
print(f"\n[완료] {p}")
json.dump({"found": found_cat, "missing": missing_cat,
           "n_catalog": len(catalog), "n_found": len(found_cat)},
          open(out/"coverage_41.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
