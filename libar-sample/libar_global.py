# -*- coding: utf-8 -*-
"""시퀀스 전역 배정(global decoding) — 캐시된 이중 OCR(dualocr.json) 재사용, 재OCR 없음.
  단계:
   A. spine별 독립 추출(접두어파편 제거→하단우선→카탈로그 권차만) : 어제 방식, 중복 발생
   B. + 전역 단조 배정: 서가가 거의 정렬돼 있다는 사실을 활용해
      '비내림차순을 만족하는 최대 배정'을 DP로 선택 → 이웃 오염·중복 제거
      배정 못 받았지만 후보가 있는 spine = 오배열/오염 의심(suspect)
   C. + 제목 신호: 미배정 spine을 제목 매칭(0.65)으로 복구.
      제목이 가리키는 권차가 이웃 배정값 사이에 들어가면 ok, 아니면 misplaced 의심
  출력: 지표 비교 + out_ondevice/shelf_4558_global41.jpg (AR)
"""
import sys, json, re, difflib, unicodedata
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

cat59 = L.load_catalog(str(HERE/"books_4558.csv"))
cat41 = {r["call_number"] for r in L.load_catalog(str(HERE/"newton_41.csv"))}
VOLS = {r["_toks"][-1] for r in cat59}
BY_VOL = {r["_toks"][-1]: r for r in cat59}
books = json.load(open(HERE/"shelf_4558.dualocr.json", encoding="utf-8"))
books.sort(key=lambda b: (b["box"][0]+b["box"][2])/2)
n = len(books)

NOISE = re.compile(r"^(4?08|88|884|8|0|40|408)$")
def candidates(ctoks):
    """하단 우선 순서의 카탈로그 실재 권차 후보 (중복 제거)."""
    out = []
    for t in reversed(ctoks):                     # read_label은 상단→하단 정렬이므로 뒤집기
        for m in re.findall(r"\d{1,3}", t):
            if NOISE.match(m) or m not in VOLS: continue
            if m not in out: out.append(m)
    return out[:4]

def ntitle(s): return re.sub(r"[^0-9A-Za-z가-힣]", "", unicodedata.normalize("NFC", str(s))).lower()
def match_title(text, thr=0.65):
    t = ntitle(text)
    if len(t) < 2: return None, 0.0
    best, bs = None, 0.0
    for r in cat59:
        c = ntitle(r["title"])
        if not c: continue
        lm = difflib.SequenceMatcher(None, t, c).find_longest_match(0, len(t), 0, len(c))
        p = lm.size/min(len(t), len(c)) if min(len(t), len(c)) else 0
        s = 0.6*p + 0.4*difflib.SequenceMatcher(None, t, c).ratio()
        if s > bs: best, bs = r, s
    return (best, bs) if bs >= thr else (None, bs)

cands = [candidates(b["ctoks"]) for b in books]

# ── A. 독립 추출(비교 기준) ──
indep = [c[0] if c else None for c in cands]
hitsA = [v for v in indep if v]
seqA = [int(v) for v in hitsA]
lisA = L.lis_misplaced(seqA)
print(f"[A 독립추출]   추출 {len(hitsA)}/{n} · 고유 {len(set(hitsA))} · 순서위반 {len(lisA)}")

# ── B. 전역 단조 배정 (DP: 비내림차순 최대 배정, 같은 값 최대 2회=복본 허용) ──
vals = sorted({int(c) for cl in cands for c in cl})
vidx = {v: i for i, v in enumerate(vals)}
NEG = -1  # 아직 아무것도 선택 안 함
# dp[j] = (count, ptr) : 마지막 값 vals[j](j=-1이면 없음)로 끝나는 최대 배정 수
# ptr: (spine_idx, value, prev_j, prev_use) 재구성용. use=해당 값 사용 횟수(1|2)
import copy
# 상태: (j, use) — 마지막 값 인덱스와 그 값의 연속 사용 횟수
best = {(-1, 0): (0, None)}
for i in range(n):
    cur = dict(best)
    for c in cands[i]:
        cv = int(c); j = vidx[cv]
        for (pj, pu), (cnt, ptr) in best.items():
            if pj == -1 or vals[pj] < cv:
                key = (j, 1)
            elif pj == j and pu < 2:              # 복본(c.2) 허용: 같은 값 2회까지
                key = (j, 2)
            else:
                continue
            cand_state = (cnt+1, (i, cv, pj, pu, ptr))
            if key not in cur or cand_state[0] > cur[key][0]:
                cur[key] = cand_state
    best = cur
(top_cnt, top_ptr) = max(best.values(), key=lambda x: x[0])
assign = {}
p = top_ptr
while p:
    i, cv, pj, pu, prev = p
    assign[i] = str(cv)
    p = prev
hitsB = list(assign.values())
print(f"[B 전역배정]   배정 {len(assign)}/{n} · 고유 {len(set(hitsB))} · (정의상 순서위반 0)")

# ── C. 제목 신호로 미배정 복구 + 상태 분류 ──
status = {}; how = {}; final = {}
sorted_idx = sorted(assign.keys())
for i in range(n):
    if i in assign:
        final[i] = assign[i]; status[i] = "ok"; how[i] = "청구기호"
        row, sc = match_title(books[i].get("ttext", ""))
        if row and row["_toks"][-1] == assign[i]: how[i] = "이중확정"
        continue
    row, sc = match_title(books[i].get("ttext", ""))
    if row:
        v = int(row["_toks"][-1])
        lo = max((int(assign[j]) for j in assign if j < i), default=-10**9)
        hi = min((int(assign[j]) for j in assign if j > i), default=10**9)
        final[i] = row["_toks"][-1]; how[i] = "제목복구"
        status[i] = "ok" if lo <= v <= hi else "misplaced"
    elif cands[i]:
        # 후보는 있으나 순서에 못 끼움 → 오염/오배열 의심
        final[i] = cands[i][0]; how[i] = "후보(순서불일치)"
        status[i] = "misplaced"
    else:
        final[i] = None; how[i] = "미인식"; status[i] = "unknown"

matched = [i for i in range(n) if final[i]]
found_calls = {BY_VOL[final[i]]["call_number"] for i in matched if final[i] in BY_VOL}
cov59 = len(found_calls)
cov41 = len(found_calls & cat41)
n_ok = sum(1 for i in range(n) if status[i] == "ok")
n_mis = sum(1 for i in range(n) if status[i] == "misplaced")
n_unk = sum(1 for i in range(n) if status[i] == "unknown")
n_dual = sum(1 for i in range(n) if how[i] == "이중확정")
n_tit = sum(1 for i in range(n) if how[i] == "제목복구")
print(f"[C 최종]      정상 {n_ok} · 오배열의심 {n_mis} ({n_mis/max(1,n_ok+n_mis)*100:.0f}%) · 미인식 {n_unk} · 이중확정 {n_dual} · 제목복구 {n_tit}")
print(f"[커버리지]    59권 중 {cov59}권 · 41권(ISBN) 중 {cov41}권")

# ── AR 렌더 ──
im = Image.open(HERE/"shelf_4558.jpg").convert("RGB"); W, H = im.size
d = ImageDraw.Draw(im, "RGBA")
COL = {"ok": (40, 190, 90), "misplaced": (235, 60, 60), "unknown": (150, 150, 150)}
fs = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34)
fb = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 52)
for i, b in enumerate(books):
    c = COL[status[i]]; x0, y0, x1, y1 = b["box"]
    d.rectangle([x0, y0, x1, y1], outline=c+(255,), width=6 if status[i] == "misplaced" else 4)
    if status[i] == "ok": d.rectangle([x0, y0, x1, y1], fill=c+(40,))
    if status[i] == "misplaced": d.rectangle([x0, y0, x1, y1], fill=c+(70,))
    tag = final[i] or "?"
    d.rectangle([x0, y0-50, x0+78, y0-4], fill=c+(240,))
    d.text((x0+6, y0-48), tag, font=fs, fill=(255, 255, 255, 255))
d.rectangle([0, 0, W, 170], fill=(20, 30, 60, 235))
d.text((40, 26), "LibAR 전역 배정(global decoding)  |  후처리 개선판", font=fb, fill=(255, 255, 255, 255))
d.text((40, 100), f"인식 {cov41}/41권(ISBN) · 59권 중 {cov59} · 정상 {n_ok} · 오배열의심 {n_mis} · 이중확정 {n_dual} · 제목복구 {n_tit}",
       font=fs, fill=(180, 210, 255, 255))
out = HERE/"out_ondevice"; out.mkdir(exist_ok=True)
im.save(out/"shelf_4558_global41.jpg", quality=88)
json.dump({"assign": {str(i): final[i] for i in range(n)}, "status": {str(i): status[i] for i in range(n)},
           "how": {str(i): how[i] for i in range(n)}, "cov59": cov59, "cov41": cov41},
          open(out/"global_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[완료] {out/'shelf_4558_global41.jpg'}")
print("\n[spine별]", " ".join((final[i] or "?") + {"ok": "", "misplaced": "!", "unknown": ""}[status[i]] for i in range(n)))
