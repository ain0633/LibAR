# -*- coding: utf-8 -*-
"""로직 개선 전(Colab aggregate_m2)과 후(m2_rerun.log) 사진별 매칭 비교."""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

agg = json.load(open("m2_results/out_ondevice/aggregate_m2.json", encoding="utf-8"))
before = {}
for sec, d in agg.items():
    for s, (m, t) in d["per_frame"].items():
        before[s] = (m, t, sec)

log = io.open("m2_rerun.log", encoding="utf-8", errors="replace").read()
blocks = re.split(r"=== \d+ · ", log)[1:]
after = {}
for b in blocks:
    stem = re.match(r".*?([A-Za-z_0-9]+)\.jpg", b).group(1).split("/")[-1]
    m2 = re.search(r"\[이중 인식\] 매칭 (\d+)/(\d+)", b)
    if m2: after[stem] = (int(m2.group(1)), int(m2.group(2)))

print(f"{'사진':<38}{'전(Colab)':<12}{'후(개선)':<12}Δ매칭")
tot_b = tot_a = 0
for s in sorted(before):
    b = before[s]; a = after.get(s)
    if not a: continue
    d = a[0] - b[0]
    tot_b += b[0]; tot_a += a[0]
    mark = "▲" if d > 0 else ("▼" if d < 0 else "=")
    print(f"{s:<38}{b[0]}/{b[1]:<10}{a[0]}/{a[1]:<10}{mark}{abs(d)}")
print(f"\n합계 매칭: {tot_b} → {tot_a} ({'+' if tot_a>=tot_b else ''}{tot_a-tot_b})")
