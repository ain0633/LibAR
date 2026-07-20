# -*- coding: utf-8 -*-
"""오배열 위험도 매쉬업 (offline·로컬 데이터만) — 공모전 '도서관 데이터 활용' Phase 1.

가설: 대출이 많은(손 타는) 구간 = 구조적으로 오배열에 취약한 구간일수록 우선 점검해야 한다.
- 대출 프록시  : status='관외대출' 비율 (지금 대출 나간 책 스냅샷 — 정보나루 누적 회전율은 Phase 2)
- 오배열 취약도: 현장 실증된 오배열 유발 구조 3종
    ① 권차/복본 밀집(series) — v.1/v.2·복본 (909~911 조직적 매칭 실패의 그 구조)
    ② 저자기호 인접 밀집(crowd) — 같은 분류 안 저자기호 2글자 접두 공유 (위험군 413의 구조)
    ③ 장서 밀도(density) — 구간당 권수
정직성: 실제 오배열 로그는 아직 희소(현장 6건+데모) → 취약도는 '구조 프록시'이며,
        현장 발견 청구기호가 실제로 고취약 구간에 떨어지는지로 교차검증한다.

사용: py -3.12 mashup_risk.py   (libar-sample 안)
출력: mashup_risk.txt (구간별 위험도 Top N + 상관계수 + 현장 교차검증)
"""
import csv, re, io, math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
CAT = HERE / "catalog_full.csv"

# ── 청구기호 파싱: 분류번호 / 저자기호 / 꼬리(권차·복본) ──
def parse(call):
    parts = call.split("-")
    cls = parts[0].strip()
    author = parts[1].strip() if len(parts) > 1 else ""
    tail = parts[2].strip() if len(parts) > 2 else ""
    try: clsf = float(cls)
    except ValueError: clsf = None
    return clsf, cls, author, tail

def kdc_section(clsf):                       # 구간 = KDC 3자리 정수 (673, 688, 909…) — 서가 단위
    return int(clsf) if clsf is not None else None

rows = []
for r in csv.DictReader(io.open(CAT, encoding="utf-8-sig")):
    call = r["call_number"].strip()
    clsf, cls, author, tail = parse(call)
    sec = kdc_section(clsf)
    if sec is None: continue
    rows.append({"sec": sec, "cls": cls, "author": author, "tail": tail,
                 "loan": r["status"].strip() != "비치자료", "base": f"{cls}-{author}"})

# ── 구간별 특징 집계 ──
by_sec = defaultdict(list)
for r in rows: by_sec[r["sec"]].append(r)

def z(vals):                                 # 표준화 (스코어 결합용)
    m = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals)) or 1.0
    return [(v - m) / sd for v in vals], m, sd

feat = {}
for sec, items in by_sec.items():
    n = len(items)
    if n < 15: continue                      # 표본 부족 구간 제외 (스코어 불안정)
    loan_rate = sum(r["loan"] for r in items) / n
    # ① 권차/복본 밀집: 같은 base(분류+저자)가 2권 이상인 클러스터에 속한 비율
    base_ct = defaultdict(int)
    for r in items: base_ct[r["base"]] += 1
    series_rate = sum(1 for r in items if base_ct[r["base"]] >= 2) / n
    # ② 저자기호 인접 밀집: 같은 분류번호 안에서 저자기호 2글자 접두를 공유하는 이웃이 있는 비율
    by_cls = defaultdict(list)
    for r in items: by_cls[r["cls"]].append(r["author"])
    crowd = 0
    for cls, auths in by_cls.items():
        pfx = defaultdict(int)
        for a in auths:
            if len(a) >= 2: pfx[a[:2]] += 1
        for a in auths:
            if len(a) >= 2 and pfx[a[:2]] >= 2: crowd += 1
    crowd_rate = crowd / n
    feat[sec] = {"n": n, "loan": loan_rate, "series": series_rate, "crowd": crowd_rate}

secs = sorted(feat)
zser, _, _ = z([feat[s]["series"] for s in secs])
zcro, _, _ = z([feat[s]["crowd"] for s in secs])
zloan, _, _ = z([feat[s]["loan"] for s in secs])
for i, s in enumerate(secs):
    feat[s]["vuln"] = zser[i] + zcro[i]                       # 구조적 취약도 (대출 무관)
    feat[s]["risk"] = (zser[i] + zcro[i]) + zloan[i]          # 매쉬업 위험도 = 취약도 + 대출

# ── 스피어만 순위상관 (대출 프록시 vs 구조 취약도) ──
def spearman(a, b):
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        rk = [0] * len(x)
        for pos, i in enumerate(order): rk[i] = pos
        return rk
    ra, rb = rank(a), rank(b)
    n = len(a); dsq = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * dsq / (n * (n * n - 1))

rho = spearman([feat[s]["loan"] for s in secs], [feat[s]["vuln"] for s in secs])

# ── 현장 발견 청구기호 교차검증 ──
FIELD = ["375.226", "594.5", "325.211", "592.27", "609", "001.3",   # 라벨링 중 불일치·목록밖 실물
         "688.01", "909", "911"]                                    # 데모 오배열·권차 밀집 실패
field_secs = sorted({int(float(c)) for c in FIELD})
risk_rank = {s: i + 1 for i, s in enumerate(sorted(secs, key=lambda s: -feat[s]["risk"]))}

out = io.open(HERE / "mashup_risk.txt", "w", encoding="utf-8")
def w(s=""): out.write(s + "\n"); print(s)

w(f"■ 오배열 위험도 매쉬업 (Phase 1, 로컬 offline) — 구간 {len(secs)}개 (권수 ≥15)")
w(f"  대출 프록시=관외대출비율 · 취약도=권차복본밀집+저자기호인접밀집(z합) · 위험도=취약도+대출")
w()
w(f"● 가설검정: 대출↑ 구간이 구조적 오배열 취약도↑ 인가?")
w(f"  스피어만 순위상관 ρ = {rho:+.3f}  ({'양(가설 지지)' if rho > 0.15 else '약함/무관' if abs(rho)<=0.15 else '음(반대)'})")
w()
w("● 점검 우선순위 Top 15 (위험도 순)")
w(f"  {'구간':>5s} {'권수':>5s} {'대출%':>6s} {'권차복본%':>8s} {'저자밀집%':>8s} {'위험도':>7s}")
for s in sorted(secs, key=lambda s: -feat[s]["risk"])[:15]:
    f = feat[s]
    w(f"  {s:>5d} {f['n']:>5d} {100*f['loan']:>5.1f} {100*f['series']:>8.1f} {100*f['crowd']:>8.1f} {f['risk']:>+7.2f}")
w()
w("● 현장 발견 오배열/불일치 구간의 위험도 순위 (교차검증)")
w(f"  전체 {len(secs)}구간 중 순위 — 상위일수록 '구조가 예측했다'는 근거")
for s in field_secs:
    if s in risk_rank:
        f = feat[s]; pct = 100 * risk_rank[s] / len(secs)
        w(f"  {s:>5d}: {risk_rank[s]:>3d}위 (상위 {pct:.0f}%) · 대출 {100*f['loan']:.0f}% 권차복본 {100*f['series']:.0f}% 저자밀집 {100*f['crowd']:.0f}%")
    else:
        w(f"  {s:>5d}: 표본<15 제외")
hit = sum(1 for s in field_secs if s in risk_rank and risk_rank[s] <= len(secs) * 0.5)
tot = sum(1 for s in field_secs if s in risk_rank)
w()
w(f"  → 현장 발견 {tot}구간 중 {hit}구간이 위험도 상위 50% 안 (구조 프록시 타당성)")
w()
w("[Phase 2] 정보나루 누적 대출 회전율 도착 시 loan 프록시 교체 → 위험도 재계산 (파이프라인 동일)")
out.close()
print("저장: mashup_risk.txt")
