# -*- coding: utf-8 -*-
"""검출기 v5 A/B: val 34장(v3와 동일 분할 = 둘 다 미학습)에서 v3 vs v5 재현율.
GT = v5 기하(라벨 전체) 박스. 히트 = pred IoU>=0.3 (v3의 하단40% 박스도 GT와 IoU~0.6이라 공정).
사용: py -3.12 eval_det_v5_ab.py
"""
import io, sys, glob
import numpy as np
from pathlib import Path
from ultralytics import YOLO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
VAL = HERE/"yolo_labelset_v5"

def iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1-x0) * max(0, y1-y0)
    ar = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter/ar if ar else 0

models = {"v3": YOLO(HERE/"call_label_yolo3/best.pt"), "v5": YOLO(HERE/"call_label_yolo_v5/best.pt")}
stats = {}   # (모델, 도메인) → 카운트

for imgf in sorted(glob.glob(str(VAL/"images/val/*.jpg"))):
    stem = Path(imgf).stem
    dom = "동영상" if stem.startswith("동영상") else "사진"
    import cv2
    img = cv2.imdecode(np.fromfile(imgf, np.uint8), 1)
    H, W = img.shape[:2]
    gts = []
    for l in io.open(VAL/f"labels/val/{stem}.txt", encoding="utf-8").read().splitlines():
        _, cx, cy, bw, bh = map(float, l.split())
        gts.append([(cx-bw/2)*W, (cy-bh/2)*H, (cx+bw/2)*W, (cy+bh/2)*H])
    for k, m in models.items():
        r = m.predict(img, imgsz=1280, conf=0.25, verbose=False)[0]
        preds = r.boxes.xyxy.cpu().numpy().tolist()
        hit = sum(1 for g in gts if any(iou(g, p) >= 0.3 for p in preds))
        matched_p = sum(1 for p in preds if any(iou(g, p) >= 0.3 for g in gts))
        s = stats.setdefault((k, dom), {"hit": 0, "gt": 0, "extra": 0, "pred": 0})
        s["hit"] += hit; s["gt"] += len(gts)
        s["pred"] += len(preds); s["extra"] += len(preds) - matched_p

print(f"{'모델':4s} {'도메인':4s} {'재현율':>14s} {'예측':>6s} {'GT밖':>5s}")
for (k, dom), s in sorted(stats.items(), key=lambda t: (t[0][1], t[0][0])):
    print(f"{k:4s} {dom:4s} {s['hit']:5d}/{s['gt']:<5d} {100*s['hit']/s['gt']:5.1f}% {s['pred']:6d} {s['extra']:5d}")
print("(GT밖 = GT와 안 겹치는 예측 — 미라벨 실물 책 포함이라 참고치)")
