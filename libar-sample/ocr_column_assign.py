# -*- coding: utf-8 -*-
"""컬럼 인식 토큰 귀속 — 박스 걸침 문제의 추론단 해결.
  1. best.pt call_label 박스(62)를 재OCR하되 토큰의 '절대 x좌표' 보존
  2. spine 박스(58, spine1.pt)를 컬럼 앵커로: 각 토큰을 x-중심이 속한 spine에 귀속
     (겹치는 박스들의 토큰이 spine 단위로 병합·중복 제거됨)
  3. spine별 후보(하단 우선, 카탈로그 실재 권차) + c.2 복본 플래그
  4. 전역 단조 배정(복본은 c.2 플래그 있을 때만 같은 값 허용) + 제목 복구
  캐시: shelf_4558.coltokens.json (재실행 시 재OCR 생략)
"""
import os, sys, json, re, time, difflib, unicodedata
os.environ["FLAGS_use_mkldnn"] = "0"
import cv2, numpy as np
from pathlib import Path
from PIL import Image
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
CACHE = HERE/"shelf_4558.coltokens.json"

cat59 = L.load_catalog(str(HERE/"books_4558.csv"))
cat41 = {r["call_number"] for r in L.load_catalog(str(HERE/"newton_41.csv"))}
VOLS = {r["_toks"][-1] for r in cat59}
BY_VOL = {r["_toks"][-1]: r for r in cat59}

label_boxes = json.load(open(HERE/"shelf_4558.dualocr.json", encoding="utf-8"))
spines = json.load(open(HERE/"shelf_4558.tokens.json", encoding="utf-8"))
spines.sort(key=lambda s: (s["box"][0]+s["box"][2])/2)

# ── 1) 재OCR (토큰 절대좌표 보존) ──
if CACHE.exists():
    tokens = json.load(open(CACHE, encoding="utf-8"))
    print(f"[OCR] 캐시 사용 ({len(tokens)} tokens)")
else:
    bgr = cv2.cvtColor(np.array(Image.open(HERE/"shelf_4558.jpg").convert("RGB")), cv2.COLOR_RGB2BGR)
    H, W = bgr.shape[:2]
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang="korean", enable_mkldnn=False, use_doc_orientation_classify=False,
                    use_doc_unwarping=False, use_textline_orientation=False)
    tokens = []
    t0 = time.time()
    for b in label_boxes:
        x0, y0, x1, y1 = b["box"]; py = int((y1-y0)*0.15); px = int((x1-x0)*0.05)
        cx0, cy0 = max(0, x0-px), max(0, y0-py)
        crop = bgr[cy0:min(H, y1+py), cx0:x1+px]
        if crop.size == 0: continue
        scale = 1.0
        if crop.shape[0] < 120:
            scale = 3.0
            crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
        res = ocr.predict(crop)
        if not res: continue
        r = res[0]
        for t, p in zip(r.get("rec_texts", []), r.get("rec_polys", [])):
            xs = [q[0] for q in p]; ys = [q[1] for q in p]
            tokens.append({"t": L.nn(t), "x": cx0 + (sum(xs)/len(xs))/scale,
                           "y": cy0 + (sum(ys)/len(ys))/scale})
    json.dump(tokens, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[OCR] {len(label_boxes)}박스 → {len(tokens)} tokens ({time.time()-t0:.0f}s, 캐시 저장)")

# ── 2) 토큰 → spine 귀속 ──
def spine_of(x):
    for i, s in enumerate(spines):
        if s["box"][0] <= x <= s["box"][2]: return i
    return min(range(len(spines)), key=lambda i: abs((spines[i]["box"][0]+spines[i]["box"][2])/2 - x))

per = [[] for _ in spines]
for tk in tokens:
    if not tk["t"]: continue
    per[spine_of(tk["x"])].append(tk)
for lst in per: lst.sort(key=lambda z: -z["y"])   # 하단 우선

NOISE = re.compile(r"^(4?08|88|884|8|0|40|408)$")
def cands_of(lst):
    out = []
    for tk in lst:
        for m in re.findall(r"\d{1,3}", tk["t"]):
            if NOISE.match(m) or m not in VOLS: continue
            if m not in out: out.append(m)
    return out[:4]

cands = [cands_of(lst) for lst in per]
c2flag = [any(re.search(r"c2|c\.2", tk["t"]) for tk in lst) for lst in per]
n = len(spines)

# ── 3) 전역 단조 배정 (같은 값 재사용은 c.2 spine에서만) ──
vals = sorted({int(c) for cl in cands for c in cl})
vidx = {v: i for i, v in enumerate(vals)}
best = {(-1, 0): (0, None)}
for i in range(n):
    cur = dict(best)
    for c in cands[i]:
        cv = int(c); j = vidx[cv]
        for (pj, pu), (cnt, ptr) in best.items():
            if pj == -1 or vals[pj] < cv: key = (j, 1)
            elif pj == j and pu < 2 and c2flag[i]: key = (j, 2)   # 복본은 c.2 확인시만
            else: continue
            st = (cnt+1, (i, cv, pj, pu, ptr))
            if key not in cur or st[0] > cur[key][0]: cur[key] = st
    best = cur
top = max(best.values(), key=lambda x: x[0])
assign = {}; p = top[1]
while p:
    i, cv, pj, pu, prev = p; assign[i] = str(cv); p = prev

# ── 4) 제목 복구 (dualocr의 ttext를 spine에 겹침 최대 박스로 매핑) ──
def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()
def match_title(text, thr=0.65):
    t = ntitle(text)
    if len(t) < 2: return None
    bestr, bs = None, 0.0
    for r in cat59:
        c = ntitle(r["title"])
        if not c: continue
        lm = difflib.SequenceMatcher(None, t, c).find_longest_match(0, len(t), 0, len(c))
        pscore = lm.size/min(len(t), len(c)) if min(len(t), len(c)) else 0
        s = 0.6*pscore + 0.4*difflib.SequenceMatcher(None, t, c).ratio()
        if s > bs: bestr, bs = r, s
    return bestr if bs >= thr else None

def overlap(a, b): return max(0, min(a[2], b[2])-max(a[0], b[0]))
ttext_of = []
for s in spines:
    bb = max(label_boxes, key=lambda b: overlap(s["box"], b["box"]))
    ttext_of.append(bb.get("ttext", ""))

status, final, how = {}, {}, {}
for i in range(n):
    if i in assign:
        final[i], status[i], how[i] = assign[i], "ok", "청구기호"
        r = match_title(ttext_of[i])
        if r and r["_toks"][-1] == assign[i]: how[i] = "이중확정"
    else:
        r = match_title(ttext_of[i])
        if r:
            v = int(r["_toks"][-1])
            lo = max((int(assign[j]) for j in assign if j < i), default=-10**9)
            hi = min((int(assign[j]) for j in assign if j > i), default=10**9)
            final[i], how[i] = r["_toks"][-1], "제목복구"
            status[i] = "ok" if lo <= v <= hi else "misplaced"
        elif cands[i]:
            final[i], how[i], status[i] = cands[i][0], "후보(순서불일치)", "misplaced"
        else:
            final[i], how[i], status[i] = None, "미인식", "unknown"

found = {BY_VOL[final[i]]["call_number"] for i in range(n) if final[i] in BY_VOL}
n_ok = sum(1 for i in status if status[i] == "ok"); n_mis = sum(1 for i in status if status[i] == "misplaced")
n_unk = sum(1 for i in status if status[i] == "unknown")
print(f"\n[컬럼귀속+전역배정] spine {n}개")
print(f"  배정 {len(assign)} · 정상 {n_ok} · 오배열의심 {n_mis} · 미인식 {n_unk} · c.2 감지 {sum(c2flag)}곳")
print(f"  커버리지: 59권 중 {len(found)}권 · 41권(ISBN) 중 {len(found & cat41)}권")
print(f"  (비교: 박스 단위 전역배정 = 59권 중 41권 / 기존 match_tokens = 30권)")
print("\n[spine별]", " ".join((final[i] or "?") + ("!" if status[i] == "misplaced" else "") + ("ᶜ" if c2flag[i] else "") for i in range(n)))
json.dump({"assign": {str(i): final[i] for i in range(n)}, "status": {str(i): status[i] for i in range(n)},
           "c2": c2flag, "cov59": len(found), "cov41": len(found & cat41)},
          open(HERE/"out_ondevice"/"column_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
