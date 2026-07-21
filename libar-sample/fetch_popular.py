# -*- coding: utf-8 -*-
"""인기대출도서 × 대림 장서 조인 — 히트율 검증 (서가 강조 기능의 킬 판정)

사용: py -3.12 fetch_popular.py          (.env의 DATA4LIBRARY_KEY 필요)

1) 정보나루 loanItemSrch를 KDC 대분류(0~9)별로 호출 (최근 1년, 상위 200권씩)
2) ISBN으로 대림 장서(catalog_full.csv)와 조인 → 구간별 소장 교집합
3) 킬 기준 판정: 서가 한 컷(약 25권) 기대 히트 = 교집합/구간 장서 × 25
   - 주요 구간에서 0.5권 미만이면 "박스 강조" 대신 "목록+길안내"로 다운그레이드 검토
4) 통과 시 앱 동봉용 popular_daelim.json 생성 (청구기호·제목·저자·순위·대출횟수)
"""
import io, sys, csv, json, re, urllib.request, urllib.parse
from datetime import date, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

# ── .env 로드 (의존성 없이) ──
env = {}
for line in (HERE/".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
KEY = env.get("DATA4LIBRARY_KEY", "")
if not KEY or "붙여넣기" in KEY:
    print("❌ libar-sample/.env 의 DATA4LIBRARY_KEY 에 인증키를 넣어주세요"); sys.exit(1)

def norm_isbn(s):
    d = re.sub(r"\D", "", str(s or ""))
    return d if len(d) == 13 else None

# ── 대림 장서 (ISBN → call/sec) ──
own = {}
for r in csv.DictReader(io.open(HERE/"catalog_full.csv", encoding="utf-8-sig")):
    i = norm_isbn(r["isbn13"])
    if i: own.setdefault(i, []).append(r["call_number"])
cat_n = sum(len(v) for v in own.values())
print(f"대림 장서 ISBN 보유 {len(own):,}종 / {cat_n:,}권")

# 구간별 장서 수 (한 컷 기대 히트 계산용)
sec_total = {}
for r in csv.DictReader(io.open(HERE/"catalog_full.csv", encoding="utf-8-sig")):
    m = re.match(r"^(\d)", r["call_number"])
    if m: sec_total[m.group(1)] = sec_total.get(m.group(1), 0) + 1

end = date.today(); start = end - timedelta(days=365)
BASE = "http://data4library.kr/api/loanItemSrch"

out, report = [], []
for kdc in range(10):
    q = urllib.parse.urlencode({
        "authKey": KEY, "format": "json", "startDt": start.isoformat(), "endDt": end.isoformat(),
        "kdc": kdc, "pageSize": 200,
    })
    try:
        with urllib.request.urlopen(f"{BASE}?{q}", timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"kdc={kdc}: 호출 실패 {e}"); continue
    docs = data.get("response", {}).get("docs", [])
    hits = []
    for d in docs:
        b = d.get("doc", d)
        isbn = norm_isbn(b.get("isbn13") or b.get("isbn"))
        if isbn and isbn in own:
            for call in own[isbn]:
                hits.append({"call": call, "title": b.get("bookname", ""), "author": b.get("authors", ""),
                             "rank": int(b.get("ranking", 0) or 0), "loan": int(b.get("loan_count", 0) or 0),
                             "kdc": kdc})
    out.extend(hits)
    tot = sec_total.get(str(kdc), 0)
    per_shot = len(hits) / tot * 25 if tot else 0     # 한 컷 25권 가정
    report.append((kdc, len(docs), len(hits), tot, per_shot))
    print(f"KDC {kdc}00번대: 인기대출 {len(docs)}권 중 대림 소장 {len(hits)}권 "
          f"(구간 장서 {tot:,} → 한 컷 기대 히트 {per_shot:.2f}권)")

ok = [r for r in report if r[4] >= 0.5]
print()
print(f"판정: 기대 히트 0.5권 이상 구간 {len(ok)}/10 — "
      + ("✅ 박스 강조 설계 성립" if len(ok) >= 5 else "⚠️ 낮음: 목록+길안내형으로 다운그레이드 검토"))
json.dump(out, io.open(HERE/"popular_daelim.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"저장: popular_daelim.json ({len(out)}권) — 앱 동봉 후보")
