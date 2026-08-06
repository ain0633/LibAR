# -*- coding: utf-8 -*-
"""캐시된 이중 OCR(shelf_4558.dualocr.json)로 제목 매칭 임계값을 쓸어보며
   41권 인식 커버리지 vs 오배열 변화를 비교. 재OCR 없음(즉시)."""
import sys, json, difflib, unicodedata, re
from pathlib import Path
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()
def match_title(text, catalog, thr):
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
    return (best, bs) if bs >= thr else (None, bs)

catalog = L.load_catalog(str(HERE/"newton_41.csv")); shared = L.shared_prefix(catalog)
books = json.load(open(HERE/"shelf_4558.dualocr.json", encoding="utf-8"))
n_cat = len(catalog)

def run(thr):
    bs = [dict(b) for b in books]
    for bk in bs:
        crow, _ = L.match_tokens(bk["ctoks"], catalog, shared)
        trow, _ = match_title(bk["ttext"], catalog, thr)
        if crow and trow and crow["call_number"] == trow["call_number"]: row, how = crow, "dual"
        elif crow: row, how = crow, "call"
        elif trow: row, how = trow, "title"
        else: row, how = None, "none"
        bk["call"] = row["call_number"] if row else None
        bk["order"] = row["_order"] if row else None
        bk["how"] = how
    matched = [b for b in bs if b["call"]]
    mis = L.lis_misplaced([b["order"] for b in matched])
    n_mis = len(mis)
    found = {b["call"] for b in matched}
    cov = sum(1 for r in catalog if r["call_number"] in found)
    n_title = sum(b["how"] == "title" for b in matched)
    n_dual = sum(b["how"] == "dual" for b in matched)
    ratio = n_mis/len(matched)*100 if matched else 0
    return cov, len(matched), n_mis, ratio, n_title, n_dual

print(f"41권 카탈로그 · 검출 {len(books)}권\n")
print(f"{'임계값':>6} | {'인식(41중)':>9} | {'매칭책등':>7} | {'오배열':>6} | {'오배열%':>7} | {'제목복구':>7} | {'이중확정':>7}")
print("-"*72)
for thr in [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]:
    cov, nm, nmis, ratio, nt, nd = run(thr)
    print(f"{thr:>6.2f} | {cov:>6}/41 | {nm:>7} | {nmis:>6} | {ratio:>6.1f}% | {nt:>7} | {nd:>7}")
