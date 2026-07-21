# -*- coding: utf-8 -*-
"""장서 카탈로그 갱신 — 자관 전산 엑셀 → 앱 catalog.json + 분석용 catalog_full.csv

사용: py -3.12 make_catalog.py "..\대림데이터\종합 장서 데이터(000-999).xlsx"

규칙 (2026-07-14 첫 변환과 동일):
- 필터: 배가상태 ∈ {비치자료, 관외대출자료} 그리고 청구기호 있음
  (제적·분실·파손·타관대출/반납·재정리·특별대출·수리제본 = 서가에 없어야 하는 책 → 제외)
- catalog.json 은 call/title/sec/room 만 담는다 — 공개 데모 탑재분, 내부 관리필드 비공개 원칙
- catalog_full.csv 는 위험도 분석(mashup_risk.py)용: call_number,title,author,isbn13,status

안전장치:
- 이전 catalog.json 을 demo/catalog_prev.json 으로 백업
- 전판 대비 권수 5% 이상 급감이면 중단(--force 로 무시) — 잘못된 엑셀(부분 추출) 방어
- 변화 요약(신규/제거/상태 분포) 출력 → 갱신 기록으로 남길 것
"""
import sys, io, re, json, csv, shutil, unicodedata
from pathlib import Path
import openpyxl

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
OUT_JSON = HERE / "webdemo" / "demo" / "catalog.json"
OUT_CSV = HERE / "catalog_full.csv"
KEEP = {"비치자료", "관외대출자료"}          # 서가에 실재해야 하는 상태만

if len(sys.argv) < 2:
    print(__doc__); sys.exit(1)
xlsx = Path(sys.argv[1])
force = "--force" in sys.argv

def sec_of(call):                            # 구간: 3자리 분류 → N00번대. 별치기호(아·양 등 접두) 자료는
    m = re.match(r"^(\d{3})", str(call))     # 일반 서가 구간에 없으므로 '기타' (07-14 첫 변환과 동일)
    return f"{int(m.group(1)) // 100 * 100:03d}번대" if m else "기타"

wb = openpyxl.load_workbook(xlsx, read_only=True)
ws = wb.active
rows = ws.iter_rows(values_only=True)
hdr = next(rows)
col = {h: i for i, h in enumerate(hdr) if h}
need = ["배가상태", "청구기호", "자료실명", "서명", "저작자", "ISBN"]
missing = [c for c in need if c not in col]
if missing:
    print(f"❌ 엑셀에 필요한 열이 없습니다: {missing} — 자관 전산에서 전체 열 그대로 추출했는지 확인")
    sys.exit(1)

books, st_all = [], {}
for r in rows:
    st = r[col["배가상태"]]
    st_all[st] = st_all.get(st, 0) + 1
    call = r[col["청구기호"]]
    if st not in KEEP or not call or not str(call).strip():
        continue
    norm = lambda s: unicodedata.normalize("NFC", str(s))   # 한자 호환문자(U+F90A 金 등) 통일 — 검색·매칭 일관성
    call = norm(call).strip()
    room = norm(r[col["자료실명"]] or "").replace("(대림)", "").strip()
    books.append({
        "call": call,
        "title": norm(r[col["서명"]] or "").strip(),
        "sec": sec_of(call),
        "room": room,
        "_author": str(r[col["저작자"]] or "").strip(),
        "_isbn": str(r[col["ISBN"]] or "").strip(),
        "_status": str(st),
    })

# ── 전판 대비 검증 ──
prev = json.load(io.open(OUT_JSON, encoding="utf-8")) if OUT_JSON.exists() else []
if prev:
    drop = (len(prev) - len(books)) / len(prev)
    pc, nc = {b["call"] for b in prev}, {b["call"] for b in books}
    print(f"이전 {len(prev):,}권 → 새 {len(books):,}권 (신규 청구기호 {len(nc - pc):,} · 사라짐 {len(pc - nc):,})")
    if drop > 0.05 and not force:
        print(f"❌ 권수 {drop:.0%} 급감 — 부분 추출 엑셀일 수 있어 중단합니다 (확실하면 --force)")
        sys.exit(1)
print("배가상태 분포:", {k: v for k, v in sorted(st_all.items(), key=lambda x: -x[1])})

# ── 저장 (내용이 바뀔 때만 백업 — 재실행이 이전판 백업을 덮지 않게) ──
new_json = json.dumps([{k: b[k] for k in ("call", "title", "sec", "room")} for b in books],
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
if OUT_JSON.exists() and OUT_JSON.read_bytes() != new_json:
    shutil.copy(OUT_JSON, OUT_JSON.with_name("catalog_prev.json"))
elif OUT_JSON.exists():
    print("내용 변화 없음 — 기존과 동일 (백업 생략)")
OUT_JSON.write_bytes(new_json)
with io.open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["call_number", "title", "author", "isbn13", "status"])
    for b in books:
        w.writerow([b["call"], b["title"], b["_author"], b["_isbn"], b["_status"]])

print(f"저장: {OUT_JSON} ({len(books):,}권) · {OUT_CSV}")
print("다음: ①게이트 node webdemo/tests/run_all.mjs 전부 PASS 확인 ②공개 리포 demo/catalog.json 교체·푸시")
