# -*- coding: utf-8 -*-
"""검출기 v4 설계 진단 — ①하이브리드 미판독 책의 휴리스틱 프레임(부트스트랩 후보)
②현 라벨셋 포함 여부 ③소스별 박스 h/w 분포(겸용 박스 규칙 근거)."""
import glob, io, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

# ── 정답지 (walk_grade와 동일) ──
truth = set()
for rf in glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json")):
    rows = json.load(open(rf, encoding="utf-8"))
    m = [r for r in rows if r["call"]]
    if not rows or len(m)/len(rows) < 0.6: continue
    truth |= {r["call"] for r in m if r.get("how") == "청구기호"}

# ── 하이브리드 v3 안정 인식 ──
vids = defaultdict(Counter)
for rf in sorted(glob.glob(str(HERE/"hybrid_v3_results/yolo_동영상*_result.json"))):
    rows = json.load(open(rf, encoding="utf-8"))
    m = re.search(r"(동영상\d)_f\d+", os.path.basename(rf))
    for c in {r["call"] for r in rows if r["call"]}:
        vids[m.group(1)][c] += 1
stable = set()
for v in vids: stable |= {c for c, n in vids[v].items() if n >= 2}
missed = sorted(truth - stable)
print(f"[미판독] 하이브리드 v3가 못 읽은 정답지 책 {len(missed)}권:")
for c in missed: print("  ", c)

# ── 미판독 책을 휴리스틱이 직독한 프레임 (부트스트랩 후보) ──
print("\n[부트스트랩 후보] 휴리스틱 직독 프레임:")
frame_hits = defaultdict(list)      # stem → [(call, box)]
for rf in sorted(glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json"))):
    stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
    rows = json.load(open(rf, encoding="utf-8"))
    for r in rows:
        if r["call"] in missed and r.get("how") == "청구기호":
            frame_hits[stem].append((r["call"], r["box"]))
for stem in sorted(frame_hits):
    calls = sorted({c for c, _ in frame_hits[stem]})
    print(f"   {stem}: {len(frame_hits[stem])}박스 — {', '.join(calls[:6])}")

# ── 현 라벨셋(yolo_labelset) 포함 여부 ──
inset = {}
for sp in ("train", "val"):
    for f in glob.glob(str(HERE/f"yolo_labelset/labels/{sp}/*.txt")):
        inset[Path(f).stem] = sp
print(f"\n[라벨셋 커버] 부트스트랩 후보 프레임 {len(frame_hits)}개 중:")
n_in = sum(1 for s in frame_hits if s in inset)
print(f"   라벨셋 포함 {n_in} / 미포함 {len(frame_hits)-n_in}")
for s in sorted(frame_hits):
    if s not in inset: print(f"   미포함: {s}")

# ── 소스별 박스 h/w 분포 (원본 스트립 박스 기준) ──
print("\n[박스 형태] 소스별 h/w 중앙값 (40% 컷 前 원본):")
groups = {
    "사진 600·700 (m2)": HERE/"m2_results/out_ondevice",
    "사진 800 근접 (out)": HERE/"out_ondevice",
    "사진 3차+900 (daelim_v3)": HERE/"daelim_v3_results/out_ondevice",
    "동영상 프레임 (video)": HERE/"video_results/out_ondevice",
}
for name, d in groups.items():
    ratios, n = [], 0
    for rf in glob.glob(str(d/"*_ft_result.json")):
        for r in json.load(open(rf, encoding="utf-8")):
            x0, y0, x1, y1 = r["box"]
            if x1 > x0 and y1 > y0: ratios.append((y1-y0)/(x1-x0)); n += 1
    if ratios:
        q = np.percentile(ratios, [25, 50, 75])
        print(f"   {name:28s} n={n:5d}  h/w 25%={q[0]:.2f} 50%={q[1]:.2f} 75%={q[2]:.2f}")
