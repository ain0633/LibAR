# -*- coding: utf-8 -*-
"""팀 질문 검증: '오배열 판정에 장서 데이터가 꼭 필요한가? 순서(오름차순)만으로 되지 않나?'
   같은 OCR 토큰·같은 전역 단조 배정(DP)에서 딱 하나만 바꿔 비교:
     모드 A: 카탈로그 제약 있음 (실재 권차만 후보로 인정)
     모드 B: 카탈로그 제약 없음 (읽힌 숫자면 모두 후보 = 순서만으로 판정)
"""
import sys, json, re
from pathlib import Path
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

cat59 = L.load_catalog(str(HERE/"books_4558.csv"))
VOLS = {r["_toks"][-1] for r in cat59}
books = json.load(open(HERE/"shelf_4558.dualocr.json", encoding="utf-8"))
books.sort(key=lambda b: (b["box"][0]+b["box"][2])/2)
n = len(books)

NOISE = re.compile(r"^(4?08|88|884|8|0|40|408)$")
def candidates(ctoks, use_catalog):
    out = []
    for t in reversed(ctoks):
        for m in re.findall(r"\d{1,3}", t):
            if NOISE.match(m): continue
            if use_catalog and m not in VOLS: continue
            if m not in out: out.append(m)
    return out[:4]

def decode(cands):
    """비내림차순 최대 배정 DP (같은 값 2회=복본 허용)."""
    vals = sorted({int(c) for cl in cands for c in cl})
    vidx = {v: i for i, v in enumerate(vals)}
    best = {(-1, 0): (0, None)}
    for i in range(n):
        cur = dict(best)
        for c in cands[i]:
            cv = int(c); j = vidx[cv]
            for (pj, pu), (cnt, ptr) in best.items():
                if pj == -1 or vals[pj] < cv: key = (j, 1)
                elif pj == j and pu < 2: key = (j, 2)
                else: continue
                st = (cnt+1, (i, cv, pj, pu, ptr))
                if key not in cur or st[0] > cur[key][0]: cur[key] = st
        best = cur
    top = max(best.values(), key=lambda x: x[0])
    assign = {}; p = top[1]
    while p:
        i, cv, pj, pu, prev = p; assign[i] = cv; p = prev
    return assign

for name, use_cat in [("A. 카탈로그 제약 O", True), ("B. 순서만(제약 X)", False)]:
    cands = [candidates(b["ctoks"], use_cat) for b in books]
    assign = decode(cands)
    vals = list(assign.values())
    ghost = [v for v in vals if str(v) not in VOLS]          # 실재하지 않는 권차 = 유령책
    real = [v for v in vals if str(v) in VOLS]
    uniq = len(set(real))
    # 배정 못 받았지만 후보가 있던 spine = 오배열 의심 플래그
    suspects = sum(1 for i in range(n) if i not in assign and cands[i])
    print(f"[{name}] 배정 {len(assign)}/{n} · 실재권차 {len(real)}(고유 {uniq}) · "
          f"유령책 {len(ghost)}개 {sorted(set(ghost))[:8]} · 오배열의심 {suspects}")
print()
print("※ 유령책 = 카탈로그에 없는 권차가 '정상 배열'로 배정된 것 (사서에게 잘못된 정보 제공)")
print("※ 결번(빠진 책) 탐지는 정의상 장서 목록 없이는 불가능")
