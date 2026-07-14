# -*- coding: utf-8 -*-
"""권차(v.N) 매칭 수술 A/B — OCR 재실행 없이 hybrid_v3_results의 read를 재매칭해 걷기 판독률 재계산.
수술: ①v.N 토큰을 빼고 정규식 매칭(권차가 분류번호-저자 사이에 끼어 인접성 파괴 — 911 v.1 이15ㄱ)
     ②저자 폴백에서 복본(v.1/v.2) 다의성은 권차로 판별."""
import glob, io, json, os, re, sys, csv, difflib, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def nn(s): return re.sub(r"[^0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ.]", "", unicodedata.normalize("NFC", str(s)))

# 카탈로그: 걷기 구간(900번대) 포함 — 파이프라인이 쓴 것과 동일한 catalog_900.csv
cat_path = HERE/"catalog_900.csv"
items, by_cls = [], {}
for r in csv.DictReader(open(cat_path, encoding="utf-8-sig")):
    call = re.sub(r"\s*(?:=|[cC]\.)\d+$", "", r["call_number"].strip())
    parts = call.split("-")
    if len(parts) < 2: continue
    m = re.match(r"^[가-힣A-Z]*([\d.]+)$", parts[0].strip())
    it = {"call": call, "cls": m.group(1) if m else parts[0].strip(),
          "author": nn(parts[1].strip()), "title": r["title"]}
    items.append(it); by_cls.setdefault(it["cls"], []).append(it)
print(f"카탈로그 {len(items)}권 ({cat_path.name})")

JF = {"0":"ㅇ","O":"ㅇ","o":"ㅇ","Q":"ㅇ","으":"ㅇ","이":"ㅇ","피":"ㅍ","디":"ㄷ","기":"ㄱ","니":"ㄴ",
      "리":"ㄹ","미":"ㅁ","비":"ㅂ","시":"ㅅ","지":"ㅈ","치":"ㅊ","키":"ㅋ","티":"ㅌ","히":"ㅎ",
      "프":"ㅍ","표":"ㅍ","드":"ㄷ","그":"ㄱ","느":"ㄴ","르":"ㄹ","므":"ㅁ","브":"ㅂ","스":"ㅅ",
      "즈":"ㅈ","츠":"ㅊ","크":"ㅋ","트":"ㅌ","흐":"ㅎ"}

def vol_pick(hits, txt):
    mv = re.search(r"[vV]\.?(\d+)", txt)
    if mv:
        vhits = [c for c in hits if re.match(r"^[vV]?\.?0*%s$" % mv.group(1), c["call"].split("-")[-1])]
        if len(vhits) == 1: return vhits[0]
    if len({c["call"] for c in hits}) == 1: return hits[0]
    return None

def match(txt, surgery):
    src = re.sub(r"[vV]\.?\d+", " ", txt) if surgery else txt   # ① 권차 제거 후 인접성 매칭
    t = nn(src)
    m = None
    for m2 in re.finditer(r"(\d{3}(?:\.\d+)?)([가-힣][0-9]{1,3}[가-힣ㄱ-ㅎ0Oo]?)", t):
        if m2.group(1) in by_cls: m = m2; break
    if not m:
        best = None
        for a in re.findall(r"[가-힣][0-9]{2,3}[가-힣ㄱ-ㅎ]?", t):
            vs = {a} | ({a[:-1]+JF[a[-1]]} if a[-1] in JF else set())
            hits = [c for c in items if c["author"] in vs]
            if len(hits) == 1 and len(a) >= 4: best = hits[0]
            elif surgery and len(hits) > 1 and len(a) >= 4:      # ② 복본 다의성은 권차로 판별
                p = vol_pick(hits, txt)
                if p: best = p
        return best
    clsv, author = m.group(1), m.group(2); cands = by_cls[clsv]
    variants = {author} | ({author[:-1]+JF[author[-1]]} if author[-1] in JF else set())
    hits = [c for c in cands if c["author"] in variants]
    if len(hits) > 1: return vol_pick(hits, txt)
    if len(hits) == 1: return hits[0]
    if surgery:      # ③ 첫 글자만 오독(상↔싱, 풀↔몰): 나머지 완전 일치 후보가 유일하면 인정
        h3 = [c for c in cands if len(c["author"]) == len(author) and c["author"][1:] == author[1:]
              and c["author"][:1] != author[:1]]
        if len({c["author"] for c in h3}) == 1:
            return vol_pick(h3, txt) if len(h3) > 1 else h3[0]
    def dok(c):
        da, dc = re.sub(r"\D","",author), re.sub(r"\D","",c["author"])
        return not (len(da) == len(dc) and da != dc)
    sc = sorted(((max(difflib.SequenceMatcher(None,v,c["author"]).ratio() for v in variants), c)
                 for c in cands if c["author"][:1] == author[:1] and dok(c)), key=lambda x: x[0])
    if not sc or sc[-1][0] < 0.75: return None
    if len(sc) > 1 and sc[-1][0]-sc[-2][0] < 0.05: return None
    return sc[-1][1]

# ── 정답지 ──
truth = set()
for rf in glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json")):
    rows = json.load(open(rf, encoding="utf-8"))
    m = [r for r in rows if r["call"]]
    if not rows or len(m)/len(rows) < 0.6: continue
    truth |= {r["call"] for r in m if r.get("how") == "청구기호"}

# ── 재매칭 A/B ──
for surgery in (False, True):
    vids = defaultdict(Counter)
    for rf in sorted(glob.glob(str(HERE/"hybrid_v3_results/yolo_동영상*_result.json"))):
        m = re.search(r"(동영상\d)_f\d+", os.path.basename(rf))
        calls = set()
        for r in json.load(open(rf, encoding="utf-8")):
            row = match(r.get("read") or "", surgery)
            if row: calls.add(row["call"])
        for c in calls: vids[m.group(1)][c] += 1
    stable = set()
    for v in vids: stable |= {c for c, n in vids[v].items() if n >= 2}
    hit = stable & truth
    tag = "수술 후" if surgery else "현행  "
    print(f"[{tag}] 판독률 {len(hit)}/{len(truth)} = {len(hit)/len(truth):.0%} · "
          f"확인율 {len(hit)}/{len(stable)} = {len(hit)/max(1,len(stable)):.0%} (안정 {len(stable)})")
    if surgery:
        miss = sorted(truth - stable)
        print(f"   여전히 미판독 {len(miss)}권: {', '.join(miss)}")
        extra = sorted(stable - truth)
        print(f"   정답지 밖 안정 인식 {len(extra)}권: {', '.join(extra)}")
        # 이 책들이 어떤 read에서 나왔는지 (오독 유령 vs 실재)
        for rf in sorted(glob.glob(str(HERE/"hybrid_v3_results/yolo_동영상*_result.json"))):
            for r in json.load(open(rf, encoding="utf-8")):
                row = match(r.get("read") or "", True)
                if row and row["call"] in extra:
                    print(f"      {row['call']} ← read={r['read']!r} ({os.path.basename(rf)[:22]})")
