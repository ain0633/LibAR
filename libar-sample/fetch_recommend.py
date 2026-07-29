# -*- coding: utf-8 -*-
"""국립중앙도서관 사서추천도서 × 대림 장서 조인 → 앱 동봉 recommend_daelim.json

사용: py -3.12 fetch_recommend.py     (.env의 NL_RECOMMEND_KEY 필요)
- saseoApi를 연도별(2016~올해)로 조회, ISBN으로 대림 소장분만 추출
- 추천사(recomcontens)는 HTML 제거 후 400자로 요약해 동봉
"""
import io, sys, csv, json, re, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

env = {}
for line in (HERE/".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
KEY = env.get("NL_RECOMMEND_KEY", "")
if not KEY:
    print("❌ .env의 NL_RECOMMEND_KEY 비어 있음"); sys.exit(1)

def norm_isbn(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d if len(d) == 13 else None

own = {}
for r in csv.DictReader(io.open(HERE/"catalog_full.csv", encoding="utf-8-sig")):
    i = norm_isbn(r["isbn13"])
    if i: own.setdefault(i, []).append(r["call_number"])

def clean(s, limit=400):                      # 추천사: HTML 태그·엔티티 제거
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]

BASE = "https://nl.go.kr/NL/search/openApi/saseoApi.do"
out, total = [], 0
for year in range(2016, date.today().year + 1):
    q = urllib.parse.urlencode({"key": KEY, "startRowNumApi": 1, "endRowNumApi": 500,
                                "start_date": f"{year}0101", "end_date": f"{year}1231"})
    try:
        with urllib.request.urlopen(f"{BASE}?{q}", timeout=40) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        print(f"{year}: 호출 실패 {e}"); continue
    items = root.findall(".//item")
    total += len(items)
    hit = 0
    for it in items:
        g = lambda tag: (it.findtext(tag) or "").strip()
        isbns = [norm_isbn(x) for x in g("recomisbn").split()]
        calls = {c for i in isbns if i and i in own for c in own[i]}
        for call in calls:
            hit += 1
            out.append({"call": call, "title": g("recomtitle"), "author": g("recomauthor"),
                        "note": clean(g("recomcontens")), "ym": f"{g('recomYear')}-{g('recomMonth')}",
                        "cat": g("drCodeName")})
    print(f"{year}: 추천 {len(items)}권 → 대림 소장 {hit}권")

# 구간별 분포
sec = {}
for b in out:
    m = re.match(r"^(\d)", b["call"])
    sec[(m.group(1) + "00번대") if m else "기타"] = sec.get((m.group(1) + "00번대") if m else "기타", 0) + 1
print(f"\n합계: 국중도 추천 {total}권 중 대림 소장 {len(out)}권 · 구간 분포 {dict(sorted(sec.items()))}")
json.dump(out, io.open(HERE/"recommend_daelim.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("저장: recommend_daelim.json")
