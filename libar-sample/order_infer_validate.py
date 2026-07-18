# -*- coding: utf-8 -*-
"""서가 순서 추론 정답의 정밀도 측정 (leave-one-out).
아이디어: 같은 스캔의 확정 조각들을 x순으로 늘어놓고, 각 확정 조각의 정답을 가린 뒤
양옆 이웃의 청구기호 사이 구간에 드는 카탈로그 후보가 유일하면 그걸 예측 — 정답과 대조.
정답 생성이 rec 모델과 무관(위치+카탈로그)하므로 선택 편향이 없다.
사용: py -3.12 order_infer_validate.py
"""
import io, json, glob, re, csv, zipfile, unicodedata
from collections import defaultdict

HERE_TS = 1784350000000                       # 오늘(원샷) 수집분만

def nfc(s): return unicodedata.normalize("NFC", str(s))

# 청구기호 정렬 키 (파이프라인 원칙 축약판: 분류 숫자 → 저자기호 초성 분해 근사)
CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def author_key(a):
    out = []
    for ch in a:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:
            s = o - 0xAC00
            out.append((s // 588, (s % 588) // 28, s % 28))
        elif ch in CHO:
            out.append((CHO.index(ch), -1, -1))
        elif ch.isdigit():
            out.append((100, int(ch), 0))
        else:
            out.append((200, o, 0))
    return out
def call_key(call):
    parts = nfc(call).split("-")
    try: cls = float(re.match(r"^(\d+(?:\.\d+)?)", parts[0]).group(1))
    except Exception: return None
    return (cls, author_key(parts[1]) if len(parts) > 1 else [])

# 카탈로그 정렬 목록
CAT = []
for row in csv.DictReader(io.open("catalog_full.csv", encoding="utf-8-sig")):
    k = call_key(row["call_number"])
    if k: CAT.append((k, nfc(row["call_number"])))
CAT.sort()
CAT_KEYS = [k for k, _ in CAT]

import bisect
def candidates_between(ka, kb):
    lo, hi = min(ka, kb), max(ka, kb)
    i = bisect.bisect_right(CAT_KEYS, lo)
    j = bisect.bisect_left(CAT_KEYS, hi)
    return [CAT[t][1] for t in range(i, j)]

# 오늘 스캔의 확정 조각을 스캔·행 단위로 정렬
n_pred = n_hit = n_total = 0
wrong = []
for zp in sorted(glob.glob("수집조각/libar_crops_*.zip")):
    ts = int(re.search(r"(\d{13})", zp).group(1))
    if ts < HERE_TS: continue
    with zipfile.ZipFile(zp) as z:
        if "manifest.json" not in z.namelist(): continue
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        by_scan = defaultdict(list)
        for c in man.get("crops", []):
            if c.get("call") and c.get("box"):
                by_scan[c.get("scan", 0)].append(c)
        for scan, crops in by_scan.items():
            # 같은 행(수직 겹침) 그룹: y중심 근접으로 근사
            crops.sort(key=lambda c: (round(((c["box"][1]+c["box"][3])/2) / max(1,(c["box"][3]-c["box"][1]))), c["box"][0]))
            rows = []
            for c in crops:
                cy = (c["box"][1]+c["box"][3]) / 2; h = c["box"][3]-c["box"][1]
                for r in rows:
                    if abs(r["cy"] - cy) < h * 0.6:
                        r["items"].append(c); r["cy"] = (r["cy"]+cy)/2; break
                else:
                    rows.append({"cy": cy, "items": [c]})
            for r in rows:
                items = sorted(r["items"], key=lambda c: c["box"][0])
                if len(items) < 3: continue
                for i in range(1, len(items)-1):
                    n_total += 1
                    ka, kb = call_key(items[i-1]["call"]), call_key(items[i+1]["call"])
                    kt = call_key(items[i]["call"])
                    if not ka or not kb or not kt: continue
                    if not (min(ka,kb) < kt < max(ka,kb)): continue    # 이웃이 순서 일관해야 게이트 통과
                    cands = candidates_between(ka, kb)
                    if len(cands) != 1: continue                        # 후보 유일할 때만 예측
                    n_pred += 1
                    if nfc(cands[0]) == nfc(items[i]["call"]): n_hit += 1
                    else: wrong.append((items[i]["call"], cands[0]))
print(f"[측정] 가릴 수 있던 자리 {n_total} · 예측 발동 {n_pred} · 적중 {n_hit} ({100*n_hit/max(1,n_pred):.0f}%)")
print(f"[커버리지] {100*n_pred/max(1,n_total):.0f}% — 발동 조건: 양옆 확정+순서 일관+카탈로그 후보 유일")
for w in wrong[:8]: print("  오답:", w)
