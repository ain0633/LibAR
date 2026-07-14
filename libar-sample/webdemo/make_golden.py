# -*- coding: utf-8 -*-
"""골든 케이스 추출 — 파이썬 match/sortkey/LIS의 정답을 JSON으로 (JS 이식 파리티 검증용).
daelim_yolo_pipeline.py의 함수를 그대로 재정의해 demo JSON의 read 텍스트에 적용."""
import io, sys, re, csv, json, difflib, unicodedata
from pathlib import Path

HERE = Path(__file__).parent
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def nn(s):
    return re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ.]", "", unicodedata.normalize("NFC", str(s)))

cat = json.load(io.open(HERE/"demo/catalog.json", encoding="utf-8"))
items, by_cls = [], {}
for r in cat:
    call = re.sub(r"\s*(?:=|[cC]\.)\d+$", "", str(r["call"]).strip())
    parts = call.split("-")
    if len(parts) < 2: continue
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", parts[0].strip())
    it = {"call": call, "cls": m.group(1) if m else parts[0].strip(),
          "author": nn(parts[1].strip()), "title": r["title"]}
    items.append(it); by_cls.setdefault(it["cls"], []).append(it)

JAMO_FIX = {"0": "ㅇ", "O": "ㅇ", "o": "ㅇ", "Q": "ㅇ", "으": "ㅇ", "이": "ㅇ",
            "피": "ㅍ", "디": "ㄷ", "기": "ㄱ", "니": "ㄴ", "리": "ㄹ", "미": "ㅁ",
            "비": "ㅂ", "시": "ㅅ", "지": "ㅈ", "치": "ㅊ", "키": "ㅋ", "티": "ㅌ", "히": "ㅎ",
            "프": "ㅍ", "표": "ㅍ", "드": "ㄷ", "그": "ㄱ", "느": "ㄴ", "르": "ㄹ", "므": "ㅁ",
            "브": "ㅂ", "스": "ㅅ", "즈": "ㅈ", "츠": "ㅊ", "크": "ㅋ", "트": "ㅌ", "흐": "ㅎ"}

def _vol_pick(hits, txt):
    mv = re.search(r"[vV]\.?(\d+)", txt)
    if mv:
        vhits = [c for c in hits if re.match(r"^[vV]?\.?0*%s$" % mv.group(1), c["call"].split("-")[-1])]
        if len(vhits) == 1: return vhits[0]
    if len({c["call"] for c in hits}) == 1: return hits[0]
    return None

def match(txt):   # 권차 수술(07-14) 반영 — daelim_yolo_pipeline.py와 동일해야 함
    t = nn(re.sub(r"[vV]\.?\d+", " ", txt))
    m = None
    for m2 in re.finditer(r"(\d{3}(?:\.\d+)?)([가-힣][0-9]{1,3}[가-힣ㄱ-ㅎ0Oo]?)", t):
        if m2.group(1) in by_cls: m = m2; break
    if m:
        clsv, author = m.group(1), m.group(2)
        cands = by_cls[clsv]
    else:
        best = None
        for a in re.findall(r"[가-힣][0-9]{2,3}[가-힣ㄱ-ㅎ]?", t):
            vs = {a} | ({a[:-1]+JAMO_FIX[a[-1]]} if a[-1] in JAMO_FIX else set())
            hits = [c for c in items if c["author"] in vs]
            if len(hits) == 1 and len(a) >= 4: best = hits[0]
            elif len(hits) > 1 and len(a) >= 4:
                p = _vol_pick(hits, txt)
                if p: best = p
        return (best, 0.9) if best else (None, 0.0)
    variants = {author}
    if author[-1] in JAMO_FIX: variants.add(author[:-1] + JAMO_FIX[author[-1]])
    hits = [c for c in cands if c["author"] in variants]
    if len(hits) > 1:
        p = _vol_pick(hits, txt)
        return (p, 1.0) if p else (None, 1.0)
    if len(hits) == 1: return hits[0], 1.0
    h3 = [c for c in cands if len(c["author"]) == len(author) and c["author"][1:] == author[1:]
          and c["author"][:1] != author[:1]]
    if len({c["author"] for c in h3}) == 1:
        p = _vol_pick(h3, txt) if len(h3) > 1 else h3[0]
        if p: return p, 0.95
    def digit_ok(c):
        da, dc = re.sub(r"\D", "", author), re.sub(r"\D", "", c["author"])
        return not (len(da) == len(dc) and da != dc)
    scored = sorted(((max(difflib.SequenceMatcher(None, v, c["author"]).ratio()
                          for v in variants), c) for c in cands
                     if c["author"][:1] == author[:1] and digit_ok(c)), key=lambda x: x[0])
    if not scored or scored[-1][0] < 0.75: return None, scored[-1][0] if scored else 0.0
    if len(scored) > 1 and scored[-1][0] - scored[-2][0] < 0.05: return None, scored[-1][0]
    return scored[-1][1], scored[-1][0]

_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def hkey(ch):
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3:
        i = o - 0xAC00
        return (i//588, i%588//28 + 1, i%28)
    if ch in _CHO: return (_CHO.index(ch), 0, 0)
    return (ord(ch)+100, 0, 0)
def authkey(a):
    m = re.match(r"^([가-힣A-Z]+)(\d*)(.*)$", a)
    if not m: return (a,)
    head, num, tail = m.groups()
    return (tuple(hkey(c) for c in head), float("0." + num) if num else 0,
            tuple(hkey(c) for c in tail))
def sortkey(call):
    p = call.split("-"); cls2 = re.sub(r"^[가-힣A-Z]+", "", p[0])
    vol = 0
    if len(p) > 2:
        mv = re.search(r"\d+", p[2]); vol = int(mv.group(0)) if mv else 0
    return (float(cls2) if re.match(r"^[\d.]+$", cls2) else 999,
            authkey(nn(p[1])) if len(p) > 1 else (), vol)
def lis_misplaced(keys):
    n = len(keys)
    if n == 0: return set()
    L = [1]*n; P = [-1]*n
    for i in range(n):
        for j in range(i):
            if keys[j] <= keys[i] and L[j]+1 > L[i]: L[i] = L[j]+1; P[i] = j
    e = max(range(n), key=lambda i: L[i]); keep = set()
    while e != -1: keep.add(e); e = P[e]
    return set(range(n)) - keep

# ── 케이스 1: demo read 텍스트 → match ──
match_cases = []
for n in (1, 2):
    for r in json.load(io.open(HERE/f"demo/demo{n}.json", encoding="utf-8")):
        read = r.get("read") or ""
        if not read.strip(): continue
        row, sc = match(read)
        match_cases.append({"read": read, "call": row["call"] if row else None,
                            "score": round(sc, 4)})

# ── 케이스 2: 행별 LIS — demo의 직독 call 시퀀스(밴드별 x순) ──
lis_cases = []
for n in (1, 2):
    rows = json.load(io.open(HERE/f"demo/demo{n}.json", encoding="utf-8"))
    for b in sorted({r["band"] for r in rows}):
        seq = sorted([r for r in rows if r["band"] == b and r["call"]],
                     key=lambda z: z["box"][0])
        calls = [z["call"] for z in seq]
        if len(calls) < 2: continue
        mis = sorted(lis_misplaced([sortkey(c) for c in calls]))
        lis_cases.append({"calls": calls, "mis": mis})

json.dump({"match": match_cases, "lis": lis_cases},
          io.open(HERE/"golden_cases.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"match {len(match_cases)}건 · lis {len(lis_cases)}밴드 저장")
