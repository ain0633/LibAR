# -*- coding: utf-8 -*-
"""v5 판독 회귀 진단: 데모 사진에서 v3 vs v5 박스 비교 + 렌더."""
import io, sys
import cv2, numpy as np
from pathlib import Path
from ultralytics import YOLO

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
img = cv2.imdecode(np.fromfile(str(HERE/"webdemo/demo/demo1.jpg"), np.uint8), 1)
H, W = img.shape[:2]
print(f"demo1: {W}x{H}")

for name, mdir in [("v3", "call_label_yolo3"), ("v5", "call_label_yolo_v5")]:
    m = YOLO(HERE/mdir/"best.pt")
    r = m.predict(img, imgsz=1280, conf=0.25, verbose=False)[0]
    bs = r.boxes.xyxy.cpu().numpy()
    hs = bs[:, 3] - bs[:, 1]; ws = bs[:, 2] - bs[:, 0]
    print(f"{name}: 박스 {len(bs)}개 · 높이 중앙값 {np.median(hs):.0f}px · 폭 중앙값 {np.median(ws):.0f}px"
          f" · conf 중앙값 {np.median(r.boxes.conf.cpu().numpy()):.2f}")
    vis = img.copy()
    for x0, y0, x1, y1 in bs.astype(int):
        cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0), 6)
    sc = 1400/W
    vis = cv2.resize(vis, (1400, int(H*sc)))
    cv2.imencode(".jpg", vis, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(HERE/f"diag_demo1_{name}.jpg"))
print("렌더: diag_demo1_v3.jpg / diag_demo1_v5.jpg")
