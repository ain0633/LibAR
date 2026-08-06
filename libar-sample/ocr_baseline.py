# -*- coding: utf-8 -*-
"""청구기호 OCR 베이스라인 측정 — 정답(labels.json) vs OCR(dualocr.json).
   검출 박스를 GT x에 매칭 후, 권차 숫자를 맞게 읽었는지 격리 평가 + 오류 유형 분석."""
import json, re, sys
from pathlib import Path
import libar_ondevice as L
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent

GT = json.load(open(HERE/"shelf_4558.labels.json", encoding="utf-8"))
OCR = json.load(open(HERE/"shelf_4558.dualocr.json", encoding="utf-8"))
for o in OCR:
    x0, y0, x1, y1 = o["box"]; o["cx"] = (x0+x1)/2

def nearest(gx):
    return min(OCR, key=lambda o: abs(o["cx"]-gx))

SHARED = {"408", "뉴88"}
def nums(ctoks):
    """공통 접두어(408/뉴88) 제외한 토큰에서 권차 후보 숫자."""
    rest = [t for t in ctoks if t not in SHARED and not any(s in t for s in SHARED)]
    return [n for t in rest for n in re.findall(r"\d{1,3}", t)]

def has_prefix(ctoks):
    return any(("408" in t or "뉴88" in t or t == "408") for t in ctoks)

cats = {"CORRECT": [], "MISREAD": [], "MISSING": [], "NOPREFIX": []}
for g in GT:
    exp = g["call_number"].split("-")[-1]          # 기대 권차
    o = nearest(g["x"]); dx = abs(o["cx"]-g["x"])
    ct = o["ctoks"]; cand = nums(ct)
    pref = has_prefix(ct)
    row = (g["call_number"], exp, cand, dx, ct)
    if not pref:
        cats["NOPREFIX"].append(row)
    elif exp in cand:
        cats["CORRECT"].append(row)
    elif cand:
        cats["MISREAD"].append(row)
    else:
        cats["MISSING"].append(row)

N = len(GT)
print(f"=== 청구기호 OCR 베이스라인 (정답 {N}개 라벨, best.pt+PaddleOCR) ===\n")
print(f"{'유형':10} {'권수':>4}  설명")
print(f"{'CORRECT':10} {len(cats['CORRECT']):>4}  권차 숫자 정확히 읽음")
print(f"{'MISREAD':10} {len(cats['MISREAD']):>4}  숫자 읽었으나 권차 오독")
print(f"{'MISSING':10} {len(cats['MISSING']):>4}  권차 숫자 추출 실패")
print(f"{'NOPREFIX':10} {len(cats['NOPREFIX']):>4}  408/뉴88 접두어도 못 읽음(검출·라벨 문제)")
acc = len(cats["CORRECT"])/N*100
print(f"\n권차 정확도(CORRECT/전체) = {len(cats['CORRECT'])}/{N} = {acc:.1f}%")
pref_ok = N - len(cats["NOPREFIX"])
print(f"접두어 인식률 = {pref_ok}/{N} = {pref_ok/N*100:.1f}%")

print("\n--- 오독(MISREAD): 기대권차 vs 읽은숫자 ---")
for cn, exp, cand, dx, ct in cats["MISREAD"]:
    print(f"  {cn:13} 기대 {exp:>3} → 읽음 {cand}   (Δx={dx:.0f})")
print("\n--- 권차 추출실패(MISSING) ---")
for cn, exp, cand, dx, ct in cats["MISSING"]:
    print(f"  {cn:13} 기대 {exp:>3} → 토큰 {ct}   (Δx={dx:.0f})")
print("\n--- 접두어 실패(NOPREFIX) ---")
for cn, exp, cand, dx, ct in cats["NOPREFIX"]:
    print(f"  {cn:13} 기대 {exp:>3} → 토큰 {ct}   (Δx={dx:.0f})")
