# -*- coding: utf-8 -*-
"""909 미판독의 진짜 사인 추적 — 검출은 됐다(31/31). 그럼 하이브리드 결과에서 그 박스는
뭘 읽었고 왜 매칭이 안 됐나: GT 박스와 겹치는 hybrid_v3_results 행의 read/call을 대조."""
import glob, io, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent

truth = set()
for rf in glob.glob(str(HERE/"video_results/out_ondevice/*_ft_result.json")):
    rows = json.load(open(rf, encoding="utf-8"))
    m = [r for r in rows if r["call"]]
    if not rows or len(m)/len(rows) < 0.6: continue
    truth |= {r["call"] for r in m if r.get("how") == "청구기호"}
vids = defaultdict(Counter)
for rf in sorted(glob.glob(str(HERE/"hybrid_v3_results/yolo_동영상*_result.json"))):
    rows = json.load(open(rf, encoding="utf-8"))
    m = re.search(r"(동영상\d)_f\d+", os.path.basename(rf))
    for c in {r["call"] for r in rows if r["call"]}:
        vids[m.group(1)][c] += 1
stable = set()
for v in vids: stable |= {c for c, n in vids[v].items() if n >= 2}
missed = truth - stable

def iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0: return 0.0
    inter = (x1-x0)*(y1-y0)
    return inter/((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter)

for rf in sorted(glob.glob(str(HERE/"video_results/out_ondevice/closeup동영상*_ft_result.json"))):
    stem = os.path.basename(rf).replace("closeup", "").replace("_ft_result.json", "")
    gt_rows = [r for r in json.load(open(rf, encoding="utf-8"))
               if r["call"] in missed and r.get("how") == "청구기호"]
    if not gt_rows: continue
    hf = HERE/f"hybrid_v3_results/yolo_{stem}_result.json"
    if not hf.exists(): continue
    hyb = json.load(open(hf, encoding="utf-8"))
    for g in gt_rows:
        gx0, gy0, gx1, gy1 = g["box"]
        gt = (gx0, gy1-(gy1-gy0)*0.40, gx1, gy1)     # 하단 40% (하이브리드 v3 박스 지형)
        best = max(hyb, key=lambda h: iou(gt, h["box"]), default=None)
        ov = iou(gt, best["box"]) if best else 0
        print(f"{stem} | 정답 {g['call']:<14} 휴리스틱read={g['read']!r}")
        if best and ov >= 0.2:
            print(f"   └ 하이브리드 IoU {ov:.2f}: read={best['read']!r} → call={best['call']} (score {best.get('score')})")
        else:
            print(f"   └ 하이브리드: 겹치는 박스 없음 (최대 IoU {ov:.2f})")
