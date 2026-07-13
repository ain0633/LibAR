# -*- coding: utf-8 -*-
"""걷기 하이브리드 재측정 채점기 — '몇 권'이 아니라 판독률·정밀도(진짜 수치)를 산출.

정답지 = 근접급 프레임(직독률 0.6↑)의 확정 직독 (pair_align_harvest와 같은 소스: 900v·900s).
  근접 직독은 카탈로그 문자일치라 96% 신뢰 — 이 책들은 '서가에 실재'로 간주.
채점 = 걷기 안정 인식(2프레임↑)을 정답지와 교차:
  판독률 = |안정 ∩ 정답지| / |정답지|          (도서 찾기의 재현율)
  확인율 = |안정 ∩ 정답지| / |안정|             (정밀도 하한 — 나머지는 '미확인'이지 오독 확정 아님)
사용: py -3.12 walk_grade.py [--results out_ondevice]
"""
import glob, io, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

def opt(name, default):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default
RES = HERE/opt("--results", "out_ondevice")

# ── 정답지: 근접급 확정 직독 (제목복구 제외 — 정답지는 문자일치만) ──
truth = set()
for rd in (HERE/"video_results/out_ondevice",):
    for rf in glob.glob(str(rd/"*_ft_result.json")):
        rows = json.load(open(rf, encoding="utf-8"))
        m = [r for r in rows if r["call"]]
        if not rows or len(m)/len(rows) < 0.6: continue
        truth |= {r["call"] for r in m if r.get("how") == "청구기호"}
print(f"[정답지] 근접급 확정 직독 {len(truth)}권 (900번대 세트+동영상 근접 프레임)")

# ── 걷기 하이브리드 프레임 결과 집계 ──
vids = defaultdict(Counter)          # 동영상N → call → 등장 프레임 수
for rf in sorted(glob.glob(str(RES/"yolo_동영상*_result.json"))):
    m = re.search(r"yolo_(동영상\d)_f\d+_result", os.path.basename(rf))
    if not m: continue
    rows = json.load(open(rf, encoding="utf-8"))
    for c in {r["call"] for r in rows if r["call"]}:
        vids[m.group(1)][c] += 1

total_u, total_s = set(), set()
print(f"\n{'동영상':<8}{'합산 고유':>8}{'안정(2프레임↑)':>14}{'판독률(∩정답지)':>16}{'확인율':>8}")
for v in sorted(vids):
    uniq = set(vids[v]); stab = {c for c, n in vids[v].items() if n >= 2}
    hit = stab & truth
    total_u |= uniq; total_s |= stab
    rate = f"{len(hit)}/{len(truth)}={len(hit)/max(1,len(truth)):.0%}" if truth else "-"
    conf = f"{len(hit)/max(1,len(stab)):.0%}"
    print(f"{v:<8}{len(uniq):>8}{len(stab):>14}{rate:>16}{conf:>8}")
hit_all = total_s & truth
print(f"\n[전체] 합산 고유 {len(total_u)}권 · 안정 {len(total_s)}권")
if truth:
    print(f"[판독률] 안정 ∩ 정답지 = {len(hit_all)}/{len(truth)} = {len(hit_all)/len(truth):.0%}"
          f"  (정답지 중 걷기가 못 읽은 책 {len(truth-total_s)}권)")
    print(f"[확인율] 안정 인식 중 정답지 존재 = {len(hit_all)}/{len(total_s)} = {len(hit_all)/max(1,len(total_s)):.0%}"
          f"  (미확인 {len(total_s-truth)}권 = 오독 또는 근접이 못 본 책)")
